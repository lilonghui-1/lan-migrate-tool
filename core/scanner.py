"""
数据扫描器模块
扫描本机可迁移的数据项，计算大小，生成分类列表
"""
import os
import subprocess
from typing import List, Dict, Optional

import config
from utils.helpers import get_folder_size, count_files


class DataItem:
    """数据项 - 支持多级树形结构"""

    def __init__(self, name: str, path: str, item_type: str = "folder",
                 size: int = 0, count: int = 0, description: str = "", parent=None):
        self.name = name            # 名称
        self.path = path            # 本地路径
        self.item_type = item_type  # 类型：folder, file, registry
        self.size = size            # 大小（字节）
        self.count = count          # 文件数量
        self.description = description  # 描述
        self.selected = True        # 是否被选中
        self.children: List[DataItem] = []  # 子项列表
        self.parent = parent        # 父项引用
        self._expanded = False      # 是否已展开（懒加载用）

    @property
    def is_leaf(self) -> bool:
        """是否为叶子节点（没有子项）"""
        return len(self.children) == 0

    @property
    def selected_size(self) -> int:
        """计算选中状态的总大小（递归）"""
        if not self.selected:
            return 0
        if self.is_leaf:
            return self.size
        total = 0
        for child in self.children:
            total += child.selected_size
        return total

    @property
    def selected_count(self) -> int:
        """计算选中状态的文件数量（递归）"""
        if not self.selected:
            return 0
        if self.is_leaf:
            return self.count
        total = 0
        for child in self.children:
            total += child.selected_count
        return total

    def get_selected_leaves(self) -> List['DataItem']:
        """获取所有选中的叶子节点"""
        if not self.selected:
            return []
        if self.is_leaf:
            return [self]
        leaves = []
        for child in self.children:
            leaves.extend(child.get_selected_leaves())
        return leaves

    def set_selected(self, selected: bool, recursive: bool = True):
        """设置选中状态

        Args:
            selected: 是否选中
            recursive: 是否递归设置子项
        """
        self.selected = selected
        if recursive:
            for child in self.children:
                child.set_selected(selected, recursive=True)

    def update_parent_state(self):
        """根据子项状态更新父项状态（向上传播）"""
        if not self.parent:
            return

        all_selected = all(child.selected for child in self.parent.children)
        any_selected = any(child.selected for child in self.parent.children)

        if all_selected:
            self.parent.selected = True
        elif any_selected:
            self.parent.selected = True  # 部分选中时仍标记为True，由UI显示部分选中状态
        else:
            self.parent.selected = False

        # 继续向上传播
        self.parent.update_parent_state()

    def add_child(self, child: 'DataItem'):
        """添加子项"""
        child.parent = self
        self.children.append(child)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "path": self.path,
            "type": self.item_type,
            "size": self.size,
            "count": self.count,
            "description": self.description
        }


class DataCategory:
    """数据分类"""

    def __init__(self, name: str, display_name: str, description: str = ""):
        self.name = name            # 分类标识名
        self.display_name = display_name  # 显示名称
        self.description = description    # 描述
        self.items: List[DataItem] = []   # 数据项列表
        self.selected = True        # 是否全选

    @property
    def total_size(self) -> int:
        """分类总大小（只计算选中的叶子节点）"""
        total = 0
        for item in self.items:
            total += item.selected_size
        return total

    @property
    def total_count(self) -> int:
        """分类总文件数（只计算选中的叶子节点）"""
        total = 0
        for item in self.items:
            total += item.selected_count
        return total

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "size": self.total_size,
            "count": self.total_count,
            "items": [item.to_dict() for item in self.items]
        }


