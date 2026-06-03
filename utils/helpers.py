"""
通用工具函数
"""
import os
import socket
import struct


def get_local_ip() -> str:
    """
    获取本机局域网IP地址
    
    Returns:
        IP地址字符串
    """
    try:
        # 方法1：通过UDP连接外部地址获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        pass
    
    try:
        # 方法2：通过gethostbyname获取
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    
    # 方法3：返回本地回环地址
    return "127.0.0.1"


def format_size(size_bytes: int) -> str:
    """
    将字节大小格式化为人类可读字符串
    
    Args:
        size_bytes: 字节数
    
    Returns:
        格式化后的字符串，如 "1.5 GB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def format_speed(speed_bytes_per_sec: float) -> str:
    """
    格式化传输速度
    
    Args:
        speed_bytes_per_sec: 每秒字节数
    
    Returns:
        格式化后的速度字符串，如 "10.5 MB/s"
    """
    return format_size(int(speed_bytes_per_sec)) + "/s"


def format_time(seconds: int) -> str:
    """
    将秒数格式化为人类可读的时间字符串
    
    Args:
        seconds: 秒数
    
    Returns:
        格式化后的时间字符串，如 "2小时15分钟"
    """
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        if secs > 0:
            return f"{minutes}分{secs}秒"
        return f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"


def get_folder_size(folder_path: str) -> int:
    """
    递归计算文件夹总大小
    
    Args:
        folder_path: 文件夹路径
    
    Returns:
        总字节数
    """
    total = 0
    if not os.path.exists(folder_path):
        return 0
    
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total


def count_files(folder_path: str) -> int:
    """
    递归计算文件夹中的文件数量
    
    Args:
        folder_path: 文件夹路径
    
    Returns:
        文件数量
    """
    count = 0
    if not os.path.exists(folder_path):
        return 0
    
    for dirpath, dirnames, filenames in os.walk(folder_path):
        count += len(filenames)
    return count


def ensure_dir(path: str):
    """
    确保目录存在，不存在则创建
    
    Args:
        path: 目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
