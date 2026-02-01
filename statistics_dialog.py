# statistics_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QWidget
)
from PySide6.QtCore import Qt

class StatisticsDialog(QDialog):
    def __init__(self, bible_db, parent=None):
        super().__init__(parent)
        self.bible_db = bible_db
        self.setWindowTitle("하이라이트 및 메모 통계")
        self.setMinimumSize(700, 500)
        
        self.init_ui()
        self.load_statistics()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 탭 위젯
        tab_widget = QTabWidget()
        
        # 하이라이트 통계 탭
        highlight_tab = QWidget()
        highlight_layout = QVBoxLayout(highlight_tab)
        highlight_layout.addWidget(QLabel("하이라이트 통계"))
        
        self.highlight_table = QTableWidget()
        self.highlight_table.setColumnCount(3)
        self.highlight_table.setHorizontalHeaderLabels(["책", "장", "하이라이트 개수"])
        self.highlight_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        highlight_layout.addWidget(self.highlight_table)
        
        tab_widget.addTab(highlight_tab, "하이라이트")
        
        # 메모 통계 탭
        memo_tab = QWidget()
        memo_layout = QVBoxLayout(memo_tab)
        memo_layout.addWidget(QLabel("메모 통계"))
        
        self.memo_table = QTableWidget()
        self.memo_table.setColumnCount(2)
        self.memo_table.setHorizontalHeaderLabels(["책", "메모 개수"])
        self.memo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        memo_layout.addWidget(self.memo_table)
        
        tab_widget.addTab(memo_tab, "메모")
        
        # 요약 탭
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        summary_layout.addStretch()
        
        tab_widget.addTab(summary_tab, "요약")
        
        layout.addWidget(tab_widget)
        
        # 닫기 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
    
    def load_statistics(self):
        """통계 데이터 로드"""
        # 하이라이트 통계
        highlight_stats = self.bible_db.get_highlight_statistics()
        self.highlight_table.setRowCount(len(highlight_stats['top_chapters']))
        for i, item in enumerate(highlight_stats['top_chapters']):
            self.highlight_table.setItem(i, 0, QTableWidgetItem(item['book']))
            self.highlight_table.setItem(i, 1, QTableWidgetItem(str(item['chapter'])))
            self.highlight_table.setItem(i, 2, QTableWidgetItem(str(item['count'])))
        
        # 메모 통계
        memo_stats = self.bible_db.get_memo_statistics()
        self.memo_table.setRowCount(len(memo_stats['by_book']))
        for i, item in enumerate(memo_stats['by_book']):
            self.memo_table.setItem(i, 0, QTableWidgetItem(item['book']))
            self.memo_table.setItem(i, 1, QTableWidgetItem(str(item['count'])))
        
        # 요약
        summary_text = f"""
        <h3>하이라이트 통계</h3>
        <p>전체 하이라이트 개수: <b>{highlight_stats['total']}</b>개</p>
        <p>하이라이트된 책: <b>{len(highlight_stats['by_book'])}</b>권</p>
        
        <h3>메모 통계</h3>
        <p>전체 메모 개수: <b>{memo_stats['total']}</b>개</p>
        <p>장 전체 메모: <b>{memo_stats['chapter_memos']}</b>개</p>
        <p>절 메모: <b>{memo_stats['verse_memos']}</b>개</p>
        <p>메모가 있는 책: <b>{len(memo_stats['by_book'])}</b>권</p>
        """
        self.summary_label.setText(summary_text)
