"""
mDNS 设备发现模块
基于 zeroconf 实现局域网内设备自动发现
"""
import socket
import threading
from typing import Dict, Callable, Optional

from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, ServiceListener

import config
from utils.helpers import get_local_ip


class DeviceInfo:
    """设备信息数据类"""
    
    def __init__(self, name: str, ip: str, port: int, device_name: str = "",
                 version: str = "", os_name: str = ""):
        self.name = name          # 服务全名
        self.ip = ip              # IP地址
        self.port = port          # 端口
        self.device_name = device_name  # 设备显示名称
        self.version = version    # 版本号
        self.os_name = os_name    # 操作系统
        self.online = True        # 是否在线
    
    def __repr__(self):
        return f"DeviceInfo({self.device_name}@{self.ip}:{self.port})"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "device_name": self.device_name,
            "version": self.version,
            "os": self.os_name
        }


class DiscoveryListener(ServiceListener):
    """zeroconf 服务监听器"""
    
    def __init__(self, discovery_service: 'DiscoveryService'):
        self.discovery = discovery_service
    
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """发现新服务"""
        info = zc.get_service_info(type_, name)
        if info and info.parsed_addresses():
            # 过滤掉本机
            local_ips = self.discovery._get_local_ips()
            ip = info.parsed_addresses()[0]
            if ip in local_ips and info.port == config.DEFAULT_PORT:
                return
            
            device = DeviceInfo(
                name=name,
                ip=ip,
                port=info.port,
                device_name=info.properties.get(b"device_name", b"").decode("utf-8") or name.split(".")[0],
                version=info.properties.get(b"version", b"").decode("utf-8"),
                os_name=info.properties.get(b"os", b"").decode("utf-8")
            )
            self.discovery._add_device(device)
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """服务离线"""
        self.discovery._remove_device(name)
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """服务更新"""
        self.add_service(zc, type_, name)


class DiscoveryService:
    """
    设备发现服务
    
    封装 zeroconf 服务注册与发现功能
    """
    
    def __init__(self):
        self.zeroconf: Optional[Zeroconf] = None
        self.browser: Optional[ServiceBrowser] = None
        self.service_info: Optional[ServiceInfo] = None
        self.devices: Dict[str, DeviceInfo] = {}  # name -> DeviceInfo
        self._lock = threading.Lock()
        self._callbacks: list = []  # 设备变更回调函数列表
        self._running = False
    
    def _get_local_ips(self) -> list:
        """获取本机所有IP地址"""
        ips = []
        try:
            hostname = socket.gethostname()
            ips.append(socket.gethostbyname(hostname))
        except Exception:
            pass
        
        try:
            # 获取所有网络接口的IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        
        return list(set(ips))
    
    def register_service(self, device_name: str = "") -> bool:
        """
        注册本机服务
        
        Args:
            device_name: 设备显示名称，为空则使用主机名
        
        Returns:
            是否注册成功
        """
        if not device_name:
            device_name = socket.gethostname()
        
        ip = get_local_ip()
        
        # 创建服务信息
        self.service_info = ServiceInfo(
            type_=config.SERVICE_TYPE,
            name=f"{device_name}.{config.SERVICE_TYPE}",
            addresses=[socket.inet_aton(ip)],
            port=config.DEFAULT_PORT,
            properties={
                b"device_name": device_name.encode("utf-8"),
                b"version": config.VERSION.encode("utf-8"),
                b"os": b"windows"
            },
            server=f"{device_name}.local."
        )
        
        try:
            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.service_info)
            return True
        except Exception as e:
            print(f"注册mDNS服务失败: {e}")
            return False
    
    def start_discovery(self) -> bool:
        """
        启动设备发现
        
        Returns:
            是否启动成功
        """
        if self._running:
            return True
        
        try:
            if not self.zeroconf:
                self.zeroconf = Zeroconf()
            
            listener = DiscoveryListener(self)
            self.browser = ServiceBrowser(
                self.zeroconf,
                config.SERVICE_TYPE,
                listener
            )
            self._running = True
            return True
        except Exception as e:
            print(f"启动设备发现失败: {e}")
            return False
    
    def stop(self):
        """停止服务发现和注册"""
        self._running = False
        
        if self.browser:
            self.browser.cancel()
            self.browser = None
        
        if self.service_info and self.zeroconf:
            self.zeroconf.unregister_service(self.service_info)
            self.service_info = None
        
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None
    
    def _add_device(self, device: DeviceInfo):
        """添加设备（内部方法）"""
        with self._lock:
            is_new = device.name not in self.devices
            self.devices[device.name] = device
        
        if is_new:
            self._notify_callbacks("added", device)
        else:
            self._notify_callbacks("updated", device)
    
    def _remove_device(self, name: str):
        """移除设备（内部方法）"""
        with self._lock:
            device = self.devices.pop(name, None)
        
        if device:
            device.online = False
            self._notify_callbacks("removed", device)
    
    def get_devices(self) -> list:
        """
        获取当前发现的所有设备列表
        
        Returns:
            DeviceInfo 列表
        """
        with self._lock:
            return list(self.devices.values())
    
    def get_device_by_ip(self, ip: str) -> Optional[DeviceInfo]:
        """
        根据IP地址获取设备
        
        Args:
            ip: IP地址
        
        Returns:
            DeviceInfo 或 None
        """
        with self._lock:
            for device in self.devices.values():
                if device.ip == ip:
                    return device
            return None
    
    def add_callback(self, callback: Callable[[str, DeviceInfo], None]):
        """
        添加设备变更回调
        
        Args:
            callback: 回调函数，参数为 (event_type, device)
                     event_type: "added", "updated", "removed"
        """
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """移除回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, event_type: str, device: DeviceInfo):
        """通知所有回调（内部方法）"""
        for callback in self._callbacks:
            try:
                callback(event_type, device)
            except Exception as e:
                print(f"回调执行失败: {e}")
