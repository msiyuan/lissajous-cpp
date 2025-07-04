"""
Numba优化函数模块
包含使用Numba加速的数值计算函数
"""

import numba
import numpy as np

@numba.njit(cache=True)
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

def warm_up_interpolation_function():
    """
    预编译插值函数，避免首次运行时的JIT编译延迟
    
    Returns:
        float: 编译耗时（秒）
    """
    import time
    
    start_time = time.time()
    
    # 创建测试数据
    dummy_image_size = 512
    dummy_image = np.random.rand(dummy_image_size, dummy_image_size).astype(np.float32)
    
    # 确保图像中有NaN值以触发插值逻辑
    dummy_image[0:100, 0:100] = np.nan
    dummy_nan_mask = np.isnan(dummy_image)
    
    # 调用函数触发编译
    _interpolate_columns_numba(dummy_image, dummy_nan_mask)
    
    end_time = time.time()
    return end_time - start_time