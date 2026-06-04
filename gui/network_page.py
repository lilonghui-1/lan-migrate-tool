"""
网络检查配置页面
"""
import socket
import subprocess
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTextEdit, QLineEdit, QComboBox, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette

import config


class NetworkPage(QWidget):
    """网络检查配置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()
        
        # 测试状态
        self.test_results = {}
        self.ping_progress = 0
        self.ping_timer = QTimer(self)
        self.ping_timer.timeout.connect(self.update_ping_progress)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("网络配置检查")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 网络信息区域
        info_group = QGroupBox("网络信息")
        info_layout = QVBoxLayout(info_group)
        
        # IP地址列表
        self.ip_list = QTextEdit()
        self.ip_list.setReadOnly(True)
        self.ip_list.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
                padding: 5px;
            }
        """)
        info_layout.addWidget(self.ip_list)
        
        layout.addWidget(info_group)
        
        # 端口配置区域
        port_group = QGroupBox("端口配置")
        port_layout = QHBoxLayout(port_group)
        
        port_layout.addWidget(QLabel("服务端口:"))
        
        self.port_input = QLineEdit(str(config.DEFAULT_PORT))
        self.port_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 3px 5px;
                width: 80px;
            }
        """)
        port_layout.addWidget(self.port_input)
        
        port_layout.addStretch()
        
        self.port_status = QLabel("")
        self.port_status.setStyleSheet("font-size: 12px;")
        port_layout.addWidget(self.port_status)
        
        layout.addWidget(port_group)
        
        # 连接测试区域
        test_group = QGroupBox("连接测试")
        test_layout = QVBoxLayout(test_group)
        
        # 目标IP输入
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标IP:"))
        
        self.target_ip = QLineEdit()
        self.target_ip.setPlaceholderText("例如: 192.168.1.100")
        self.target_ip.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 3px 5px;
            }
        """)
        target_layout.addWidget(self.target_ip)
        
        self.test_btn = QPushButton("开始测试")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #1976D2;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        """)
        target_layout.addWidget(self.test_btn)
        
        test_layout.addLayout(target_layout)
        
        # 测试进度条
        self.test_progress = QProgressBar()
        self.test_progress.setRange(0, 100)
        self.test_progress.setTextVisible(True)
        self.test_progress.setValue(0)
        test_layout.addWidget(self.test_progress)
        
        # 测试结果列表
        self.test_result_list = QTextEdit()
        self.test_result_list.setReadOnly(True)
        self.test_result_list.setMaximumHeight(150)
        self.test_result_list.setStyleSheet("""
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
        test_layout.addWidget(self.test_result_list)
        
        layout.addWidget(test_group)
        
        # 网络状态监控区域
        monitor_group = QGroupBox("网络状态")
        monitor_layout = QVBoxLayout(monitor_group)
        
        # 状态标签
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("检查中...")
        self.status_label.setFont(QFont("Microsoft YaHei", 12))
        status_layout.addWidget(self.status_label)
        
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(20, 20)
        status_layout.addWidget(self.status_icon)
        
        monitor_layout.addLayout(status_layout)
        
        # 延迟显示
        latency_layout = QHBoxLayout()
        latency_layout.addWidget(QLabel("当前延迟:"))
        
        self.latency_label = QLabel("-- ms")
        self.latency_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        latency_layout.addWidget(self.latency_label)
        
        latency_layout.addStretch()
        
        monitor_layout.addLayout(latency_layout)
        
        layout.addWidget(monitor_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新网络信息")
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
        
        self.apply_btn = QPushButton("应用配置")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        btn_layout.addWidget(self.apply_btn)
        
        # 重要：使用 addLayout 而不是 addWidget
        layout.addLayout(btn_layout)
    
    def setup_connections(self):
        """设置信号连接"""
        self.refresh_btn.clicked.connect(self.refresh_network_info)
        self.apply_btn.clicked.connect(self.apply_config)
        self.test_btn.clicked.connect(self.run_tests)
    
    def refresh_network_info(self):
        """刷新网络信息"""
        self.update_ip_info()
        self.check_port_status()
        self.update_network_status()
    
    def update_ip_info(self):
        """更新IP信息"""
        ip_info = self.get_network_interfaces()
        self.ip_list.clear()
        self.ip_list.append(ip_info)
    
    def get_network_interfaces(self):
        """获取网络接口信息"""
        result = "=== 网络接口信息 ===\n\n"
        
        try:
            hostname = socket.gethostname()
            result += f"主机名: {hostname}\n\n"
            
            # 获取本机IP地址
            ips = self._get_local_ips()
            result += "本机IP地址:\n"
            for ip in ips:
                result += f"  - {ip}\n"
            result += "\n"
            
            # 获取路由信息
            result += "路由表信息:\n"
            try:
                import subprocess as sub
                output = sub.check_output(
                    ['route', 'print'],
                    text=True,
                    timeout=5
                )
                lines = output.split('\n')
                for line in lines[:20]:
                    result += f"  {line}\n"
            except Exception as e:
                result += f"  获取路由表失败: {e}\n"
        
        except Exception as e:
            result += f"获取网络信息失败: {e}\n"
        
        return result
    
    def _get_local_ips(self):
        """获取本机所有IP地址"""
        ips = []
        try:
            # 获取主机名对应的IP
            hostname = socket.gethostname()
            ips.append(socket.gethostbyname(hostname))
        except Exception:
            pass
        
        try:
            # 通过连接外部地址获取当前网络接口IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        
        # 获取所有网络接口地址
        try:
            import os
            if os.name == 'nt':
                # Windows系统
                output = os.popen('ipconfig').read()
                for line in output.split('\n'):
                    if 'IPv4 Address' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            ip = parts[1].strip()
                            if ip and not ip.startswith('127.'):
                                ips.append(ip)
            else:
                # Unix/Linux系统
                output = os.popen('ifconfig').read()
                for line in output.split('\n'):
                    if 'inet ' in line and '127.0.0.1' not in line:
                        parts = line.split()
                        if len(parts) > 1:
                            ips.append(parts[1])
        except Exception:
            pass
        
        return list(set(ips))
    
    def check_port_status(self):
        """检查端口状态"""
        port = int(self.port_input.text())
        
        try:
            # 检查端口是否被占用
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 尝试绑定端口
            result = sock.bind(('0.0.0.0', port))
            sock.close()
            
            self.port_status.setText(f"端口 {port} 可用")
            self.port_status.setStyleSheet("color: #4CAF50;")
            
        except socket.error as e:
            if e.errno == 10048:  # 端口已被占用
                self.port_status.setText(f"端口 {port} 已被占用")
                self.port_status.setStyleSheet("color: #f44336;")
            else:
                self.port_status.setText(f"检查失败: {e}")
                self.port_status.setStyleSheet("color: #FF9800;")
    
    def update_network_status(self):
        """更新网络状态"""
        # 测试网络连接
        try:
            # 尝试连接到网关或外部地址
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("8.8.8.8", 53))
            sock.close()
            
            if result == 0:
                self.status_label.setText("网络连接正常")
                self.status_label.setStyleSheet("color: #4CAF50;")
                self.status_icon.setStyleSheet("background: #4CAF50; border-radius: 50%;")
            else:
                self.status_label.setText("网络连接异常")
                self.status_label.setStyleSheet("color: #f44336;")
                self.status_icon.setStyleSheet("background: #f44336; border-radius: 50%;")
                
        except Exception as e:
            self.status_label.setText(f"检查失败: {e}")
            self.status_label.setStyleSheet("color: #FF9800;")
    
    def run_tests(self):
        """运行连接测试"""
        target_ip = self.target_ip.text().strip()
        
        if not target_ip:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请输入目标IP地址")
            return
        
        self.test_btn.setEnabled(False)
        self.test_progress.setValue(0)
        self.test_result_list.clear()
        
        # 在新线程中执行测试
        thread = threading.Thread(
            target=self._run_tests_thread,
            args=(target_ip,),
            daemon=True
        )
        thread.start()
    
    def _run_tests_thread(self, target_ip):
        """在后台线程中执行测试"""
        self.log_test("开始网络连接测试...")
        self.update_progress(10)
        
        # 1. Ping测试
        self.log_test("1. 正在执行Ping测试...")
        ping_result = self.ping_test(target_ip)
        self.test_results['ping'] = ping_result
        self.update_progress(30)
        
        # 2. 端口测试
        self.log_test("2. 正在测试端口连接...")
        port = int(self.port_input.text())
        port_result = self.port_test(target_ip, port)
        self.test_results['port'] = port_result
        self.update_progress(60)
        
        # 3. 服务发现测试
        self.log_test("3. 正在检查服务状态...")
        service_result = self.service_test(target_ip)
        self.test_results['service'] = service_result
        self.update_progress(90)
        
        # 总结
        self.log_test("")
        self.log_test("=== 测试结果总结 ===")
        
        all_passed = True
        if self.test_results.get('ping'):
            self.log_test("[✓] Ping测试: 通过")
        else:
            self.log_test("[✗] Ping测试: 失败")
            all_passed = False
        
        if self.test_results.get('port'):
            self.log_test("[✓] 端口测试: 通过")
        else:
            self.log_test("[✗] 端口测试: 失败")
            all_passed = False
        
        if self.test_results.get('service'):
            self.log_test("[✓] 服务测试: 通过")
        else:
            self.log_test("[✗] 服务测试: 失败")
            all_passed = False
        
        self.log_test("")
        if all_passed:
            self.log_test("所有测试通过！可以进行数据迁移。")
        else:
            self.log_test("部分测试失败，请检查网络连接和目标设备状态。")
        
        self.update_progress(100)
        self.test_btn.setEnabled(True)
    
    def log_test(self, message):
        """记录测试日志"""
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self.test_result_list,
            "append",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, message)
        )
    
    def update_progress(self, value):
        """更新进度条"""
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self.test_progress,
            "setValue",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(int, value)
        )
    
    def ping_test(self, target_ip):
        """执行Ping测试"""
        try:
            # 使用subprocess执行ping命令
            result = subprocess.run(
                ['ping', '-n', '2', '-w', '1000', target_ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            return result.returncode == 0
        except Exception as e:
            return False
    
    def port_test(self, target_ip, port):
        """测试端口是否可连接"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((target_ip, port))
            sock.close()
            
            return result == 0
        except Exception as e:
            return False
    
    def service_test(self, target_ip):
        """检查服务是否可用"""
        # 尝试连接并发送握手信号
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((target_ip, int(self.port_input.text())))
            
            # 发送正确格式的协议消息（HELLO命令）
            from core.protocol import Command, pack_message, create_hello_payload
            
            hello_payload = create_hello_payload("测试客户端", "1.0.0")
            message = pack_message(Command.HELLO, hello_payload)
            sock.sendall(message)
            
            # 等待响应
            sock.settimeout(2)
            response = sock.recv(1024)
            sock.close()
            
            # 检查是否收到响应（响应也是协议格式的消息）
            if len(response) > 0:
                # 尝试解析响应
                from core.protocol import unpack_message
                cmd, payload, _ = unpack_message(response)
                if cmd == Command.HELLO:
                    return True
            return False
        except socket.timeout:
            return False
        except Exception as e:
            return False
    
    def update_ping_progress(self):
        """更新Ping进度"""
        self.ping_progress += 1
        if self.ping_progress > 100:
            self.ping_progress = 0
    
    def apply_config(self):
        """应用配置"""
        from PyQt6.QtWidgets import QMessageBox
        
        try:
            new_port = int(self.port_input.text())
            
            if new_port < 1 or new_port > 65535:
                QMessageBox.warning(self, "提示", "端口号必须在1-65535之间")
                return
            
            # 更新配置
            config.DEFAULT_PORT = new_port
            
            QMessageBox.information(self, "配置已应用", f"端口已更新为 {new_port}")
            
        except ValueError:
            QMessageBox.warning(self, "提示", "请输入有效的端口号")
    
    def showEvent(self, event):
        """页面显示时刷新信息"""
        super().showEvent(event)
        self.refresh_network_info()
