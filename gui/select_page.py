"""
数据选择页面
支持多级树形结构、目标目录选择、添加目录功能
"""
import os
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QSplitter, QTextEdit, QMessageBox,
    QFileDialog, QFrame, QAbstractItemView, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QMetaObject, Q_ARG
from PyQt6.QtGui import QFont, QIcon

from core.scanner import DataScanner, DataCategory, DataItem
from utils.helpers import format_size


class CheckableTreeItem(QTreeWidgetItem):
    """可勾选的树形项，支持多级树形结构"""

    def __init__(self, parent=None, data_item=None):
        super().__init__(parent)
        self.data_item = data_item
        # 启用用户可勾选和自动三态
        self.setFlags(
            self.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsAutoTristate
        )
        if data_item:
            self.setCheckState(0, Qt.CheckState.Checked if data_item.selected else Qt.CheckState.Unchecked)
        else:
            self.setCheckState(0, Qt.CheckState.Checked)


class SelectPage(QWidget):
    """数据选择页面"""

    # 信号：开始传输，传递选中的数据项列表、目标目录、任务ID
    transfer_started = pyqtSignal(list, str, str)
    back_requested = pyqtSignal()  # 返回上一页

    # 内部信号，用于线程间通信
    _scan_finished = pyqtSignal(list)  # 扫描完成信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = DataScanner()
        self._scanning = False  # 扫描状态标志
        self.pending_task_info = None  # 待恢复的任务
        self._updating_check = False  # 防止递归更新勾选状态
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题
        title = QLabel("选择要迁移的数据")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 说明
        self.desc_label = QLabel("正在扫描本地数据...")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setStyleSheet("color: #666;")
        layout.addWidget(self.desc_label)

        # 目标目录选择区域
        target_layout = QHBoxLayout()
        target_label = QLabel("目标目录:")
        target_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        target_layout.addWidget(target_label)

        self.target_dir_edit = QLineEdit()
        self.target_dir_edit.setPlaceholderText("选择目标设备上的保存位置（可选）")
        self.target_dir_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 5px;
                background: white;
            }
        """)
        target_layout.addWidget(self.target_dir_edit, stretch=1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: #607D8B;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #455A64;
            }
        """)
        target_layout.addWidget(self.browse_btn)

        layout.addLayout(target_layout)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：数据树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["数据项", "大小", "数量", "描述"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 60)
        self.tree.setIndentation(20)
        self.tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectItems)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
            }
            QTreeWidget::item {
                padding: 5px;
                color: #333;
            }
            QTreeWidget::item:selected {
                background: #1a1a1a;
                color: white;
            }
            QTreeWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.tree.setMinimumWidth(400)
        splitter.addWidget(self.tree)

        # 右侧：详情面板
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)

        detail_title = QLabel("详细信息")
        detail_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        detail_layout.addWidget(detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: #f9f9f9;
                padding: 10px;
            }
        """)
        detail_layout.addWidget(self.detail_text)

        splitter.addWidget(detail_widget)
        splitter.setSizes([500, 300])

        layout.addWidget(splitter)

        # 统计信息
        self.stats_label = QLabel("已选择: 0 项, 总计: 0 B")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2196F3;
                padding: 10px;
                background: #e3f2fd;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.stats_label)

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

        self.scan_btn = QPushButton("重新扫描")
        self.scan_btn.setStyleSheet("""
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
        btn_layout.addWidget(self.scan_btn)

        self.add_dir_btn = QPushButton("添加目录")
        self.add_dir_btn.setStyleSheet("""
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
        btn_layout.addWidget(self.add_dir_btn)

        self.resume_btn = QPushButton("继续上次传输")
        self.resume_btn.setStyleSheet("""
            QPushButton {
                background: #FF5722;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #F4511E;
            }
        """)
        self.resume_btn.hide()  # 默认隐藏，有未完成任务时才显示
        btn_layout.addWidget(self.resume_btn)

        self.start_btn = QPushButton("开始迁移")
        self.start_btn.setStyleSheet("""
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
        """)
        btn_layout.addWidget(self.start_btn)

        layout.addLayout(btn_layout)

    def setup_connections(self):
        """设置信号连接"""
        self.scan_btn.clicked.connect(self.scan_data)
        self.start_btn.clicked.connect(self.start_transfer)
        self.resume_btn.clicked.connect(self.resume_transfer)
        self.back_btn.clicked.connect(self.back_requested)
        self.add_dir_btn.clicked.connect(self.add_directory)
        self.browse_btn.clicked.connect(self.browse_target_dir)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemChanged.connect(self.on_item_changed)
        # 扫描完成信号连接
        self._scan_finished.connect(self._on_scan_finished)

    def browse_target_dir(self):
        """浏览选择目标目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择目标保存目录",
            os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            self.target_dir_edit.setText(dir_path)

    def scan_data(self):
        """扫描数据（在后台线程中执行）"""
        if self._scanning:
            return

        self._scanning = True
        self.scan_btn.setEnabled(False)
        self.add_dir_btn.setEnabled(False)
        self.desc_label.setText("正在扫描本地数据，请稍候...")
        self.tree.clear()

        # 在后台线程中执行扫描
        thread = threading.Thread(target=self._scan_worker, daemon=True)
        thread.start()

    def _scan_worker(self):
        """扫描工作线程"""
        try:
            # 执行扫描
            categories = self.scanner.scan_all()
        except Exception as e:
            categories = []

        # 发送扫描完成信号
        self._scan_finished.emit(categories)

    def _on_scan_finished(self, categories):
        """扫描完成处理（在主线程中执行）"""
        # 填充树
        for category in categories:
            self.add_category_to_tree(category)

        # 更新统计
        self.update_stats()

        summary = self.scanner.get_summary()
        self.desc_label.setText(
            f"扫描完成，发现 {summary['category_count']} 类数据，"
            f"共 {format_size(summary['total_size'])}"
        )

        self._scanning = False
        self.scan_btn.setEnabled(True)
        self.add_dir_btn.setEnabled(True)

    def add_directory(self):
        """添加自定义目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择要迁移的目录",
            os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly
        )

        if not dir_path:
            return

        # 检查目录是否已存在
        exists = False
        for category in self.scanner.categories:
            for item in category.items:
                if item.path == dir_path:
                    exists = True
                    break
                # 也检查子项
                for leaf in item.get_selected_leaves():
                    if leaf.path == dir_path:
                        exists = True
                        break
                if exists:
                    break
            if exists:
                break

        if exists:
            QMessageBox.information(self, "提示", "该目录已存在于列表中")
            return

        # 使用递归扫描构建多级树
        item = self.scanner._scan_directory_recursive(dir_path, max_depth=2)

        if not item:
            QMessageBox.warning(self, "提示", "无法读取该目录或目录为空")
            return

        # 查找或创建自定义分类
        custom_category = None
        for category in self.scanner.categories:
            if category.name == "custom_dirs":
                custom_category = category
                break

        if not custom_category:
            custom_category = DataCategory(
                name="custom_dirs",
                display_name="自定义目录",
                description="手动添加的目录"
            )
            self.scanner.categories.append(custom_category)

        custom_category.items.append(item)

        # 如果分类还没在树中，添加分类
        cat_exists = False
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            cat_data = top_item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(cat_data, DataCategory) and cat_data.name == "custom_dirs":
                cat_exists = True
                self.add_item_to_tree(top_item, item)
                top_item.setExpanded(True)
                break

        if not cat_exists:
            self.add_category_to_tree(custom_category)

        # 更新统计
        self.update_stats()

        QMessageBox.information(
            self,
            "添加成功",
            f"已成功添加目录: {os.path.basename(dir_path)}\n"
            f"大小: {format_size(item.size)}\n"
            f"文件数: {item.count}"
        )

    def add_category_to_tree(self, category: DataCategory):
        """添加分类到树"""
        cat_item = CheckableTreeItem(self.tree)
        cat_item.setText(0, category.display_name)
        cat_item.setText(1, format_size(category.total_size))
        cat_item.setText(2, str(category.total_count))
        cat_item.setText(3, category.description)
        cat_item.setData(0, Qt.ItemDataRole.UserRole, category)
        cat_item.setExpanded(True)

        # 添加子项
        for item in category.items:
            self.add_item_to_tree(cat_item, item)

    def add_item_to_tree(self, parent: QTreeWidgetItem, item: DataItem):
        """递归添加数据项到树"""
        tree_item = CheckableTreeItem(parent, item)
        tree_item.setText(0, item.name)
        tree_item.setText(1, format_size(item.size))
        tree_item.setText(2, str(item.count))
        tree_item.setText(3, item.description)
        tree_item.setData(0, Qt.ItemDataRole.UserRole, item)

        # 如果有子项，递归添加
        for child in item.children:
            self.add_item_to_tree(tree_item, child)

    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        """树项状态变更（勾选状态变化）"""
        if column != 0:
            return
        if self._updating_check:
            return

        self._updating_check = True
        try:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            check_state = item.checkState(0)
            is_checked = check_state == Qt.CheckState.Checked
            is_partial = check_state == Qt.CheckState.PartiallyChecked

            if isinstance(data, DataCategory):
                # 分类变更，更新所有子项
                data.selected = is_checked or is_partial
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, check_state)
                    # 递归更新子项的数据对象
                    self._update_data_item_check_state(child, is_checked)

            elif isinstance(data, DataItem):
                # 子项变更，递归更新所有子项
                self._update_data_item_check_state(item, is_checked)

                # 向上更新父项状态
                self._update_parent_check_state(item)

            self.update_stats()
        finally:
            self._updating_check = False

    def _update_data_item_check_state(self, tree_item: QTreeWidgetItem, checked: bool):
        """递归更新数据对象的选中状态"""
        data = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, DataItem):
            data.selected = checked
            # 递归更新子项
            for i in range(tree_item.childCount()):
                child = tree_item.child(i)
                child.setCheckState(
                    0,
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
                self._update_data_item_check_state(child, checked)

    def _update_parent_check_state(self, tree_item: QTreeWidgetItem):
        """向上更新父项的勾选状态"""
        parent = tree_item.parent()
        if not parent:
            return

        # 检查所有兄弟项的状态
        all_checked = True
        any_checked = False
        any_partial = False

        for i in range(parent.childCount()):
            sibling = parent.child(i)
            state = sibling.checkState(0)
            if state == Qt.CheckState.Checked:
                any_checked = True
            elif state == Qt.CheckState.PartiallyChecked:
                any_partial = True
                any_checked = True
            else:
                all_checked = False

        # 设置父项状态
        if all_checked and any_checked:
            parent.setCheckState(0, Qt.CheckState.Checked)
        elif any_checked or any_partial:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        else:
            parent.setCheckState(0, Qt.CheckState.Unchecked)

        # 更新父项的数据对象
        parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(parent_data, DataCategory):
            parent_data.selected = any_checked or any_partial
        elif isinstance(parent_data, DataItem):
            parent_data.selected = any_checked or any_partial

        # 继续向上更新
        self._update_parent_check_state(parent)

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """点击树项 - 显示详细信息"""
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if isinstance(data, DataItem):
            # 计算选中状态的大小
            selected_size = data.selected_size
            selected_count = data.selected_count

            info = f"""
<b>名称:</b> {data.name}<br>
<b>路径:</b> {data.path}<br>
<b>类型:</b> {data.item_type}<br>
<b>总大小:</b> {format_size(data.size)}<br>
<b>总文件数:</b> {data.count}<br>
<b>选中大小:</b> {format_size(selected_size)}<br>
<b>选中文件数:</b> {selected_count}<br>
<b>描述:</b> {data.description}<br>
<b>子目录数:</b> {len(data.children)}
            """.strip()
            self.detail_text.setHtml(info)

        elif isinstance(data, DataCategory):
            info = f"""
<b>分类:</b> {data.display_name}<br>
<b>描述:</b> {data.description}<br>
<b>总大小:</b> {format_size(data.total_size)}<br>
<b>总文件数:</b> {data.total_count}<br>
<b>包含项:</b> {len(data.items)}
            """.strip()
            self.detail_text.setHtml(info)

    def update_stats(self):
        """更新统计信息（只统计叶子节点）"""
        selected_items = self.scanner.get_selected_items()
        total_size = sum(item.size for item in selected_items)

        self.stats_label.setText(
            f"已选择: {len(selected_items)} 项, 总计: {format_size(total_size)}"
        )

    def start_transfer(self):
        """开始传输"""
        selected_items = self.scanner.get_selected_items()

        if not selected_items:
            QMessageBox.warning(self, "提示", "请至少选择一项数据进行迁移")
            return

        # 检查是否有浏览器正在运行
        browser_items = [item for item in selected_items
                        if "browser" in item.path.lower() or
                        any(b in item.name for b in ["Chrome", "Edge", "Firefox"])]

        for item in browser_items:
            if "正在运行" in item.description:
                reply = QMessageBox.question(
                    self,
                    "浏览器正在运行",
                    f"{item.name} 似乎正在运行。迁移浏览器数据前需要关闭浏览器，是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

        # 获取目标目录
        target_dir = self.target_dir_edit.text().strip()

        # 转换为字典列表
        items_dict = [item.to_dict() for item in selected_items]
        self.transfer_started.emit(items_dict, target_dir, "")  # 新任务，task_id 为空

    def set_pending_task_info(self, task_info: dict):
        """设置待恢复的任务信息"""
        self.pending_task_info = task_info
        if task_info:
            self.resume_btn.show()
        else:
            self.resume_btn.hide()

    def resume_transfer(self):
        """继续上次未完成的传输"""
        if not self.pending_task_info:
            QMessageBox.warning(self, "提示", "没有待恢复的任务")
            return

        # 发送恢复传输信号
        task_id = self.pending_task_info["task_id"]
        items = self.pending_task_info["items"]
        target_dir = self.pending_task_info.get("target_dir", "")

        # 清空待恢复任务
        self.pending_task_info = None
        self.resume_btn.hide()

        # 开始恢复传输，传递 task_id 用于断点续传
        self.transfer_started.emit(items, target_dir, task_id)

    def showEvent(self, event):
        """页面显示事件"""
        super().showEvent(event)
        # 取消自动扫描，用户需要手动点击扫描按钮
