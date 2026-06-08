"""
LAN迁移工具 - 程序入口

基于 Python + PyQt6 的 Windows 局域网文件迁移工具
支持新旧电脑之间的完整数据迁移
"""
import sys
import os

# 确保可以导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import config
from gui.main_window import MainWindow


def main():
    """程序主入口"""
    import traceback
    
    try:
        print(f"[DEBUG] 程序启动，版本: {config.VERSION}")
        print(f"[DEBUG] Python路径: {sys.executable}")
        print(f"[DEBUG] 当前工作目录: {os.getcwd()}")
        
        # 启用高DPI支持
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            print("[DEBUG] 启用高DPI缩放")
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            print("[DEBUG] 启用高DPI图片")
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        # 创建应用
        print("[DEBUG] 创建QApplication")
        app = QApplication(sys.argv)
        app.setApplicationName(config.APP_NAME)
        app.setApplicationVersion(config.VERSION)
        
        # 设置全局字体
        print("[DEBUG] 设置全局字体")
        font = QFont("Microsoft YaHei", 10)
        app.setFont(font)
        
        # 创建并显示主窗口
        print("[DEBUG] 创建主窗口")
        window = MainWindow()
        print("[DEBUG] 显示主窗口")
        window.show()
        
        # 运行应用
        print("[DEBUG] 启动事件循环")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"[ERROR] 程序启动失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
