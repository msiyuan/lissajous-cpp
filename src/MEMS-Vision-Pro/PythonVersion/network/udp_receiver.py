"""
UDP接收器模块
负责接收UDP数据包并放入全局队列
"""

import socket
import time
from PyQt5.QtCore import QThread, pyqtSignal
from utils.global_queue import put_packet
from config.constants import SOCKET_RECV_BUFFER

class UDPReceiver(QThread):
    """
    UDP数据接收线程
    只负责网络接收，将包放入全局队列
    """
    packet_received = pyqtSignal(bytes)  # 用于更新计数器
    log_message = pyqtSignal(str)

    def __init__(self, target_ip, recv_port, parent=None):
        """
        初始化UDP接收器
        
        Args:
            target_ip: 目标IP（下位机IP）
            recv_port: 接收端口（8003）
            parent: 父对象
        """
        super().__init__(parent)
        self.target_ip = target_ip
        self.recv_port = recv_port
        self._is_running = True
        self.save_data = False
        self.save_file = None
        self.sock = None

    def start_saving(self, filename):
        """
        开始保存数据
        
        Args:
            filename: 保存文件名
        """
        try:
            self.save_file = open(filename, 'wb')
            self.save_data = True
            self.log_message.emit(f"开始保存原始数据到: {filename}")
        except Exception as e:
            self.log_message.emit(f"创建保存文件失败: {e}")
            self.save_data = False

    def stop_saving(self):
        """停止保存数据"""
        if self.save_file:
            self.save_file.close()
            self.save_file = None
        self.save_data = False
        self.log_message.emit("停止保存原始数据")

    def run(self):
        """主运行循环"""
        try:
            self._setup_socket()
        except Exception as e:
            self.log_message.emit(f"Failed to bind socket: {e}")
            return

        self.log_message.emit(f"UDP Receiver started on port {self.recv_port}")

        while self._is_running:
            try:
                self._receive_and_process_packet()
            except Exception as e:
                self.log_message.emit(f"Error receiving UDP packets: {e}")
                time.sleep(0.001)

        self.stop_saving()  # 确保关闭保存文件
        self.log_message.emit("UDP Receiver stopped.")

    def _setup_socket(self):
        """设置socket"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_RECV_BUFFER)
        # 添加端口重用选项
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.recv_port))

    def _receive_and_process_packet(self):
        """接收并处理数据包"""
        data, _ = self.sock.recvfrom(65535)
        
        # 保存原始数据
        if self.save_data and self.save_file:
            self._save_raw_data(data)

        # 将数据放入全局队列
        success = put_packet(data, block=False)
        if success:
            self.packet_received.emit(data)
        else:
            self.log_message.emit("警告：队列已满，丢弃新包")

    def _save_raw_data(self, data):
        """保存原始数据到文件"""
        try:
            # 写入包长度和包数据
            length = len(data)
            self.save_file.write(length.to_bytes(4, 'big'))
            self.save_file.write(data)
            self.save_file.flush()
        except Exception as e:
            self.log_message.emit(f"保存数据出错: {e}")

    def stop(self):
        """停止接收器"""
        self._is_running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.sock.close()
            self.sock = None
        self.stop_saving()
        self.wait()

    def is_running(self):
        """检查是否正在运行"""
        return self._is_running and self.isRunning()