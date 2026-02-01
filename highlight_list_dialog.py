# highlight_list_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal

class HighlightListDialog(QDialog):
    verse_selected = Signal(str, int, int)
    
    def __init__(self, bible_db, data_loader, parent=None):
        super().__init__(parent)
        self.bible_db = bible_db
        self.data_loader = data_loader
        self.setWindowTitle("하이라이트 목록")
        self.setMinimumSize(600, 500)
        
        self.init_ui()
        self.load_highlights()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 검색 필터
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("검색:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("책 이름으로 필터링...")
        self.filter_input.textChanged.connect(self.filter_highlights)
        filter_layout.addWidget(self.filter_input)
        layout.addLayout(filter_layout)
        
        # 하이라이트 목록
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # 버튼
        button_layout = QHBoxLayout()
        self.delete_button = QPushButton("선택 항목 삭제")
        self.delete_button.clicked.connect(self.delete_selected)
        self.close_button = QPushButton("닫기")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
    
    def load_highlights(self):
        """하이라이트 목록 로드"""
        self.list_widget.clear()
        highlights = self.bible_db.get_all_highlights()
        
        for highlight in highlights:
            book = highlight['book']
            chapter = highlight['chapter']
            verse = highlight['verse']
            book_abbr = self.data_loader.full_name_to_abbr_map.get(book, book)
            item_text = f"{book_abbr} {chapter}:{verse} - {book} {chapter}장 {verse}절"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, (book, chapter, verse))
            self.list_widget.addItem(item)
    
    def filter_highlights(self, text):
        """하이라이트 필터링"""
        filter_text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_text = item.text().lower()
            item.setHidden(filter_text not in item_text if filter_text else False)
    
    def on_item_clicked(self, item):
        """항목 한 번 클릭 시 해당 구절로 이동 (목록창은 유지)"""
        book, chapter, verse = item.data(Qt.ItemDataRole.UserRole)
        self.verse_selected.emit(book, chapter, verse)

    def on_item_double_clicked(self, item):
        """항목 더블클릭 시 해당 구절로 이동 후 목록창 닫기"""
        book, chapter, verse = item.data(Qt.ItemDataRole.UserRole)
        self.verse_selected.emit(book, chapter, verse)
        self.accept()
    
    def delete_selected(self):
        """선택된 하이라이트 삭제"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "알림", "삭제할 항목을 선택하세요.")
            return
        
        reply = QMessageBox.question(
            self, "삭제 확인",
            "선택한 하이라이트를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            book, chapter, verse = current_item.data(Qt.ItemDataRole.UserRole)
            self.bible_db.remove_highlight(book, chapter, verse)
            self.load_highlights()
            
            # 화면 갱신을 위해 시그널 발생
            main_window = self.window()
            if hasattr(main_window, 'update_all_tabs_content'):
                main_window.update_all_tabs_content()
