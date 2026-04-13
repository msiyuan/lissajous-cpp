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

    def save_stack_data(self, image_stack: list, filename: str = None) -> bool:
        """
        保存图像堆栈数据为TIFF格式
        
        Args:
            image_stack: 图像堆栈列表（numpy数组列表）
            filename: 文件名（可选）
            
        Returns:
            bool: 是否成功保存
        """
        import numpy as np
        
        if not image_stack:
            print("警告：没有图像堆栈数据可保存")
            return False

        if filename is None:
            timestamp = int(time.time() * 1000)
            filename = f"stack_{timestamp}.tiff"
        
        try:
            # 确保目录存在
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            
            # 检查并处理图像数据
            processed_stack = []
            for i, img in enumerate(image_stack):
                print(f"处理第{i+1}张图像，原始形状: {img.shape}, 数据类型: {img.dtype}")
                
                # 确保数据类型为uint16
                if img.dtype != np.uint16:
                    # 转换为uint16类型
                    if img.max() != img.min():  # 避免除零错误
                        img_normalized = ((img - img.min()) / (img.max() - img.min()) * 65535).astype(np.uint16)
                    else:
                        img_normalized = np.zeros_like(img, dtype=np.uint16)
                else:
                    img_normalized = img
                
                # 确保图像是二维的
                if img_normalized.ndim == 3:
                    # 如果是三维数组，取第一个通道或平均所有通道转换为二维
                    if img_normalized.shape[2] == 1:
                        img_2d = img_normalized[:, :, 0]
                    else:
                        img_2d = np.mean(img_normalized, axis=2).astype(np.uint16)
                    processed_stack.append(img_2d)
                    print(f"  添加转换后的灰度图像，形状: {img_2d.shape}")
                elif img_normalized.ndim == 2:
                    # 二维灰度图像，直接添加
                    processed_stack.append(img_normalized)
                    print(f"  添加灰度图像，形状: {img_normalized.shape}")
                else:
                    # 其他情况，转换为二维
                    img_flat = img_normalized.reshape(img_normalized.shape[0], -1)
                    processed_stack.append(img_flat)
                    print(f"  添加转换后的灰度图像，形状: {img_flat.shape}")
            
            if not processed_stack:
                print("错误：没有有效的图像可用于堆栈")
                return False
            
            # 确保所有图像尺寸一致
            first_shape = processed_stack[0].shape
            print(f"第一张图像形状: {first_shape}")
            
            # 过滤掉尺寸不一致的图像
            consistent_stack = []
            for i, img in enumerate(processed_stack):
                if img.shape == first_shape:
                    consistent_stack.append(img)
                else:
                    print(f"警告：第{i+1}张图像尺寸不匹配 ({img.shape})，跳过")
            
            if not consistent_stack:
                print("错误：没有尺寸一致的图像可用于堆栈")
                return False
            
            print(f"最终堆栈包含 {len(consistent_stack)} 张图像")
            
            # 将图像堆栈转换为numpy数组 (N, H, W) 格式
            stack_array = np.array(consistent_stack)
            print(f"堆栈数组形状: {stack_array.shape}, 数据类型: {stack_array.dtype}")
            
            # 尝试使用tifffile库保存多页TIFF文件
            try:
                import tifffile
                # 保存为多页TIFF文件
                tifffile.imwrite(filename, stack_array)
                print(f"图像堆栈已保存为多页TIFF: {filename} ({len(consistent_stack)}帧)")
                return True
            except ImportError:
                print("tifffile库未安装，尝试使用OpenCV保存")
                # 使用OpenCV保存，但需要特殊处理
                return self._save_stack_with_opencv(stack_array, filename)
        except Exception as e:
            print(f"保存图像堆栈失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_stack_with_opencv(self, stack_array, filename: str) -> bool:
        """
        使用OpenCV保存图像堆栈
        
        Args:
            stack_array: 图像堆栈数组 (N, H, W)
            filename: 文件名
            
        Returns:
            bool: 是否成功保存
        """
        try:
            import cv2
            import numpy as np
            
            # OpenCV不能直接保存多页TIFF，我们需要保存为.npz格式或者其他格式
            # 这里我们保存为.npy格式，这是numpy的二进制格式
            npy_filename = filename.replace('.tiff', '.npy').replace('.tif', '.npy')
            np.save(npy_filename, stack_array)
            print(f"图像堆栈已保存为numpy格式: {npy_filename} ({stack_array.shape[0]}帧)")
            return True
        except Exception as e:
            print(f"使用OpenCV保存堆栈时出错: {e}")
            return False
            
    def _save_stack_as_separate_images(self, image_stack: list, base_filename: str) -> bool:
        """
        将图像堆栈分别保存为单独的图像文件
        
        Args:
            image_stack: 图像堆栈列表
            base_filename: 基础文件名
            
        Returns:
            bool: 是否成功保存
        """
        try:
            import cv2
            import numpy as np
            import os
            
            # 获取基础文件名和扩展名
            base_name, ext = os.path.splitext(base_filename)
            if not ext:
                ext = '.tiff'
            
            success_count = 0
            for i, img in enumerate(image_stack):
                # 生成文件名
                page_filename = f"{base_name}_page_{i:03d}{ext}"
                # 保存图像
                success = cv2.imwrite(page_filename, img)
                if success:
                    success_count += 1
                    print(f"  已保存: {page_filename}")
                else:
                    print(f"  保存失败: {page_filename}")
            
            if success_count == len(image_stack):
                print(f"所有图像页已分别保存 ({success_count}/{len(image_stack)}帧)")
                return True
            else:
                print(f"部分图像页保存失败 ({success_count}/{len(image_stack)}帧)")
                return False
        except Exception as e:
            print(f"保存分离图像时出错: {e}")
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