"""
图像处理工具模块
包含图像转换、调整和处理的通用函数
"""

import cupy as cp
import numpy as np
import cupyx.scipy.ndimage

def convert_to_8bit_cv2(final_image):
    """
    将图像归一化到0-255并转为8位
    
    Args:
        final_image: 输入图像（numpy数组或cupy数组）
        
    Returns:
        cp.ndarray: 8位图像（cupy数组）
    """
    # 使用CuPy直接处理数据，避免使用OpenCV
    # 计算图像的最大值和最小值
    if isinstance(final_image, np.ndarray):
        # 如果输入是NumPy数组，先转换为CuPy
        final_image_gpu = cp.asarray(final_image)
    else:
        final_image_gpu = final_image
    
    min_val = cp.min(final_image_gpu)
    max_val = cp.max(final_image_gpu)
    
    # 如果最大值等于最小值，避免除零错误
    if max_val == min_val:
        return cp.zeros_like(final_image_gpu, dtype=cp.uint8)
    
    # 归一化到0-255
    normalized_image = ((final_image_gpu - min_val) / (max_val - min_val) * 255.0)
    
    # 转换为8位整数
    return cp.uint8(normalized_image)

def binary_threshold_by_mode(final_image):
    """
    对最常见非零像素做阈值二值化
    
    Args:
        final_image: 输入图像
        
    Returns:
        cp.ndarray: 二值化后的图像
    """
    # 确保使用GPU处理
    if isinstance(final_image, np.ndarray):
        # 如果输入是NumPy数组，先转换为CuPy
        final_image_gpu = cp.asarray(final_image)
    else:
        final_image_gpu = final_image
    
    # 只处理非零像素
    non_zero_mask = final_image_gpu > 0
    if cp.sum(non_zero_mask) == 0:
        return cp.zeros_like(final_image_gpu, dtype=cp.uint8)
    
    # 使用直方图找到最频繁值
    non_zero_values = final_image_gpu[non_zero_mask]
    
    # 如果值的范围较大，进行离散化处理以加速计算
    if cp.max(non_zero_values) - cp.min(non_zero_values) > 1000:
        # 将值映射到1000个bin
        bins = 1000
        hist = cp.histogram(non_zero_values, bins=bins)
        bin_idx = cp.argmax(hist[0])
        bin_edges = hist[1]
        most_frequent_value = (bin_edges[bin_idx] + bin_edges[bin_idx + 1]) / 2
    else:
        # 直接计算唯一值和计数
        unique, counts = cp.unique(non_zero_values, return_counts=True)
        if len(unique) == 0:
            most_frequent_value = 0
        else:
            most_frequent_value = unique[cp.argmax(counts)]
    
    # 使用阈值创建二值图像
    binary_image = cp.where(final_image_gpu > most_frequent_value, 255, 0)
    return cp.uint8(binary_image)

def pad_image(image, target_size):
    """
    将图像填充到指定大小（保持居中）
    
    Args:
        image: 输入图像
        target_size: 目标尺寸 (height, width)
        
    Returns:
        cp.ndarray: 填充后的图像
    """
    # 确保图像是在GPU上的CuPy数组
    if isinstance(image, np.ndarray):
        image_gpu = cp.asarray(image)
    else:
        image_gpu = image
    
    # 获取原始图像尺寸
    h, w = image_gpu.shape[:2]
    
    # 计算需要填充的尺寸
    pad_top = (target_size[0] - h) // 2
    pad_bottom = target_size[0] - h - pad_top
    pad_left = (target_size[1] - w) // 2
    pad_right = target_size[1] - w - pad_left
    
    # 使用CuPy的pad函数直接在GPU上执行填充
    if len(image_gpu.shape) == 2:
        # 灰度图像
        return cp.pad(image_gpu, ((pad_top, pad_bottom), (pad_left, pad_right)), mode='constant')
    else:
        # 彩色图像
        return cp.pad(image_gpu, ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)), mode='constant')

