"""
传输引擎模块
管理 TCP 连接，执行文件发送/接收，支持断点续传
"""
import os
import sqlite3
import struct
import threading
import time
from typing import Optional, Callable, List, Dict

import config
from core.protocol import (
    Command, pack_message, unpack_message, pack_file_chunk, unpack_file_chunk,
    create_hello_payload, create_file_header_payload, create_resume_check_payload,
    create_resume_response_payload, create_progress_payload, create_error_payload
)
from utils.checksum import compute_file_hash, verify_file_hash
from utils.helpers import ensure_dir, format_size


class TransferStateDB:
    """
    传输状态数据库
    
    使用 SQLite 持久化断点续传状态
    """
    
    def __init__(self, db_path: str = config.DB_NAME):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transfer_state (
                task_id TEXT,
                file_path TEXT,
                chunk_index INTEGER,
                received INTEGER DEFAULT 0,
                checksum TEXT,
                PRIMARY KEY (task_id, file_path, chunk_index)
            )
        """)
        conn.commit()
        conn.close()
    
    def save_chunk_state(self, task_id: str, file_path: str,
                          chunk_index: int, received: bool, checksum: str = ""):
        """保存块状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO transfer_state 
            (task_id, file_path, chunk_index, received, checksum)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, file_path, chunk_index, 1 if received else 0, checksum))
        conn.commit()
        conn.close()
    
    def get_received_chunks(self, task_id: str, file_path: str) -> List[int]:
        """获取已接收的块索引列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chunk_index FROM transfer_state
            WHERE task_id = ? AND file_path = ? AND received = 1
        """, (task_id, file_path))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    
    def clear_task(self, task_id: str):
        """清除任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transfer_state WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()


class TransferServer:
    """
    TCP 传输服务端
    
    监听连接并处理传输请求
    """
    
    def __init__(self):
        self.socket = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.connections: List = []
        self.state_db = TransferStateDB()
        self.receive_dir = os.path.join(os.path.expanduser("~"), "LAN_Migrate_Received")
        ensure_dir(self.receive_dir)
        
        # 回调函数
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def start(self) -> bool:
        """启动服务端"""
        import socket as sock
        
        try:
            self.socket = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
            self.socket.setsockopt(sock.SOL_SOCKET, sock.SO_REUSEADDR, 1)
            self.socket.bind(("0.0.0.0", config.DEFAULT_PORT))
            self.socket.listen(5)
            self.socket.settimeout(1.0)
            self.running = True
            
            self.thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            print(f"启动传输服务端失败: {e}")
            return False
    
    def stop(self):
        """停止服务端"""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            try:
                conn, addr = self.socket.accept()
                handler = ConnectionHandler(conn, addr, self.receive_dir, self.state_db)
                handler.on_progress = self.on_progress
                handler.on_complete = self.on_complete
                handler.on_error = self.on_error
                
                thread = threading.Thread(target=handler.handle, daemon=True)
                thread.start()
                self.connections.append(handler)
            except sock.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"接受连接失败: {e}")
    
    def set_callbacks(self, on_progress=None, on_complete=None, on_error=None):
        """设置回调函数"""
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error


class ConnectionHandler:
    """
    连接处理器
    
    处理单个客户端连接
    """
    
    def __init__(self, conn, addr, receive_dir: str, state_db: TransferStateDB):
        self.conn = conn
        self.addr = addr
        self.receive_dir = receive_dir
        self.state_db = state_db
        self.buffer = b""
        self.current_file = None
        self.current_file_path = None
        self.current_file_size = 0
        self.received_size = 0
        self.task_id = ""
        
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def handle(self):
        """处理连接"""
        try:
            self.conn.settimeout(config.SOCKET_TIMEOUT)
            
            while True:
                data = self.conn.recv(config.CHUNK_SIZE)
                if not data:
                    break
                
                self.buffer += data
                self._process_buffer()
        
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
        finally:
            self.conn.close()
    
    def _process_buffer(self):
        """处理接收缓冲区"""
        while len(self.buffer) >= 8:
            cmd, payload, remaining = unpack_message(self.buffer)
            
            if cmd is None:
                # 数据不足，等待更多数据
                if len(self.buffer) >= 8:
                    # 尝试解析文件块
                    chunk_idx, chunk_data, remaining = unpack_file_chunk(self.buffer)
                    if chunk_idx is not None:
                        self._handle_file_chunk(chunk_idx, chunk_data)
                        self.buffer = remaining
                        continue
                break
            
            self.buffer = remaining
            self._handle_command(cmd, payload)
    
    def _handle_command(self, cmd: Command, payload: dict):
        """处理命令"""
        if cmd == Command.HELLO:
            # 握手响应
            response = pack_message(Command.HELLO, create_hello_payload(
                "接收端", config.VERSION
            ))
            self.conn.sendall(response)
        
        elif cmd == Command.SCAN_REQUEST:
            # 处理扫描请求
            from core.scanner import DataScanner
            scanner = DataScanner()
            categories = scanner.scan_all()
            response_data = {
                "categories": [cat.to_dict() for cat in categories]
            }
            response = pack_message(Command.SCAN_RESPONSE, response_data)
            self.conn.sendall(response)
        
        elif cmd == Command.TRANSFER_START:
            # 开始传输
            self.task_id = payload.get("task_id", "")
            response = pack_message(Command.TRANSFER_START, {"status": "ready"})
            self.conn.sendall(response)
        
        elif cmd == Command.FILE_HEADER:
            # 文件头部
            self._handle_file_header(payload)
        
        elif cmd == Command.RESUME_CHECK:
            # 断点续传检查
            self._handle_resume_check(payload)
        
        elif cmd == Command.VERIFY_REQUEST:
            # 校验请求
            self._handle_verify_request(payload)
        
        elif cmd == Command.COMPLETE:
            # 传输完成
            if self.on_complete:
                self.on_complete()
        
        elif cmd == Command.CANCEL:
            # 取消传输
            self._cleanup_current_file()
        
        elif cmd == Command.ERROR:
            # 错误
            if self.on_error:
                self.on_error(payload.get("message", "未知错误"))
    
    def _handle_file_header(self, payload: dict):
        """处理文件头部"""
        relative_path = payload.get("relative_path", "")
        file_size = payload.get("file_size", 0)
        
        # 构建接收路径
        if relative_path:
            self.current_file_path = os.path.join(self.receive_dir, relative_path)
        else:
            self.current_file_path = os.path.join(
                self.receive_dir,
                os.path.basename(payload.get("file_path", "unknown"))
            )
        
        ensure_dir(os.path.dirname(self.current_file_path))
        self.current_file_size = file_size
        self.received_size = 0
        
        # 以追加模式打开文件（支持断点续传）
        self.current_file = open(self.current_file_path, "ab")
        
        # 发送确认
        response = pack_message(Command.FILE_HEADER, {"status": "ok"})
        self.conn.sendall(response)
    
    def _handle_file_chunk(self, chunk_index: int, data: bytes):
        """处理文件数据块"""
        if self.current_file:
            self.current_file.write(data)
            self.received_size += len(data)
            
            # 保存块状态
            if self.task_id:
                self.state_db.save_chunk_state(
                    self.task_id,
                    self.current_file_path or "",
                    chunk_index,
                    True
                )
            
            # 通知进度
            if self.on_progress and self.current_file_size > 0:
                progress = int(self.received_size / self.current_file_size * 100)
                self.on_progress({
                    "file_path": self.current_file_path,
                    "progress": progress,
                    "received": self.received_size,
                    "total": self.current_file_size
                })
    
    def _handle_resume_check(self, payload: dict):
        """处理断点续传检查"""
        file_path = payload.get("file_path", "")
        task_id = payload.get("task_id", "")
        
        received_chunks = self.state_db.get_received_chunks(task_id, file_path)
        
        response = pack_message(Command.RESUME_RESPONSE, {
            "file_path": file_path,
            "received_chunks": received_chunks,
            "missing_chunks": []
        })
        self.conn.sendall(response)
    
    def _handle_verify_request(self, payload: dict):
        """处理校验请求"""
        file_path = payload.get("file_path", "")
        expected_checksum = payload.get("checksum", "")
        
        full_path = os.path.join(self.receive_dir, file_path)
        
        if os.path.exists(full_path):
            actual_checksum = compute_file_hash(full_path)
            verified = actual_checksum == expected_checksum
        else:
            verified = False
            actual_checksum = ""
        
        response = pack_message(Command.VERIFY_RESPONSE, {
            "file_path": file_path,
            "verified": verified,
            "checksum": actual_checksum
        })
        self.conn.sendall(response)
    
    def _cleanup_current_file(self):
        """清理当前文件"""
        if self.current_file:
            self.current_file.close()
            self.current_file = None


class TransferClient:
    """
    TCP 传输客户端
    
    向目标设备发起连接并发送数据
    """
    
    def __init__(self):
        self.socket = None
        self.connected = False
        self.state_db = TransferStateDB()
        self.buffer = b""
        
        # 回调
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def connect(self, ip: str, port: int = config.DEFAULT_PORT) -> bool:
        """
        连接到目标设备
        
        Args:
            ip: 目标IP地址
            port: 目标端口
        
        Returns:
            是否连接成功
        """
        import socket as sock
        
        try:
            self.socket = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
            self.socket.settimeout(config.SOCKET_TIMEOUT)
            self.socket.connect((ip, port))
            self.connected = True
            
            # 发送握手
            hello = pack_message(Command.HELLO, create_hello_payload(
                "发送端", config.VERSION
            ))
            self.socket.sendall(hello)
            
            # 等待响应
            response = self._wait_response(Command.HELLO)
            return response is not None
        
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.socket:
            self.socket.close()
            self.socket = None
        self.connected = False
    
    def request_scan(self) -> Optional[list]:
        """
        请求扫描目标设备数据
        
        Returns:
            数据分类列表，失败返回 None
        """
        if not self.connected:
            return None
        
        try:
            request = pack_message(Command.SCAN_REQUEST, {})
            self.socket.sendall(request)
            
            response = self._wait_response(Command.SCAN_RESPONSE)
            if response:
                return response.get("categories", [])
            return None
        
        except Exception as e:
            print(f"扫描请求失败: {e}")
            return None
    
    def send_file(self, filepath: str, relative_path: str = "",
                   task_id: str = "") -> bool:
        """
        发送单个文件
        
        Args:
            filepath: 本地文件路径
            relative_path: 相对路径（用于目标端重建目录）
            task_id: 任务ID（用于断点续传）
        
        Returns:
            是否发送成功
        """
        if not self.connected or not os.path.exists(filepath):
            return False
        
        try:
            file_size = os.path.getsize(filepath)
            checksum = compute_file_hash(filepath)
            
            # 发送文件头部
            header = pack_message(Command.FILE_HEADER, create_file_header_payload(
                filepath, file_size, checksum, relative_path
            ))
            self.socket.sendall(header)
            
            # 等待确认
            response = self._wait_response(Command.FILE_HEADER)
            if not response:
                return False
            
            # 发送文件内容
            sent = 0
            start_time = time.time()
            
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(config.CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    self.socket.sendall(chunk)
                    sent += len(chunk)
                    
                    # 通知进度
                    if self.on_progress and file_size > 0:
                        elapsed = time.time() - start_time
                        speed = sent / elapsed if elapsed > 0 else 0
                        progress = int(sent / file_size * 100)
                        self.on_progress({
                            "file_path": filepath,
                            "progress": progress,
                            "sent": sent,
                            "total": file_size,
                            "speed": speed
                        })
            
            # 发送校验请求
            verify = pack_message(Command.VERIFY_REQUEST, {
                "file_path": relative_path or os.path.basename(filepath),
                "checksum": checksum
            })
            self.socket.sendall(verify)
            
            response = self._wait_response(Command.VERIFY_RESPONSE)
            if response and response.get("verified"):
                return True
            
            return False
        
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            return False
    
    def send_file_with_resume(self, filepath: str, relative_path: str = "",
                               task_id: str = "") -> bool:
        """
        发送文件（支持断点续传）
        
        Args:
            filepath: 本地文件路径
            relative_path: 相对路径
            task_id: 任务ID
        
        Returns:
            是否发送成功
        """
        if not self.connected or not os.path.exists(filepath):
            return False
        
        try:
            file_size = os.path.getsize(filepath)
            checksum = compute_file_hash(filepath)
            total_chunks = (file_size + config.RESUME_CHUNK_SIZE - 1) // config.RESUME_CHUNK_SIZE
            
            # 发送断点续传检查
            resume_check = pack_message(Command.RESUME_CHECK, {
                "file_path": relative_path or os.path.basename(filepath),
                "file_size": file_size,
                "chunk_size": config.RESUME_CHUNK_SIZE,
                "total_chunks": total_chunks,
                "task_id": task_id
            })
            self.socket.sendall(resume_check)
            
            response = self._wait_response(Command.RESUME_RESPONSE)
            if response:
                received_chunks = set(response.get("received_chunks", []))
            else:
                received_chunks = set()
            
            # 发送文件头部
            header = pack_message(Command.FILE_HEADER, create_file_header_payload(
                filepath, file_size, checksum, relative_path
            ))
            self.socket.sendall(header)
            
            ack = self._wait_response(Command.FILE_HEADER)
            if not ack:
                return False
            
            # 发送缺失的块
            sent = 0
            start_time = time.time()
            
            with open(filepath, "rb") as f:
                for chunk_idx in range(total_chunks):
                    if chunk_idx in received_chunks:
                        # 跳过已接收的块
                        f.seek((chunk_idx + 1) * config.RESUME_CHUNK_SIZE)
                        continue
                    
                    offset = chunk_idx * config.RESUME_CHUNK_SIZE
                    f.seek(offset)
                    chunk_data = f.read(config.RESUME_CHUNK_SIZE)
                    
                    # 使用文件块协议发送
                    chunk_packet = pack_file_chunk(chunk_idx, chunk_data)
                    self.socket.sendall(chunk_packet)
                    
                    sent += len(chunk_data)
                    
                    # 通知进度
                    if self.on_progress and file_size > 0:
                        elapsed = time.time() - start_time
                        speed = sent / elapsed if elapsed > 0 else 0
                        progress = int(sent / file_size * 100)
                        self.on_progress({
                            "file_path": filepath,
                            "progress": progress,
                            "sent": sent,
                            "total": file_size,
                            "speed": speed,
                            "chunk": chunk_idx,
                            "total_chunks": total_chunks
                        })
            
            # 校验
            verify = pack_message(Command.VERIFY_REQUEST, {
                "file_path": relative_path or os.path.basename(filepath),
                "checksum": checksum
            })
            self.socket.sendall(verify)
            
            response = self._wait_response(Command.VERIFY_RESPONSE)
            return response is not None and response.get("verified", False)
        
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            return False
    
    def send_complete(self):
        """发送传输完成通知"""
        if self.connected:
            msg = pack_message(Command.COMPLETE, {})
            self.socket.sendall(msg)
    
    def send_cancel(self):
        """发送取消通知"""
        if self.connected:
            msg = pack_message(Command.CANCEL, {})
            self.socket.sendall(msg)
    
    def _wait_response(self, expected_cmd: Command, timeout: int = 10) -> Optional[dict]:
        """
        等待特定类型的响应
        
        Args:
            expected_cmd: 期望的命令类型
            timeout: 超时时间（秒）
        
        Returns:
            响应载荷，超时返回 None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            data = self.socket.recv(config.CHUNK_SIZE)
            if not data:
                break
            
            self.buffer += data
            
            while len(self.buffer) >= 8:
                cmd, payload, remaining = unpack_message(self.buffer)
                if cmd is None:
                    break
                
                self.buffer = remaining
                
                if cmd == expected_cmd:
                    return payload
                elif cmd == Command.ERROR:
                    if self.on_error:
                        self.on_error(payload.get("message", "未知错误"))
                    return None
        
        return None


