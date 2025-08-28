import sys
import math
import numpy as np
import os
import time
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QProgressBar,
    QDoubleSpinBox,  # 使用 QDoubleSpinBox
    QGroupBox,
    QGridLayout,
    QSlider,  # 添加滑动条控件
    QLineEdit,
)
import glob  # 添加此导入用于文件查找
import numba  # 确保 numba 已导入




def adjust_image(image, min_val, max_val, contrast, brightness):
    """
    调整图像的显示参数
    """
    # 规范化到0-65535范围
    normalized = np.clip((image - min_val) / (max_val - min_val) * 65535, 0, 65535)
    # 应用对比度
    contrasted = np.clip(normalized * (contrast / 100.0), 0, 65535)
    # 应用亮度
    with np.errstate(over='ignore'):
        brightened = np.clip(contrasted + (brightness / 100.0 * 65535), 0, 65535)
    return brightened.astype(np.uint16)


@numba.njit(cache=True)  # 使用 njit 以获得最佳性能，启用缓存
def _interpolate_columns_numba(image_data, nan_mask):
    """
    使用 Numba 优化的垂直插值函数。
    为每一列中的 NaN 值插值。
    
    Args:
        image_data (np.ndarray): 包含 NaN 值的图像数据
        nan_mask (np.ndarray): 布尔掩码，标记 NaN 位置
        
    Returns:
        np.ndarray: 插值后的图像
    """
    # 获取图像维度
    rows, cols = image_data.shape
    # 创建行索引数组
    row_indices = np.arange(rows)
    # 创建输出数组的副本
    result = image_data.copy()
    
    # 逐列处理
    for col in range(cols):
        # 获取当前列的掩码
        col_mask = nan_mask[:, col]
        
        # 检查列中是否既有 NaN 值又有有效值
        if np.any(col_mask) and not np.all(col_mask):
            # 获取有效点的位置和值
            valid_rows = row_indices[~col_mask]
            valid_values = image_data[valid_rows, col]
            
            # 获取 NaN 位置
            nan_rows = row_indices[col_mask]
            
            # 确保有足够的有效点进行插值
            if len(valid_rows) > 1 and len(nan_rows) > 0:
                # 一次性计算所有插值点
                interpolated_values = np.interp(nan_rows, valid_rows, valid_values)
                # 更新结果数组
                result[nan_rows, col] = interpolated_values
    
    return result


