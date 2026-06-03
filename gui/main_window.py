"""
主窗口
"""
import socket
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

import config
from core.discovery import DiscoveryService
from core.transfer import TransferManager
from gui.device_page import DevicePage
from gui.select_page import SelectPage
from gui.transfer_page import TransferPage


class MainWindow(QMainWindow):
    """应用程序主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化核心服务
        self.discovery = DiscoveryService()
        self.transfer_manager = TransferManager()
        
        # 当前连接的设备
        self.current_device = None
        self.selected_items = []
        
        self.setup_ui()
        self.setup_services()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(900, 600)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧导航栏
        nav_widget = QWidget()
        nav_widget.setMaximumWidth(200)
        nav_widget.setStyleSheet("""
            QWidget {
                background: #2c3e50;
            }
        """)
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(10, 20, 10, 20)
        nav_layout.setSpacing(10)
        
        # 标题
        title = QLabel(config.APP_NAME)
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(title)
        
        # 版本号
        version = QLabel(f"v{config.VERSION}")
        version.setStyleSheet("color: #95a5a6; font-size: 10px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(version)
        
        nav_layout.addSpacing(30)
        
        # 导航按钮
        self.nav_buttons = []
        
        self.btn_device = self.create_nav_button("发现设备", True)
        self.btn_device.clicked.connect(lambda: self.switch_page(0))
        nav_layout.addWidget(self.btn_device)
        self.nav_buttons.append(self.btn_device)
        
        self.btn_select = self.create_nav_button("选择数据", False)
        self.btn_select.clicked.connect(lambda: self.switch_page(1))
        nav_layout.addWidget(self.btn_select)
        self.nav_buttons.append(self.btn_select)
        
        self.btn_transfer = self.create_nav_button("传输进度", False)
        self.btn_transfer.clicked.connect(lambda: self.switch_page(2))
        nav_layout.addWidget(self.btn_transfer)
        self.nav_buttons.append(self.btn_transfer)
        
        nav_layout.addStretch()
        
        # 帮助按钮
        self.btn_help = self.create_nav_button("使用帮助", False)
        self.btn_help.clicked.connect(self.show_help)
        nav_layout.addWidget(self.btn_help)
        
        main_layout.addWidget(nav_widget)
        
        # 右侧内容区
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("""
            QStackedWidget {
                background: #f5f5f5;
            }
        """)
        
        # 创建页面
        self.device_page = DevicePage(self.discovery)
        self.device_page.device_selected.connect(self.on_device_selected)
        
        self.select_page = SelectPage()
        self.select_page.transfer_started.connect(self.on_transfer_started)
        self.select_page.back_requested.connect(lambda: self.switch_page(0))
        
        self.transfer_page = TransferPage()
        self.transfer_page.transfer_finished.connect(self.on_transfer_finished)
        self.transfer_page.back_requested.connect(lambda: self.switch_page(1))
        self.transfer_page.cancel_requested.connect(self.on_transfer_cancelled)
        
        # 添加页面到堆叠部件
        self.stack.addWidget(self.device_page)
        self.stack.addWidget(self.select_page)
        self.stack.addWidget(self.transfer_page)
        
        main_layout.addWidget(self.stack)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def create_nav_button(self, text: str, active: bool = False) -> QPushButton:
        """创建导航按钮"""
        btn = QPushButton(text)
        btn.setMinimumHeight(40)
        
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background: #3498db;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: #2980b9;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #ecf0f1;
                    border: none;
                    border-radius: 5px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: #34495e;
                }
            """)
        
        return btn
    
    def update_nav_button(self, index: int):
        """更新导航按钮状态"""
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #3498db;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background: #2980b9;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #ecf0f1;
                        border: none;
                        border-radius: 5px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background: #34495e;
                    }
                """)
    
    def switch_page(self, index: int):
        """切换页面"""
        self.stack.setCurrentIndex(index)
        self.update_nav_button(index)
    
    def setup_services(self):
        """启动后台服务"""
        # 注册mDNS服务
        if self.discovery.register_service():
            self.status_bar.showMessage(f"服务已启动，端口: {config.DEFAULT_PORT}")
        else:
            self.status_bar.showMessage("服务注册失败")
        
        # 启动设备发现
        self.discovery.start_discovery()
        
        # 启动传输服务端
        if self.transfer_manager.start_server():
            self.status_bar.showMessage(
                f"服务已启动，端口: {config.DEFAULT_PORT} | 等待连接..."
            )
        
        # 设置传输回调
        self.transfer_manager.set_callbacks(
            on_progress=self.on_transfer_progress,
            on_complete=self.on_transfer_complete,
            on_error=self.on_transfer_error
        )
    
    def on_device_selected(self, device):
        """设备被选中"""
        self.current_device = device
        
        # 连接到设备
        self.status_bar.showMessage(f"正在连接到 {device.device_name} ({device.ip})...")
        
        if self.transfer_manager.connect_to_device(device.ip, device.port):
            self.status_bar.showMessage(f"已连接到 {device.device_name}")
            self.switch_page(1)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "连接失败",
                f"无法连接到 {device.device_name} ({device.ip})\n"
                f"请检查目标设备是否已启动并处于同一网络。"
            )
            self.status_bar.showMessage("连接失败")
    
    def on_transfer_started(self, items):
        """开始传输"""
        self.selected_items = items
        
        # 计算总大小
        total_size = sum(item.get("size", 0) for item in items)
        
        # 切换到传输页面
        self.switch_page(2)
        self.transfer_page.start_transfer(len(items), total_size)
        
        # 启动传输
        self.status_bar.showMessage("正在传输数据...")
        
        # 在新线程中执行传输
        import threading
        thread = threading.Thread(
            target=self._do_transfer,
            args=(items,),
            daemon=True
        )
        thread.start()
    
    def _do_transfer(self, items):
        """执行传输（在线程中）"""
        results = self.transfer_manager.transfer_items(items)
        
        # 在主线程中更新UI
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self,
            "_on_transfer_complete_internal",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(dict, results)
        )
    
    def _on_transfer_complete_internal(self, results: dict):
        """传输完成内部处理"""
        self.transfer_page.transfer_complete(results)
    
    def on_transfer_progress(self, data: dict):
        """传输进度更新"""
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self.transfer_page,
            "update_progress",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(dict, data)
        )
    
    def on_transfer_complete(self):
        """传输完成回调"""
        pass
    
    def on_transfer_error(self, error: str):
        """传输错误回调"""
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self.transfer_page,
            "log",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, f"错误: {error}")
        )
    
    def on_transfer_finished(self, results: dict):
        """传输完成处理"""
        self.status_bar.showMessage(
            f"传输完成 - 成功: {results.get('success', 0)}, "
            f"失败: {results.get('failed', 0)}"
        )
    
    def on_transfer_cancelled(self):
        """传输被取消"""
        self.transfer_manager.cancel()
        self.status_bar.showMessage("传输已取消")
    
    def show_help(self):
        """显示帮助"""
        from PyQt6.QtWidgets import QMessageBox
        
        help_text = """
<b>使用说明</b><br><br>

<b>1. 发现设备</b><br>
启动工具后，程序会自动扫描局域网内的其他设备。<br>
如果未发现设备，可以手动输入IP地址进行连接。<br><br>

<b>2. 选择数据</b><br>
连接成功后，选择要迁移的数据类型：<br>
- 用户文件夹（文档、桌面、下载等）<br>
- 浏览器数据（书签、历史、密码）<br>
- 应用数据<br>
- 注册表设置<br><br>

<b>3. 传输数据</b><br>
点击"开始迁移"后，数据将通过局域网传输到目标设备。<br>
支持断点续传，网络中断后可恢复传输。<br><br>

<b>注意事项</b><br>
- 确保两台电脑处于同一局域网<br>
- 迁移浏览器数据前请先关闭浏览器<br>
- 传输过程中请勿关闭程序
        """.strip()
        
        QMessageBox.information(self, "使用帮助", help_text)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止服务
        self.discovery.stop()
        self.transfer_manager.stop_server()
        self.transfer_manager.disconnect()
        
        event.accept()
