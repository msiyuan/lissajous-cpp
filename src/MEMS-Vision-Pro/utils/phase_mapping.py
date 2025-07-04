"""
相位映射模块
包含X/Y方向的相位补偿映射函数
"""

from config.constants import (
    X_PHASE_COMPENSATION_LOW, X_PHASE_COMPENSATION_HIGH,
    Y_PHASE_COMPENSATION_LOW, Y_PHASE_COMPENSATION_HIGH
)

# 全局变量来跟踪相位变化
_previous_x_phase = None
_previous_y_phase = None
_x_phase_increasing_flag = False
_y_phase_increasing_flag = False

def map_delta_phasex(original_phase):
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
        return X_PHASE_COMPENSATION_LOW  # 默认返回6
    
    # 检测相位变化趋势
    current_trend_increasing = original_phase > _previous_x_phase
    
    # 只有当出现下降趋势时才切换补偿值
    if not current_trend_increasing:  # 下降趋势
        _x_phase_increasing_flag = not _x_phase_increasing_flag
    # 上升趋势时，保持当前的flag不变
    
    # 根据当前的flag选择补偿值
    compensation = X_PHASE_COMPENSATION_HIGH if _x_phase_increasing_flag else X_PHASE_COMPENSATION_LOW
    
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
        return Y_PHASE_COMPENSATION_LOW  # 默认返回35
    
    # 检测相位变化趋势
    current_trend_increasing = original_phase > _previous_y_phase
    
    # 只有当趋势发生变化时才切换flag
    if current_trend_increasing:
        _y_phase_increasing_flag = not _y_phase_increasing_flag
   
    # 根据当前的flag选择补偿值
    compensation = Y_PHASE_COMPENSATION_HIGH if _y_phase_increasing_flag else Y_PHASE_COMPENSATION_LOW
    
    # 更新前一次的相位值
    _previous_y_phase = original_phase
    
    # 调试输出
    trend = "上升" if current_trend_increasing else "下降"
    # print(f"Y相位: {original_phase:.1f}° -> 趋势={trend} -> flag={_y_phase_increasing_flag} -> 补偿={compensation}")
    
    return compensation

def reset_phase_mapping():
    """
    重置相位映射状态
    """
    global _previous_x_phase, _previous_y_phase, _x_phase_increasing_flag, _y_phase_increasing_flag
    _previous_x_phase = None
    _previous_y_phase = None
    _x_phase_increasing_flag = False
    _y_phase_increasing_flag = False

def get_phase_mapping_status():
    """
    获取当前相位映射状态
    
    Returns:
        dict: 包含当前相位映射状态的字典
    """
    return {
        'previous_x_phase': _previous_x_phase,
        'previous_y_phase': _previous_y_phase,
        'x_phase_increasing_flag': _x_phase_increasing_flag,
        'y_phase_increasing_flag': _y_phase_increasing_flag
    }