class AutoImageProcessor(QThread):
    """
    Worker thread for processing images to keep the GUI responsive (Automatic Processing).
    """
    image_processed = pyqtSignal(np.ndarray, float, float, float, float)  # 修改类型为 float
    progress_update = pyqtSignal(int)
    manual_phase_requested = pyqtSignal(float, float)  # Signal for manual processing

    def __init__(
        self,
        packets,
        SampleRate,
        Freqx,
        Freqy,
        delta_phase_x_range,
        delta_phase_y_range,
        parent=None,
    ):
        super().__init__(parent)
        self.packets = packets
        self.SampleRate = SampleRate
        self.Freqx = Freqx
        self.Freqy = Freqy
        self.delta_phase_x_range = delta_phase_x_range
        self.delta_phase_y_range = delta_phase_y_range
        self._is_running = True
        self._is_paused_x = True  # X方向初始为暂停状态
        self._is_paused_y = True  # Y方向初始为暂停状态
        self.manual_request = False
        self.manual_phase_x = 0.0
        self.manual_phase_y = 0.0
        self.current_x_index = 0  # 当前X相位索引
        self.current_y_index = 0  # 当前Y相位索引

        # Connect manual phase request signal to slot
        self.manual_phase_requested.connect(self.process_manual_phase)

    def run(self):
        while self._is_running:
            # 处理暂停状态
            if self._is_paused_x and self._is_paused_y:
                self.msleep(100)
                continue

            # 检查手动请求
            if self.manual_request:
                print(f"处理手动相位: X={self.manual_phase_x}, Y={self.manual_phase_y}")
                final_image, px_deg, py_deg = self.process_single_frame_one_freq(
                    self.packets, self.SampleRate, self.Freqx, self.Freqy,
                    self.manual_phase_x, self.manual_phase_y
                )
                self.image_processed.emit(final_image, self.manual_phase_x, self.manual_phase_y, px_deg, py_deg)
                self.manual_request = False
                continue

            # 获取当前X相位值
            delta_phase_x = self.delta_phase_x_range[self.current_x_index]
            # 获取当前Y相位值
            delta_phase_y = self.delta_phase_y_range[self.current_y_index]

            start_time=time.time()

            # 处理当前相位组合
            final_image, px_deg, py_deg = self.process_single_frame_one_freq(
                self.packets, self.SampleRate, self.Freqx, self.Freqy,
                delta_phase_x, delta_phase_y
            )
            end_time=time.time()
            print(f"处理时间: {end_time-start_time} 秒")

            # 发送处理结果
            self.image_processed.emit(final_image, delta_phase_x, delta_phase_y, px_deg, py_deg)

            # 更新X相位
            if not self._is_paused_x:
                self.current_x_index += 1
                if self.current_x_index >= len(self.delta_phase_x_range):
                    self.current_x_index = 0

            # 更新Y相位
            if not self._is_paused_y:
                self.current_y_index += 1
                if self.current_y_index >= len(self.delta_phase_y_range):
                    self.current_y_index = 0

            # 计算进度
            x_progress = (self.current_x_index / len(self.delta_phase_x_range)) * 50
            y_progress = (self.current_y_index / len(self.delta_phase_y_range)) * 50
            total_progress = int(x_progress + y_progress)
            self.progress_update.emit(total_progress)

            # 保持GUI响应
            self.msleep(100)  # 增加延时以便观察相位变化

    def stop(self):
        self._is_running = False
        self.resume()  # Prevent thread from being stuck in pause

    def pause(self):
        self._is_paused_x = True
        self._is_paused_y = True

    def resume(self):
        self._is_paused_x = False
        self._is_paused_y = False

    @pyqtSlot(float, float)
    def process_manual_phase(self, delta_phase_x, delta_phase_y):
        """
        Slot to handle manual phase processing requests.
        """
        print(f"Received manual phase request: X={delta_phase_x}, Y={delta_phase_y}")  # Debug
        self.manual_phase_x = delta_phase_x
        self.manual_phase_y = delta_phase_y
        self.manual_request = True

    def process_single_frame_one_freq(
        self,
        packets,
        SampleRate,
        Freqx,
        Freqy,
        deltaphasex,
        deltaphasey,
    ):
        """
        中文说明：
        该函数对原有的 process_single_frame_one_freq 做了部分矢量化优化：
          1. 使用 NumPy 批量计算 X、Y 轨迹。
          2. 使用 bincount 进行像素访问次数和灰度值的累加。
          3. 保留对 packet 的逐包解析逻辑，提取灰度值并映射到对应帧的像素坐标。
        
        参数:
        - packets       : 数据包列表，每个元素是一个字节数组，包含相应的相位、灰度等信息。
        - SampleRate    : 采样率 (Hz)，用于计算相位随时间变化的步进。
        - Freqx, Freqy  : X 方向和 Y 方向的扫描频率。
        - deltaphasex,
          deltaphasey   : 相位偏移（°），在计算时会加到从数据包读出的相位上。
        
        返回:
        - final_image   : 处理后得到的最终图像 (512 x 512)。
        - phasex_deg    : X 方向相位（度）。
        - phasey_deg    : Y 方向相位（度）。
        """

        # ---------------------
        # 第 1 步：基本参数设置
        # ---------------------
        NumFrame = int(1e6)         # 每帧的采样点数
        ImageSize = 512             # 图像大小为 512 x 512
        Delta_t = 1.0 / SampleRate  # 每个采样点之间的时间间隔

        X_Amp = ImageSize / 2.0     # X 方向扫描振幅
        Y_Amp = ImageSize / 2.0     # Y 方向扫描振幅

        # X_Freq、Y_Freq 表示：在每个采样点 i 的相位步进
        X_Freq = math.pi * Delta_t * 2 * Freqx  # 等价于 2π(SampleRate^-1)*Freqx
        Y_Freq = math.pi * Delta_t * 2 * Freqy

        # 用于累加像素灰度和像素访问次数的数组
        PixelData = np.zeros((ImageSize, ImageSize), dtype=np.int64)

        # ---------------------
        # 第 2 步：解析第一个数据包，获取初相信息 (phasex, phasey)
        # ---------------------
        first_packet = packets[0]

        phase_x_raw = (
            (first_packet[6] << 24)
            + (first_packet[7] << 16)
            + (first_packet[8] << 8)
            + first_packet[9]
        )
        phase_y_raw = (
            (first_packet[10] << 24)
            + (first_packet[11] << 16)
            + (first_packet[12] << 8)
            + first_packet[13]
        )

        # 简化相位计算，减少不必要的转换
        phase_x_deg = (phase_x_raw * 360.0 / 33554432.0)
        phase_y_deg = (phase_y_raw * 360.0 / 33554432.0)

        # 直接计算最终相位，避免多次转换
        phasex_deg = (phase_x_deg + deltaphasex) % 360.0
        phasey_deg = (phase_y_deg + deltaphasey) % 360.0

        # 直接转换为弧度，减少精度可能会提高速度
        phasex = math.radians(phasex_deg)
        phasey = math.radians(phasey_deg)

        # ---------------------
        # 第 3 步：使用向量化方法计算 X, Y 坐标
        # ---------------------
        i_arr = np.arange(NumFrame, dtype=np.float64)  # [0, 1, 2, ..., 999999]

        # 计算 xflip 和 yflip
        xflip = -1.0 if np.sin(phasex) > 0 else 1.0
        yflip = -1.0 if np.sin(phasey) > 0 else 1.0

        # 计算扫描轨迹：X_vals, Y_vals
        X_vals = X_Amp * np.sin(X_Freq * i_arr + phasex) + 256.0
        print("X_vals[0]:",X_vals[0],"xflip:",xflip,"phasex:",phasex,"without xflip:",X_Amp * np.sin(X_Freq * i_arr + phasex) + 256.0)
        
        Y_vals = Y_Amp * np.sin(Y_Freq * i_arr + phasey) + 256.0
        print("Y_vals[0]:",Y_vals[0],"yflip:",yflip,"phasey:",phasey,"without yflip:",Y_Amp * np.sin(Y_Freq * i_arr + phasey) + 256.0)

        # 对结果取 floor 并限制在 [0, ImageSize - 1] 范围内
        X_vals = np.floor(X_vals).astype(np.int32)
        Y_vals = np.floor(Y_vals).astype(np.int32)

        np.clip(X_vals, 0, ImageSize - 1, out=X_vals)
        np.clip(Y_vals, 0, ImageSize - 1, out=Y_vals)

        # ---------------------
        # 第 4 步：计算像素访问次数 PixelTimes
        # ---------------------
        # 将 (x, y) 转换为线性索引： index = x * ImageSize + y
        XY_linear_indices = X_vals * ImageSize + Y_vals

        # 统计每个索引出现了多少次，从而得到像素被访问的次数
        PixelTimes_flat = np.bincount(
            XY_linear_indices,
            minlength=ImageSize * ImageSize
        )
        PixelTimes = PixelTimes_flat.reshape((ImageSize, ImageSize))

        # 同时准备一个一维的灰度累加缓存，用于后续一次性累加
        PixelDataFlat = np.zeros(ImageSize * ImageSize, dtype=np.int64)

        # 一帧对应的数据量 = NumFrame * 2（与原逻辑相同）
        TotalNumEachFrame = NumFrame * 2

        # ---------------------
        # 第 5 步：解析第一个数据包中的灰度值
        # ---------------------
        packageNum = (first_packet[4] << 8) + first_packet[5]

        i = 14   # 跳过前 14 个字节（相位数据等）
        flag = 14

        # 用于暂存 (pixel_index, gray_value) 的列表
        pixel_indices_list = []
        gray_values_list = []

        # 逐 2 字节读取灰度值
        while i < packageNum + 6 and (i + 1) < len(first_packet):
            val = (first_packet[i] << 8) + first_packet[i + 1]
            gray = 65535-val

            # 计算该灰度属于哪一个帧采样点
            pixel_index = int(NumFrame - (TotalNumEachFrame - i + flag) / 2)
            if 0 <= pixel_index < NumFrame:
                pixel_indices_list.append(pixel_index)
                gray_values_list.append(gray)

            i += 2

        # 修正包大小
        packageNum -= 8
        TotalNumEachFrame -= packageNum

        # ---------------------
        # 第 6 步：解析后续数据包
        # ---------------------
        for pkt in packets[1:]:
            packageNum = (pkt[4] << 8) + pkt[5]
            i = 6
            flag = 6

            while i < packageNum + 6 and (i + 1) < len(pkt):
                val = (pkt[i] << 8) + pkt[i + 1]
                gray = val

                pixel_index = int(NumFrame - (TotalNumEachFrame - i + flag) / 2)
                if 0 <= pixel_index < NumFrame:
                    pixel_indices_list.append(pixel_index)
                    gray_values_list.append(gray)

                i += 2

            # 如果需要，和原始逻辑一样做一次修正
            if flag == 14:
                packageNum -= 8

            TotalNumEachFrame -= packageNum
            if TotalNumEachFrame < 5:
                break  # 数据已读取完成或余量很小

        # ---------------------
        # 第 7 步：累加灰度值
        # ---------------------
        if len(pixel_indices_list) > 0:
            pixel_indices_arr = np.array(pixel_indices_list, dtype=np.int64)
            gray_values_arr = np.array(gray_values_list, dtype=np.int64)

            # 根据 pixel_index 找到对应的像素线性索引
            final_pixel_linear_indices = XY_linear_indices[pixel_indices_arr]

            # 使用 bincount 一次性完成灰度值的累加，并确保输出类型为 int64
            accum = np.bincount(
                final_pixel_linear_indices,
                weights=gray_values_arr,
                minlength=ImageSize * ImageSize
            ).astype(np.int64)  # 显式转换为 int64 类型

            # 现在 accum 和 PixelDataFlat 都是 int64 类型，可以安全地相加
            PixelDataFlat += accum

        # 将一维数组重塑回二维
        PixelData = PixelDataFlat.reshape((ImageSize, ImageSize))

        # ---------------------
        # 第 8 步：计算最终图像
        # ---------------------
        with np.errstate(divide='ignore', invalid='ignore'):
            final_image = PixelData / PixelTimes
            final_image[~np.isfinite(final_image)] = np.nan  # 将无效值、Inf、NaN 设为 NaN

        # 使用 Numba 插值函数对 NaN 值进行插值
        nan_mask = np.isnan(final_image)
        final_image = _interpolate_columns_numba(final_image, nan_mask)

        # 将剩余的 NaN 填充为 0（例如整列都是 NaN 的情况）
        final_image = np.nan_to_num(final_image, nan=0.0)

        return final_image, phasex_deg, phasey_deg



