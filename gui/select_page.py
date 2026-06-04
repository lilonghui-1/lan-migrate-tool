"""
数据选择页面
"""
import os
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QSplitter, QTextEdit, QMessageBox,
    QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QMetaObject, Q_ARG
from PyQt6.QtGui import QFont

from core.scanner import DataScanner, DataCategory, DataItem
from utils.helpers import format_size


class SelectPage(QWidget):
    """数据选择页面"""
    
    # 信号
    transfer_started = pyqtSignal(list)  # 开始传输，传递选中的数据项列表
    back_requested = pyqtSignal()  # 返回上一页
    
    # 内部信号，用于线程间通信
    _scan_finished = pyqtSignal(list)  # 扫描完成信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = DataScanner()
        self._scanning = False  # 扫描状态标志
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
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：数据树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["数据项", "大小", "数量", "描述"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 60)
        # 确保复选框可以正常工作
        self.tree.setIndentation(20)
        # 设置选择行为，确保点击可以触发复选框
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
        self.back_btn.clicked.connect(self.back_requested)
        self.add_dir_btn.clicked.connect(self.add_directory)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemChanged.connect(self.on_item_changed)
        # 扫描完成信号连接
        self._scan_finished.connect(self._on_scan_finished)
    
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
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if not dir_path:
            return
        
        # 检查目录是否已存在
        for category in self.scanner.categories:
            for item in category.items:
                if item.path == dir_path:
                    QMessageBox.warning(self, "提示", "该目录已在列表中")
                    return
        
        # 获取目录信息
        size = self.get_folder_size(dir_path)
        count = self.count_files(dir_path)
        
        if size == 0:
            QMessageBox.warning(self, "提示", "该目录为空")
            return
        
        # 创建自定义数据项
        dir_name = os.path.basename(dir_path)
        
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
        
        # 创建数据项
        item = DataItem(
            name=dir_name,
            path=dir_path,
            item_type="folder",
            size=size,
            count=count,
            description=f"自定义目录: {dir_path}"
        )
        custom_category.items.append(item)
        
        # 如果分类还没在树中，添加分类
        if custom_category not in [cat.data(0, Qt.ItemDataRole.UserRole) for cat in self.tree.findItems("", Qt.MatchFlag.MatchContains)]:
            self.add_category_to_tree(custom_category)
        else:
            # 找到分类节点并添加子项
            for i in range(self.tree.topLevelItemCount()):
                top_item = self.tree.topLevelItem(i)
                cat_data = top_item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(cat_data, DataCategory) and cat_data.name == "custom_dirs":
                    self.add_item_to_tree(top_item, item)
                    top_item.setExpanded(True)
                    break
        
        # 更新统计
        self.update_stats()
        
        QMessageBox.information(self, "成功", f"已添加目录: {dir_path}")
    
    def get_folder_size(self, folder_path):
        """计算文件夹大小"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        return total_size
    
    def count_files(self, folder_path):
        """统计文件数量"""
        count = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                count += len(filenames)
        except (OSError, PermissionError):
            pass
        return count
    
    def add_category_to_tree(self, category: DataCategory):
        """添加分类到树"""
        cat_item = QTreeWidgetItem(self.tree)
        cat_item.setText(0, category.display_name)
        cat_item.setText(1, format_size(category.total_size))
        cat_item.setText(2, str(category.total_count))
        cat_item.setText(3, category.description)
        cat_item.setData(0, Qt.ItemDataRole.UserRole, category)
        cat_item.setExpanded(True)
        
        # 创建复选框控件
        checkbox = QCheckBox()
        checkbox.setChecked(category.selected)
        checkbox.stateChanged.connect(lambda state, item=cat_item: self.on_category_checkbox_changed(item, state))
        self.tree.setItemWidget(cat_item, 0, checkbox)
        
        # 添加子项
        for item in category.items:
            self.add_item_to_tree(cat_item, item)
    
    def add_item_to_tree(self, parent: QTreeWidgetItem, item: DataItem):
        """添加数据项到树"""
        tree_item = QTreeWidgetItem(parent)
        tree_item.setText(0, item.name)
        tree_item.setText(1, format_size(item.size))
        tree_item.setText(2, str(item.count))
        tree_item.setText(3, item.description)
        tree_item.setData(0, Qt.ItemDataRole.UserRole, item)
        
        # 创建复选框控件
        checkbox = QCheckBox()
        checkbox.setChecked(item.selected)
        checkbox.stateChanged.connect(lambda state, item=tree_item: self.on_item_checkbox_changed(item, state))
        self.tree.setItemWidget(tree_item, 0, checkbox)
    
    def on_category_checkbox_changed(self, item: QTreeWidgetItem, state):
        """分类复选框状态变更"""
        is_checked = state == Qt.CheckState.Checked.value
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if isinstance(data, DataCategory):
            data.selected = is_checked
            for i in range(item.childCount()):
                child = item.child(i)
                checkbox = self.tree.itemWidget(child, 0)
                if isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(is_checked)
        
        self.update_stats()
    
    def on_item_checkbox_changed(self, item: QTreeWidgetItem, state):
        """子项复选框状态变更"""
        is_checked = state == Qt.CheckState.Checked.value
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if isinstance(data, DataItem):
            data.selected = is_checked
            
            # 更新父项状态
            parent = item.parent()
            if parent:
                parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(parent_data, DataCategory):
                    all_checked = True
                    any_checked = False
                    for i in range(parent.childCount()):
                        child = parent.child(i)
                        checkbox = self.tree.itemWidget(child, 0)
                        if isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                            any_checked = True
                        else:
                            all_checked = False
                    
                    parent_checkbox = self.tree.itemWidget(parent, 0)
                    if isinstance(parent_checkbox, QCheckBox):
                        parent_checkbox.setChecked(all_checked)
        
        self.update_stats()
    
    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """点击树项 - 显示详细信息"""
        # 显示详细信息
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if isinstance(data, DataItem):
            info = f"""