def extract_center_region(image, target_size):
    """
    从大图像中提取中心区域
    
    Args:
        image: 输入图像
        target_size: 目标尺寸 (height, width)
        
    Returns:
        cp.ndarray: 提取的中心区域
    """
    # 确保图像是在GPU上的CuPy数组
    if isinstance(image, np.ndarray):
        image_gpu = cp.asarray(image)
    else:
        image_gpu = image
    
    # 获取原始图像尺寸
    h, w = image_gpu.shape[:2]
    
    # 计算中心区域的起始位置
    start_h = (h - target_size[0]) // 2
    start_w = (w - target_size[1]) // 2
    
    # 提取中心区域
    if len(image_gpu.shape) == 2:
        # 灰度图像
        return image_gpu[start_h:start_h+target_size[0], start_w:start_w+target_size[1]]
    else:
        # 彩色图像
        return image_gpu[start_h:start_h+target_size[0], start_w:start_w+target_size[1], :]

def resize_image(image, target_size):
    """
    调整图像大小，保持宽高比，并确保在GPU上处理
    
    Args:
        image: 输入图像
        target_size: 目标尺寸 (height, width)
        
    Returns:
        cp.ndarray: 调整大小后的图像
    """
    # 确保图像是在GPU上的CuPy数组
    if isinstance(image, np.ndarray):
        image_gpu = cp.asarray(image)
    else:
        image_gpu = image
    
    # 获取原始图像尺寸
    h, w = image_gpu.shape[:2]
    
    # 计算缩放比例
    scale = min(target_size[0] / h, target_size[1] / w)
    
    # 计算新尺寸
    new_h = int(h * scale)
    new_w = int(w * scale)
    
    # 使用cupyx.scipy.ndimage进行调整大小
    if len(image_gpu.shape) == 2:
        # 灰度图像
        resized = cupyx.scipy.ndimage.zoom(image_gpu, (new_h/h, new_w/w), order=1)
    else:
        # 彩色图像
        resized = cupyx.scipy.ndimage.zoom(image_gpu, (new_h/h, new_w/w, 1), order=1)
    
    return resized

def apply_image_adjustments(image, min_val, max_val, contrast, brightness):
    """
    应用图像调整参数（最大最小值、对比度、亮度）
    
    Args:
        image: 输入16位图像
        min_val: 最小值
        max_val: 最大值
        contrast: 对比度（百分比）
        brightness: 亮度调整值
        
    Returns:
        np.ndarray: 调整后的8位图像
    """
    try:
        # 1. 首先应用最大最小值范围
        img_adjusted = np.clip(image, min_val, max_val)
        img_adjusted = ((img_adjusted - min_val) / (max_val - min_val) * 65535).astype(np.uint16)
        
        # 2. 应用对比度
        img_adjusted = img_adjusted.astype(np.float32)
        img_adjusted = img_adjusted * (contrast / 100.0)
        
        # 3. 应用亮度
        img_adjusted = img_adjusted + (brightness * 65535 / 100)
        
        # 4. 裁剪到有效范围
        img_adjusted = np.clip(img_adjusted, 0, 65535)
        
        # 5. 转换为8位显示
        img_8bit = (img_adjusted / 65535 * 255).astype(np.uint8)
        
        return img_8bit
        
    except Exception as e:
        print(f"图像调整出错：{str(e)}")
        return None

def auto_adjust_range(image):
    """
    自动调整图像显示范围
    
    Args:
        image: 输入图像
        
    Returns:
        tuple: (min_val, max_val) 建议的最小值和最大值
    """
    try:
        # 计算图像的实际范围
        valid_pixels = image[image > 0]  # 排除0值
        if len(valid_pixels) == 0:
            return 0, 65535
            
        # 获取有效像素的最小值和最大值
        min_val = np.percentile(valid_pixels, 1)  # 使用1%分位数作为最小值
        max_val = np.percentile(valid_pixels, 99)  # 使用99%分位数作为最大值
        
        return int(min_val), int(max_val)
        
    except Exception as e:
        print(f"自动调整范围出错：{str(e)}")
        return 0, 65535