class ManualProcessor(QThread):
    """
    Worker thread for processing images with manual phase settings.
    """
    image_processed = pyqtSignal(np.ndarray, float, float, float, float)  # 修改类型为 float

    def __init__(
        self,
        packets,
        SampleRate,
        Freqx,
        Freqy,
        delta_phase_x,
        delta_phase_y,
        parent=None,
    ):
        super().__init__(parent)
        self.packets = packets
        self.SampleRate = SampleRate
        self.Freqx = Freqx
        self.Freqy = Freqy
        self.delta_phase_x = delta_phase_x
        self.delta_phase_y = delta_phase_y

    def run(self):
        start_time = time.time()  # 记录开始时间
        final_image, phasex_deg, phasey_deg = self.process_single_frame_one_freq(
            self.packets,
            self.SampleRate,
            self.Freqx,
            self.Freqy,
            self.delta_phase_x,
            self.delta_phase_y,
        )
        end_time = time.time()  # 记录结束时间
        processing_time = end_time - start_time  # 计算处理时间
        print(f"ManualProcessor 处理时间: {processing_time:.4f} 秒")  # 打印处理时间

        self.image_processed.emit(final_image, self.delta_phase_x, self.delta_phase_y, phasex_deg, phasey_deg)

    def process_single_frame_one_freq(
        self,
        packets,
        SampleRate,
        Freqx,
        Freqy,
        deltaphasex,
        deltaphasey,
    ):
        """
        中文说明：
        该函数对原有的 process_single_frame_one_freq 做了部分矢量化优化：
          1. 使用 NumPy 批量计算 X、Y 轨迹。
          2. 使用 bincount 进行像素访问次数和灰度值的累加。
          3. 保留对 packet 的逐包解析逻辑，提取灰度值并映射到对应帧的像素坐标。
        
        参数:
        - packets       : 数据包列表，每个元素是一个字节数组，包含相应的相位、灰度等信息。
        - SampleRate    : 采样率 (Hz)，用于计算相位随时间变化的步进。
        - Freqx, Freqy  : X 方向和 Y 方向的扫描频率。
        - deltaphasex,
          deltaphasey   : 相位偏移（°），在计算时会加到从数据包读出的相位上。
        
        返回:
        - final_image   : 处理后得到的最终图像 (512 x 512)。
        - phasex_deg    : X 方向相位（度）。
        - phasey_deg    : Y 方向相位（度）。
        """

        # ---------------------
        # 第 1 步：基本参数设置
        # ---------------------
        NumFrame = int(1e6)         # 每帧的采样点数
        ImageSize = 512             # 图像大小为 512 x 512
        Delta_t = 1.0 / SampleRate  # 每个采样点之间的时间间隔

        X_Amp = ImageSize / 2.0     # X 方向扫描振幅
        Y_Amp = ImageSize / 2.0     # Y 方向扫描振幅

        # X_Freq、Y_Freq 表示：在每个采样点 i 的相位步进
        X_Freq = math.pi * Delta_t * 2 * Freqx  # 等价于 2π(SampleRate^-1)*Freqx
        Y_Freq = math.pi * Delta_t * 2 * Freqy

        # 使用更高效的数据类型
        PixelData = np.zeros((ImageSize, ImageSize), dtype=np.int32)

        # ---------------------
        # 第 2 步：解析第一个数据包，获取初相信息 (phasex, phasey)
        # ---------------------
        first_packet = packets[0]

        phase_x_raw = (
            (first_packet[6] << 24)
            + (first_packet[7] << 16)
            + (first_packet[8] << 8)
            + first_packet[9]
        )
        phase_y_raw = (
            (first_packet[10] << 24)
            + (first_packet[11] << 16)
            + (first_packet[12] << 8)
            + first_packet[13]
        )

        
        print("原始x相位:",phase_x_raw * 360.0 / 33554432.0)
        print("原始y相位:",phase_y_raw * 360.0 / 33554432.0)

        phasex_compensation = map_delta_phase((phase_x_raw * 360.0 / 33554432.0)% 360.0)
        phasey_compensation = map_delta_phasey((phase_y_raw * 360.0 / 33554432.0)% 360.0)
        # phasex_compensation = 0
        # phasey_compensation = 0

        phasex_deg = ((phase_x_raw * 360.0 / 33554432.0) + phasex_compensation + deltaphasex) % 360.0
        phasey_deg = ((phase_y_raw * 360.0 / 33554432.0) + phasey_compensation + deltaphasey) % 360.0
        # phasex_deg = 0
        # phasey_deg = 0

        
        # 四舍五入到 1 位小数，再转为弧度
        # 直接转换为弧度，不进行舍入
        phasex = math.radians(phasex_deg)
        phasey = math.radians(phasey_deg)
        # phasex = math.radians(round(phasex_deg * 1000) / 1000)
        # phasey = math.radians(round(phasey_deg * 1000) / 1000)

        # ---------------------
        # 第 3 步：使用向量化方法计算 X, Y 坐标
        # ---------------------
        i_arr = np.arange(NumFrame, dtype=np.float64)  # [0, 1, 2, ..., 999999]

        

        # 计算扫描轨迹：X_vals, Y_vals
        X_vals = X_Amp  * np.sin(X_Freq * i_arr + phasex ) + 256.0
        # print("X_vals[0]:",X_vals[0],"xflip:",xflip,"phasex:",phasex,"without xflip:",X_Amp * np.sin(X_Freq * i_arr + phasex) + 256.0)
        
        Y_vals = Y_Amp  * np.sin(Y_Freq * i_arr + phasey ) + 256.0
        # print("Y_vals[0]:",Y_vals[0],"yflip:",yflip,"phasey:",phasey,"without yflip:",Y_Amp * np.sin(Y_Freq * i_arr + phasey) + 256.0)
        # 对结果取 floor 并限制在 [0, ImageSize - 1] 范围内
        X_vals = np.floor(X_vals).astype(np.int32)
        Y_vals = np.floor(Y_vals).astype(np.int32)

        np.clip(X_vals, 0, ImageSize - 1, out=X_vals)
        np.clip(Y_vals, 0, ImageSize - 1, out=Y_vals)

      

        # ---------------------
        # 第 4 步：计算像素访问次数 PixelTimes
        # ---------------------
        # 将 (x, y) 转换为线性索引： index = x * ImageSize + y
        XY_linear_indices = X_vals * ImageSize + Y_vals

        # 统计每个索引出现了多少次，从而得到像素被访问的次数
        PixelTimes_flat = np.bincount(
            XY_linear_indices,
            minlength=ImageSize * ImageSize
        )
        PixelTimes = PixelTimes_flat.reshape((ImageSize, ImageSize))

        # 同时准备一个一维的灰度累加缓存，用于后续一次性累加
        PixelDataFlat = np.zeros(ImageSize * ImageSize, dtype=np.int32)

        # 一帧对应的数据量 = NumFrame * 2（与原逻辑相同）
        TotalNumEachFrame = NumFrame * 2

        # ---------------------
        # 第 5 步：解析第一个数据包中的灰度值
        # ---------------------
        packageNum = (first_packet[4] << 8) + first_packet[5]

        i = 14   # 跳过前 14 个字节（相位数据等）
        flag = 14

        # 使用预分配的数组而不是列表来存储像素索引和灰度值
        max_expected_values = 2000000  # 根据实际情况调整
        pixel_indices_arr = np.zeros(max_expected_values, dtype=np.int32)
        gray_values_arr = np.zeros(max_expected_values, dtype=np.int32)
        value_count = 0

        # 然后在循环中直接赋值而不是append
        while i < packageNum + 6 and (i + 1) < len(first_packet):
            val = (first_packet[i] << 8) + first_packet[i + 1]
            gray = val

            # 计算该灰度属于哪一个帧采样点
            pixel_index = int(NumFrame - (TotalNumEachFrame - i + flag) / 2)
            if 0 <= pixel_index < NumFrame:
                if value_count < max_expected_values:
                    pixel_indices_arr[value_count] = pixel_index
                    gray_values_arr[value_count] = gray
                    value_count += 1

            i += 2

        # 修正包大小
        packageNum -= 8
        TotalNumEachFrame -= packageNum

        # ---------------------
        # 第 6 步：解析后续数据包
        # ---------------------
        for pkt in packets[1:]:
            packageNum = (pkt[4] << 8) + pkt[5]
            i = 6
            flag = 6

            while i < packageNum + 6 and (i + 1) < len(pkt):
                val = (pkt[i] << 8) + pkt[i + 1]
                gray = val

                pixel_index = int(NumFrame - (TotalNumEachFrame - i + flag) / 2)
                if 0 <= pixel_index < NumFrame:
                    if value_count < max_expected_values:
                        pixel_indices_arr[value_count] = pixel_index
                        gray_values_arr[value_count] = gray
                        value_count += 1

                i += 2

            # 如果需要，和原始逻辑一样做一次修正
            if flag == 14:
                packageNum -= 8

            TotalNumEachFrame -= packageNum
            if TotalNumEachFrame < 5:
                break  # 数据已读取完成或余量很小

        # ---------------------
        # 第 7 步：累加灰度值
        # ---------------------
        if value_count > 0:
            # 根据 pixel_index 找到对应的像素线性索引
            final_pixel_linear_indices = XY_linear_indices[pixel_indices_arr[:value_count]]

            # 使用 bincount 一次性完成灰度值的累加，并确保输出类型为 int32
            accum = np.bincount(
                final_pixel_linear_indices,
                weights=gray_values_arr[:value_count],
                minlength=ImageSize * ImageSize
            ).astype(np.int32)  # 显式转换为 int32 类型

            # 现在 accum 和 PixelDataFlat 都是 int32 类型，可以安全地相加
            PixelDataFlat += accum

        # 将一维数组重塑回二维
        PixelData = PixelDataFlat.reshape((ImageSize, ImageSize))

        # ---------------------
        # 第 8 步：计算最终图像
        # ---------------------
        with np.errstate(divide='ignore', invalid='ignore'):
            final_image = PixelData / PixelTimes
            final_image[~np.isfinite(final_image)] = np.nan  # 将无效值、Inf、NaN 设为 NaN

        # 使用 Numba 插值函数对 NaN 值进行插值
        nan_mask = np.isnan(final_image)
        final_image = _interpolate_columns_numba(final_image, nan_mask)

        # 将剩余的 NaN 填充为 0（例如整列都是 NaN 的情况）
        final_image = np.nan_to_num(final_image, nan=0.0)

        return final_image, phasex_deg, phasey_deg


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("相位扫描v1")
        self.setGeometry(100, 100, 1200, 900)

        # 主布局
        main_layout = QVBoxLayout()

        # 图像显示
        self.image_label = QLabel("图像将在此显示")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")  # 设置背景色以更好显示图像
        main_layout.addWidget(self.image_label, stretch=1)

        # 相位信息
        self.phase_info = QLabel("Delta Phase X: 0° | Delta Phase Y: 0°\nPhasex: 0.00° | Phasey: 0.00°")
        main_layout.addWidget(self.phase_info)

        # 进度条
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        # 功能区布局
        functional_layout = QHBoxLayout()

        # 自动控制区
        auto_control_group = QGroupBox("自动控制区")
        auto_layout = QGridLayout()

        # X方向控制组
        x_control_group = QGroupBox("X相位控制")
        x_layout = QVBoxLayout()
        
        # X方向启动按钮
        self.start_x_button = QPushButton("启动X扫描")
        self.start_x_button.clicked.connect(self.start_x_scan)
        x_layout.addWidget(self.start_x_button)
        
        # X方向步进按钮
        self.step_x_button = QPushButton("X步进")
        self.step_x_button.clicked.connect(self.step_x_phase)
        x_layout.addWidget(self.step_x_button)
        
        # X方向暂停按钮
        self.pause_x_button = QPushButton("暂停X")
        self.pause_x_button.clicked.connect(self.pause_x_scan)
        self.pause_x_button.setEnabled(False)
        x_layout.addWidget(self.pause_x_button)
        
        x_control_group.setLayout(x_layout)

        # Y方向控制组
        y_control_group = QGroupBox("Y相位控制")
        y_layout = QVBoxLayout()
        
        # Y方向启动按钮
        self.start_y_button = QPushButton("启动Y扫描")
        self.start_y_button.clicked.connect(self.start_y_scan)
        y_layout.addWidget(self.start_y_button)
        
        # Y方向步进按钮
        self.step_y_button = QPushButton("Y步进")
        self.step_y_button.clicked.connect(self.step_y_phase)
        y_layout.addWidget(self.step_y_button)
        
        # Y方向暂停按钮
        self.pause_y_button = QPushButton("暂停Y")
        self.pause_y_button.clicked.connect(self.pause_y_scan)
        self.pause_y_button.setEnabled(False)
        y_layout.addWidget(self.pause_y_button)
        
        y_control_group.setLayout(y_layout)

        # 停止按钮
        self.stop_button = QPushButton("停止扫描")
        self.stop_button.clicked.connect(self.stop_scanning)
        self.stop_button.setEnabled(False)

        # 添加到自动控制区布局
        auto_layout.addWidget(x_control_group, 0, 0)
        auto_layout.addWidget(y_control_group, 0, 1)
        auto_layout.addWidget(self.stop_button, 1, 0, 1, 2)
        auto_control_group.setLayout(auto_layout)
        functional_layout.addWidget(auto_control_group)

        # 手动控制区
        manual_control_group = QGroupBox("手动控制区")
        manual_layout = QGridLayout()

        # Delta Phase X
        manual_layout.addWidget(QLabel("Delta Phase X (°):"), 0, 0)
        self.delta_phase_x_spin = QDoubleSpinBox()
        self.delta_phase_x_spin.setRange(-360.0, 360.0)  # 修改范围为 -360 到 360
        self.delta_phase_x_spin.setDecimals(1)
        self.delta_phase_x_spin.setSingleStep(0.1)
        self.delta_phase_x_spin.setValue(0.0)
        manual_layout.addWidget(self.delta_phase_x_spin, 0, 1)

        # Delta Phase Y
        manual_layout.addWidget(QLabel("Delta Phase Y (°):"), 1, 0)
        self.delta_phase_y_spin = QDoubleSpinBox()
        self.delta_phase_y_spin.setRange(-360.0, 360.0)  # 修改范围为 -360 到 360
        self.delta_phase_y_spin.setDecimals(1)
        self.delta_phase_y_spin.setSingleStep(0.1)
        self.delta_phase_y_spin.setValue(0.0)
        manual_layout.addWidget(self.delta_phase_y_spin, 1, 1)

        # 连接值变化信号到自动更新函数
        self.delta_phase_x_spin.valueChanged.connect(self.auto_update_manual_phase)
        self.delta_phase_y_spin.valueChanged.connect(self.auto_update_manual_phase)

        manual_control_group.setLayout(manual_layout)
        functional_layout.addWidget(manual_control_group)

        # 数据和参数控制区
        data_control_group = QGroupBox("数据和参数")
        data_layout = QGridLayout()

        data_layout.addWidget(QLabel("Bin文件路径:"), 0, 0)
        self.bin_path_edit = QLineEdit('D:\\code\\Lissajous_scan_git\\Lissajous_sacn\\beads_11380_3790')
        data_layout.addWidget(self.bin_path_edit, 0, 1, 1, 2)
        
        self.load_bin_button = QPushButton("加载文件")
        self.load_bin_button.clicked.connect(self.load_bin_files)
        data_layout.addWidget(self.load_bin_button, 0, 3)

        data_layout.addWidget(QLabel("频率 X (Hz):"), 1, 0)
        self.freq_x_spin = QDoubleSpinBox()
        self.freq_x_spin.setRange(1, 100000)
        self.freq_x_spin.setValue(11380)
        self.freq_x_spin.setDecimals(0)
        self.freq_x_spin.editingFinished.connect(self.auto_update_manual_phase)
        data_layout.addWidget(self.freq_x_spin, 1, 1)

        data_layout.addWidget(QLabel("频率 Y (Hz):"), 1, 2)
        self.freq_y_spin = QDoubleSpinBox()
        self.freq_y_spin.setRange(1, 100000)
        self.freq_y_spin.setValue(3790)
        self.freq_y_spin.setDecimals(0)
        self.freq_y_spin.editingFinished.connect(self.auto_update_manual_phase)
        data_layout.addWidget(self.freq_y_spin, 1, 3)

        data_control_group.setLayout(data_layout)
        main_layout.addWidget(data_control_group)

        # 在功能区布局之前添加图像调整控制区
        image_control_group = QGroupBox("图像调整")
        image_control_layout = QGridLayout()

        # 最小值滑动条
        image_control_layout.addWidget(QLabel("最小值:"), 0, 0)
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(0, 65535)
        self.min_slider.setValue(0)
        self.min_slider.valueChanged.connect(self.update_display)
        image_control_layout.addWidget(self.min_slider, 0, 1)
        self.min_value_label = QLabel("0")
        image_control_layout.addWidget(self.min_value_label, 0, 2)

        # 最大值滑动条
        image_control_layout.addWidget(QLabel("最大值:"), 1, 0)
        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setRange(0, 65535)
        self.max_slider.setValue(65535)
        self.max_slider.valueChanged.connect(self.update_display)
        image_control_layout.addWidget(self.max_slider, 1, 1)
        self.max_value_label = QLabel("65535")
        image_control_layout.addWidget(self.max_value_label, 1, 2)

        # 对比度滑动条
        image_control_layout.addWidget(QLabel("对比度:"), 2, 0)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.update_display)
        image_control_layout.addWidget(self.contrast_slider, 2, 1)
        self.contrast_value_label = QLabel("100%")
        image_control_layout.addWidget(self.contrast_value_label, 2, 2)

        # 亮度滑动条
        image_control_layout.addWidget(QLabel("亮度:"), 3, 0)
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.update_display)
        image_control_layout.addWidget(self.brightness_slider, 3, 1)
        self.brightness_value_label = QLabel("0%")
        image_control_layout.addWidget(self.brightness_value_label, 3, 2)

        # 自动调整按钮
        self.auto_adjust_button = QPushButton("自动调整")
        self.auto_adjust_button.clicked.connect(self.auto_adjust_image)
        image_control_layout.addWidget(self.auto_adjust_button, 4, 0, 1, 3)

        image_control_group.setLayout(image_control_layout)
        main_layout.addWidget(image_control_group)

        # 在功能区布局中添加帧切换控制组
        frame_control_group = QGroupBox("帧控制")
        frame_layout = QHBoxLayout()

        self.prev_frame_button = QPushButton("上一帧")
        self.prev_frame_button.clicked.connect(self.load_prev_frame)
        frame_layout.addWidget(self.prev_frame_button)

        self.frame_label = QLabel("当前帧: 0")
        frame_layout.addWidget(self.frame_label)

        self.next_frame_button = QPushButton("下一帧")
        self.next_frame_button.clicked.connect(self.load_next_frame)
        frame_layout.addWidget(self.next_frame_button)

        frame_control_group.setLayout(frame_layout)
        functional_layout.addWidget(frame_control_group)

        # 存储当前图像
        self.current_image = None

        main_layout.addLayout(functional_layout)

        # 设置主窗口的中央部件
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # 初始化变量
        self.worker = None
        self.packets = []
        self.manual_threads = []  # 保持对ManualProcessor线程的引用
        self.load_packets()

        # 修改手动控制区的相位输入控件连接
        self.delta_phase_x_spin.valueChanged.connect(self.auto_update_manual_phase)
        self.delta_phase_y_spin.valueChanged.connect(self.auto_update_manual_phase)

        # Ensure the imgs directory exists
        self.imgs_dir = './imgsFOV'
        if not os.path.exists(self.imgs_dir):
            os.makedirs(self.imgs_dir)

    def load_packets(self):
        """
        初始化时加载bin文件
        """
        self.load_bin_files()

    def load_bin_files(self):
        """
        加载文件夹中的所有bin文件
        """
        BIN_FOLDER_PATH = self.bin_path_edit.text()
        self.bin_files = sorted(glob.glob(os.path.join(BIN_FOLDER_PATH, 'frame_*.bin')))
        
        if not self.bin_files:
            self.image_label.setText("未找到bin文件")
            return
            
        # 加载第一帧
        self.current_frame_index = 0
        self.load_current_frame()
        self.update_frame_controls()

    def load_current_frame(self):
        """
        加载当前帧的bin文件并自动触发处理
        """
        if 0 <= self.current_frame_index < len(self.bin_files):
            current_file = self.bin_files[self.current_frame_index]
            # print(f"正在加载文件: {current_file}")
            
            try:
                with open(current_file, 'rb') as f:
                    data = f.read()

                packet_size = 1406
                num_packets = len(data) // packet_size
                self.packets = [data[i * packet_size:(i + 1) * packet_size] for i in range(num_packets)]
                # print(f"成功加载 {num_packets} 个数据包")

                # 更新帧标签
                frame_number = os.path.basename(current_file).replace('frame_', '').replace('.bin', '')
                self.frame_label.setText(f"当前帧: {frame_number}")

                # 如果正在进行处理，停止它
                if self.worker and self.worker.isRunning():
                    self.worker.stop()
                    self.worker = None
                    
                    # 更新按钮状态
                    self.start_x_button.setEnabled(True)
                    self.start_y_button.setEnabled(True)
                    self.pause_x_button.setEnabled(False)
                    self.pause_y_button.setEnabled(False)
                    self.stop_button.setEnabled(False)
                    self.pause_x_button.setText("暂停X")
                    self.pause_y_button.setText("暂停Y")

                # 清除当前显示的图像
                self.current_image = None
                self.image_label.clear()

                # 自动触发手动相位处理
                self.auto_update_manual_phase()
                
            except Exception as e:
                print(f"加载文件时出错: {str(e)}")
                self.image_label.setText(f"加载文件时出错: {str(e)}")

    def update_frame_controls(self):
        """
        更新帧控制按钮的状态
        """
        self.prev_frame_button.setEnabled(self.current_frame_index > 0)
        self.next_frame_button.setEnabled(self.current_frame_index < len(self.bin_files) - 1)

    def load_prev_frame(self):
        """
        加载前一帧
        """
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            self.load_current_frame()
            self.update_frame_controls()

    def load_next_frame(self):
        """
        加载后一帧
        """
        if self.current_frame_index < len(self.bin_files) - 1:
            self.current_frame_index += 1
            self.load_current_frame()
            self.update_frame_controls()

    def start_processing(self):
        """
        初始化处理线程
        """
        if not self.packets:
            print("没有可处理的数据包")
            self.image_label.setText("没有可处理的数据包。")
            return

        print(f"开始处理，数据包数量: {len(self.packets)}")

        # 基本参数设置
        freqx = self.freq_x_spin.value()
        freqy = self.freq_y_spin.value()
        SampleRate = 1e7
        
        # 相位扫描范围设置
        delta_phase_step = 0.1  # 步进值为0.1度
        
        # 修改相位范围：-360到+360度
        delta_phase_x_range = np.arange(-360.0, 360.0, delta_phase_step).tolist()
        delta_phase_y_range = np.arange(-360.0, 360.0, delta_phase_step).tolist()

        self.worker = AutoImageProcessor(
            packets=self.packets,
            SampleRate=SampleRate,
            Freqx=freqx,
            Freqy=freqy,
            delta_phase_x_range=delta_phase_x_range,
            delta_phase_y_range=delta_phase_y_range,
            parent=self,
        )
        
        self.worker.image_processed.connect(self.update_image)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.processing_finished)
        
        # 初始状态为暂停
        self.worker._is_paused_x = True
        self.worker._is_paused_y = True
        
        # 更新按钮状态
        self.start_x_button.setEnabled(True)
        self.start_y_button.setEnabled(True)
        self.pause_x_button.setEnabled(False)
        self.pause_y_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        self.worker.start()
        print("处理线程已启动")

    def pause_processing(self):
        """
        Toggle pause and resume for the worker thread.
        """
        if self.worker is None:
            return

        if not self.worker._is_paused_x and not self.worker._is_paused_y:
            self.worker.pause()
            self.pause_button.setText("恢复")
        else:
            self.worker.resume()
            self.pause_button.setText("暂停")

    def stop_processing(self):
        """
        停止处理
        """
        if self.worker:
            self.worker.stop()
            self.worker = None
            
        # 更新按钮状态为初始状态
        self.start_x_button.setEnabled(True)
        self.start_y_button.setEnabled(True)
        self.pause_x_button.setEnabled(False)
        self.pause_y_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_x_button.setText("暂停X")
        self.pause_y_button.setText("暂停Y")

    def auto_update_manual_phase(self):
        """
        自动触发手动相位处理
        """
        if not self.packets:  # 确保有数据可处理
            return

        # 获取当前的相位值
        delta_phase_x = self.delta_phase_x_spin.value()
        delta_phase_y = self.delta_phase_y_spin.value()

        # 获取频率参数
        freqx = self.freq_x_spin.value()
        freqy = self.freq_y_spin.value()
        SampleRate = 1e7

        # 初始化并启动手动处理线程
        manual_processor = ManualProcessor(
            packets=self.packets,
            SampleRate=SampleRate,
            Freqx=freqx,
            Freqy=freqy,
            delta_phase_x=delta_phase_x,
            delta_phase_y=delta_phase_y,
            parent=self,
        )
        manual_processor.image_processed.connect(self.update_image)

        # 保持对手动处理线程的引用
        self.manual_threads.append(manual_processor)
        manual_processor.finished.connect(lambda: self.cleanup_manual_thread(manual_processor))

        manual_processor.start()

    def cleanup_manual_thread(self, thread):
        """
        Cleanup the ManualProcessor thread after it finishes.
        """
        if thread in self.manual_threads:
            self.manual_threads.remove(thread)
        thread.deleteLater()

    def processing_finished(self):
        """
        处理完成时的操作
        """
        # 更新所有按钮状态
        self.start_x_button.setEnabled(True)
        self.start_y_button.setEnabled(True)
        self.pause_x_button.setEnabled(False)
        self.pause_y_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_x_button.setText("暂停X")
        self.pause_y_button.setText("暂停Y")
        self.progress_bar.setValue(100)

    def update_progress(self, value):
        """
        Update the progress bar.
        """
        self.progress_bar.setValue(value)

    def update_display(self):
        """
        根据滑动条值更新图像显示
        """
        if self.current_image is None:
            return

        # 更新标签显示
        self.min_value_label.setText(str(self.min_slider.value()))
        self.max_value_label.setText(str(self.max_slider.value()))
        self.contrast_value_label.setText(f"{self.contrast_slider.value()}%")
        self.brightness_value_label.setText(f"{self.brightness_slider.value()}%")

        # 调整图像
        adjusted = adjust_image(
            self.current_image,
            self.min_slider.value(),
            self.max_slider.value(),
            self.contrast_slider.value(),
            self.brightness_slider.value()
        )

        # 转换为QImage显示
        height, width = adjusted.shape
        bytes_per_line = width * 2  # 16位图像每个像素2字节
        q_image = QImage(adjusted.data, width, height, bytes_per_line, QImage.Format_Grayscale16)
        pixmap = QPixmap.fromImage(q_image).scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.KeepAspectRatio,
        )
        self.image_label.setPixmap(pixmap)

    def auto_adjust_image(self):
        """
        自动调整图像显示参数
        """
        if self.current_image is None:
            return

        # 计算有效像素的最小值和最大值（忽略0值）
        valid_pixels = self.current_image[self.current_image > 0]
        if len(valid_pixels) > 0:
            min_val = np.percentile(valid_pixels, 1)  # 使用1%分位数作为最小值
            max_val = np.percentile(valid_pixels, 99)  # 使用99%分位数作为最大值
            
            # 更新滑动条值
            self.min_slider.setValue(int(min_val))
            self.max_slider.setValue(int(max_val))
            self.contrast_slider.setValue(100)
            self.brightness_slider.setValue(0)

    def update_image(self, final_image, delta_phase_x, delta_phase_y, phasex_deg, phasey_deg):
        """
        更新显示的图像和相位信息
        """
        # 存储当前图像
        self.current_image = final_image

        # Save the image to the imgs directory
        self.save_current_image()

        # 更新显示
        self.update_display()

        # 更新相位信息
        self.phase_info.setText(
            f"Delta Phase X: {delta_phase_x:.1f}° | Delta Phase Y: {delta_phase_y:.1f}°\n"
            f"Phasex: {phasex_deg:.2f}° | Phasey: {phasey_deg:.2f}°"
        )

    def save_current_image(self):
        """
        Save the current final_image to the imgs directory with the bin file name.
        """
        if self.current_image is None:
            print("没有图像可保存")
            return

        # Get the current bin file name
        current_file = self.bin_files[self.current_frame_index]
        file_name = os.path.basename(current_file).replace('.bin', '.png')
        save_path = os.path.join(self.imgs_dir, file_name)

        # Ensure the image is in the correct format
        if self.current_image.dtype != np.uint16:
            print("图像数据类型不正确，转换为uint16")
            self.current_image = self.current_image.astype(np.uint16)

        # Convert the image to a format suitable for saving
        height, width = self.current_image.shape
        bytes_per_line = width * 2  # 16-bit image, 2 bytes per pixel
        q_image = QImage(self.current_image.data, width, height, bytes_per_line, QImage.Format_Grayscale16)

        # Save the image
        if q_image.save(save_path):
            print(f"图像已保存到 {save_path}")
        else:
            print("图像保存失败")

    def closeEvent(self, event):
        """
        Handle the window close event to ensure all threads are properly terminated.
        """
        if self.worker:
            self.worker.stop()
            self.worker.wait()

        for thread in self.manual_threads[:]:  # Iterate over a copy of the list
            if thread.isRunning():
                thread.quit()
                thread.wait()
            self.manual_threads.remove(thread)

        event.accept()

    def start_x_scan(self):
        """启动X方向扫描"""
        if not hasattr(self, 'worker') or self.worker is None:
            self.start_processing()
        self.worker._is_paused_x = False
        self.start_x_button.setEnabled(False)
        self.pause_x_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def start_y_scan(self):
        """启动Y方向扫描"""
        if not hasattr(self, 'worker') or self.worker is None:
            self.start_processing()
        self.worker._is_paused_y = False
        self.start_y_button.setEnabled(False)
        self.pause_y_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def pause_x_scan(self):
        """暂停/恢复X方向扫描"""
        if self.worker:
            if not self.worker._is_paused_x:
                self.worker._is_paused_x = True
                self.pause_x_button.setText("恢复X")
                self.start_x_button.setEnabled(True)
            else:
                self.worker._is_paused_x = False
                self.pause_x_button.setText("暂停X")
                self.start_x_button.setEnabled(False)

    def pause_y_scan(self):
        """暂停/恢复Y方向扫描"""
        if self.worker:
            if not self.worker._is_paused_y:
                self.worker._is_paused_y = True
                self.pause_y_button.setText("恢复Y")
                self.start_y_button.setEnabled(True)
            else:
                self.worker._is_paused_y = False
                self.pause_y_button.setText("暂停Y")
                self.start_y_button.setEnabled(False)

    def step_x_phase(self):
        """X相位单步进"""
        if self.worker and self.worker._is_paused_x:
            self.worker.current_x_index = (self.worker.current_x_index + 1) % len(self.worker.delta_phase_x_range)
            self.worker.manual_phase_x = self.worker.delta_phase_x_range[self.worker.current_x_index]
            self.worker.manual_request = True

    def step_y_phase(self):
        """Y相位单步进"""
        if self.worker and self.worker._is_paused_y:
            self.worker.current_y_index = (self.worker.current_y_index + 1) % len(self.worker.delta_phase_y_range)
            self.worker.manual_phase_y = self.worker.delta_phase_y_range[self.worker.current_y_index]
            self.worker.manual_request = True

    def stop_scanning(self):
        """停止所有扫描"""
        if self.worker:
            self.worker.stop()
            self.worker = None
            
        # 重置按钮状态
        self.start_x_button.setEnabled(True)
        self.start_y_button.setEnabled(True)
        self.pause_x_button.setEnabled(False)
        self.pause_y_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_x_button.setText("暂停X")
        self.pause_y_button.setText("暂停Y")




