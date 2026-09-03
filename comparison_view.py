# comparison_view.py

import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QPushButton, QTextBrowser,
    QComboBox, QToolBar, QWidget, QSizePolicy, QLabel
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont

from html_utils import get_direction_style, html_escape

class ComparisonDialog(QDialog):
    """
    한 구절을 모든 번역본으로 비교하여 보여주는 대화상자.
    메인 프로그램의 테마(스타일)와 폰트 설정을 전달받아 적용합니다.
    """
    # 폰트 크기 변경 신호 정의
    font_size_changed = Signal(int)

    def __init__(self, data_loader, book, chapter, verse, parent=None, stylesheet="", font_family="Malgun Gothic", font_size=12, end_verse=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.current_book = book
        self.current_chapter = chapter
        self.current_verse = verse
        self.end_verse = end_verse or verse
        self.verse_count = 0
        self.font_family = font_family
        self.font_size = font_size

        self.setWindowTitle("번역본 비교")
        self.setMinimumSize(600, 700)
        self.setSizeGripEnabled(True)

        self.init_ui()
        self.connect_signals()

        if stylesheet:
            self.nav_bar.setStyleSheet(stylesheet)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.update_location(self.current_book, self.current_chapter, self.current_verse)
        QApplication.restoreOverrideCursor()

    def accept(self):
        """다이얼로그가 닫힐 때 현재 폰트 크기를 신호로 보냅니다."""
        self.font_size_changed.emit(self.font_size)
        super().accept()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        self.nav_bar = QToolBar()
        self.nav_bar.setMovable(False)
        self.nav_bar.setFloatable(False)

        self.prev_book_btn = QPushButton("<<")
        self.prev_chap_btn = QPushButton("<")
        self.location_btn = QPushButton()
        self.location_btn.setFixedWidth(140)
        self.next_chap_btn = QPushButton(">")
        self.next_book_btn = QPushButton(">>")
        
        self.prev_verse_btn = QPushButton("<")
        self.verse_combo = QComboBox()
        self.verse_combo.setFixedWidth(60)
        self.next_verse_btn = QPushButton(">")
        
        self.decrease_font_btn = QPushButton("-")
        self.font_size_label = QLabel(str(self.font_size))
        self.increase_font_btn = QPushButton("+")

        self.close_btn = QPushButton("닫기")

        self.nav_bar.addWidget(self.prev_book_btn)
        self.nav_bar.addWidget(self.prev_chap_btn)
        self.nav_bar.addWidget(self.location_btn)
        self.nav_bar.addWidget(self.next_chap_btn)
        self.nav_bar.addWidget(self.next_book_btn)
        self.nav_bar.addSeparator()
        self.nav_bar.addWidget(self.prev_verse_btn)
        self.nav_bar.addWidget(self.verse_combo)
        self.nav_bar.addWidget(self.next_verse_btn)
        self.nav_bar.addSeparator()
        self.nav_bar.addWidget(self.decrease_font_btn)
        self.nav_bar.addWidget(self.font_size_label)
        self.nav_bar.addWidget(self.increase_font_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.nav_bar.addWidget(spacer)
        
        self.nav_bar.addWidget(self.close_btn)
        
        main_layout.addWidget(self.nav_bar)

        self.text_browser = QTextBrowser()
        self.apply_font_settings() # 폰트 설정 적용
        
        main_layout.addWidget(self.text_browser, 1)

    def connect_signals(self):
        self.prev_book_btn.clicked.connect(self.go_to_prev_book)
        self.next_book_btn.clicked.connect(self.go_to_next_book)
        self.prev_chap_btn.clicked.connect(self.go_to_prev_chapter)
        self.next_chap_btn.clicked.connect(self.go_to_next_chapter)
        self.prev_verse_btn.clicked.connect(self.go_to_prev_verse)
        self.next_verse_btn.clicked.connect(self.go_to_next_verse)
        
        self.location_btn.clicked.connect(self.show_book_chapter_popup)
        self.verse_combo.currentIndexChanged.connect(self.on_verse_changed)

        self.decrease_font_btn.clicked.connect(self.decrease_font_size)
        self.increase_font_btn.clicked.connect(self.increase_font_size)
        
        self.close_btn.clicked.connect(self.accept)

    def apply_font_settings(self):
        """현재 폰트 설정(크기, 글꼴)을 위젯에 적용합니다."""
        font = QFont(self.font_family, self.font_size)
        self.text_browser.setFont(font)
        self.font_size_label.setText(str(self.font_size))

    @Slot()
    def decrease_font_size(self):
        """글자 크기를 1 감소시킵니다."""
        self.font_size = max(8, self.font_size - 1)
        self.apply_font_settings()

    @Slot()
    def increase_font_size(self):
        """글자 크기를 1 증가시킵니다."""
        self.font_size = min(30, self.font_size + 1)
        self.apply_font_settings()

    def update_location(self, book, chapter, verse):
        self.current_book = book
        self.current_chapter = chapter

        any_translation = self.data_loader.get_available_translations()[0]
        try:
            translation_data = self.data_loader.load_translation_data(any_translation)
            chapter_content = translation_data["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
            self.verse_count = len([line for line in chapter_content if not line.startswith('<')])
        except Exception:
            self.verse_count = 0

        self.current_verse = max(1, min(verse, self.verse_count if self.verse_count > 0 else 1))
        self.end_verse = max(self.current_verse, min(self.end_verse, self.verse_count if self.verse_count > 0 else self.current_verse))

        self.update_nav_display()
        self.update_verse_combo()
        self.update_content()
        
    def update_nav_display(self):
        self.location_btn.setText(f"{self.current_book} {self.current_chapter}장")

    def update_verse_combo(self):
        self.verse_combo.blockSignals(True)
        self.verse_combo.clear()
        if self.verse_count > 0:
            self.verse_combo.addItems([str(i) for i in range(1, self.verse_count + 1)])
            self.verse_combo.setCurrentText(str(self.current_verse))
        self.verse_combo.blockSignals(False)

    def update_content(self):
        self.text_browser.clear()
        self.text_browser.setLayoutDirection(Qt.LeftToRight)
        
        translations = self.data_loader.get_available_translations()
        start = min(self.current_verse, self.end_verse)
        end = max(self.current_verse, self.end_verse)
        if start == end:
            reference = f"{self.current_book} {self.current_chapter}:{start}"
        else:
            reference = f"{self.current_book} {self.current_chapter}:{start}-{end}"

        html_parts = [
            "<html><head><style>",
            "body { font-family: 'Malgun Gothic', Arial, sans-serif; line-height: 1.55; }",
            ".translation { margin-bottom: 18px; }",
            ".translation-title { font-weight: 700; margin-bottom: 4px; }",
            ".verse-line { margin: 2px 0; }",
            ".verse-number { color: #57606a; font-size: 90%; }",
            "</style></head><body>",
            f"<h3>{html_escape(reference)}</h3>",
        ]

        for trans_name in translations:
            data = self.data_loader.load_translation_data(trans_name)
            direction_style = get_direction_style(data)
            lines = []
            for verse_num in range(start, end + 1):
                verse_text = self.data_loader.get_verse_text(
                    trans_name, self.current_book, self.current_chapter, verse_num
                )
                if verse_text:
                    if start == end:
                        lines.append(f"<div class='verse-line'>{html_escape(verse_text)}</div>")
                    else:
                        lines.append(
                            f"<div class='verse-line'><span class='verse-number'>{verse_num}</span> "
                            f"{html_escape(verse_text)}</div>"
                        )

            html_parts.append(f"<div class='translation' {direction_style}>")
            html_parts.append(f"<div class='translation-title'>{html_escape(trans_name)}</div>")
            if lines:
                # 각 절이 이미 block(<div>)이므로 <br>로 이으면 빈 줄이 하나 더 생긴다.
                html_parts.append("".join(lines))
            else:
                html_parts.append("<i>(내용 없음)</i>")
            html_parts.append("</div>")
        
        html_parts.append("</body></html>")
        self.text_browser.setHtml("\n".join(html_parts))

    @Slot(int)
    def on_verse_changed(self, index):
        if index == -1: return
        new_verse = index + 1
        if self.current_verse != new_verse:
            self.current_verse = new_verse
            self.end_verse = new_verse
            self.update_content()

    def go_to_adjacent_chapter(self, delta):
        new_chapter = self.current_chapter + delta
        if 1 <= new_chapter <= self.data_loader.global_book_chapter_counts.get(self.current_book, 0):
             self.update_location(self.current_book, new_chapter, 1)
        elif delta < 0: 
            self.go_to_prev_book(move_to_last_chapter=True)
        else:
            self.go_to_next_book()

    @Slot()
    def go_to_prev_chapter(self): self.go_to_adjacent_chapter(-1)
    
    @Slot()
    def go_to_next_chapter(self): self.go_to_adjacent_chapter(1)

    def go_to_adjacent_book(self, delta, move_to_last_chapter=False):
        book_defs = self.data_loader.book_definitions
        try:
            idx = next(i for i, (_, _, full) in enumerate(book_defs) if full == self.current_book)
            if 0 <= idx + delta < len(book_defs):
                new_book_name = book_defs[idx + delta][2]
                chap = self.data_loader.global_book_chapter_counts.get(new_book_name, 1) if move_to_last_chapter else 1
                self.update_location(new_book_name, chap, 1)
        except StopIteration:
            pass
            
    @Slot()
    def go_to_prev_book(self, move_to_last_chapter=False): self.go_to_adjacent_book(-1, move_to_last_chapter)

    @Slot()
    def go_to_next_book(self): self.go_to_adjacent_book(1)
        
    def go_to_adjacent_verse(self, delta):
        new_verse = self.current_verse + delta
        if 1 <= new_verse <= self.verse_count:
            self.verse_combo.setCurrentText(str(new_verse))

    @Slot()
    def go_to_prev_verse(self): self.go_to_adjacent_verse(-1)
    
    @Slot()
    def go_to_next_verse(self): self.go_to_adjacent_verse(1)
    
    @Slot()
    def show_book_chapter_popup(self):
        from popups import BookChapterPopup
        
        popup = BookChapterPopup(self.data_loader, self)
        popup.selection_made.connect(lambda book, chap: self.update_location(book, chap, 1))
        popup.move(self.location_btn.mapToGlobal(self.location_btn.rect().bottomLeft()))
        popup.show()
