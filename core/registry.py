"""
Windows 注册表操作模块
安全地导出和导入用户级注册表设置
"""
import os
import tempfile
import subprocess
from typing import List, Optional

import winreg


class RegistryManager:
    """
    注册表管理器
    
    仅操作 HKEY_CURRENT_USER，确保安全
    """
    
    # 常见软件注册表路径
    COMMON_SOFTWARE_KEYS = [
        r"Software\Microsoft\Windows\CurrentVersion\Explorer",
        r"Software\Microsoft\Internet Explorer",
        r"Software\Microsoft\Office",
        r"Software\Google",
        r"Software\Mozilla",
        r"Software\Notepad++",
        r"Software\Sublime Text",
        r"Software\JetBrains",
        r"Software\Microsoft\Windows\CurrentVersion\Run",
    ]
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    def list_software_keys(self) -> List[dict]:
        """
        枚举 HKCU\Software 下的软件项
        
        Returns:
            软件项列表，每项包含 name 和 path
        """
        software_list = []
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software") as key:
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        subkey_path = f"Software\\{subkey_name}"
                        software_list.append({
                            "name": subkey_name,
                            "path": subkey_path
                        })
                        index += 1
                    except OSError:
                        break
        except Exception as e:
            print(f"枚举注册表失败: {e}")
        
        return software_list
    
    def export_registry_key(self, key_path: str, output_file: str) -> bool:
        """
        导出指定注册表项到 .reg 文件
        
        Args:
            key_path: 注册表路径（相对于 HKCU）
            output_file: 输出文件路径
        
        Returns:
            是否导出成功
        """
        try:
            full_path = f"HKEY_CURRENT_USER\\{key_path}"
            result = subprocess.run(
                ["reg", "export", full_path, output_file, "/y"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception as e:
            print(f"导出注册表失败 {key_path}: {e}")
            return False
    
    def export_all_software(self, output_dir: str) -> List[str]:
        """
        导出所有软件注册表设置
        
        Args:
            output_dir: 输出目录
        
        Returns:
            导出的 .reg 文件路径列表
        """
        exported_files = []
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 导出整个 Software 键
        main_file = os.path.join(output_dir, "software.reg")
        if self.export_registry_key("Software", main_file):
            exported_files.append(main_file)
        
        return exported_files
    
    def import_registry_file(self, reg_file: str) -> bool:
        """
        导入 .reg 文件到注册表
        
        Args:
            reg_file: .reg 文件路径
        
        Returns:
            是否导入成功
        """
        if not os.path.exists(reg_file):
            print(f"注册表文件不存在: {reg_file}")
            return False
        
        try:
            result = subprocess.run(
                ["reg", "import", reg_file],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return True
            else:
                print(f"导入注册表失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"导入注册表异常: {e}")
            return False
    
    def read_registry_value(self, key_path: str, value_name: str) -> Optional[any]:
        """
        读取注册表值
        
        Args:
            key_path: 注册表路径（相对于 HKCU）
            value_name: 值名称
        
        Returns:
            注册表值，失败返回 None
        """
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value
        except Exception:
            return None
    
    def write_registry_value(self, key_path: str, value_name: str,
                              value: any, value_type: int = winreg.REG_SZ) -> bool:
        """
        写入注册表值
        
        Args:
            key_path: 注册表路径（相对于 HKCU）
            value_name: 值名称
            value: 值数据
            value_type: 值类型
        
        Returns:
            是否写入成功
        """
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, value_name, 0, value_type, value)
                return True
        except Exception as e:
            print(f"写入注册表失败: {e}")
            return False
    
    def get_registry_size_estimate(self, key_path: str = "Software") -> int:
        """
        估算注册表项大小
        
        Args:
            key_path: 注册表路径
        
        Returns:
        估算大小（字节）
        """
        # 注册表大小难以精确计算，这里返回一个估算值
        # 实际导出后才能知道准确大小
        return 1024 * 1024  # 估算 1MB
