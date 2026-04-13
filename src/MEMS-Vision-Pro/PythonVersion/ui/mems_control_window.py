"""
MEMS控制独立窗口
提供MEMS使能和启动的单独控制
"""

import sys
import os

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir))

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from network.udp_sender import UDPSender
from network.protocol_commands import build_register_command
from config.default_params import REGISTER_ADDRESSES, REGISTER_DEFAULTS
from config.constants import DEFAULT_TARGET_IP, DEFAULT_CONTROL_PORT


class MEMSControlWindow(QMainWindow):
    """MEMS控制独立窗口"""

    def __init__(self):
        """初始化窗口"""
        super().__init__()
        self.udp_sender = UDPSender(DEFAULT_TARGET_IP, DEFAULT_CONTROL_PORT)
        self.setup_window()
        self.setup_ui()

    def setup_window(self):
        """设置窗口基本属性"""
        self.setWindowTitle("MEMS控制面板")
        self.setMinimumSize(300, 150)
        self.resize(350, 180)

    def setup_ui(self):
        """设置界面布局"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("MEMS 控制")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 控制按钮区域
        control_group = self.create_control_section()
        main_layout.addWidget(control_group)

        # 状态显示
        self.status_label = QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        central_widget.setLayout(main_layout)

    def create_control_section(self):
        """创建控制按钮区域"""
        group = QGroupBox("控制")
        layout = QHBoxLayout()
        layout.setSpacing(20)

        # MEMS使能按钮 (mems_en - 0x114)
        self.mems_en_button = QPushButton("MEMS使能")
        self.mems_en_button.setCheckable(True)
        self.mems_en_button.setChecked(False)
        self.mems_en_button.clicked.connect(lambda checked: self.toggle_mems_en(checked))
        self.mems_en_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:checked {
                background-color: #0D47A1;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:checked:hover {
                background-color: #1565C0;
            }
        """)
        layout.addWidget(self.mems_en_button)

        # 启动按钮 (mems_start - 0x115)
        self.mems_start_button = QPushButton("启动")
        self.mems_start_button.setCheckable(True)
        self.mems_start_button.setChecked(False)
        self.mems_start_button.clicked.connect(lambda checked: self.toggle_mems_start(checked))
        self.mems_start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:checked {
                background-color: #1B5E20;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:checked:hover {
                background-color: #2E7D32;
            }
        """)
        layout.addWidget(self.mems_start_button)

        group.setLayout(layout)
        return group

    def toggle_mems_en(self, checked: bool):
        """切换MEMS使能状态"""
        value = 1 if checked else 0
        address = REGISTER_ADDRESSES.get('mems_en', 0x114)

        try:
            command = build_register_command(address, value, 1)
            success, bytes_sent = self.udp_sender.send_command(command)

            if success:
                status = "启动" if checked else "停止"
                self.status_label.setText(f"MEMS使能: {status}")
            else:
                self.status_label.setText("发送失败!")
                self.mems_en_button.setChecked(not checked)
        except Exception as e:
            self.status_label.setText(f"错误: {str(e)}")
            self.mems_en_button.setChecked(not checked)

    def toggle_mems_start(self, checked: bool):
        """切换启动状态"""
        value = 1 if checked else 0
        address = REGISTER_ADDRESSES.get('mems_start', 0x115)

        try:
            command = build_register_command(address, value, 1)
            success, bytes_sent = self.udp_sender.send_command(command)

            if success:
                status = "启动" if checked else "停止"
                self.status_label.setText(f"启动: {status}")
            else:
                self.status_label.setText("发送失败!")
                self.mems_start_button.setChecked(not checked)
        except Exception as e:
            self.status_label.setText(f"错误: {str(e)}")
            self.mems_start_button.setChecked(not checked)


def main():
    """独立运行入口"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MEMSControlWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()