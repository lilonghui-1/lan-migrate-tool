"""
设备发现页面
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QMetaObject, Q_ARG
from PyQt6.QtGui import QFont

from core.discovery import DiscoveryService, DeviceInfo


class DeviceItemWidget(QWidget):
    """设备列表项自定义控件"""
    
    def __init__(self, device: DeviceInfo, parent=None):
        super().__init__(parent)
        self.device = device
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 设备名称
        self.name_label = QLabel(self.device.device_name or self.device.name.split(".")[0])
        self.name_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(self.name_label)
        
        layout.addStretch()
        
        # IP地址
        self.ip_label = QLabel(f"{self.device.ip}:{self.device.port}")
        self.ip_label.setStyleSheet("color: #666;")
        layout.addWidget(self.ip_label)
        
        # 操作系统
        if self.device.os_name:
            self.os_label = QLabel(f"[{self.device.os_name}]")
            self.os_label.setStyleSheet("color: #999; font-size: 10px;")
            layout.addWidget(self.os_label)


class DevicePage(QWidget):
    """设备发现页面"""
    
    # 信号
    device_selected = pyqtSignal(DeviceInfo)  # 设备被选中
    device_changed_signal = pyqtSignal(str, object)  # 设备变更信号
    
    def __init__(self, discovery: DiscoveryService, parent=None):
        super().__init__(parent)
        self.discovery = discovery
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("发现局域网设备")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 说明文字
        desc = QLabel("在下方列表中选择要连接的设备，或手动输入IP地址")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)
        
        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
            }
            QListWidget::item {
                border-bottom: 1px solid #eee;
                padding: 5px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                border-left: 3px solid #2196F3;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.device_list.setMinimumHeight(250)
        layout.addWidget(self.device_list)
        
        # 手动输入区域
        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("手动输入IP:"))
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("例如: 192.168.1.100")
        self.ip_input.setMinimumWidth(150)
        manual_layout.addWidget(self.ip_input)
        
        manual_layout.addWidget(QLabel("端口:"))
        
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("默认9000")
        self.port_input.setText("9000")
        self.port_input.setMaximumWidth(80)
        manual_layout.addWidget(self.port_input)
        
        self.manual_connect_btn = QPushButton("连接")
        self.manual_connect_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        manual_layout.addWidget(self.manual_connect_btn)
        
        layout.addLayout(manual_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #1976D2;
            }
        """)
        btn_layout.addWidget(self.refresh_btn)
        
        btn_layout.addStretch()
        
        self.connect_btn = QPushButton("连接选中设备")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #45a049;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        """)
        self.connect_btn.setEnabled(False)
        btn_layout.addWidget(self.connect_btn)
        
        layout.addLayout(btn_layout)
        
        # 状态标签
        self.status_label = QLabel("正在扫描局域网...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(self.status_label)
    
    def setup_connections(self):
        """设置信号连接"""
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.connect_btn.clicked.connect(self.connect_selected)
        self.manual_connect_btn.clicked.connect(self.connect_manual)
        self.device_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.device_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # 设备变更信号连接（用于线程安全的UI更新）
        self.device_changed_signal.connect(self._handle_device_changed)
        
        # 注册设备发现回调
        self.discovery.add_callback(self.on_device_changed)
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.device_list.clear()
        devices = self.discovery.get_devices()
        
        for device in devices:
            self.add_device_to_list(device)
        
        self.update_status()
    
    def add_device_to_list(self, device: DeviceInfo):
        """添加设备到列表"""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, device)
        
        widget = DeviceItemWidget(device)
        
        self.device_list.addItem(item)
        self.device_list.setItemWidget(item, widget)
    
    def on_device_changed(self, event_type: str, device: DeviceInfo):
        """设备变更回调（在发现线程中调用）"""
        # 使用信号将 UI 更新切回主线程
        self.device_changed_signal.emit(event_type, device)
    
    def _handle_device_changed(self, event_type: str, device: DeviceInfo):
        """设备变更处理（在主线程中执行）"""
        if event_type == "added":
            # 检查是否已存在
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                existing = item.data(Qt.ItemDataRole.UserRole)
                if existing and existing.name == device.name:
                    return
            self.add_device_to_list(device)
            self.update_status()
        
        elif event_type == "removed":
            # 移除设备
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                existing = item.data(Qt.ItemDataRole.UserRole)
                if existing and existing.name == device.name:
                    self.device_list.takeItem(i)
                    break
            self.update_status()
    
    def on_selection_changed(self):
        """选择变更"""
        has_selection = len(self.device_list.selectedItems()) > 0
        self.connect_btn.setEnabled(has_selection)
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """双击设备项"""
        device = item.data(Qt.ItemDataRole.UserRole)
        if device:
            self.device_selected.emit(device)
    
    def connect_selected(self):
        """连接选中的设备"""
        items = self.device_list.selectedItems()
        if not items:
            return
        
        device = items[0].data(Qt.ItemDataRole.UserRole)
        if device:
            self.device_selected.emit(device)
    
    def connect_manual(self):
        """手动连接"""
        ip = self.ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "提示", "请输入IP地址")
            return
        
        # 获取端口号
        port_text = self.port_input.text().strip()
        if port_text:
            try:
                port = int(port_text)
                if port < 1 or port > 65535:
                    QMessageBox.warning(self, "提示", "端口号必须在1-65535之间")
                    return
            except ValueError:
                QMessageBox.warning(self, "提示", "端口号必须是数字")
                return
        else:
            port = 9000  # 默认端口
        
        # 创建虚拟设备信息
        device = DeviceInfo(
            name=f"manual_{ip}:{port}",
            ip=ip,
            port=port,
            device_name=f"手动输入 ({ip}:{port})",
            version="unknown",
            os_name="unknown"
        )
        self.device_selected.emit(device)
    
    def update_status(self):
        """更新状态标签"""
        count = self.device_list.count()
        if count == 0:
            self.status_label.setText("未发现设备，请确保目标设备已启动并处于同一局域网")
        else:
            self.status_label.setText(f"发现 {count} 个设备")
    
    def showEvent(self, event):
        """页面显示时刷新设备列表"""
        super().showEvent(event)
        self.refresh_devices()
