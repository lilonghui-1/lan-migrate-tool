"""
自定义传输协议
消息帧格式: [4B 命令类型][4B 载荷长度][N B 载荷数据(JSON)]
"""
import json
import struct
from enum import IntEnum
from typing import Tuple, Any, Optional


class Command(IntEnum):
    """命令类型枚举"""
    HELLO = 1           # 握手，交换设备信息
    SCAN_REQUEST = 2    # 请求扫描对方可迁移数据
    SCAN_RESPONSE = 3   # 返回数据项列表
    TRANSFER_START = 4  # 开始传输
    FILE_HEADER = 5     # 单个文件元数据
    FILE_CHUNK = 6      # 文件数据块
    RESUME_CHECK = 7    # 断点续传状态查询
    RESUME_RESPONSE = 8 # 返回已接收块索引
    VERIFY_REQUEST = 9  # 请求校验文件完整性
    VERIFY_RESPONSE = 10 # 返回校验结果
    PROGRESS = 11       # 进度更新（用于接收方反馈）
    COMPLETE = 12       # 传输完成
    CANCEL = 13         # 取消传输
    ERROR = 99          # 错误通知


# 消息头部大小（4字节命令 + 4字节长度）
HEADER_SIZE = 8


def pack_message(cmd: Command, payload: Optional[Any] = None) -> bytes:
    """
    打包消息
    
    Args:
        cmd: 命令类型
        payload: 载荷数据（会被JSON序列化）
    
    Returns:
        打包后的字节数据
    """
    if payload is not None:
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    else:
        payload_bytes = b""
    
    header = struct.pack(">II", int(cmd), len(payload_bytes))
    return header + payload_bytes


def unpack_message(data: bytes) -> Tuple[Optional[Command], Optional[Any], bytes]:
    """
    从字节流中解包消息
    
    Args:
        data: 接收到的字节数据
    
    Returns:
        (命令类型, 载荷数据, 剩余未处理数据)
        如果数据不足，返回 (None, None, data)
    """
    if len(data) < HEADER_SIZE:
        return None, None, data
    
    cmd, payload_len = struct.unpack(">II", data[:HEADER_SIZE])
    
    if len(data) < HEADER_SIZE + payload_len:
        return None, None, data
    
    payload_bytes = data[HEADER_SIZE:HEADER_SIZE + payload_len]
    remaining = data[HEADER_SIZE + payload_len:]
    
    try:
        payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None
    
    return Command(cmd), payload, remaining


def pack_file_chunk(chunk_index: int, data: bytes) -> bytes:
    """
    打包文件数据块
    
    Args:
        chunk_index: 块索引
        data: 二进制数据
    
    Returns:
        打包后的字节数据
    """
    header = struct.pack(">II", int(Command.FILE_CHUNK), len(data) + 4)
    chunk_header = struct.pack(">I", chunk_index)
    return header + chunk_header + data


def unpack_file_chunk(data: bytes) -> Tuple[Optional[int], Optional[bytes], bytes]:
    """
    从字节流中解包文件数据块
    
    Args:
        data: 接收到的字节数据
    
    Returns:
        (块索引, 块数据, 剩余未处理数据)
    """
    if len(data) < HEADER_SIZE:
        return None, None, data
    
    cmd, payload_len = struct.unpack(">II", data[:HEADER_SIZE])
    
    if cmd != Command.FILE_CHUNK:
        # 如果不是文件块命令，使用标准解包
        c, p, r = unpack_message(data)
        return None, None, r if r else data
    
    if len(data) < HEADER_SIZE + payload_len:
        return None, None, data
    
    chunk_index = struct.unpack(">I", data[HEADER_SIZE:HEADER_SIZE + 4])[0]
    chunk_data = data[HEADER_SIZE + 4:HEADER_SIZE + payload_len]
    remaining = data[HEADER_SIZE + payload_len:]
    
    return chunk_index, chunk_data, remaining


def create_hello_payload(device_name: str, version: str, os_name: str = "windows") -> dict:
    """
    创建握手消息载荷
    
    Args:
        device_name: 设备名称
        version: 版本号
        os_name: 操作系统名称
    
    Returns:
        握手消息字典
    """
    return {
        "device_name": device_name,
        "version": version,
        "os": os_name
    }


def create_scan_response_payload(categories: list) -> dict:
    """
    创建扫描响应消息载荷
    
    Args:
        categories: 数据分类列表，每项包含 name, display_name, size, count, items
    
    Returns:
        扫描响应消息字典
    """
    return {
        "categories": categories
    }


def create_file_header_payload(file_path: str, file_size: int, checksum: str,
                                relative_path: str = "") -> dict:
    """
    创建文件头部消息载荷
    
    Args:
        file_path: 原始文件路径
        file_size: 文件大小
        checksum: 文件校验和
        relative_path: 相对路径（用于在目标端重建目录结构）
    
    Returns:
        文件头部消息字典
    """
    return {
        "file_path": file_path,
        "relative_path": relative_path,
        "file_size": file_size,
        "checksum": checksum
    }


def create_resume_check_payload(file_path: str, file_size: int,
                                 chunk_size: int, total_chunks: int) -> dict:
    """
    创建断点续传检查消息载荷
    
    Args:
        file_path: 文件路径
        file_size: 文件大小
        chunk_size: 分块大小
        total_chunks: 总块数
    
    Returns:
        断点续传检查消息字典
    """
    return {
        "file_path": file_path,
        "file_size": file_size,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks
    }


def create_resume_response_payload(file_path: str, received_chunks: list,
                                    missing_chunks: list) -> dict:
    """
    创建断点续传响应消息载荷
    
    Args:
        file_path: 文件路径
        received_chunks: 已接收块索引列表
        missing_chunks: 缺失块索引列表
    
    Returns:
        断点续传响应消息字典
    """
    return {
        "file_path": file_path,
        "received_chunks": received_chunks,
        "missing_chunks": missing_chunks
    }


def create_error_payload(error_code: int, message: str) -> dict:
    """
    创建错误消息载荷
    
    Args:
        error_code: 错误码
        message: 错误描述
    
    Returns:
        错误消息字典
    """
    return {
        "error_code": error_code,
        "message": message
    }


def create_progress_payload(file_path: str, bytes_transferred: int,
                             total_bytes: int, speed: float) -> dict:
    """
    创建进度消息载荷
    
    Args:
        file_path: 当前文件路径
        bytes_transferred: 已传输字节数
        total_bytes: 总字节数
        speed: 当前速度（字节/秒）
    
    Returns:
        进度消息字典
    """
    return {
        "file_path": file_path,
        "bytes_transferred": bytes_transferred,
        "total_bytes": total_bytes,
        "speed": speed
    }
