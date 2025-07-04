"""
全局队列管理模块
管理UDP数据包的全局队列和相关操作
"""

from queue import Queue, Empty
from PyQt5.QtCore import QMutex, QMutexLocker
from config.constants import QUEUE_MAX_SIZE

# 全局队列和锁
packet_queue = Queue(maxsize=QUEUE_MAX_SIZE)
queue_mutex = QMutex()

def get_queue_size():
    """
    获取当前队列大小
    
    Returns:
        int: 当前队列中的元素数量
    """
    with QMutexLocker(queue_mutex):
        return packet_queue.qsize()

def put_packet(packet, block=False):
    """
    向队列中添加数据包
    
    Args:
        packet: 数据包
        block: 是否阻塞等待
        
    Returns:
        bool: 是否成功添加
    """
    try:
        with QMutexLocker(queue_mutex):
            packet_queue.put(packet, block=block)
            return True
    except:
        return False

def get_packet(block=False):
    """
    从队列中获取数据包
    
    Args:
        block: 是否阻塞等待
        
    Returns:
        packet: 数据包，如果队列为空返回None
    """
    try:
        with QMutexLocker(queue_mutex):
            return packet_queue.get(block=block)
    except Empty:
        return None

def get_multiple_packets(max_count):
    """
    批量获取多个数据包
    
    Args:
        max_count: 最大获取数量
        
    Returns:
        list: 数据包列表
    """
    packets = []
    with QMutexLocker(queue_mutex):
        count = 0
        while not packet_queue.empty() and count < max_count:
            try:
                packets.append(packet_queue.get_nowait())
                count += 1
            except Empty:
                break
    return packets

def clear_queue():
    """
    清空队列中的所有数据
    """
    with QMutexLocker(queue_mutex):
        while not packet_queue.empty():
            try:
                packet_queue.get_nowait()
            except Empty:
                break

def is_queue_empty():
    """
    检查队列是否为空
    
    Returns:
        bool: 队列是否为空
    """
    with QMutexLocker(queue_mutex):
        return packet_queue.empty()

def is_queue_full():
    """
    检查队列是否已满
    
    Returns:
        bool: 队列是否已满
    """
    with QMutexLocker(queue_mutex):
        return packet_queue.full()