<b>名称:</b> {data.name}<br>
<b>路径:</b> {data.path}<br>
<b>类型:</b> {data.item_type}<br>
<b>大小:</b> {format_size(data.size)}<br>
<b>文件数:</b> {data.count}<br>
<b>描述:</b> {data.description}
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
    
    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        """树项状态变更"""
        if column != 0:
            return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        check_state = item.checkState(0)
        is_checked = check_state == Qt.CheckState.Checked
        
        if isinstance(data, DataCategory):
            # 分类变更，更新所有子项
            data.selected = is_checked
            for i in range(item.childCount()):
                child = item.child(i)
                child.setCheckState(0, check_state)
                child_data = child.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(child_data, DataItem):
                    child_data.selected = is_checked
        
        elif isinstance(data, DataItem):
            # 子项变更
            data.selected = is_checked
            
            # 更新父项状态
            parent = item.parent()
            if parent:
                parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(parent_data, DataCategory):
                    # 检查所有子项状态
                    all_checked = True
                    any_checked = False
                    for i in range(parent.childCount()):
                        child = parent.child(i)
                        if child.checkState(0) == Qt.CheckState.Checked:
                            any_checked = True
                        else:
                            all_checked = False
                    
                    if all_checked:
                        parent.setCheckState(0, Qt.CheckState.Checked)
                        parent_data.selected = True
                    elif any_checked:
                        parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
                        parent_data.selected = True
                    else:
                        parent.setCheckState(0, Qt.CheckState.Unchecked)
                        parent_data.selected = False
        
        self.update_stats()
    
    def update_stats(self):
        """更新统计信息"""
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
        
        # 转换为字典列表
        items_dict = [item.to_dict() for item in selected_items]
        self.transfer_started.emit(items_dict)
    
    def showEvent(self, event):
        """页面显示时自动扫描"""
        super().showEvent(event)
        if not self.scanner._scanned:
            self.scan_data()
