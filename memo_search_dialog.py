# memo_search_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QTextEdit, QSplitter, QMessageBox
)
from PySide6.QtCore import Qt, Signal

class MemoSearchDialog(QDialog):
    verse_selected = Signal(str, int, int)
    
    def __init__(self, bible_db, data_loader, parent=None):
        super().__init__(parent)
        self.bible_db = bible_db
        self.data_loader = data_loader
        self.setWindowTitle("메모 검색")
        self.setMinimumSize(800, 600)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 검색 입력
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("검색어:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("메모 내용에서 검색...")
        self.search_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        self.search_button = QPushButton("검색")
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_button)
        layout.addLayout(search_layout)
        
        # 결과 영역
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 메모 목록
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        splitter.addWidget(self.list_widget)
        
        # 메모 내용 보기
        content_widget = QTextEdit()
        content_widget.setReadOnly(True)
        self.content_view = content_widget
        splitter.addWidget(content_widget)
        
        splitter.setSizes([300, 500])
        layout.addWidget(splitter)
        
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
    
    def perform_search(self):
        """메모 검색 실행"""
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.information(self, "알림", "검색어를 입력하세요.")
            return
        
        self.list_widget.clear()
        self.content_view.clear()
        
        memos = self.bible_db.search_memos(keyword)
        
        if not memos:
            QMessageBox.information(self, "검색 결과", "검색 결과가 없습니다.")
            return
        
        for memo in memos:
            book = memo['book']
            chapter = memo['chapter']
            verse = memo.get('verse')
            book_abbr = self.data_loader.full_name_to_abbr_map.get(book, book)
            
            if verse:
                item_text = f"{book_abbr} {chapter}:{verse} - {book} {chapter}장 {verse}절"
            else:
                item_text = f"{book_abbr} {chapter}장 - {book} {chapter}장 (전체)"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, memo)
            self.list_widget.addItem(item)
    
    def on_item_clicked(self, item):
        """항목 한 번 클릭 시 메모 내용 표시 + 해당 구절로 이동 (목록창은 유지)"""
        memo = item.data(Qt.ItemDataRole.UserRole)
        self.content_view.setPlainText(memo['content'])
        book = memo['book']
        chapter = memo['chapter']
        verse = memo.get('verse') or 1
        self.verse_selected.emit(book, chapter, verse)
    
    def on_item_double_clicked(self, item):
        """항목 더블클릭 시 해당 구절로 이동 후 목록창 닫기"""
        memo = item.data(Qt.ItemDataRole.UserRole)
        book = memo['book']
        chapter = memo['chapter']
        verse = memo.get('verse') or 1
        self.verse_selected.emit(book, chapter, verse)
        self.accept()
    
    def delete_selected(self):
        """선택된 메모 삭제"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "알림", "삭제할 항목을 선택하세요.")
            return
        
        reply = QMessageBox.question(
            self, "삭제 확인",
            "선택한 메모를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            memo = current_item.data(Qt.ItemDataRole.UserRole)
            self.bible_db.delete_memo(memo['book'], memo['chapter'], memo.get('verse'))
            self.perform_search()  # 검색 결과 갱신
