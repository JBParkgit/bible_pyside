# bible_view.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QComboBox, QLabel, QPushButton, QFrame, QApplication, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QPoint
from PySide6.QtGui import QFont, QTextOption, QPalette, QTextCursor

class SharedBibleView(QWidget):
    translation_changed = Signal(str)
    font_size_changed = Signal(int)
    verse_anchor_clicked = Signal(QUrl)
    scroll_changed = Signal(int)

    request_commentary = Signal(str, int, int)
    request_cross_ref = Signal(str, int, int)
    request_search = Signal(str, str)
    request_add_to_collection = Signal(object, str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)

    def __init__(self, data_loader, available_translations, parent=None, initial_settings=None, is_main_reader=False, context='read'):
        super().__init__(parent)
        self.data_loader = data_loader
        self.available_translations = available_translations
        self.is_main_reader = is_main_reader
        self.context = context
        self.current_book = "창세기"
        self.current_chapter = 1
        self.current_verse_for_context = 1
        if initial_settings is None: initial_settings = {}
        self.verse_display_mode = initial_settings.get('verse_display_mode', 0)
        self.font_size = initial_settings.get('bible_font_size', 14)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.init_ui()
        self.connect_signals()
        initial_translation = initial_settings.get('translation')
        if initial_translation and initial_translation in self.available_translations:
            self.translation_combo.setCurrentText(initial_translation)
        # self.font_size_label.setText(str(self.font_size)) # 삭제
        self.text_browser.setFont(QFont(self.font_family, self.font_size))
        self.set_word_wrap_mode(self.translation_combo.currentText())

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        control_bar = QFrame()
        control_bar_layout = QHBoxLayout(control_bar)
        control_bar_layout.setContentsMargins(2, 2, 2, 2)
        self.translation_combo = QComboBox()
        self.translation_combo.addItems(self.available_translations)
        self.translation_combo.setToolTip("번역본을 선택하세요.")
        
        # 폰트 크기 조절 UI 삭제
        # self.font_size_label = QLabel(str(self.font_size))
        # self.font_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.font_size_label.setMinimumWidth(25)
        # self.font_plus_button = QPushButton("+")
        # self.font_plus_button.setFixedSize(24, 24)
        # self.font_plus_button.setToolTip("글자 크기 키우기")
        # self.font_minus_button = QPushButton("-")
        # self.font_minus_button.setFixedSize(24, 24)
        # self.font_minus_button.setToolTip("글자 크기 줄이기")
        
        control_bar_layout.addWidget(self.translation_combo)
        
        # 폰트 크기 조절 UI 레이아웃 추가 코드 삭제
        # control_bar_layout.addWidget(self.font_minus_button)
        # control_bar_layout.addWidget(self.font_size_label)
        # control_bar_layout.addWidget(self.font_plus_button)
        
        control_bar_layout.addStretch(1)
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(control_bar)
        layout.addWidget(self.text_browser)

    def connect_signals(self):
        # 폰트 버튼 시그널 연결 삭제
        # self.font_plus_button.clicked.connect(lambda: self.change_font_size(1))
        # self.font_minus_button.clicked.connect(lambda: self.change_font_size(-1))
        
        self.translation_combo.currentTextChanged.connect(self.on_translation_changed)
        self.text_browser.verticalScrollBar().valueChanged.connect(self.scroll_changed.emit)
        self.text_browser.customContextMenuRequested.connect(self.show_context_menu)
        self.text_browser.anchorClicked.connect(self.verse_anchor_clicked.emit)

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.text_browser.setFont(QFont(self.font_family, self.font_size))

    @Slot(int)
    def set_font_size(self, size):
        if self.font_size == size: return
        self.font_size = max(8, size)
        # self.font_size_label.setText(str(self.font_size)) # 삭제
        self.text_browser.setFont(QFont(self.font_family, self.font_size))
        self.update_content()

    # change_font_size 메서드 삭제
    # def change_font_size(self, delta):
    #     new_size = self.font_size + delta
    #     if new_size >= 8:
    #         self.font_size_changed.emit(new_size)

    @Slot(int)
    def set_verse_display_mode(self, mode):
        if self.verse_display_mode != mode:
            self.verse_display_mode = mode
            self.update_content()

    def set_word_wrap_mode(self, translation_name):
        try:
            data = self.data_loader.load_translation_data(translation_name)
            language = data.get('language', 'unknown')
            if language in ['korean', 'chinese']:
                self.text_browser.setWordWrapMode(QTextOption.WrapAnywhere)
            else:
                self.text_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        except Exception:
            self.text_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

    @Slot(str)
    def set_translation(self, text):
        if self.translation_combo.currentText() != text:
            self.translation_combo.blockSignals(True)
            self.translation_combo.setCurrentText(text)
            self.translation_combo.blockSignals(False)
            self.set_word_wrap_mode(text)
            self.update_content()

    @Slot(str)
    def on_translation_changed(self, text):
        self.set_word_wrap_mode(text)
        self.update_content()
        self.translation_changed.emit(text)

    def update_content(self, book=None, chapter=None):
        if book: self.current_book = book
        if chapter: self.current_chapter = chapter
        translation = self.translation_combo.currentText()
        if not translation: return
        try:
            data = self.data_loader.load_translation_data(translation)
            chapter_content = data["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
        except Exception as e:
            self.text_browser.setHtml(f"<p style='color:red;'>'{translation}' 로드 중 오류 발생:<br>{e}</p>")
            return
        if not chapter_content:
            self.text_browser.setHtml(f"<p>'{self.current_book} {self.current_chapter}장' 데이터를 찾을 수 없습니다.</p>")
            return
        html_content, verse_counter = [], 1
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, "")
        text_color_name = QApplication.palette().color(QPalette.ColorRole.Text).name()
        for line in chapter_content:
            subtitle_match = re.match(r'<\s*(.+?)\s*>', line)
            if subtitle_match:
                html_content.append(f"<p style='text-align:center; font-weight:bold; color:{text_color_name}; margin-top:15px; margin-bottom:5px;'>{subtitle_match.group(1)}</p>")
            else:
                verse_prefix = ""
                if self.verse_display_mode == 0: verse_prefix = f"<span style='color: {text_color_name};'>({book_abbr} {self.current_chapter}:{verse_counter})</span> "
                elif self.verse_display_mode == 1: verse_prefix = f"<span style='color: {text_color_name};'>{book_abbr} {self.current_chapter}:{verse_counter}</span> "
                elif self.verse_display_mode == 2: verse_prefix = f"<span style='color: {text_color_name};'>{verse_counter}.</span> "
                html_content.append(f"<p style='line-height: 1.2;'><a href='#{verse_counter}' style='text-decoration:none; color:{text_color_name};'>{verse_prefix}{line}</a></p>")
                verse_counter += 1
        self.text_browser.setHtml("".join(html_content))

    def show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        pos_cursor = self.text_browser.cursorForPosition(pos)
        block_text = pos_cursor.block().text()
        match_full = re.match(r'^\s*\(?[가-힣A-Za-z]+\s*\d+:\s*(\d+)\)?', block_text)
        match_num = re.match(r'^\s*(\d+)\.', block_text)
        verse_num = None
        if match_full: verse_num = int(match_full.group(1))
        elif match_num: verse_num = int(match_num.group(1))
        position_actions_added = False
        if verse_num:
            self.current_verse_for_context = verse_num
            c_action = menu.addAction("이 절 주석 보기")
            cr_action = menu.addAction("이 절 관주 보기")
            if self.context == 'commentary': c_action.setEnabled(False)
            elif self.context == 'crossref': cr_action.setEnabled(False)
            c_action.triggered.connect(lambda: self.request_commentary.emit(self.current_book, self.current_chapter, self.current_verse_for_context))
            cr_action.triggered.connect(lambda: self.request_cross_ref.emit(self.current_book, self.current_chapter, self.current_verse_for_context))
            position_actions_added = True
        if position_actions_added: menu.addSeparator()
        text_cursor = self.text_browser.textCursor()
        has_selection = text_cursor.hasSelection()
        s_action = menu.addAction("검색")
        col_action = menu.addAction("구절모음으로 보내기")
        word_action = menu.addAction("MS Word로 보내기")
        ppt_action = menu.addAction("MS PowerPoint로 보내기")
        s_action.setEnabled(has_selection)
        col_action.setEnabled(has_selection)
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)
        if has_selection:
            selected_text_for_search = text_cursor.selectedText()
            text_to_send_for_collection = text_cursor.selection().toPlainText().strip()
            lines = text_to_send_for_collection.split('\n')
            def get_verse_num_from_line(line_text):
                m1 = re.match(r'^\(?\s*[가-힣A-Za-z]+\s*\d+:(\d+)\s*\)?', line_text)
                if m1: return m1.group(1)
                m2 = re.match(r'^\s*(\d+)\.', line_text)
                if m2: return m2.group(1)
                return None
            first_verse = get_verse_num_from_line(lines[0])
            last_verse = get_verse_num_from_line(lines[-1]) if len(lines) > 1 else first_verse
            range_str = ""
            book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, "")
            if first_verse:
                if not last_verse or first_verse == last_verse:
                    range_str = f"{book_abbr} {self.current_chapter}:{first_verse}"
                else:
                    range_str = f"{book_abbr} {self.current_chapter}:{first_verse}-{last_verse}"
            s_action.triggered.connect(lambda: self.request_search.emit(selected_text_for_search, self.translation_combo.currentText()))
            col_action.triggered.connect(lambda: self.request_add_to_collection.emit(self, text_to_send_for_collection, range_str))
            word_action.triggered.connect(lambda: self.request_send_to_word.emit(text_to_send_for_collection))
            ppt_action.triggered.connect(lambda: self.request_send_to_powerpoint.emit(self, text_to_send_for_collection))
        menu.exec(self.text_browser.mapToGlobal(pos))

    @Slot(int)
    def scroll_to_verse(self, verse_num):
        doc = self.text_browser.document()
        block = doc.begin()
        verse_blocks_found = 0
        target_block = None
        while block.isValid():
            if block.blockFormat().alignment() != Qt.AlignmentFlag.AlignCenter:
                verse_blocks_found += 1
                if verse_blocks_found == verse_num:
                    target_block = block
                    break
            block = block.next()
        if target_block and target_block.isValid():
            cursor = QTextCursor(target_block)
            self.text_browser.setTextCursor(cursor)
            scroll_bar = self.text_browser.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.value() + self.text_browser.cursorRect().top())