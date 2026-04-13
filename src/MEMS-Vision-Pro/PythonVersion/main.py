#!/usr/bin/env python3
"""
UDP图像处理系统 - 模块化版本
主程序入口

本程序将原始的单体文件UDP_img_V3gpu.py重构为模块化架构，包含：
- config: 配置模块（常量和默认参数）
- utils: 工具函数模块（队列管理、图像处理、相位映射、Numba优化）
- network: 网络通信模块（UDP接收器、发送器、协议命令）
- processing: 数据处理模块（帧组装器、图像处理器、数据保存）
- ui: 用户界面模块（主窗口、协议控制、图像控制、状态显示）

模块化重构的优势：
1. 职责分离：每个模块专注于特定功能
2. 易于维护：bug修复和功能升级更容易定位
3. 代码复用：工具函数可以被多个模块使用
4. 测试友好：每个模块可以独立测试
5. 团队协作：不同开发者可以并行开发不同模块
6. 扩展性：新功能可以作为独立模块添加
"""

import sys
import os
import argparse

# 添加当前目录到Python路径，确保能够导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 在创建QApplication之前设置高DPI缩放属性
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

# 设置高DPI缩放属性（必须在创建QApplication之前）
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# 延迟导入主窗口，避免循环导入
def setup_application():
    """设置应用程序"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("UDP图像处理系统")
    app.setApplicationVersion("2.0.0 (模块化版本)")
    app.setOrganizationName("图像处理实验室")
    
    return app

def main():
    """主程序入口"""
    try:
        # 创建应用程序
        app = setup_application()

        # 延迟导入主窗口，避免在设置Qt属性之前导入
        from ui.main_window import MainWindow

        # 创建主窗口
        window = MainWindow()

        # 显示窗口
        window.show()

        # 打印启动信息
        print("=" * 60)
        print("UDP图像处理系统 - 模块化版本")
        print("=" * 60)
        print("模块架构:")
        print("  ├── config/          # 配置模块")
        print("  ├── utils/           # 工具函数模块")
        print("  ├── network/         # 网络通信模块")
        print("  ├── processing/      # 数据处理模块")
        print("  ├── ui/              # 用户界面模块")
        print("  └── main.py          # 程序入口")
        print("=" * 60)
        print("系统已启动，等待用户操作...")
        print("=" * 60)

        # 启动应用程序事件循环
        exit_code = app.exec_()

        print("系统已退出")
        return exit_code

    except ImportError as e:
        print(f"模块导入错误: {e}")
        print("请确保所有必要的依赖包已安装:")
        print("  - PyQt5")
        print("  - numpy")
        print("  - cupy")
        print("  - numba")
        print("  - opencv-python")
        return 1

    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

def check_dependencies():
    """检查依赖包"""
    required_packages = [
        'PyQt5',
        'numpy', 
        'cupy',
        'numba',
        'cv2'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("缺少以下依赖包:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请使用以下命令安装:")
        print("pip install PyQt5 numpy cupy numba opencv-python")
        return False
    
    return True

def main_mems_control():
    """独立运行MEMS控制窗口"""
    try:
        app = setup_application()

        from ui.mems_control_window import MEMSControlWindow

        window = MEMSControlWindow()
        window.show()

        print("=" * 60)
        print("MEMS控制面板已启动")
        print("=" * 60)

        exit_code = app.exec_()
        print("已退出")
        return exit_code

    except ImportError as e:
        print(f"模块导入错误: {e}")
        return 1
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

def create_requirements_file():
    """创建requirements.txt文件"""
    requirements_content = """# UDP图像处理系统依赖包
PyQt5>=5.15.0
numpy>=1.20.0
cupy>=9.0.0
numba>=0.56.0
opencv-python>=4.5.0
"""
    
    try:
        with open('requirements.txt', 'w', encoding='utf-8') as f:
            f.write(requirements_content)
        print("已创建 requirements.txt 文件")
    except Exception as e:
        print(f"创建 requirements.txt 失败: {e}")

if __name__ == "__main__":
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("错误：需要Python 3.7或更高版本")
        sys.exit(1)

    # 检查依赖包
    if not check_dependencies():
        create_requirements_file()
        sys.exit(1)

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='MEMS Vision Pro')
    parser.add_argument('--mems-only', action='store_true',
                        help='仅运行MEMS控制面板')
    args = parser.parse_args()

    # 根据参数选择运行模式
    if args.mems_only:
        exit_code = main_mems_control()
    else:
        exit_code = main()

    sys.exit(exit_code)