class DataScanner:
    """
    数据扫描器

    扫描并分类本地可迁移数据
    """

    def __init__(self):
        self.categories: List[DataCategory] = []
        self._scanned = False

    def scan_all(self) -> List[DataCategory]:
        """
        扫描所有可迁移数据

        Returns:
            数据分类列表
        """
        self.categories = []

        # 扫描用户文件夹
        user_folders = self.scan_user_folders()
        if user_folders.items:
            self.categories.append(user_folders)

        # 扫描浏览器数据
        browser_data = self.scan_browser_data()
        if browser_data.items:
            self.categories.append(browser_data)

        # 扫描应用数据
        app_data = self.scan_appdata()
        if app_data.items:
            self.categories.append(app_data)

        # 扫描C盘其他数据
        c_drive_data = self.scan_c_drive_data()
        if c_drive_data.items:
            self.categories.append(c_drive_data)

        # 扫描注册表
        registry_data = self.scan_registry()
        if registry_data.items:
            self.categories.append(registry_data)

        # 扫描Windows凭据数据
        credential_data = self.scan_windows_credentials()
        if credential_data.items:
            self.categories.append(credential_data)

        self._scanned = True
        return self.categories

    def scan_user_folders(self) -> DataCategory:
        """
        扫描用户文件夹

        Returns:
            用户文件夹数据分类
        """
        category = DataCategory(
            name="user_folders",
            display_name="用户文件夹",
            description="文档、桌面、下载等个人文件"
        )

        user_profile = os.environ.get("USERPROFILE", "")
        if not user_profile:
            return category

        for folder_name, display_name in config.USER_FOLDERS:
            folder_path = os.path.join(user_profile, folder_name)
            if os.path.exists(folder_path):
                size = get_folder_size(folder_path)
                count = count_files(folder_path)
                if size > 0:
                    item = DataItem(
                        name=folder_name,
                        path=folder_path,
                        item_type="folder",
                        size=size,
                        count=count,
                        description=display_name
                    )
                    category.items.append(item)

        return category

    def scan_browser_data(self) -> DataCategory:
        """
        扫描浏览器数据

        Returns:
            浏览器数据分类
        """
        category = DataCategory(
            name="browser_data",
            display_name="浏览器数据",
            description="书签、历史记录、密码、扩展等"
        )

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        roaming_app_data = os.environ.get("APPDATA", "")

        for browser_name, browser_config in config.BROWSERS.items():
            if browser_config["local"]:
                base_path = local_app_data
            else:
                base_path = roaming_app_data

            browser_path = os.path.join(base_path, browser_config["path"])
            if os.path.exists(browser_path):
                size = get_folder_size(browser_path)
                count = count_files(browser_path)
                if size > 0:
                    # 检查浏览器是否正在运行
                    running = self._is_process_running(browser_config["processes"])
                    description = browser_name
                    if running:
                        description += " (正在运行，请先关闭)"

                    item = DataItem(
                        name=browser_name,
                        path=browser_path,
                        item_type="folder",
                        size=size,
                        count=count,
                        description=description
                    )
                    if running:
                        item.selected = False
                    category.items.append(item)

        return category

    def scan_appdata(self) -> DataCategory:
        """
        扫描应用数据

        Returns:
            应用数据分类
        """
        category = DataCategory(
            name="app_data",
            display_name="应用数据",
            description="应用程序的配置和缓存数据"
        )

        roaming = os.environ.get("APPDATA", "")
        local = os.environ.get("LOCALAPPDATA", "")

        # Roaming 应用数据
        if roaming and os.path.exists(roaming):
            size = get_folder_size(roaming)
            count = count_files(roaming)
            if size > 0:
                item = DataItem(
                    name="Roaming",
                    path=roaming,
                    item_type="folder",
                    size=size,
                    count=count,
                    description="漫游应用数据"
                )
                category.items.append(item)

        # Local 应用数据
        if local and os.path.exists(local):
            size = get_folder_size(local)
            count = count_files(local)
            if size > 0:
                item = DataItem(
                    name="Local",
                    path=local,
                    item_type="folder",
                    size=size,
                    count=count,
                    description="本地应用数据"
                )
                category.items.append(item)

        return category

    def scan_c_drive_data(self) -> DataCategory:
        """
        扫描C盘其他数据

        Returns:
            C盘数据分类
        """
        category = DataCategory(
            name="c_drive_data",
            display_name="C盘其他数据",
            description="公共文件夹、程序数据等C盘上的其他数据"
        )

        # 公共文件夹
        public_path = os.environ.get("PUBLIC", "")
        if public_path and os.path.exists(public_path):
            # 公共文档
            public_documents = os.path.join(public_path, "Documents")
            if os.path.exists(public_documents):
                size = get_folder_size(public_documents)
                count = count_files(public_documents)
                if size > 0:
                    item = DataItem(
                        name="PublicDocuments",
                        path=public_documents,
                        item_type="folder",
                        size=size,
                        count=count,
                        description="公共文档"
                    )
                    category.items.append(item)

            # 公共桌面
            public_desktop = os.path.join(public_path, "Desktop")
            if os.path.exists(public_desktop):
                size = get_folder_size(public_desktop)
                count = count_files(public_desktop)
                if size > 0:
                    item = DataItem(
                        name="PublicDesktop",
                        path=public_desktop,
                        item_type="folder",
                        size=size,
                        count=count,
                        description="公共桌面"
                    )
                    category.items.append(item)

            # 公共下载
            public_downloads = os.path.join(public_path, "Downloads")
            if os.path.exists(public_downloads):
                size = get_folder_size(public_downloads)
                count = count_files(public_downloads)
                if size > 0:
                    item = DataItem(
                        name="PublicDownloads",
                        path=public_downloads,
                        item_type="folder",
                        size=size,
                        count=count,
                        description="公共下载"
                    )
                    category.items.append(item)

        # ProgramData 文件夹
        program_data = os.environ.get("PROGRAMDATA", "")
        if program_data and os.path.exists(program_data):
            size = get_folder_size(program_data)
            count = count_files(program_data)
            if size > 0:
                item = DataItem(
                    name="ProgramData",
                    path=program_data,
                    item_type="folder",
                    size=size,
                    count=count,
                    description="程序数据 (ProgramData)"
                )
                # 默认不选中，因为这通常包含系统程序数据
                item.selected = False
                category.items.append(item)

        # 直接扫描C盘根目录下的常见用户数据目录
        c_drive = "C:\\"

        # OneDrive 目录（如果存在）
        user_profile = os.environ.get("USERPROFILE", "")
        if user_profile:
            onedrive_path = os.path.join(user_profile, "OneDrive")
            if os.path.exists(onedrive_path):
                size = get_folder_size(onedrive_path)
                count = count_files(onedrive_path)
                if size > 0:
                    item = DataItem(
                        name="OneDrive",
                        path=onedrive_path,
                        item_type="folder",
                        size=size,
                        count=count,
                        description="OneDrive 云存储"
                    )
                    category.items.append(item)

        return category

    def scan_registry(self) -> DataCategory:
        """
        扫描注册表设置

        Returns:
            注册表数据分类
        """
        category = DataCategory(
            name="registry",
            display_name="注册表设置",
            description="用户级软件注册表配置"
        )

        # 注册表数据比较特殊，我们创建一个虚拟项
        # 实际导出会在传输时进行
        item = DataItem(
            name="UserRegistry",
            path=r"HKEY_CURRENT_USER\Software",
            item_type="registry",
            size=0,  # 大小不确定，传输时计算
            count=0,
            description="用户软件设置"
        )
        category.items.append(item)

        return category

    def scan_windows_credentials(self) -> DataCategory:
        """
        扫描Windows凭据数据

        Returns:
            凭据数据分类
        """
        category = DataCategory(
            name="credentials",
            display_name="Windows凭据",
            description="凭据管理器、证书、WLAN配置等敏感数据"
        )

        roaming = os.environ.get("APPDATA", "")
        local = os.environ.get("LOCALAPPDATA", "")

        # 定义要扫描的凭据路径
        credential_paths = [
            {
                "name": "UserCredentials",
                "path": os.path.join(roaming, "Microsoft", "Credentials"),
                "description": "用户凭据存储",
                "selected": False
            },
            {
                "name": "LocalCredentials",
                "path": os.path.join(local, "Microsoft", "Credentials"),
                "description": "本地凭据存储",
                "selected": False
            },
            {
                "name": "UserCertificates",
                "path": os.path.join(roaming, "Microsoft", "SystemCertificates", "My", "Certificates"),
                "description": "用户证书",
                "selected": False
            },
            {
                "name": "WLANProfiles",
                "path": os.path.join(roaming, "Microsoft", "WlanSvc", "Profiles", "Interfaces"),
                "description": "WLAN无线配置文件",
                "selected": True
            },
            {
                "name": "IEPasswords",
                "path": os.path.join(roaming, "Microsoft", "Internet Explorer", "IntelliForms", "Storage2"),
                "description": "IE/Edge浏览器密码",
                "selected": False
            }
        ]

        # 扫描所有凭据路径
        for cred_info in credential_paths:
            path = cred_info["path"]
            if not os.path.exists(path):
                continue

            try:
                size = self._get_folder_size_safe(path)
                count = self._count_files_safe(path)

                if size > 0 or count > 0:
                    item = DataItem(
                        name=cred_info["name"],
                        path=path,
                        item_type="folder",
                        size=size,
                        count=count,
                        description=cred_info["description"]
                    )
                    item.selected = cred_info["selected"]
                    category.items.append(item)
            except PermissionError:
                # 跳过需要管理员权限的目录
                continue
            except Exception as e:
                print(f"扫描凭据路径失败 {path}: {e}")
                continue

        return category

    def _scan_directory_recursive(self, path: str, name: str = None, max_depth: int = 2, current_depth: int = 0) -> Optional[DataItem]:
        """递归扫描目录，构建多级树形结构

        Args:
            path: 目录路径
            name: 显示名称（默认使用目录名）
            max_depth: 最大递归深度
            current_depth: 当前深度

        Returns:
            DataItem 对象，如果目录不存在或为空则返回 None
        """
        if not os.path.exists(path) or not os.path.isdir(path):
            return None

        if name is None:
            name = os.path.basename(path)

        size = get_folder_size(path)
        count = count_files(path)

        item = DataItem(
            name=name,
            path=path,
            item_type="folder",
            size=size,
            count=count,
            description=name
        )

        # 如果未达到最大深度，递归扫描子目录
        if current_depth < max_depth:
            try:
                entries = os.listdir(path)
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    if os.path.isdir(full_path):
                        # 跳过系统目录
                        if entry.startswith('$') or entry.startswith('.') or entry in ['System Volume Information']:
                            continue
                        child = self._scan_directory_recursive(
                            full_path, entry, max_depth, current_depth + 1
                        )
                        if child:
                            item.add_child(child)
            except (PermissionError, OSError):
                pass

        return item

    def _get_folder_size_safe(self, folder_path: str) -> int:
        """
        安全地计算文件夹大小（跳过无权限的文件和系统文件）

        Args:
            folder_path: 文件夹路径

        Returns:
            总字节数
        """
        total = 0
        blacklist_dirs = ['$RECYCLE.BIN', 'System Volume Information', '$Recycle.Bin']
        blacklist_files = ['desktop.ini', 'thumbs.db', '.DS_Store']

        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                # 跳过黑名单目录
                dirnames[:] = [d for d in dirnames if d not in blacklist_dirs]

                for f in filenames:
                    # 跳过黑名单文件
                    if f.lower() in [bf.lower() for bf in blacklist_files]:
                        continue

                    fp = os.path.join(dirpath, f)
                    try:
                        if os.path.exists(fp):
                            total += os.path.getsize(fp)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass
        return total

    def _count_files_safe(self, folder_path: str) -> int:
        """
        安全地计算文件数量（跳过无权限的目录和系统文件）

        Args:
            folder_path: 文件夹路径

        Returns:
            文件数量
        """
        count = 0
        blacklist_dirs = ['$RECYCLE.BIN', 'System Volume Information', '$Recycle.Bin']
        blacklist_files = ['desktop.ini', 'thumbs.db', '.DS_Store']

        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                # 跳过黑名单目录
                dirnames[:] = [d for d in dirnames if d not in blacklist_dirs]

                # 统计时排除黑名单文件
                filtered_files = [f for f in filenames if f.lower() not in [bf.lower() for bf in blacklist_files]]
                count += len(filtered_files)
        except (PermissionError, OSError):
            pass
        return count

    def _is_process_running(self, process_names: List[str]) -> bool:
        """
        检查进程是否正在运行

        Args:
            process_names: 进程名称列表

        Returns:
            是否有进程在运行
        """
        try:
            for proc_name in process_names:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc_name}"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if proc_name.lower() in result.stdout.lower():
                    return True
        except Exception:
            pass
        return False

    def get_summary(self) -> Dict[str, any]:
        """
        获取扫描汇总信息

        Returns:
            汇总字典
        """
        total_size = sum(cat.total_size for cat in self.categories)
        total_count = sum(cat.total_count for cat in self.categories)
        selected_categories = [cat for cat in self.categories if cat.selected]

        return {
            "total_size": total_size,
            "total_count": total_count,
            "category_count": len(self.categories),
            "categories": [cat.to_dict() for cat in self.categories]
        }

    def get_selected_items(self) -> List[DataItem]:
        """
        获取所有选中的叶子节点数据项

        Returns:
            选中的数据项列表（仅叶子节点）
        """
        items = []
        for category in self.categories:
            for item in category.items:
                items.extend(item.get_selected_leaves())
        return items