# 添加全局变量来跟踪相位变化
_previous_x_phase = None
_previous_y_phase = None
_x_phase_increasing_flag = False
_y_phase_increasing_flag = False

# def map_delta_phase(original_phase):
#     """
#     将原始相位映射到补偿相位 - X方向
    
#     参数:
#     original_phase: 原始相位值 (0-360度)
    
#     返回:
#     mapped_phase: 补偿相位值 (6 或 186)
#     """
#     global _previous_x_phase, _x_phase_increasing_flag
    
#     # 确保输入相位在0-360度范围内
#     original_phase = original_phase % 360
    
#     # 如果是第一次调用，初始化
#     if _previous_x_phase is None:
#         _previous_x_phase = original_phase
#         return 6  # 默认返回6
    
#     # 检测相位变化趋势
#     current_trend_increasing = original_phase > _previous_x_phase
    
#     # 只有当趋势发生变化时才切换flag
#     if current_trend_increasing :
#         _x_phase_increasing_flag = not _x_phase_increasing_flag

    
#     # 根据当前的flag选择补偿值
#     compensation = 186 if _x_phase_increasing_flag else 6
    
#     # 更新前一次的相位值
#     _previous_x_phase = original_phase
    
#     # 调试输出
#     trend = "上升" if current_trend_increasing else "下降"
#     print(f"X相位: {original_phase:.1f}° -> 趋势={trend} -> flag={_x_phase_increasing_flag} -> 补偿={compensation}")
    
