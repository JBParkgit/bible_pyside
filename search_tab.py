# search_tab.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLabel, QPushButton, QRadioButton, QButtonGroup, QApplication, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QPoint
from PySide6.QtGui import QFont, QTextOption, QPalette, QKeySequence, QShortcut

class SearchTab(QWidget):
    settings_changed = Signal()
    request_commentary = Signal(str, int, int)
    request_cross_ref = Signal(str, int, int)
    request_navigation = Signal(str, int, int)
    request_new_read_tab = Signal(str, int, int) # 신규 시그널
    request_search = Signal(str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)

    def __init__(self, data_loader, parent=None, initial_settings=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.last_search_results = []
        self.last_keywords = []
        self.last_full_keyword = ""
        self.last_translation = ""
        self.last_status_message = ""
        if initial_settings is None: initial_settings = {}
        self.font_size = initial_settings.get('search_font_size', 12)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.revert_status_message)
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        top_bar_layout = QHBoxLayout()
        self.font_size_label = QLabel(str(self.font_size))
        self.font_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_size_label.setMinimumWidth(25)
        self.font_plus_button = QPushButton("+")
        self.font_plus_button.setFixedSize(24, 24)
        self.font_minus_button = QPushButton("-")
        self.font_minus_button.setFixedSize(24, 24)
        self.style_option_group = QButtonGroup(self)
        option1 = QRadioButton("(창 1:1)")
        option2 = QRadioButton("창 1:1")
        self.style_option_group.addButton(option1, 0)
        self.style_option_group.addButton(option2, 1)
        # 기본값: 괄호 없는 구절 표시 (창 1:1)
        option2.setChecked(True)
        top_bar_layout.addWidget(self.font_minus_button)
        top_bar_layout.addWidget(self.font_size_label)
        top_bar_layout.addWidget(self.font_plus_button)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(QLabel("결과 표시 스타일:"))
        top_bar_layout.addWidget(option1)
        top_bar_layout.addWidget(option2)
        self.results_browser = QTextBrowser()
        self.results_browser.setFont(QFont(self.font_family, self.font_size))
        self.results_browser.setOpenExternalLinks(False)
        self.results_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.results_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # 개편된 status_label
        status_container = QHBoxLayout()
        self.status_label_left = QLabel("검색어를 입력하고 검색 버튼을 누르세요.")
        self.status_label_left.setContentsMargins(5, 2, 0, 2)
        self.status_label_right = QLabel("이 말씀은 곧 하나님이시니라(요 1:1)")
        self.status_label_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label_right.setContentsMargins(0, 2, 5, 2)
        
        status_container.addWidget(self.status_label_left)
        status_container.addStretch(1)
        status_container.addWidget(self.status_label_right)

        layout.addLayout(top_bar_layout)
        layout.addWidget(self.results_browser, 1)
        layout.addLayout(status_container) # 레이아웃 추가

    def connect_signals(self):
        self.style_option_group.idClicked.connect(self.update_display)
        self.font_plus_button.clicked.connect(lambda: self.change_font_size(1))
        self.font_minus_button.clicked.connect(lambda: self.change_font_size(-1))
        self.results_browser.customContextMenuRequested.connect(self.show_context_menu)
        
        # Ctrl+G 단축키: 현재 커서 위치의 구절로 이동
        self.navigate_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        self.navigate_shortcut.activated.connect(self.navigate_to_current_verse)

    # --- 단축키 핸들러 추가 ---
    def handle_send_to_word_shortcut(self):
        cursor = self.results_browser.textCursor()
        if cursor.hasSelection():
            self.request_send_to_word.emit(cursor.selection().toPlainText().strip())

    def handle_send_to_powerpoint_shortcut(self):
        cursor = self.results_browser.textCursor()
        if cursor.hasSelection():
            self.request_send_to_powerpoint.emit(self, cursor.selection().toPlainText().strip())
    # ----------------------------------------

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.results_browser.setFont(QFont(self.font_family, self.font_size))

    def change_font_size(self, delta):
        self.font_size = max(8, self.font_size + delta)
        self.font_size_label.setText(str(self.font_size))
        self.results_browser.setFont(QFont(self.font_family, self.font_size))
        self.settings_changed.emit()

    def display_results(self, results, keywords, full_keyword, translation):
        self.last_search_results = results
        self.last_keywords = keywords
        self.last_full_keyword = full_keyword
        self.last_translation = translation
        self.last_status_message = f"'{translation}'에서 '{full_keyword}' 검색 결과: {len(results)}개"
        self.status_label_left.setText(self.last_status_message)
        self.update_display()

    def update_display(self):
        if not self.last_search_results:
            self.results_browser.clear()
            return
        html_content = []
        highlight_color = QApplication.palette().highlight().color().name()
        highlight_text_color = QApplication.palette().highlightedText().color().name()
        highlight_style = f"style='background-color: {highlight_color}; color: {highlight_text_color};'"
        text_color = QApplication.palette().color(QPalette.ColorRole.Text).name()
        ref_color = QApplication.palette().color(QPalette.ColorRole.Link).name()
        style_option = self.style_option_group.checkedId()
        language = 'unknown'
        try:
            language = self.data_loader.load_translation_data(self.last_translation).get('language', 'unknown')
            self.results_browser.setWordWrapMode(QTextOption.WrapAnywhere if language in ['korean', 'chinese'] else QTextOption.WrapAtWordBoundaryOrAnywhere)
        except Exception:
            self.results_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        # 구절 표시를 굵게/링크색으로 구분하고, 줄바꿈 시 본문이 구절표시 아래로
        # 들어가지 않도록 매달린 들여쓰기(hanging indent)를 준다.
        indent = max(64, int(self.font_size * 6.5))
        for book, chapter, verse_num, verse_text in self.last_search_results:
            book_abbr = self.data_loader.get_book_abbr(book, language=language)
            highlighted_text = verse_text
            for keyword in self.last_keywords:
                highlighted_text = re.sub(re.escape(keyword), f"<span {highlight_style}>{keyword}</span>", highlighted_text, flags=re.IGNORECASE)
            prefix = f"({book_abbr} {chapter}:{verse_num})" if style_option == 0 else f"{book_abbr} {chapter}:{verse_num}"
            html_content.append(
                f"<p style='margin-top:0; margin-bottom:9px; margin-left:{indent}px; "
                f"text-indent:-{indent}px; line-height:1.35;'>"
                f"<b><span style='color:{ref_color};'>{prefix}</span></b>&nbsp;&nbsp;"
                f"<span style='color:{text_color};'>{highlighted_text}</span></p>"
            )
        self.results_browser.setHtml("".join(html_content))
        
    @Slot(QPoint)
    def show_context_menu(self, pos):
        menu = QMenu(self)
        pos_cursor = self.results_browser.cursorForPosition(pos)
        block_text = pos_cursor.block().text()
        verse_match = re.match(r'^\(?\s*([가-힣A-Za-z]+)\s*(\d+):(\d+)\s*\)?', block_text)
        position_actions_added = False
        if verse_match:
            book_abbr, chapter_str, verse_str = verse_match.groups()
            book_full_name = self.data_loader.book_alias_map.get(book_abbr)
            if book_full_name:
                chapter_num, verse_num = int(chapter_str), int(verse_str)
                
                nav_action = menu.addAction("이 구절로 이동 (Ctrl+G)")
                nav_action.setShortcut(QKeySequence("Ctrl+G"))
                nav_action.triggered.connect(lambda: self.request_navigation.emit(book_full_name, chapter_num, verse_num))

                new_tab_action = menu.addAction("읽기탭추가해서 이동하기")
                new_tab_action.triggered.connect(lambda: self.request_new_read_tab.emit(book_full_name, chapter_num, verse_num))
                
                c_action = menu.addAction("이 절 주석 보기")
                cr_action = menu.addAction("이 절 관주 보기")
                c_action.triggered.connect(lambda: self.request_commentary.emit(book_full_name, chapter_num, verse_num))
                cr_action.triggered.connect(lambda: self.request_cross_ref.emit(book_full_name, chapter_num, verse_num))
                position_actions_added = True
        if position_actions_added: menu.addSeparator()
        
        text_cursor = self.results_browser.textCursor()
        has_selection = text_cursor.hasSelection()

        # --- 복사하기 액션 추가 ---
        copy_action = menu.addAction("복사하기")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.results_browser.copy)
        menu.addSeparator()
        # ------------------------

        s_action = menu.addAction("검색")
        word_action = menu.addAction("MS Word로 보내기 (Ctrl+W)")
        ppt_action = menu.addAction("MS PowerPoint로 보내기 (Ctrl+P)")
        s_action.setEnabled(has_selection)
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)
        if has_selection:
            selected_text_for_search = text_cursor.selectedText()
            text_to_send_for_collection = text_cursor.selection().toPlainText().strip()
            s_action.triggered.connect(lambda: self.request_search.emit(selected_text_for_search, self.last_translation))
            word_action.triggered.connect(lambda: self.request_send_to_word.emit(text_to_send_for_collection))
            ppt_action.triggered.connect(lambda: self.request_send_to_powerpoint.emit(self, text_to_send_for_collection))
        if not menu.isEmpty():
            menu.exec(self.results_browser.mapToGlobal(pos))
            
    def show_temporary_message(self, message):
        self.status_timer.stop()
        self.status_label_left.setText(message)
        self.status_timer.start(5000)

    def revert_status_message(self):
        self.status_label_left.setText(self.last_status_message)
    
    def navigate_to_current_verse(self):
        """Ctrl+G 단축키: 현재 커서 위치의 구절로 이동"""
        cursor = self.results_browser.textCursor()
        block_text = cursor.block().text()
        verse_match = re.match(r'^\(?\s*([가-힣A-Za-z]+)\s*(\d+):(\d+)\s*\)?', block_text)
        if verse_match:
            book_abbr, chapter_str, verse_str = verse_match.groups()
            book_full_name = self.data_loader.book_alias_map.get(book_abbr)
            if book_full_name:
                chapter_num, verse_num = int(chapter_str), int(verse_str)
                self.request_navigation.emit(book_full_name, chapter_num, verse_num)