"""
UDP发送器模块
负责发送控制指令到下位机
"""

import socket
from config.constants import DEFAULT_CONTROL_PORT

class UDPSender:
    """UDP发送类，用于发送控制指令到下位机"""

    def __init__(self, target_ip: str, target_port: int = DEFAULT_CONTROL_PORT):
        """
        初始化UDP发送器

        Args:
            target_ip: 目标IP地址
            target_port: 目标端口号（默认为控制端口0x8004）
        """
        self.target_ip = target_ip
        self.target_port = target_port

    def send_command(self, command: bytes) -> tuple[bool, int]:
        """
        发送命令到下位机

        Args:
            command: 要发送的命令字节数组

        Returns:
            tuple: (是否成功, 发送的字节数)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 绑定到本地端口发送（使用系统自动分配的端口）
            bytes_sent = sock.sendto(command, (self.target_ip, self.target_port))
            sock.close()
            return True, bytes_sent
        except Exception as e:
            print(f"UDP发送失败: {e}")
            return False, 0

    def update_target(self, target_ip: str, target_port: int = None):
        """
        更新目标地址
        
        Args:
            target_ip: 新的目标IP地址
            target_port: 新的目标端口号（可选）
        """
        self.target_ip = target_ip
        if target_port is not None:
            self.target_port = target_port

    def get_target_info(self) -> tuple[str, int]:
        """
        获取当前目标信息
        
        Returns:
            tuple: (目标IP, 目标端口)
        """
        return self.target_ip, self.target_port

    def test_connection(self) -> bool:
        """
        测试连接是否可用
        
        Returns:
            bool: 连接是否可用
        """
        try:
            # 发送一个简单的测试包
            test_command = bytes([0xAA, 0x00, 0x01, 0x00])  # 简单的测试命令
            success, _ = self.send_command(test_command)
            return success
        except Exception:
            return False