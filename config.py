"""
全局配置文件
"""

# 应用信息
APP_NAME = "LAN迁移工具"
VERSION = "1.0.0"

# 网络配置
SERVICE_TYPE = "_filetransfer._tcp.local."
DEFAULT_PORT = 9000

# 传输配置
CHUNK_SIZE = 65536              # 64KB，常规传输块大小
RESUME_CHUNK_SIZE = 4194304     # 4MB，断点续传分块大小
MAX_RETRIES = 3                 # 最大重试次数
SOCKET_TIMEOUT = 30             # socket超时时间（秒）

# 数据库配置
DB_NAME = "transfer_state.db"

# 浏览器配置
BROWSERS = {
    "Chrome": {
        "path": r"Google\Chrome\User Data",
        "local": True,
        "processes": ["chrome.exe"]
    },
    "Edge": {
        "path": r"Microsoft\Edge\User Data",
        "local": True,
        "processes": ["msedge.exe"]
    },
    "Firefox": {
        "path": r"Mozilla\Firefox\Profiles",
        "local": False,
        "processes": ["firefox.exe"]
    }
}

# 用户文件夹配置
USER_FOLDERS = [
    ("Documents", "文档"),
    ("Desktop", "桌面"),
    ("Downloads", "下载"),
    ("Pictures", "图片"),
    ("Videos", "视频"),
    ("Music", "音乐"),
]

# 注册表配置
REGISTRY_ROOT = r"Software"
