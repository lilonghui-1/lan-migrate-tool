"""
传输进度页面
"""
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from utils.helpers import format_size, format_speed, format_time


class TransferPage(QWidget):
    """传输进度页面"""
    
    # 信号
    transfer_finished = pyqtSignal(dict)  # 传输完成
    back_requested = pyqtSignal()  # 返回上一页
    cancel_requested = pyqtSignal()  # 取消传输
    
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
        
        # 日志区域
        log_group = QGroupBox("传输日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)  # 限制最大行数
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
            
            # 估算总体进度
            if self.total_bytes > 0:
                total_progress = int(
                    (self.transferred_bytes + sent) / self.total_bytes * 100
                )
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
    
    def on_back(self):
        """返回按钮"""
        self.back_requested.emit()
    
    def on_pause_resume(self):
        """暂停/继续按钮"""
        if self.pause_btn.text() == "暂停":
            self.pause_btn.setText("继续")
            self.log("传输已暂停")
            # TODO: 实现暂停逻辑
        else:
            self.pause_btn.setText("暂停")
            self.log("传输已继续")
            # TODO: 实现继续逻辑
    
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
    
    def transfer_complete(self, results: dict):
        """
        传输完成
        
        Args:
            results: 传输结果统计
        """
        self.timer.stop()
        
        success = results.get("success", 0)
        failed = results.get("failed", 0)
        total_size = results.get("transferred_size", 0)
        elapsed = int(time.time() - self.start_time)
        
        self.log("-" * 40)
        self.log("传输完成!")
        self.log(f"成功: {success} 项")
        self.log(f"失败: {failed} 项")
        self.log(f"总计: {format_size(total_size)}")
        self.log(f"用时: {format_time(elapsed)}")
        
        self.total_progress.setValue(100)
        self.file_progress.setValue(100)
        self.current_file_label.setText("传输完成!")
        self.speed_label.setText("速度: --")
        
        # 显示完成对话框
        QMessageBox.information(
            self,
            "传输完成",
            f"传输已完成!\n\n"
            f"成功: {success} 项\n"
            f"失败: {failed} 项\n"
            f"总计: {format_size(total_size)}\n"
            f"用时: {format_time(elapsed)}"
        )
        
        self.transfer_finished.emit(results)
    
    def showEvent(self, event):
        """页面显示"""
        super().showEvent(event)
        self.pause_btn.setText("暂停")
