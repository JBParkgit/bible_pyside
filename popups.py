# popups.py
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QListWidget, QListWidgetItem, QFrame, QVBoxLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QEvent

class BookChapterPopup(QWidget):
    """
    책과 장을 선택하는 팝업 위젯 클래스.
    """
    selection_made = Signal(str, int)
    def __init__(self, data_loader, parent=None, current_book=None, current_chapter=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.data_loader = data_loader
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.main_frame = QFrame(self); self.main_frame.setObjectName("mainFrame"); self.main_frame.setStyleSheet("#mainFrame { border: 1px solid palette(highlight); border-radius: 5px; background-color: palette(window); }")
        layout = QHBoxLayout(self.main_frame); layout.setContentsMargins(5, 5, 5, 5)
        self.book_list, self.chapter_list = QListWidget(), QListWidget()
        self.book_list.setFixedWidth(150); self.chapter_list.setFixedWidth(80)
        layout.addWidget(self.book_list); layout.addWidget(self.chapter_list)
        self.setLayout(QVBoxLayout()); self.layout().addWidget(self.main_frame); self.layout().setContentsMargins(0,0,0,0)
        current_book_item = None
        for num, abbr, full in self.data_loader.book_definitions:
            item = QListWidgetItem(f"{num} {full}"); item.setData(Qt.ItemDataRole.UserRole, full); self.book_list.addItem(item)
            if full == current_book: current_book_item = item
        self.book_list.currentItemChanged.connect(self.on_book_selected)
        self.chapter_list.itemDoubleClicked.connect(self.on_chapter_selected)
        if current_book_item is not None:
            self.book_list.setCurrentItem(current_book_item)
            self.book_list.scrollToItem(current_book_item, QAbstractItemView.ScrollHint.PositionAtCenter)
            if current_chapter:
                chapter_item = self.chapter_list.item(current_chapter - 1)
                if chapter_item is not None:
                    self.chapter_list.setCurrentItem(chapter_item)
                    self.chapter_list.scrollToItem(chapter_item, QAbstractItemView.ScrollHint.PositionAtCenter)
    def on_book_selected(self, current_item, previous_item):
        if not current_item: return
        book_name = current_item.data(Qt.ItemDataRole.UserRole)
        self.chapter_list.clear(); self.chapter_list.addItems([str(i) for i in range(1, self.data_loader.global_book_chapter_counts.get(book_name, 0) + 1)])
    def on_chapter_selected(self, item):
        book_item = self.book_list.currentItem(); book_name = book_item.data(Qt.ItemDataRole.UserRole)
        self.selection_made.emit(book_name, int(item.text())); self.close()
    def event(self, e):
        if e.type() == QEvent.Type.WindowDeactivate: self.close()
        return super().event(e)