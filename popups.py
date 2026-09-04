# popups.py
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QFrame,
    QVBoxLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QEvent, QTimer

class BookChapterPopup(QWidget):
    """
    책과 장을 선택하는 팝업 위젯 클래스. 상단에 수동 입력 이동창도 함께 제공한다.
    """
    selection_made = Signal(str, int)
    text_navigation = Signal(str)  # 수동 입력 이동 (예: "창1:1")

    def __init__(self, data_loader, parent=None, current_book=None, current_chapter=None):
        # Qt.Popup 창은 활성화되지 않아 한글(IME) 입력 조합이 되지 않는다.
        # Qt.Tool 로 띄우고, 바깥 클릭 시 닫히는 동작은 event()에서 직접 처리한다.
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.data_loader = data_loader
        self._ready = False  # 표시 직후의 순간적 비활성화로 자동 닫힘 방지
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.main_frame = QFrame(self); self.main_frame.setObjectName("mainFrame")
        self.main_frame.setStyleSheet("#mainFrame { border: 1px solid palette(mid); border-radius: 8px; background-color: palette(base); }")

        outer = QVBoxLayout(self.main_frame); outer.setContentsMargins(5, 5, 5, 5); outer.setSpacing(4)

        self.nav_input = QLineEdit()
        self.nav_input.setPlaceholderText("이동 입력 후 Enter (예: 창1:1)")
        self.nav_input.setToolTip("책/장(/절)을 직접 입력해 이동합니다. 예: 창1:1, 요한복음 3장")
        self.nav_input.returnPressed.connect(self._on_nav_input)
        outer.addWidget(self.nav_input)

        lists_row = QHBoxLayout(); lists_row.setContentsMargins(0, 0, 0, 0)
        self.book_list, self.chapter_list = QListWidget(), QListWidget()
        self.book_list.setFixedWidth(150); self.chapter_list.setFixedWidth(80)
        lists_row.addWidget(self.book_list); lists_row.addWidget(self.chapter_list)
        outer.addLayout(lists_row)

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
        self.nav_input.setFocus()

    def showEvent(self, e):
        super().showEvent(e)
        # Tool 창이 실제로 활성화돼야 IME(한글 조합)가 입력창에 붙는다.
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._focus_input)
        QTimer.singleShot(200, lambda: setattr(self, "_ready", True))

    def _focus_input(self):
        self.activateWindow()
        self.nav_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def _on_nav_input(self):
        text = self.nav_input.text().strip()
        if text:
            self.text_navigation.emit(text)
            self.close()

    def on_book_selected(self, current_item, previous_item):
        if not current_item: return
        book_name = current_item.data(Qt.ItemDataRole.UserRole)
        self.chapter_list.clear(); self.chapter_list.addItems([str(i) for i in range(1, self.data_loader.global_book_chapter_counts.get(book_name, 0) + 1)])
    def on_chapter_selected(self, item):
        book_item = self.book_list.currentItem(); book_name = book_item.data(Qt.ItemDataRole.UserRole)
        self.selection_made.emit(book_name, int(item.text())); self.close()
    def event(self, e):
        if e.type() == QEvent.Type.WindowDeactivate and self._ready:
            self.close()
        return super().event(e)
