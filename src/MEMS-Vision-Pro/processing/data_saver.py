"""
数据保存模块
负责保存原始数据和处理后的数据
"""

import os
import time
from typing import Optional, List

class DataSaver:
    """数据保存管理器"""
    
    def __init__(self):
        """初始化数据保存器"""
        self.save_file: Optional[object] = None
        self.is_saving = False
        self.save_filename = ""
        
    def start_saving(self, filename: str) -> bool:
        """
        开始保存数据
        
        Args:
            filename: 保存文件名
            
        Returns:
            bool: 是否成功开始保存
        """
        try:
            # 确保目录存在
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            self.save_file = open(filename, 'wb')
            self.is_saving = True
            self.save_filename = filename
            return True
        except Exception as e:
            print(f"创建保存文件失败: {e}")
            self.is_saving = False
            return False
    
    def stop_saving(self) -> bool:
        """
        停止保存数据
        
        Returns:
            bool: 是否成功停止保存
        """
        try:
            if self.save_file:
                self.save_file.close()
                self.save_file = None
            self.is_saving = False
            saved_filename = self.save_filename
            self.save_filename = ""
            return True
        except Exception as e:
            print(f"停止保存数据失败: {e}")
            return False
    
    def save_packet(self, packet: bytes) -> bool:
        """
        保存单个数据包
        
        Args:
            packet: 数据包字节
            
        Returns:
            bool: 是否成功保存
        """
        if not self.is_saving or not self.save_file:
            return False
            
        try:
            # 写入包长度和包数据
            length = len(packet)
            self.save_file.write(length.to_bytes(4, 'big'))
            self.save_file.write(packet)
            self.save_file.flush()
            return True
        except Exception as e:
            print(f"保存数据包失败: {e}")
            return False
    
    def save_packets_to_bin(self, packets: List[bytes], filename: str = None) -> bool:
        """
        保存数据包列表到二进制文件
        
        Args:
            packets: 数据包列表
            filename: 文件名（可选，如果不提供则自动生成）
            
        Returns:
            bool: 是否成功保存
        """
        if not packets:
            print("警告：没有数据包可保存")
            return False

        if filename is None:
            timestamp = int(time.time() * 1000)
            filename = f"frame_{timestamp}.bin"
        
        try:
            # 检查是否有有效数据
            valid_packets = [p for p in packets if p and len(p) > 0]
            if not valid_packets:
                print("警告：所有数据包都为空")
                return False
                
            # 确保目录存在
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            with open(filename, 'wb') as f:
                for packet in valid_packets:
                    f.write(packet)
            
            print(f"帧已保存为: {filename}")
            return True
        except Exception as e:
            print(f"保存帧失败: {e}")
            return False
    
    def save_image_data(self, image_data, filename: str = None, format: str = 'npy') -> bool:
        """
        保存图像数据
        
        Args:
            image_data: 图像数据（numpy数组）
            filename: 文件名（可选）
            format: 保存格式 ('npy', 'png', 'tiff')
            
        Returns:
            bool: 是否成功保存
        """
        import numpy as np
        
        if filename is None:
            timestamp = int(time.time() * 1000)
            filename = f"image_{timestamp}.{format}"
        
        try:
            # 确保目录存在
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            
            if format.lower() == 'npy':
                np.save(filename, image_data)
            elif format.lower() == 'png':
                import cv2
                # 转换为8位图像
                if image_data.dtype != np.uint8:
                    image_8bit = ((image_data - image_data.min()) / 
                                 (image_data.max() - image_data.min()) * 255).astype(np.uint8)
                else:
                    image_8bit = image_data
                cv2.imwrite(filename, image_8bit)
            elif format.lower() == 'tiff':
                import cv2
                cv2.imwrite(filename, image_data.astype(np.uint16))
            else:
                raise ValueError(f"不支持的格式: {format}")
            
            print(f"图像已保存为: {filename}")
            return True
        except Exception as e:
            print(f"保存图像失败: {e}")
            return False
    
    def get_save_status(self) -> dict:
        """
        获取保存状态
        
        Returns:
            dict: 包含保存状态信息的字典
        """
        return {
            'is_saving': self.is_saving,
            'filename': self.save_filename,
            'file_exists': self.save_file is not None
        }
    
    def __del__(self):
        """析构函数，确保文件被正确关闭"""
        if self.save_file:
            try:
                self.save_file.close()
            except:
                pass

class BatchDataSaver:
    """批量数据保存器"""
    
    def __init__(self, base_directory: str = "saved_data"):
        """
        初始化批量数据保存器
        
        Args:
            base_directory: 基础保存目录
        """
        self.base_directory = base_directory
        self.session_directory = None
        self.frame_counter = 0
        
        # 确保基础目录存在
        if not os.path.exists(self.base_directory):
            os.makedirs(self.base_directory)
    
    def start_session(self, session_name: str = None) -> str:
        """
        开始新的保存会话
        
        Args:
            session_name: 会话名称（可选）
            
        Returns:
            str: 会话目录路径
        """
        if session_name is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            session_name = f"session_{timestamp}"
        
        self.session_directory = os.path.join(self.base_directory, session_name)
        if not os.path.exists(self.session_directory):
            os.makedirs(self.session_directory)
        
        self.frame_counter = 0
        print(f"开始新会话: {self.session_directory}")
        return self.session_directory
    
    def save_frame_data(self, packets: List[bytes], image_data=None) -> bool:
        """
        保存帧数据（原始数据包和处理后的图像）
        
        Args:
            packets: 原始数据包
            image_data: 处理后的图像数据（可选）
            
        Returns:
            bool: 是否成功保存
        """
        if not self.session_directory:
            print("错误：未开始会话")
            return False
        
        self.frame_counter += 1
        frame_dir = os.path.join(self.session_directory, f"frame_{self.frame_counter:06d}")
        
        if not os.path.exists(frame_dir):
            os.makedirs(frame_dir)
        
        success = True
        
        # 保存原始数据包
        raw_filename = os.path.join(frame_dir, "raw_data.bin")
        saver = DataSaver()
        if not saver.save_packets_to_bin(packets, raw_filename):
            success = False
        
        # 保存处理后的图像
        if image_data is not None:
            image_filename = os.path.join(frame_dir, "processed_image.npy")
            if not saver.save_image_data(image_data, image_filename, 'npy'):
                success = False
        
        return success
    
    def end_session(self):
        """结束当前会话"""
        if self.session_directory:
            print(f"会话结束: {self.session_directory}, 共保存 {self.frame_counter} 帧")
            self.session_directory = None
            self.frame_counter = 0