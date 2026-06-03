"""
数据选择页面
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QSplitter, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.scanner import DataScanner, DataCategory, DataItem
from utils.helpers import format_size


class SelectPage(QWidget):
    """数据选择页面"""
    
    # 信号
    transfer_started = pyqtSignal(list)  # 开始传输，传递选中的数据项列表
    back_requested = pyqtSignal()  # 返回上一页
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = DataScanner()
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
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background: #e3f2fd;
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
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemChanged.connect(self.on_item_changed)
    
    def scan_data(self):
        """扫描数据"""
        self.desc_label.setText("正在扫描本地数据，请稍候...")
        self.tree.clear()
        
        # 执行扫描
        categories = self.scanner.scan_all()
        
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
    
    def add_category_to_tree(self, category: DataCategory):
        """添加分类到树"""
        cat_item = QTreeWidgetItem(self.tree)
        cat_item.setText(0, category.display_name)
        cat_item.setText(1, format_size(category.total_size))
        cat_item.setText(2, str(category.total_count))
        cat_item.setText(3, category.description)
        cat_item.setFlags(cat_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        cat_item.setCheckState(0, Qt.CheckState.Checked)
        cat_item.setData(0, Qt.ItemDataRole.UserRole, category)
        cat_item.setExpanded(True)
        
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
        tree_item.setFlags(tree_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        
        if item.selected:
            tree_item.setCheckState(0, Qt.CheckState.Checked)
        else:
            tree_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        tree_item.setData(0, Qt.ItemDataRole.UserRole, item)
    
    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """点击树项"""
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
