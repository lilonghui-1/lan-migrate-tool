"""
全局配置文件
"""

# 应用信息
APP_NAME = "LAN迁移工具"
VERSION = "1.0.0"

# 调试配置
DEBUG = True  # 启用调试模式
DEBUG_LOG_FILE = "transfer_debug.log"  # 调试日志文件

# 网络配置
SERVICE_TYPE = "_filetransfer._tcp.local."
DEFAULT_PORT = 9000

# 传输配置
CHUNK_SIZE = 524288               # 512KB，增大常规传输块大小以提高吞吐量
RESUME_CHUNK_SIZE = 33554432      # 32MB，大幅增大断点续传分块大小
MAX_RETRIES = 1                   # 减少重试次数
SOCKET_TIMEOUT = 600              # socket超时时间增加到10分钟
FILE_MAX_RETRIES = 0              # 取消单个文件重试，由上层管理

# 心跳配置
HEARTBEAT_INTERVAL = 30           # 心跳间隔增大到30秒，减少网络开销
HEARTBEAT_TIMEOUT = 120           # 心跳超时时间增加到2分钟

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
