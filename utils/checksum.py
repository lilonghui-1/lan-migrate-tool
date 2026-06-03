"""
校验和计算工具
"""
import hashlib
import os
from typing import Optional


def compute_file_hash(filepath: str, algorithm: str = "md5", block_size: int = 65536) -> str:
    """
    计算文件的哈希值
    
    Args:
        filepath: 文件路径
        algorithm: 哈希算法，支持 md5, sha1, sha256
        block_size: 读取块大小
    
    Returns:
        十六进制哈希字符串
    """
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")
    
    with open(filepath, "rb") as f:
        while chunk := f.read(block_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def compute_chunk_hash(data: bytes, algorithm: str = "md5") -> str:
    """
    计算数据块的哈希值
    
    Args:
        data: 二进制数据
        algorithm: 哈希算法
    
    Returns:
        十六进制哈希字符串
    """
    if algorithm == "md5":
        return hashlib.md5(data).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(data).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")


def compute_file_chunks_hash(filepath: str, chunk_size: int, algorithm: str = "md5") -> list:
    """
    计算文件每个分块的哈希值
    
    Args:
        filepath: 文件路径
        chunk_size: 分块大小
        algorithm: 哈希算法
    
    Returns:
        每块哈希值的列表
    """
    hashes = []
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hashes.append(compute_chunk_hash(chunk, algorithm))
    return hashes


def verify_file_hash(filepath: str, expected_hash: str, algorithm: str = "md5") -> bool:
    """
    验证文件哈希值是否匹配
    
    Args:
        filepath: 文件路径
        expected_hash: 期望的哈希值
        algorithm: 哈希算法
    
    Returns:
        是否匹配
    """
    if not os.path.exists(filepath):
        return False
    actual_hash = compute_file_hash(filepath, algorithm)
    return actual_hash.lower() == expected_hash.lower()