#     return 6
#     return compensation

def map_delta_phase(original_phase):
    """
    将原始相位映射到补偿相位 - X方向
    
    参数:
    original_phase: 原始相位值 (0-360度)
    
    返回:
    mapped_phase: 补偿相位值 (6 或 186)
    """
    global _previous_x_phase, _x_phase_increasing_flag
    
    # 确保输入相位在0-360度范围内
    original_phase = original_phase % 360
    
    # 如果是第一次调用，初始化
    if _previous_x_phase is None:
        _previous_x_phase = original_phase
        _x_phase_increasing_flag = False  # 初始补偿为6
        return 16  # 默认返回6
    
    # 检测相位变化趋势
    current_trend_increasing = original_phase < _previous_x_phase
    
    # 只有当出现下降趋势时才切换补偿值
    if not current_trend_increasing:  # 下降趋势
        _x_phase_increasing_flag = not _x_phase_increasing_flag
    # 上升趋势时，保持当前的flag不变
    
    # 根据当前的flag选择补偿值
    compensation = 16 if _x_phase_increasing_flag else 186
    
    # 更新前一次的相位值
    _previous_x_phase = original_phase
    
    # 调试输出
    trend = "上升" if current_trend_increasing else "下降"
    action = "切换补偿" if not current_trend_increasing else "保持补偿"
    print(f"X相位: {original_phase:.1f}° -> 趋势={trend} -> {action} -> flag={_x_phase_increasing_flag} -> 补偿={compensation}")
    
    return compensation

def map_delta_phasey(original_phase):
    """
    将原始相位映射到补偿相位 - Y方向
    
    参数:
    original_phase: 原始相位值 (0-360度)
    
    返回:
    mapped_phase: 补偿相位值 (35 或 215)
    """
    global _previous_y_phase, _y_phase_increasing_flag
    
    # 确保输入相位在0-360度范围内
    original_phase = original_phase % 360
    
    # 如果是第一次调用，初始化
    if _previous_y_phase is None:
        _previous_y_phase = original_phase
        return 35  # 默认返回35
    
    # 检测相位变化趋势
    current_trend_increasing = original_phase < _previous_y_phase
    
    # 只有当趋势发生变化时才切换flag
    if current_trend_increasing :
        _y_phase_increasing_flag = not _y_phase_increasing_flag
   
    # 根据当前的flag选择补偿值
    compensation = 35 if _y_phase_increasing_flag else 215
    
    # 更新前一次的相位值
    _previous_y_phase = original_phase
    
    # 调试输出
    trend = "上升" if current_trend_increasing else "下降"
    print(f"Y相位: {original_phase:.1f}° -> 趋势={trend} -> flag={_y_phase_increasing_flag} -> 补偿={compensation}")
    
    return compensation


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
