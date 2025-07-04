"""
图像控制界面模块
包含图像显示控制、参数调节和图像处理设置
"""

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QLineEdit, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage

from config.constants import (
    IMAGE_LABEL_SIZE, SLIDER_MAX_RANGE, SLIDER_MIN_RANGE, 
    CONTRAST_RANGE, BRIGHTNESS_RANGE, DISPLAY_UPDATE_DELAY, LABEL_UPDATE_DELAY
)
from config.default_params import DEFAULT_IMAGE_PARAMS, DEFAULT_UI_PARAMS
from utils.image_utils import apply_image_adjustments, auto_adjust_range

class ImageControlWidget(QWidget):
    """图像显示控制界面"""
    
    # 信号定义
    display_params_changed = pyqtSignal()
    image_params_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        """
        初始化图像控制组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self.current_16bit_image = None
        self._current_params = DEFAULT_IMAGE_PARAMS.copy()
        self.setup_ui()
        self.setup_timers()
    
    def setup_ui(self):
        """设置界面布局"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)  # 设置组件间距
        
        # 参数控制区域（放在顶部）
        params_group = self.create_params_control_group()
        main_layout.addWidget(params_group)
        
        # 图像显示区域
        self.setup_image_display()
        main_layout.addWidget(self.image_label)
        
        # 图像调节控制区域
        adjust_group = self.create_image_adjustment_group()
        main_layout.addWidget(adjust_group)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        self.setLayout(main_layout)
    
    def setup_image_display(self):
        """设置图像显示区域"""
        self.image_label = QLabel("等待图像")
        self.image_label.setFixedSize(IMAGE_LABEL_SIZE, IMAGE_LABEL_SIZE)
        self.image_label.setStyleSheet("background-color: black; color: white; border: 1px solid gray;")
        self.image_label.setAlignment(Qt.AlignCenter)
    
    def create_params_control_group(self):
        """创建参数控制组"""
        group = QGroupBox("图像处理参数")
        group.setMaximumHeight(120)  # 限制组的高度
        
        layout = QGridLayout()
        layout.setSpacing(5)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边距
        
        # 第一行：X相位和Y相位
        layout.addWidget(QLabel("X相位:"), 0, 0)
        self.phase_x_input = QLineEdit(str(DEFAULT_IMAGE_PARAMS['deltaphasex']))
        self.phase_x_input.setFixedWidth(70)
        layout.addWidget(self.phase_x_input, 0, 1)
        
        layout.addWidget(QLabel("Y相位:"), 0, 2)
        self.phase_y_input = QLineEdit(str(DEFAULT_IMAGE_PARAMS['deltaphasey']))
        self.phase_y_input.setFixedWidth(70)
        layout.addWidget(self.phase_y_input, 0, 3)
        
        # 第二行：X频率和Y频率
        layout.addWidget(QLabel("X频率:"), 1, 0)
        self.freq_x_input = QLineEdit(str(DEFAULT_IMAGE_PARAMS['freqx']))
        self.freq_x_input.setFixedWidth(70)
        layout.addWidget(self.freq_x_input, 1, 1)
        
        layout.addWidget(QLabel("Y频率:"), 1, 2)
        self.freq_y_input = QLineEdit(str(DEFAULT_IMAGE_PARAMS['freqy']))
        self.freq_y_input.setFixedWidth(70)
        layout.addWidget(self.freq_y_input, 1, 3)
        
        # 第三行：应用参数按钮
        self.apply_params_button = QPushButton("应用参数")
        self.apply_params_button.clicked.connect(self.apply_parameters)
        self.apply_params_button.setMaximumHeight(30)
        layout.addWidget(self.apply_params_button, 2, 0, 1, 4)
        
        # 设置列的拉伸
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        
        group.setLayout(layout)
        return group
    
    def create_image_adjustment_group(self):
        """创建图像调节控制组"""
        group = QGroupBox("图像显示调节")
        group.setMaximumHeight(180)  # 限制组的高度
        
        layout = QVBoxLayout()
        layout.setSpacing(5)  # 减少间距
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边距
        
        # 最大值滑动条
        max_layout = QHBoxLayout()
        max_label = QLabel("最大值:")
        max_label.setFixedWidth(50)
        max_layout.addWidget(max_label)
        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setRange(SLIDER_MIN_RANGE, SLIDER_MAX_RANGE)
        self.max_slider.setValue(DEFAULT_UI_PARAMS['max_slider_value'])
        self.max_slider.valueChanged.connect(self.schedule_update)
        max_layout.addWidget(self.max_slider)
        self.max_value_label = QLabel(str(DEFAULT_UI_PARAMS['max_slider_value']))
        self.max_value_label.setFixedWidth(50)
        self.max_value_label.setAlignment(Qt.AlignCenter)
        max_layout.addWidget(self.max_value_label)
        layout.addLayout(max_layout)
        
        # 最小值滑动条
        min_layout = QHBoxLayout()
        min_label = QLabel("最小值:")
        min_label.setFixedWidth(50)
        min_layout.addWidget(min_label)
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(SLIDER_MIN_RANGE, SLIDER_MAX_RANGE)
        self.min_slider.setValue(DEFAULT_UI_PARAMS['min_slider_value'])
        self.min_slider.valueChanged.connect(self.schedule_update)
        min_layout.addWidget(self.min_slider)
        self.min_value_label = QLabel(str(DEFAULT_UI_PARAMS['min_slider_value']))
        self.min_value_label.setFixedWidth(50)
        self.min_value_label.setAlignment(Qt.AlignCenter)
        min_layout.addWidget(self.min_value_label)
        layout.addLayout(min_layout)
        
        # 对比度滑动条
        contrast_layout = QHBoxLayout()
        contrast_label = QLabel("对比度:")
        contrast_label.setFixedWidth(50)
        contrast_layout.addWidget(contrast_label)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, CONTRAST_RANGE)
        self.contrast_slider.setValue(DEFAULT_UI_PARAMS['contrast_value'])
        self.contrast_slider.valueChanged.connect(self.schedule_update)
        contrast_layout.addWidget(self.contrast_slider)
        self.contrast_value_label = QLabel("1.0")
        self.contrast_value_label.setFixedWidth(50)
        self.contrast_value_label.setAlignment(Qt.AlignCenter)
        contrast_layout.addWidget(self.contrast_value_label)
        layout.addLayout(contrast_layout)
        
        # 亮度滑动条
        brightness_layout = QHBoxLayout()
        brightness_label = QLabel("亮度:")
        brightness_label.setFixedWidth(50)
        brightness_layout.addWidget(brightness_label)
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(DEFAULT_UI_PARAMS['brightness_value'])
        self.brightness_slider.valueChanged.connect(self.schedule_update)
        brightness_layout.addWidget(self.brightness_slider)
        self.brightness_value_label = QLabel("0")
        self.brightness_value_label.setFixedWidth(50)
        self.brightness_value_label.setAlignment(Qt.AlignCenter)
        brightness_layout.addWidget(self.brightness_value_label)
        layout.addLayout(brightness_layout)
        
        # 自动调整按钮
        auto_adjust_layout = QHBoxLayout()
        self.auto_adjust_button = QPushButton("自动调整显示范围")
        self.auto_adjust_button.setMaximumHeight(30)
        self.auto_adjust_button.clicked.connect(self.auto_adjust_display_range)
        auto_adjust_layout.addWidget(self.auto_adjust_button)
        auto_adjust_layout.addStretch()
        layout.addLayout(auto_adjust_layout)
        
        group.setLayout(layout)
        return group
    
    def setup_timers(self):
        """设置定时器"""
        # 防抖动定时器
        self.display_timer = QTimer()
        self.display_timer.setSingleShot(True)
        self.display_timer.timeout.connect(self.update_image_display)
        
        # 标签更新定时器
        self.label_timer = QTimer()
        self.label_timer.setSingleShot(True)
        self.label_timer.timeout.connect(self.update_value_labels)
    
    def schedule_update(self):
        """计划更新显示"""
        # 立即更新数值标签
        self.label_timer.start(LABEL_UPDATE_DELAY)
        # 计划更新图像显示
        self.display_timer.start(DISPLAY_UPDATE_DELAY)
    
    def update_value_labels(self):
        """更新数值标签"""
        self.max_value_label.setText(str(self.max_slider.value()))
        self.min_value_label.setText(str(self.min_slider.value()))
        self.contrast_value_label.setText(f"{self.contrast_slider.value()/100:.1f}")
        self.brightness_value_label.setText(str(self.brightness_slider.value()))
    
    def update_image_display(self):
        """更新图像显示"""
        if self.current_16bit_image is None:
            return
            
        # 获取当前设置
        max_val = self.max_slider.value()
        min_val = self.min_slider.value()
        contrast = self.contrast_slider.value()
        brightness = self.brightness_slider.value()
        
        try:
            # 应用设置到图像
            img_8bit = apply_image_adjustments(
                self.current_16bit_image, min_val, max_val, contrast, brightness
            )
            
            if img_8bit is not None:
                # 显示图像
                h, w = img_8bit.shape
                qimg = QImage(img_8bit.data, w, h, w, QImage.Format_Grayscale8)
                pixmap = QPixmap.fromImage(qimg).scaled(
                    self.image_label.width(),
                    self.image_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(pixmap)
            
        except Exception as e:
            print(f"更新图像显示出错：{str(e)}")
    
    def set_image(self, image_data: np.ndarray):
        """
        设置要显示的图像
        
        Args:
            image_data: 16位图像数据
        """
        self.current_16bit_image = image_data
        self.update_image_display()
    
    def auto_adjust_display_range(self):
        """自动调整图像显示范围"""
        if self.current_16bit_image is None:
            return
            
        try:
            min_val, max_val = auto_adjust_range(self.current_16bit_image)
            
            # 设置滑动条的值
            self.min_slider.setValue(min_val)
            self.max_slider.setValue(max_val)
            
            print(f"自动调整范围：最小值={min_val}，最大值={max_val}")
            
        except Exception as e:
            print(f"自动调整显示范围出错：{str(e)}")
    
    def apply_parameters(self):
        """应用新的处理参数"""
        try:
            # 获取新的参数值
            deltaphasex = float(self.phase_x_input.text())
            deltaphasey = float(self.phase_y_input.text())
            freqx = float(self.freq_x_input.text())
            freqy = float(self.freq_y_input.text())
            
            # 更新内部参数
            self._current_params = {
                'deltaphasex': deltaphasex,
                'deltaphasey': deltaphasey,
                'freqx': freqx,
                'freqy': freqy
            }
            
            # 发射参数变化信号
            self.image_params_changed.emit(self._current_params)
            
            print(f"已更新参数：X相位={deltaphasex}°, Y相位={deltaphasey}°, X频率={freqx}, Y频率={freqy}")
                                
        except ValueError:
            print("错误：请输入有效的数字")
        except Exception as e:
            print(f"更新参数失败：{str(e)}")
    
    def get_current_params(self) -> dict:
        """
        获取当前处理参数
        
        Returns:
            dict: 当前参数字典
        """
        return self._current_params.copy()
    
    def get_display_settings(self) -> dict:
        """
        获取当前显示设置
        
        Returns:
            dict: 显示设置字典
        """
        return {
            'max_val': self.max_slider.value(),
            'min_val': self.min_slider.value(),
            'contrast': self.contrast_slider.value(),
            'brightness': self.brightness_slider.value()
        }
    
    def set_display_settings(self, settings: dict):
        """
        设置显示参数
        
        Args:
            settings: 显示设置字典
        """
        if 'max_val' in settings:
            self.max_slider.setValue(settings['max_val'])
        if 'min_val' in settings:
            self.min_slider.setValue(settings['min_val'])
        if 'contrast' in settings:
            self.contrast_slider.setValue(settings['contrast'])
        if 'brightness' in settings:
            self.brightness_slider.setValue(settings['brightness'])
    
    def reset_to_defaults(self):
        """重置为默认值"""
        # 重置处理参数
        self.phase_x_input.setText(str(DEFAULT_IMAGE_PARAMS['deltaphasex']))
        self.phase_y_input.setText(str(DEFAULT_IMAGE_PARAMS['deltaphasey']))
        self.freq_x_input.setText(str(DEFAULT_IMAGE_PARAMS['freqx']))
        self.freq_y_input.setText(str(DEFAULT_IMAGE_PARAMS['freqy']))
        
        # 重置显示参数
        self.max_slider.setValue(DEFAULT_UI_PARAMS['max_slider_value'])
        self.min_slider.setValue(DEFAULT_UI_PARAMS['min_slider_value'])
        self.contrast_slider.setValue(DEFAULT_UI_PARAMS['contrast_value'])
        self.brightness_slider.setValue(DEFAULT_UI_PARAMS['brightness_value'])
        
        # 应用参数
        self.apply_parameters()
        
        print("已重置为默认参数")
    
    def clear_image(self):
        """清空图像显示"""
        self.current_16bit_image = None
        self.image_label.clear()
        self.image_label.setText("等待图像")
    
    def save_current_image(self, filename: str = None) -> bool:
        """
        保存当前显示的图像
        
        Args:
            filename: 保存文件名
            
        Returns:
            bool: 是否成功保存
        """
        if self.current_16bit_image is None:
            print("没有图像可保存")
            return False
        
        try:
            from processing.data_saver import DataSaver
            saver = DataSaver()
            return saver.save_image_data(self.current_16bit_image, filename)
        except Exception as e:
            print(f"保存图像失败: {e}")
            return False