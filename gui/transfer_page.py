"""
传输进度页面
"""
import os
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QGroupBox, QMessageBox, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from utils.helpers import format_size, format_speed, format_time


class TransferPage(QWidget):
    """传输进度页面"""
    
    # 信号
    transfer_finished = pyqtSignal(dict)  # 传输完成
    back_requested = pyqtSignal()  # 返回上一页
    cancel_requested = pyqtSignal()  # 取消传输
    pause_requested = pyqtSignal()  # 暂停传输
    resume_requested = pyqtSignal()  # 继续传输
    progress_updated = pyqtSignal(dict)  # 进度更新（用于线程安全更新）
    file_sent = pyqtSignal(int, str)  # 文件发送完成（用于线程安全更新）
    log_message = pyqtSignal(str)  # 日志消息（用于线程安全更新）
    parallel_status = pyqtSignal(dict)  # 并行文件状态更新
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()
        
        # 状态
        self.start_time = 0
        self.total_bytes = 0
        self.transferred_bytes = 0
        self.current_file_bytes = 0
        self.current_file_total = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed_time)
        
        # 并行文件状态
        self.parallel_files = {}  # key: 文件路径, value: {'progress': int, 'status': str, 'speed': int}
        self.parallel_widgets = {}  # key: 文件路径, value: QFrame
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("数据传输中")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 当前文件信息
        self.current_file_group = QGroupBox("当前文件")
        file_layout = QVBoxLayout(self.current_file_group)
        
        self.current_file_label = QLabel("准备中...")
        self.current_file_label.setWordWrap(True)
        file_layout.addWidget(self.current_file_label)
        
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        self.file_progress.setTextVisible(True)
        self.file_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background: #2196F3;
                border-radius: 5px;
            }
        """)
        file_layout.addWidget(self.file_progress)
        
        layout.addWidget(self.current_file_group)
        
        # 总体进度
        self.total_group = QGroupBox("总体进度")
        total_layout = QVBoxLayout(self.total_group)
        
        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 100)
        self.total_progress.setTextVisible(True)
        self.total_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 5px;
                text-align: center;
                height: 30px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: #4CAF50;
                border-radius: 5px;
            }
        """)
        total_layout.addWidget(self.total_progress)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        
        self.speed_label = QLabel("速度: --")
        self.speed_label.setStyleSheet("font-size: 12px;")
        stats_layout.addWidget(self.speed_label)
        
        stats_layout.addStretch()
        
        self.time_label = QLabel("已用: 0秒 | 剩余: --")
        self.time_label.setStyleSheet("font-size: 12px;")
        stats_layout.addWidget(self.time_label)
        
        total_layout.addLayout(stats_layout)
        
        layout.addWidget(self.total_group)
        
        # 并行传输状态
        self.parallel_group = QGroupBox("并行传输状态")
        parallel_layout = QVBoxLayout(self.parallel_group)
        
        self.parallel_scroll = QScrollArea()
        self.parallel_scroll.setWidgetResizable(True)
        self.parallel_scroll.setMaximumHeight(150)
        self.parallel_container = QWidget()
        self.parallel_layout = QVBoxLayout(self.parallel_container)
        self.parallel_scroll.setWidget(self.parallel_container)
        parallel_layout.addWidget(self.parallel_scroll)
        
        layout.addWidget(self.parallel_group)
        
        # 日志区域
        log_group = QGroupBox("传输日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
                padding: 5px;
            }
        """)
        log_layout.addWidget(self.log_text)
        self.max_log_lines = 500
        
        layout.addWidget(log_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.back_btn = QPushButton("返回")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background: #9E9E9E;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #757575;
            }
        """)
        btn_layout.addWidget(self.back_btn)
        
        btn_layout.addStretch()
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background: #FF9800;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #F57C00;
            }
        """)
        btn_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #d32f2f;
            }
        """)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def setup_connections(self):
        """设置信号连接"""
        self.back_btn.clicked.connect(self.on_back)
        self.pause_btn.clicked.connect(self.on_pause_resume)
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.progress_updated.connect(self.update_progress)
        self.file_sent.connect(self.on_file_sent)
        self.log_message.connect(self.log)
        self.parallel_status.connect(self.update_parallel_status)
    
    def start_transfer(self, total_items: int, total_size: int):
        """
        开始传输
        
        Args:
            total_items: 总项目数
            total_size: 总大小（字节）
        """
        self.start_time = time.time()
        self.total_bytes = total_size
        self.transferred_bytes = 0
        self.current_file_bytes = 0
        self.current_file_total = 0
        
        self.total_progress.setValue(0)
        self.file_progress.setValue(0)
        self.current_file_label.setText("准备中...")
        
        self.log_text.clear()
        self.log("传输开始")
        self.log(f"总计 {total_items} 项, {format_size(total_size)}")
        
        self.timer.start(1000)  # 每秒更新一次时间
    
    def update_progress(self, data: dict):
        """
        更新进度
        
        Args:
            data: 进度数据，包含 file_path, progress, sent/total, speed
        """
        # 检查是否是连接状态信息
        status = data.get("status", "")
        if status == "connected":
            # 客户端连接通知（接收端）
            client = data.get("client", "")
            message = data.get("message", "")
            self.current_file_label.setText(message)
            self.log(f"连接建立: {client}")
            return
        
        # 检查是否是传输开始通知
        if status == "transfer_start":
            # 接收端收到传输开始通知
            total_count = data.get("total_count", 0)
            total_size = data.get("total_size", 0)
            
            self.total_bytes = total_size
            self.transferred_bytes = 0
            
            self.log(f"传输开始")
            self.log(f"总计 {total_count} 项, {format_size(total_size)}")
            return
        
        file_path = data.get("file_path", "")
        progress = data.get("progress", 0)
        sent = data.get("sent", 0)
        total = data.get("total", 0)
        speed = data.get("speed", 0)
        
        # 更新当前文件信息
        self.current_file_label.setText(f"正在传输: {file_path}")
        self.file_progress.setValue(progress)
        
        # 更新速度
        if speed > 0:
            self.speed_label.setText(f"速度: {format_speed(speed)}")
        
        # 更新总体进度
        if total > 0:
            self.current_file_bytes = sent
            self.current_file_total = total
            
            # 计算总体进度：已完成的文件大小 + 当前文件已发送的大小
            if self.total_bytes > 0:
                total_progress = int(
                    (self.transferred_bytes + sent) / self.total_bytes * 100
                )
                self.total_progress.setValue(min(total_progress, 100))
    
    def on_file_sent(self, file_size: int, file_path: str):
        """
        文件发送完成
        
        Args:
            file_size: 文件大小
            file_path: 文件路径
        """
        self.transferred_bytes += file_size
        self.log(f"已完成: {file_path}")
        
        # 更新总体进度
        if self.total_bytes > 0:
            total_progress = int(self.transferred_bytes / self.total_bytes * 100)
            self.total_progress.setValue(min(total_progress, 100))
    
    def file_completed(self, file_path: str, success: bool):
        """
        文件传输完成
        
        Args:
            file_path: 文件路径
            success: 是否成功
        """
        if success:
            self.transferred_bytes += self.current_file_total
            self.log(f"✓ 完成: {file_path}")
        else:
            self.log(f"✗ 失败: {file_path}")
        
        self.current_file_bytes = 0
        self.current_file_total = 0
    
    def update_elapsed_time(self):
        """更新已用时间"""
        elapsed = int(time.time() - self.start_time)
        
        # 计算剩余时间
        if self.transferred_bytes > 0 and self.total_bytes > 0:
            speed = self.transferred_bytes / elapsed if elapsed > 0 else 0
            remaining_bytes = self.total_bytes - self.transferred_bytes
            if speed > 0:
                remaining = int(remaining_bytes / speed)
                self.time_label.setText(
                    f"已用: {format_time(elapsed)} | 剩余: {format_time(remaining)}"
                )
            else:
                self.time_label.setText(f"已用: {format_time(elapsed)} | 剩余: --")
        else:
            self.time_label.setText(f"已用: {format_time(elapsed)} | 剩余: --")
    
    def log(self, message: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 限制最大行数
        cursor = self.log_text.textCursor()
        block_count = self.log_text.document().blockCount()
        if block_count > self.max_log_lines:
            cursor.setPosition(0)
            cursor.movePosition(cursor.MoveOperation.NextBlock, cursor.MoveMode.KeepAnchor, block_count - self.max_log_lines)
            cursor.removeSelectedText()
    
    def on_back(self):
        """返回按钮"""
        self.back_requested.emit()
    
    def on_pause_resume(self):
        """暂停/继续按钮"""
        if self.pause_btn.text() == "暂停":
            self.pause_btn.setText("继续")
            self.log("传输已暂停")
            self.pause_requested.emit()
        else:
            self.pause_btn.setText("暂停")
            self.log("传输已继续")
            self.resume_requested.emit()
    
    def on_cancel(self):
        """取消按钮"""
        reply = QMessageBox.question(
            self,
            "确认取消",
            "确定要取消传输吗？已传输的数据将保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log("用户取消传输")
            self.cancel_requested.emit()
            self.timer.stop()
    
    def update_parallel_status(self, data: dict):
        """
        更新并行传输文件状态
        
        Args:
            data: 包含 file_path, progress, status, speed
        """
        file_path = data.get("file_path", "")
        progress = data.get("progress", 0)
        status = data.get("status", "")
        speed = data.get("speed", 0)
        
        if not file_path:
            return
        
        # 更新状态字典
        self.parallel_files[file_path] = {
            'progress': progress,
            'status': status,
            'speed': speed
        }
        
        # 如果文件完成，移除并清理UI
        if status == "completed" or status == "failed":
            if file_path in self.parallel_widgets:
                widgets = self.parallel_widgets[file_path]
                self.parallel_layout.removeWidget(widgets['frame'])
                widgets['frame'].deleteLater()
                del self.parallel_widgets[file_path]
            del self.parallel_files[file_path]
            return
        
        # 创建或更新UI组件
        if file_path not in self.parallel_widgets:
            # 创建新的文件状态widget
            frame = QFrame()
            frame.setStyleSheet("border-bottom: 1px solid #eee; padding: 4px;")
            frame_layout = QHBoxLayout(frame)
            
            # 状态图标
            status_label = QLabel()
            status_label.setFixedSize(16, 16)
            if status == "transferring":
                status_label.setStyleSheet("background-color: #4CAF50; border-radius: 8px;")
            elif status == "pending":
                status_label.setStyleSheet("background-color: #FF9800; border-radius: 8px;")
            frame_layout.addWidget(status_label)
            
            # 文件名称
            name_label = QLabel(os.path.basename(file_path))
            name_label.setStyleSheet("font-size: 11px;")
            name_label.setMinimumWidth(150)
            frame_layout.addWidget(name_label)
            
            # 进度条
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(progress)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    text-align: center;
                    height: 12px;
                    font-size: 10px;
                }
                QProgressBar::chunk {
                    background: #2196F3;
                    border-radius: 3px;
                }
            """)
            progress_bar.setMinimumWidth(100)
            progress_bar.setMaximumWidth(150)
            frame_layout.addWidget(progress_bar)
            
            # 速度
            speed_label = QLabel()
            speed_label.setStyleSheet("font-size: 10px; color: #666;")
            speed_label.setMinimumWidth(60)
            frame_layout.addWidget(speed_label)
            
            # 保存引用
            self.parallel_widgets[file_path] = {
                'frame': frame,
                'progress_bar': progress_bar,
                'speed_label': speed_label
            }
            self.parallel_layout.addWidget(frame)
        
        # 更新进度和速度
        if file_path in self.parallel_widgets:
            widgets = self.parallel_widgets[file_path]
            widgets['progress_bar'].setValue(progress)
            if speed > 0:
                widgets['speed_label'].setText(f"{format_speed(speed)}")
            else:
                widgets['speed_label'].setText("--")
    
    def transfer_complete(self, results: dict):
        """
        传输完成
        
        Args:
            results: 传输结果统计
        """
        self.timer.stop()
        
        # 清理并行状态UI
        for file_path in list(self.parallel_widgets.keys()):
            widget = self.parallel_widgets[file_path]['frame']
            self.parallel_layout.removeWidget(widget)
            widget.deleteLater()
            del self.parallel_widgets[file_path]
        self.parallel_files.clear()
        
        success = results.get("success", 0)
        failed = results.get("failed", 0)
        total_size = results.get("transferred_size", 0)
        failed_files = results.get("failed_files", [])
        elapsed = int(time.time() - self.start_time)
        
        self.log("-" * 40)
        self.log("传输完成!")
        self.log(f"成功: {success} 项")
        self.log(f"失败: {failed} 项")
        self.log(f"总计: {format_size(total_size)}")
        self.log(f"用时: {format_time(elapsed)}")
        
        # 显示失败文件列表
        if failed_files:
            self.log(f"\n失败文件列表 ({len(failed_files)} 个):")
            for failed_file in failed_files:
                self.log(f"  - {failed_file}")
        
        self.total_progress.setValue(100)
        self.file_progress.setValue(100)
        self.current_file_label.setText("传输完成!")
        self.speed_label.setText("速度: --")
        
        # 构建完成消息
        complete_msg = (
            f"传输已完成!\n\n"
            f"成功: {success} 项\n"
            f"失败: {failed} 项\n"
            f"总计: {format_size(total_size)}\n"
            f"用时: {format_time(elapsed)}"
        )
        
        # 如果有失败文件，显示前10个
        if failed_files:
            complete_msg += f"\n\n失败文件列表 ({len(failed_files)} 个):"
            for i, failed_file in enumerate(failed_files[:10]):
                complete_msg += f"\n  {os.path.basename(failed_file)}"
            if len(failed_files) > 10:
                complete_msg += f"\n  ... 还有 {len(failed_files) - 10} 个文件"
        
        # 显示完成对话框
        QMessageBox.information(self, "传输完成", complete_msg)
        
        self.transfer_finished.emit(results)
    
    def showEvent(self, event):
        """页面显示"""
        super().showEvent(event)
        self.pause_btn.setText("暂停")
