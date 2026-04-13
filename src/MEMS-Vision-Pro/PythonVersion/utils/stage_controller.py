"""
位移台控制器模块
实现与位移台硬件的通信和控制功能
"""

import serial
import serial.tools.list_ports
import threading
import time
import json
import os
from queue import Queue
from typing import Optional, Callable, Any
import numpy as np

class StageController:
    """位移台控制器类"""
    
    def __init__(self, config_file: str = "stage_config.json"):
        """初始化位移台控制器"""
        # --- Protocol and Device Constants ---
        self.CAN_ID = 0x5D
        self.MOTOR_ID_Z = 2
        
        # 串口相关变量
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.receive_thread: Optional[threading.Thread] = None
        self.query_thread: Optional[threading.Thread] = None
        self.running = True
        
        # 位移台状态变量
        self.position_z_actual = 0.0  # 绝对硬件位置
        self.zero_z = 0.0             # 软件零点偏移
        self.max_speed_z = 1000
        self.min_limit_z = -10.0
        self.max_limit_z = 10.0
        
        # 转换参数
        self.change_z_screw_pitch = 0.3048
        self.change_z_encoder = 8000
        self.change_z = self.change_z_screw_pitch / self.change_z_encoder
        
        self.config_file = config_file
        self.gui_queue = Queue()
        
        # 回调函数
        self.position_callback: Optional[Callable[[float], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        
        # 微米级移动和图像拍摄相关
        self.step_size = 0.001  # 默认步进值(1微米)
        self.images_per_step = 1  # 每步拍摄图像数
        self.image_capture_callback: Optional[Callable[[], np.ndarray]] = None
        self.stack_images = []  # 存储图像堆栈
        
        # 添加停止拍摄标志
        self.stop_capture = False
        
        self.load_config()
        
    def set_callbacks(self, position_callback=None, status_callback=None, error_callback=None):
        """设置回调函数"""
        self.position_callback = position_callback
        self.status_callback = status_callback
        self.error_callback = error_callback
        
    def set_image_capture_callback(self, callback: Callable[[], np.ndarray]):
        """设置图像捕获回调函数"""
        self.image_capture_callback = callback
        
    def set_step_parameters(self, step_size: float, images_per_step: int):
        """设置步进参数"""
        self.step_size = abs(step_size)  # 确保步进值为正数（毫米）
        self.images_per_step = max(1, images_per_step)  # 确保至少拍摄1张图像
        
    def get_available_ports(self) -> list:
        """获取可用的串口列表"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        return ports
        
    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """连接到位移台"""
        try:
            if self.is_connected and self.serial_port:
                self.disconnect()
                
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            self.is_connected = True
            self.running = True
            
            # 启动接收线程
            self.receive_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.receive_thread.start()
            
            # 启动位置查询线程
            self.query_thread = threading.Thread(target=self.query_position_loop, daemon=True)
            self.query_thread.start()
            
            self._update_status(f"已连接到 {port}")
            return True
        except Exception as e:
            self._update_error(f"无法连接到串口: {str(e)}")
            self.is_connected = False
            return False
            
    def disconnect(self):
        """断开连接"""
        self.running = False
        if self.query_thread:
            self.query_thread.join(timeout=0.2)
        if self.receive_thread:
            self.receive_thread.join(timeout=0.2)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self._update_status("未连接")
        
    def receive_data(self):
        """接收数据线程函数"""
        buffer = bytearray()
        while self.running and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    buffer.extend(self.serial_port.read(self.serial_port.in_waiting))
                while len(buffer) >= 9:
                    if buffer[0] == self.CAN_ID:
                        self.process_received_message(bytes(buffer[:9]))  # 转换为bytes
                        buffer = buffer[9:]
                    else:
                        buffer = buffer[1:]
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    self._update_error(f"接收数据时出错: {e}")
                    self.disconnect()
                break
                
    def process_received_message(self, data: bytes):
        """处理接收到的消息"""
        data_type, motor_id = data[1], data[3]
        if motor_id != self.MOTOR_ID_Z:
            return
        if data_type == 0xAA:
            position_raw = int.from_bytes(data[4:8], byteorder='big', signed=True)
            self.position_z_actual = position_raw * self.change_z
            self.gui_queue.put(self.update_position_display)
            
    def update_position_display(self):
        """更新位置显示"""
        current_pos = self.position_z_actual - self.zero_z
        if self.position_callback:
            # 传递当前位置给回调函数
            self.position_callback(current_pos)
            
    def query_position_loop(self):
        """位置查询循环"""
        while self.running and self.is_connected:
            command = bytes(bytearray([self.CAN_ID, 0xAA, 0x01, self.MOTOR_ID_Z, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]))
            self.send_command(command)
            time.sleep(0.2)
            
    def _update_status(self, message: str):
        """更新状态信息"""
        if self.status_callback:
            self.status_callback(message)
            
    def _update_error(self, message: str):
        """更新错误信息"""
        if self.error_callback:
            self.error_callback(message)
            
    # --- Command Functions ---
    
    def go_to_software_zero(self):
        """移动到当前的软件零点位置"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        # 目标绝对位置就是软件零点本身
        target_absolute = self.zero_z
        position_int = int(target_absolute / self.change_z)
        
        payload = position_int.to_bytes(4, byteorder='big', signed=True)
        command = bytes(bytearray([self.CAN_ID, 0xAB, 0x02, self.MOTOR_ID_Z]) + payload + bytearray([0xFF]))
        success = self.send_command(command)
        if success:
            self._update_status(f"指令: 回到软件零点 {self.zero_z:.3f}mm")
        return success
        
    def mechanical_home_axis(self):
        """移动到机械零点 (绝对位置0) 并将软件零点重置为0"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        # 步骤1: 使用绝对定位命令移动到硬件位置0
        position_int = 0
        payload = position_int.to_bytes(4, byteorder='big', signed=True)
        command = bytes(bytearray([self.CAN_ID, 0xAB, 0x02, self.MOTOR_ID_Z]) + payload + bytearray([0xFF]))
        success = self.send_command(command)
        if not success:
            return False
            
        self._update_status("指令: 移动到机械零点 (绝对位置 0mm)")
        
        # 步骤2: 将软件零点偏移重置为0
        self.zero_z = 0.0
        self.gui_queue.put(self.update_position_display)
        self._update_status("软件零点已重置为 0.0 mm")
        return True
        
    def zero_axis(self):
        """将当前位置设为软件零点 (纯软件操作)"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        self.zero_z = self.position_z_actual
        self.gui_queue.put(self.update_position_display)
        self._update_status(f"新的软件零点被设置在绝对位置: {self.zero_z:.3f} mm")
        return True
        
    def move_to_position(self, target_relative: float) -> bool:
        """移动到指定位置（相对位置，单位：毫米）"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        try:
            # 检查是否在限位范围内
            if not (self.min_limit_z <= target_relative <= self.max_limit_z):
                self._update_error(f"目标位置超出范围 ({self.min_limit_z} ~ {self.max_limit_z} mm)")
                return False
                
            target_absolute = target_relative + self.zero_z
            position_int = int(target_absolute / self.change_z)
            payload = position_int.to_bytes(4, byteorder='big', signed=True)
            command = bytes(bytearray([self.CAN_ID, 0xAB, 0x02, self.MOTOR_ID_Z]) + payload + bytearray([0xFF]))
            success = self.send_command(command)
            if success:
                self._update_status(f"移动到位置: {target_relative*1000:.1f} 微米")
            return success
        except ValueError:
            self._update_error("请输入有效的数字")
            return False
            
    def move_relative(self, direction: int) -> bool:
        """相对移动"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        try:
            step = self.step_size * direction
            current_pos = self.position_z_actual - self.zero_z
            if not (self.min_limit_z <= current_pos + step <= self.max_limit_z):
                self._update_error("相对移动会超出限位范围")
                return False
                
            position_int = int(step / self.change_z)
            payload = position_int.to_bytes(4, byteorder='big', signed=True)
            command = bytes(bytearray([self.CAN_ID, 0xAC, 0x02, self.MOTOR_ID_Z]) + payload + bytearray([0xFF]))
            success = self.send_command(command)
            if success:
                self._update_status(f"相对移动: {step:.6f}mm")
            return success
        except Exception as e:  # 修改这里，捕获所有异常
            self._update_error(f"相对移动时出错: {str(e)}")
            return False
            
    def move_to_limit(self, direction: int) -> bool:
        """移动到限位"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        payload_val = 1 if direction > 0 else -1
        payload_byte = payload_val.to_bytes(1, byteorder='big', signed=True)
        command = bytes(bytearray([self.CAN_ID, 0x31, 0x02, self.MOTOR_ID_Z]) + payload_byte + bytearray([0xFF, 0xFF, 0xFF, 0xFF]))
        success = self.send_command(command)
        if success:
            direction_str = "正限位" if direction > 0 else "负限位"
            self._update_status(f"移动到{direction_str}")
        return success
        
    def stop_axis(self) -> bool:
        """停止轴运动"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        command = bytes(bytearray([self.CAN_ID, 0x12, 0x02, self.MOTOR_ID_Z, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]))
        success = self.send_command(command)
        if success:
            self._update_status("轴已停止")
        return success
        
    def set_speed(self, speed: int) -> bool:
        """设置速度"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        try:
            if not (1 <= speed <= 3000):
                self._update_error("速度范围必须在 1 ~ 3000 之间")
                return False
                
            self.max_speed_z = speed
            payload = speed.to_bytes(2, byteorder='big')
            command = bytes(bytearray([self.CAN_ID, 0x56, 0x02, self.MOTOR_ID_Z]) + payload + bytearray([0xFF, 0xFF, 0xFF]))
            success = self.send_command(command)
            if success:
                self._update_status(f"速度已设置为: {speed} pps")
            return success
        except ValueError:
            self._update_error("请输入有效的整数")
            return False
            
    def set_limit(self, min_val: float, max_val: float) -> bool:
        """设置限位"""
        try:
            if min_val >= max_val:
                self._update_error("最小值必须小于最大值")
                return False
                
            self.min_limit_z, self.max_limit_z = min_val, max_val
            self._update_status(f"限位已设置: {self.min_limit_z:.1f} ~ {self.max_limit_z:.1f}")
            return True
        except ValueError:
            self._update_error("请输入有效的数字")
            return False
            
    def save_config(self):
        """保存配置"""
        config = {
            "zero_z": self.zero_z,
            "max_speed_z": self.max_speed_z,
            "min_limit_z": self.min_limit_z,
            "max_limit_z": self.max_limit_z,
            "step_size": self.step_size,
            "images_per_step": self.images_per_step
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            self._update_status(f"配置已保存到 {self.config_file}")
            return True
        except Exception as e:
            self._update_error(f"无法保存配置: {str(e)}")
            return False
            
    def load_config(self):
        """加载配置"""
        if not os.path.exists(self.config_file):
            return False
            
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            self.zero_z = config.get("zero_z", 0.0)
            self.max_speed_z = config.get("max_speed_z", 1000)
            self.min_limit_z = config.get("min_limit_z", -20.0)
            self.max_limit_z = config.get("max_limit_z", 20.0)
            self.step_size = config.get("step_size", 0.001)
            self.images_per_step = config.get("images_per_step", 1)
            return True
        except Exception as e:
            self._update_error(f"加载配置时出错: {e}")
            return False
            
    def send_command(self, command_bytes: bytes) -> bool:
        """发送命令"""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(command_bytes)
                return True
            except Exception as e:
                self._update_error(f"发送命令失败: {e}")
                self.disconnect()
                return False
        return False
        
    def micro_step_and_capture(self, direction: int) -> bool:
        """微米级步进并拍摄图像"""
        if not self.is_connected:
            self._update_error("未连接到设备")
            return False
            
        # 执行相对移动
        if not self.move_relative(direction):
            return False
            
        # 等待移动完成（简单延时）
        time.sleep(0.1)
        
        # 拍摄指定数量的图像
        for i in range(self.images_per_step):
            if self.image_capture_callback:
                image = self.image_capture_callback()
                if image is not None:
                    self.stack_images.append(image.copy())
                    self._update_status(f"已拍摄图像 {len(self.stack_images)}")
                else:
                    self._update_error(f"拍摄第{i+1}张图像失败")
            else:
                self._update_error("未设置图像捕获回调函数")
                return False
                
        return True
        
    def auto_capture_sequence(self, start_pos: float, end_pos: float, step_size: float) -> bool:
        """自动拍摄序列（所有参数均为毫米）"""
        if not self.is_connected:
            return False
            
        if step_size <= 0:
            return False
            
        # 检查停止标志
        if self.stop_capture:
            self._update_status("拍摄已停止")
            return True
            
        # 确定移动方向
        direction = 1 if end_pos > start_pos else -1
        steps = int(abs(end_pos - start_pos) / step_size) + 1
    
        self._update_status(f"开始自动拍摄序列: 从{start_pos*1000:.1f}到{end_pos*1000:.1f}微米，步进{step_size*1000:.1f}微米，共{steps}步")
    
        # 清空之前的堆栈
        self.clear_stack_images()
    
        # 从当前软件零点开始
        zero_position = self.zero_z
    
        # 遍历每个位置进行拍摄
        for step in range(steps):
            # 检查停止标志
            if self.stop_capture:
                self._update_status("拍摄已停止")
                # 保存已拍摄的图像
                if self.stack_images:
                    self._update_status(f"已停止，保存已拍摄的{len(self.stack_images)}张图像")
                return True
            
            # 计算当前位置（相对于软件零点）
            current_pos = start_pos + direction * step * step_size
            target_pos = zero_position + current_pos
            
            # 移动到当前位置
            if not self.move_to_position(current_pos):  # move_to_position使用相对位置
                return False
            
            # 等待移动完成
            time.sleep(0.2)
            
            # 检查停止标志
            if self.stop_capture:
                self._update_status("拍摄已停止")
                # 保存已拍摄的图像
                if self.stack_images:
                    self._update_status(f"已停止，保存已拍摄的{len(self.stack_images)}张图像")
                return True
        
            # 在当前位置拍摄指定数量的图像
            for i in range(self.images_per_step):
                # 检查停止标志
                if self.stop_capture:
                    self._update_status("拍摄已停止")
                    # 保存已拍摄的图像
                    if self.stack_images:
                        self._update_status(f"已停止，保存已拍摄的{len(self.stack_images)}张图像")
                    return True
                
                if self.image_capture_callback:
                    # 在每次拍摄前添加一个小延时，确保图像数据更新
                    time.sleep(0.1)  # 100ms延时
                    image = self.image_capture_callback()
                    # 检查图像是否有效
                    if image is not None and hasattr(image, 'size') and image.size > 0:
                        self.stack_images.append(image.copy())
                        self._update_status(f"位置{current_pos*1000:.1f}微米第{i+1}张图像已拍摄，共{len(self.stack_images)}张")
                    else:
                        # 如果没有获取到有效图像，等待一段时间再尝试
                        time.sleep(0.1)  # 再等待100ms
                        image = self.image_capture_callback()
                        if image is not None and hasattr(image, 'size') and image.size > 0:
                            self.stack_images.append(image.copy())
                            self._update_status(f"位置{current_pos*1000:.1f}微米第{i+1}张图像已拍摄，共{len(self.stack_images)}张")
                        else:
                            self._update_error(f"位置{current_pos*1000:.1f}微米第{i+1}张图像拍摄失败")
                else:
                    self._update_error("未设置图像捕获回调函数")
                    return False
    
        self._update_status(f"自动拍摄序列完成，共拍摄{len(self.stack_images)}张图像")
        return True
        
    def get_stack_images(self) -> list:
        """获取图像堆栈"""
        return self.stack_images.copy()
        
    def clear_stack_images(self):
        """清空图像堆栈"""
        self.stack_images.clear()
        
    def close(self):
        """关闭控制器"""
        self.disconnect()
        self.running = False