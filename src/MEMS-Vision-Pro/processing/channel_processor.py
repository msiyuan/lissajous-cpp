"""
通道处理器模块 - 独立进程版本
每个通道在独立的Python进程中运行，拥有自己的GIL和CUDA上下文
"""

import os
import sys
import time
import struct
import socket
import numpy as np
from multiprocessing import Process, Queue, Event
from queue import Empty, Full


class ChannelProcessor(Process):
    """
    独立进程的通道处理器
    包含：UDP接收 -> 帧组装 -> 图像处理 的完整流水线
    """

    def __init__(self, channel: str, port: int, target_ip: str,
                 input_queue: Queue, output_queue: Queue,
                 params_queue: Queue, stop_event: Event,
                 gpu_id: int = 0):
        """
        初始化通道处理器

        Args:
            channel: 通道标识 ('ch1' 或 'ch2')
            port: UDP接收端口
            target_ip: 目标IP地址
            input_queue: 控制命令输入队列
            output_queue: 处理结果输出队列
            params_queue: 参数更新队列
            stop_event: 停止事件
            gpu_id: GPU设备ID
        """
        super().__init__(daemon=True)
        self.channel = channel
        self.port = port
        self.target_ip = target_ip
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.params_queue = params_queue
        self.stop_event = stop_event
        self.gpu_id = gpu_id

        # 处理参数（将在进程启动后初始化）
        self.current_params = {
            'deltaphasex': 0.0,
            'deltaphasey': 0.0,
            'freqx': 200.0,
            'freqy': 233.0
        }

        # 帧组装状态
        self.current_frame = None
        self.current_frame_id = None

        # 协议常量
        self.FRAME_HEADER_MAGIC = 0x2AFF
        self.PACKET_HEADER_MAGIC = 0x2CFF

        # 性能统计
        self.frame_count = 0
        self.last_log_time = 0

    def run(self):
        """进程主入口"""
        try:
            self._log(f"通道处理进程启动 (PID={os.getpid()}, GPU={self.gpu_id})")

            # 初始化CUDA（在子进程中）
            self._init_cuda()

            # 预编译Numba函数
            self._warmup_numba()

            # 设置UDP socket
            sock = self._setup_socket()
            if sock is None:
                return

            # 主循环
            self._main_loop(sock)

        except Exception as e:
            self._log(f"进程异常退出: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._log("通道处理进程结束")

    def _init_cuda(self):
        """初始化CUDA环境"""
        try:
            import cupy as cp
            cp.cuda.Device(self.gpu_id).use()
            # 执行一个小操作来初始化CUDA上下文
            _ = cp.array([1, 2, 3])
            self._log(f"CUDA初始化成功 (Device {self.gpu_id})")
        except Exception as e:
            self._log(f"CUDA初始化失败: {e}")

    def _warmup_numba(self):
        """预编译Numba函数"""
        try:
            from utils.numba_functions import warm_up_interpolation_function
            warm_up_interpolation_function()
            self._log("Numba函数预编译完成")
        except Exception as e:
            self._log(f"Numba预编译失败: {e}")

    def _setup_socket(self) -> socket.socket:
        """设置UDP socket"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(0.1)  # 100ms超时，允许检查stop_event
            sock.bind(('', self.port))
            self._log(f"UDP socket绑定成功 (端口 0x{self.port:X})")
            return sock
        except Exception as e:
            self._log(f"UDP socket绑定失败: {e}")
            return None

    def _main_loop(self, sock: socket.socket):
        """主处理循环"""
        packets_buffer = []
        last_process_time = time.time()

        while not self.stop_event.is_set():
            # 检查参数更新
            self._check_params_update()

            # 接收UDP数据
            try:
                data, _ = sock.recvfrom(65535)
                packets_buffer.append(data)
            except socket.timeout:
                pass
            except Exception as e:
                if not self.stop_event.is_set():
                    self._log(f"UDP接收错误: {e}")
                continue

            # 批量处理数据包
            if packets_buffer:
                self._process_packets(packets_buffer)
                packets_buffer.clear()

            # 检查帧完成
            current_time = time.time()
            if current_time - last_process_time >= 0.01:  # 10ms检查间隔
                self._check_frame_complete()
                last_process_time = current_time

        sock.close()

    def _check_params_update(self):
        """检查参数更新"""
        try:
            while True:
                params = self.params_queue.get_nowait()
                self.current_params.update(params)
                self._log(f"参数已更新: {params}")
        except Empty:
            pass

    def _process_packets(self, packets: list):
        """处理数据包批次"""
        for data in packets:
            if len(data) < 2:
                continue

            magic = struct.unpack('>H', data[0:2])[0]

            if magic == self.FRAME_HEADER_MAGIC:
                # 新帧头：完成当前帧，开始新帧
                self._finalize_current_frame()
                self._start_new_frame(data)
            elif magic == self.PACKET_HEADER_MAGIC:
                # 数据包：添加到当前帧
                self._add_packet_to_frame(data)

    def _start_new_frame(self, data: bytes):
        """开始新帧"""
        if len(data) < 17:
            return

        frame_cnt = struct.unpack('>H', data[2:4])[0]
        sample_point = struct.unpack('>I', data[4:8])[0]

        if sample_point > 2000000:
            sample_point = 1000000

        self.current_frame_id = frame_cnt
        self.current_frame = {
            'packets': [data],
            'timestamp': time.time(),
            'sample_point': sample_point,
            'received_bytes': len(data) - 16 if len(data) > 16 else 0
        }

    def _add_packet_to_frame(self, data: bytes):
        """添加数据包到当前帧"""
        if self.current_frame is None:
            return

        self.current_frame['packets'].append(data)
        if len(data) > 4:
            self.current_frame['received_bytes'] += len(data) - 4

    def _finalize_current_frame(self):
        """完成当前帧并处理"""
        if self.current_frame is None:
            return

        packets = self.current_frame['packets']
        if len(packets) > 0:
            self._process_frame(packets)

        self.current_frame = None
        self.current_frame_id = None

    def _check_frame_complete(self):
        """检查帧超时"""
        if self.current_frame is None:
            return

        age = time.time() - self.current_frame['timestamp']
        if age > 0.5:  # 500ms超时
            self._finalize_current_frame()

    def _process_frame(self, packets: list):
        """处理完整帧"""
        try:
            # 导入处理模块（在子进程中）
            from processing.image_processor import ImageProcessor

            processor = ImageProcessor(
                packets,
                self.current_params['deltaphasex'],
                self.current_params['deltaphasey'],
                self.current_params['freqx'],
                self.current_params['freqy']
            )

            # 同步处理（在独立进程中，不需要线程）
            final_image, phasex, phasey = processor.process_single_frame_one_freq(
                packets,
                SampleRate=1e7,
                Freqx=self.current_params['freqx'],
                Freqy=self.current_params['freqy'],
                deltaphasex=self.current_params['deltaphasex'],
                deltaphasey=self.current_params['deltaphasey']
            )

            if final_image is not None:
                # 发送处理结果到主进程（非阻塞，队列满则丢弃旧帧）
                try:
                    self.output_queue.put_nowait({
                        'channel': self.channel,
                        'image': final_image.astype(np.uint16),  # 确保类型正确
                        'phasex': float(phasex) if hasattr(phasex, '__float__') else phasex,
                        'phasey': float(phasey) if hasattr(phasey, '__float__') else phasey,
                        'timestamp': time.time()
                    })
                except Full:
                    pass  # 队列满时丢弃当前帧，避免阻塞

                self.frame_count += 1

                # 定期日志
                current_time = time.time()
                if current_time - self.last_log_time > 5.0:
                    self._log(f"已处理 {self.frame_count} 帧")
                    self.last_log_time = current_time

        except Exception as e:
            self._log(f"帧处理错误: {e}")
            import traceback
            traceback.print_exc()

    def _log(self, message: str):
        """发送日志消息到主进程（非阻塞）"""
        try:
            self.output_queue.put_nowait({
                'channel': self.channel,
                'type': 'log',
                'message': f"[{self.channel}] {message}"
            })
        except (Full, Exception):
            print(f"[{self.channel}] {message}")  # 降级为控制台输出


class DualChannelManager:
    """
    双通道管理器
    管理两个独立的通道处理进程
    """

    def __init__(self):
        self.processes = {}
        self.output_queues = {}
        self.params_queues = {}
        self.stop_events = {}
        self.is_running = False

    def start(self, target_ip: str, port_ch1: int, port_ch2: int):
        """启动双通道处理"""
        if self.is_running:
            self.stop()

        # 创建通道1
        self._create_channel('ch1', port_ch1, target_ip, gpu_id=0)

        # 创建通道2
        self._create_channel('ch2', port_ch2, target_ip, gpu_id=0)

        # 启动进程
        for channel, process in self.processes.items():
            process.start()
            print(f"[Manager] 通道 {channel} 进程已启动")

        self.is_running = True

    def _create_channel(self, channel: str, port: int, target_ip: str, gpu_id: int):
        """创建通道处理器"""
        input_queue = Queue()
        output_queue = Queue(maxsize=10)  # 限制队列大小防止内存溢出
        params_queue = Queue()
        stop_event = Event()

        process = ChannelProcessor(
            channel=channel,
            port=port,
            target_ip=target_ip,
            input_queue=input_queue,
            output_queue=output_queue,
            params_queue=params_queue,
            stop_event=stop_event,
            gpu_id=gpu_id
        )

        self.processes[channel] = process
        self.output_queues[channel] = output_queue
        self.params_queues[channel] = params_queue
        self.stop_events[channel] = stop_event

    def stop(self):
        """停止所有通道"""
        if not self.is_running:
            return

        # 发送停止信号
        for channel, event in self.stop_events.items():
            event.set()
            print(f"[Manager] 发送停止信号到通道 {channel}")

        # 等待进程结束
        for channel, process in self.processes.items():
            process.join(timeout=3.0)
            if process.is_alive():
                process.terminate()
                print(f"[Manager] 强制终止通道 {channel}")

        self.processes.clear()
        self.output_queues.clear()
        self.params_queues.clear()
        self.stop_events.clear()
        self.is_running = False
        print("[Manager] 所有通道已停止")

    def update_params(self, params: dict):
        """更新所有通道的参数"""
        for channel, queue in self.params_queues.items():
            try:
                queue.put_nowait(params)
            except:
                pass

    def get_results(self) -> list:
        """获取所有通道的处理结果（非阻塞）"""
        results = []
        for channel, queue in self.output_queues.items():
            try:
                while True:
                    result = queue.get_nowait()
                    results.append(result)
            except Empty:
                pass
        return results

    def is_alive(self) -> bool:
        """检查进程是否存活"""
        if not self.is_running:
            return False
        return all(p.is_alive() for p in self.processes.values())