class TransferManager:
    """
    传输管理器
    
    管理批量传输任务
    """
    
    def __init__(self):
        self.server = TransferServer()
        self.client = TransferClient()
        self.task_id = ""
        self.cancelled = False
    
    def start_server(self) -> bool:
        """启动接收服务端"""
        return self.server.start()
    
    def stop_server(self):
        """停止接收服务端"""
        self.server.stop()
    
    def connect_to_device(self, ip: str, port: int = config.DEFAULT_PORT) -> bool:
        """连接到发送设备"""
        return self.client.connect(ip, port)
    
    def disconnect(self):
        """断开连接"""
        self.client.disconnect()
    
    def transfer_items(self, items: list, target_dir: str = "") -> dict:
        """
        批量传输数据项
        
        Args:
            items: 数据项列表
            target_dir: 目标目录
        
        Returns:
            传输结果统计
        """
        import uuid
        self.task_id = str(uuid.uuid4())
        self.cancelled = False
        
        results = {
            "total": len(items),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total_size": 0,
            "transferred_size": 0
        }
        
        # 发送传输开始
        start_msg = pack_message(Command.TRANSFER_START, {"task_id": self.task_id})
        self.client.socket.sendall(start_msg)
        
        for item in items:
            if self.cancelled:
                results["skipped"] += len(items) - results["success"] - results["failed"]
                break
            
            filepath = item.get("path", "")
            item_type = item.get("type", "folder")
            
            if not os.path.exists(filepath):
                results["failed"] += 1
                continue
            
            if item_type == "folder":
                # 传输文件夹中的所有文件
                success, size = self._transfer_folder(filepath, item.get("name", ""))
                if success:
                    results["success"] += 1
                    results["transferred_size"] += size
                else:
                    results["failed"] += 1
            elif item_type == "file":
                # 传输单个文件
                if self.client.send_file_with_resume(filepath, task_id=self.task_id):
                    results["success"] += 1
                    results["transferred_size"] += os.path.getsize(filepath)
                else:
                    results["failed"] += 1
            elif item_type == "registry":
                # 导出并传输注册表
                from core.registry import RegistryManager
                reg_manager = RegistryManager()
                temp_dir = os.path.join(os.path.expanduser("~"), "temp_registry")
                exported = reg_manager.export_all_software(temp_dir)
                for reg_file in exported:
                    if self.client.send_file_with_resume(reg_file, task_id=self.task_id):
                        results["success"] += 1
                    else:
                        results["failed"] += 1
        
        # 发送完成通知
        if not self.cancelled:
            self.client.send_complete()
        
        return results
    
    def _transfer_folder(self, folder_path: str, base_name: str) -> tuple:
        """
        传输整个文件夹
        
        Args:
            folder_path: 文件夹路径
            base_name: 基础名称
        
        Returns:
            (是否成功, 传输大小)
        """
        total_size = 0
        success = True
        
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                if self.cancelled:
                    return False, total_size
                
                filepath = os.path.join(dirpath, filename)
                # 计算相对路径
                rel_path = os.path.relpath(filepath, os.path.dirname(folder_path))
                
                if self.client.send_file_with_resume(filepath, rel_path, self.task_id):
                    total_size += os.path.getsize(filepath)
                else:
                    success = False
        
        return success, total_size
    
    def cancel(self):
        """取消传输"""
        self.cancelled = True
        self.client.send_cancel()
    
    def set_callbacks(self, on_progress=None, on_complete=None, on_error=None):
        """设置回调"""
        self.client.on_progress = on_progress
        self.client.on_complete = on_complete
        self.client.on_error = on_error
        self.server.set_callbacks(on_progress, on_complete, on_error)
