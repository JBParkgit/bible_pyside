# crossref_tab.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextBrowser,
    QComboBox, QLabel, QPushButton, QFrame, QApplication, QMenu,
    QRadioButton, QButtonGroup  # QRadioButton, QButtonGroup 임포트 추가
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QTimer, QPoint
from PySide6.QtGui import QFont, QTextOption, QPalette

from bible_view import SharedBibleView

class CrossRefTab(QWidget):
    settings_changed = Signal()
    request_navigation = Signal(str, int, int) # '이 구절로 이동' 기능을 위한 시그널 추가
    request_new_read_tab = Signal(str, int, int) # 신규 시그널
    request_search = Signal(str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)

    def __init__(self, data_loader, crossref_data_loader, parent=None, initial_settings=None, bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.crossref_data_loader = crossref_data_loader
        self.bible_db = bible_db
        if initial_settings is None: initial_settings = {}
        self.current_book = initial_settings.get('book', '창세기')
        self.current_chapter = initial_settings.get('chapter', 1)
        self.current_verse = 1
        self.available_translations = self.data_loader.get_available_translations()
        default_translation = self.available_translations[0] if self.available_translations else ""
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.crossref_font_size = initial_settings.get('crossref_display_font_size', 12)
        self.crossref_translation = initial_settings.get('crossref_display_translation', default_translation)
        
        # --- 추가된 부분 ---
        # 관주 표시 스타일 설정 불러오기 (0: (창 1:1), 1: 창 1:1)
        self.crossref_style_mode = initial_settings.get('crossref_style_mode', 0)
        # ------------------

        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.update_location_status)
        self.init_ui(initial_settings)
        self.connect_signals()
        self.crossref_data_loader.set_book_definitions(self.data_loader.book_definitions)
        self.crossref_data_loader.load_crossref_data()

    def init_ui(self, initial_settings):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1)

        bible_view_container = QWidget()
        bible_view_layout = QVBoxLayout(bible_view_container)
        bible_view_layout.setContentsMargins(0, 0, 0, 0)
        bible_view_layout.setSpacing(2)
        bible_view_settings = {
            'translation': self.available_translations[0],
            'bible_font_size': initial_settings.get('bible_font_size', 14),
            'font_family': self.font_family,
            'verse_display_mode': initial_settings.get('verse_display_mode', 0)
        }
        self.bible_view = SharedBibleView(
            self.data_loader, self.available_translations,
            initial_settings=bible_view_settings, is_main_reader=True, context='crossref', bible_db=self.bible_db
        )
        bible_view_layout.addWidget(self.bible_view)
        self.splitter.addWidget(bible_view_container)

        crossref_widget = self._create_crossref_view_widget()
        self.splitter.addWidget(crossref_widget)
        
        # 개편된 status_label
        status_container = QHBoxLayout()
        self.status_label_left = QLabel()
        self.status_label_left.setContentsMargins(5, 2, 0, 2)
        self.status_label_right = QLabel("이 말씀은 곧 하나님이시니라(요 1:1)")
        self.status_label_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label_right.setContentsMargins(0, 2, 5, 2)
        
        status_container.addWidget(self.status_label_left)
        status_container.addStretch(1)
        status_container.addWidget(self.status_label_right)
        
        main_layout.addLayout(status_container)
        
        self.splitter.setSizes([self.width() * 0.5, self.width() * 0.5])

    def _create_crossref_view_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        control_bar = QFrame()
        control_bar_layout = QHBoxLayout(control_bar)
        control_bar_layout.setContentsMargins(2, 2, 2, 2)
        
        self.crossref_translation_combo = QComboBox()
        self.crossref_translation_combo.addItems(self.available_translations)
        self.crossref_translation_combo.setCurrentText(self.crossref_translation)
        
        control_bar_layout.addWidget(self.crossref_translation_combo)
        
        # --- 추가된 부분: 관주 표시 스타일 라디오 버튼 ---
        control_bar_layout.addSpacing(10)
        control_bar_layout.addWidget(QLabel("관주 스타일:"))
        self.style_option_group = QButtonGroup(self)
        self.style_radio1 = QRadioButton("(창 1:1)")
        self.style_radio2 = QRadioButton("창 1:1")
        self.style_option_group.addButton(self.style_radio1, 0)
        self.style_option_group.addButton(self.style_radio2, 1)
        
        if self.crossref_style_mode == 1:
            self.style_radio2.setChecked(True)
        else:
            self.style_radio1.setChecked(True)
            
        control_bar_layout.addWidget(self.style_radio1)
        control_bar_layout.addWidget(self.style_radio2)
        # ---------------------------------------------

        # 성경책 장절 정보 라벨
        self.crossref_current_verse_label = QLabel("")
        self.crossref_current_verse_label.setStyleSheet("font-weight: bold; font-size: 10pt; margin-top: 4px; margin-bottom: 4px;")
        self.crossref_current_verse_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        control_bar_layout.addStretch(1) # 우측 정렬을 위해 stretch 추가
        control_bar_layout.addWidget(self.crossref_current_verse_label)

        self.crossref_text_browser = QTextBrowser()
        self.crossref_text_browser.setFont(QFont(self.font_family, self.crossref_font_size))
        self.crossref_text_browser.setReadOnly(True)
        self.crossref_text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        layout.addWidget(control_bar)
        layout.addWidget(self.crossref_text_browser)
        return widget

    def connect_signals(self):
        self.bible_view.verse_anchor_clicked.connect(self.on_verse_clicked)
        self.crossref_translation_combo.currentTextChanged.connect(self.on_crossref_translation_changed)
        self.crossref_text_browser.customContextMenuRequested.connect(self.show_crossref_context_menu)
        
        # --- 추가된 부분 ---
        self.style_option_group.idClicked.connect(self.on_style_option_changed)
        # ------------------

    # --- 단축키 핸들러 추가 ---
    def handle_send_to_word_shortcut(self):
        if self.bible_view.text_browser.hasFocus():
            self.bible_view.trigger_send_to_word()
        elif self.crossref_text_browser.hasFocus():
            cursor = self.crossref_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_word.emit(cursor.selection().toPlainText().strip())

    def handle_send_to_powerpoint_shortcut(self):
        if self.bible_view.text_browser.hasFocus():
            self.bible_view.trigger_send_to_powerpoint()
        elif self.crossref_text_browser.hasFocus():
            cursor = self.crossref_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_powerpoint.emit(self, cursor.selection().toPlainText().strip())
    # ----------------------------------------

    @Slot(QPoint)
    def show_crossref_context_menu(self, pos):
        menu = QMenu(self)
        pos_cursor = self.crossref_text_browser.cursorForPosition(pos)
        block_text = pos_cursor.block().text()
        
        # --- 수정된 부분: 정규식 변경 ---
        # (창 1:1) 또는 창 1:1 형태 모두 인식하도록 수정
        verse_match = re.match(r'^\(?\s*([가-힣A-Za-z]+)\s*(\d+):(\d+)', block_text)
        # ---------------------------

        position_actions_added = False

        if verse_match:
            book_abbr, chapter_str, verse_str = verse_match.groups()
            book_full_name = self.data_loader.book_alias_map.get(book_abbr)
            
            if book_full_name:
                chapter_num, verse_num = int(chapter_str), int(verse_str)
                
                nav_action = menu.addAction("이 구절로 이동")
                nav_action.triggered.connect(lambda: self.request_navigation.emit(book_full_name, chapter_num, verse_num))

                new_tab_action = menu.addAction("읽기탭추가해서 이동하기")
                new_tab_action.triggered.connect(lambda: self.request_new_read_tab.emit(book_full_name, chapter_num, verse_num))

                position_actions_added = True
        
        if position_actions_added:
            menu.addSeparator()

        text_cursor = self.crossref_text_browser.textCursor()
        has_selection = text_cursor.hasSelection()

        # --- 복사하기 액션 추가 ---
        copy_action = menu.addAction("복사하기")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.crossref_text_browser.copy)
        menu.addSeparator()
        # ------------------------

        search_action = menu.addAction("검색")
        word_action = menu.addAction("MS Word로 보내기 (Ctrl+W)")
        ppt_action = menu.addAction("MS PowerPoint로 보내기 (Ctrl+P)")
        search_action.setEnabled(has_selection)
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)
        if has_selection:
            selected_text = text_cursor.selection().toPlainText().strip()
            search_translation = self.crossref_translation_combo.currentText()
            search_action.triggered.connect(lambda: self.request_search.emit(selected_text, search_translation))
            word_action.triggered.connect(lambda: self.request_send_to_word.emit(selected_text))
            ppt_action.triggered.connect(lambda: self.request_send_to_powerpoint.emit(self, selected_text))
        menu.exec(self.crossref_text_browser.mapToGlobal(pos))

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.bible_view.set_font_family(font_name)
        self.crossref_text_browser.setFont(QFont(self.font_family, self.crossref_font_size))
        # self.crossref_current_verse_label.setFont(QFont(self.font_family, self.crossref_font_size + 2, QFont.Bold)) # 삭제
        self.crossref_current_verse_label.setFont(QFont(self.font_family, self.crossref_current_verse_label.font().pointSize(), QFont.Bold)) # 크기 고정

    @Slot(int)
    def set_bible_font_size(self, size):
        self.bible_view.set_font_size(size)

    @Slot(str)
    def set_bible_translation(self, translation):
        self.bible_view.set_translation(translation)

    @Slot(int)
    def set_verse_display_mode(self, mode_id):
        self.bible_view.set_verse_display_mode(mode_id)
        
    def set_crossref_font_size(self, size):
        """외부에서 관주 폰트 크기를 설정하는 메서드"""
        self.crossref_font_size = max(8, min(30, size))
        self.crossref_text_browser.setFont(QFont(self.font_family, self.crossref_font_size))
        self.update_crossref_display()
        self.settings_changed.emit()

    @Slot(str)
    def on_crossref_translation_changed(self, text):
        self.crossref_translation = text
        self.update_crossref_display()
        self.settings_changed.emit()

    # --- 추가된 슬롯 ---
    @Slot(int)
    def on_style_option_changed(self, style_id):
        """관주 표시 스타일 라디오 버튼 클릭 시 호출되는 슬롯"""
        self.crossref_style_mode = style_id
        self.update_crossref_display()
        self.settings_changed.emit() # 설정 저장을 위해 시그널 발생
    # ------------------

    @Slot(QUrl)
    def on_verse_clicked(self, url):
        verse_num_str = url.fragment()
        if verse_num_str:
            try:
                self.current_verse = int(verse_num_str)
                self.update_crossref_display()
            except (ValueError) as e:
                print(f"Warning: 관주 구절 번호 파싱 오류 '{verse_num_str}': {e}")

    def update_crossref_display(self):
        self.crossref_text_browser.clear()
        
        # --- 수정된 부분 ---
        # self.current_book (풀네임)의 약어를 가져옵니다.
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, self.current_book)
        # 라벨 텍스트를 풀네임 대신 약어로 설정합니다.
        self.crossref_current_verse_label.setText(f"{book_abbr} {self.current_chapter}:{self.current_verse}")
        # ----------------
        
        translation = self.crossref_translation
        self._set_word_wrap_mode(self.crossref_text_browser, translation)
        cross_refs = self.crossref_data_loader.loaded_crossref_data.get(self.current_book, {}) \
            .get(int(self.current_chapter), {}).get(self.current_verse, [])
        if not cross_refs:
            self.crossref_text_browser.setHtml(f"<p>'{self.current_book} {self.current_chapter}:{self.current_verse}'에 대한 관주 정보가 없습니다.</p>")
            return
        cross_refs.sort()
        grouped_refs = []
        if cross_refs:
            current_group = [cross_refs[0]]
            for i in range(1, len(cross_refs)):
                prev_book, prev_chap, prev_verse = cross_refs[i-1]
                curr_book, curr_chap, curr_verse = cross_refs[i]
                if curr_book == prev_book and curr_chap == prev_chap and curr_verse == prev_verse + 1:
                    current_group.append(cross_refs[i])
                else:
                    grouped_refs.append(current_group)
                    current_group = [cross_refs[i]]
            grouped_refs.append(current_group)
        html_content = []
        # CSS 스타일 추가: 폰트 굵기 일관성 유지
        html_content.append("<style>a { font-weight: normal !important; } p { font-weight: normal; } span { font-weight: normal; }</style>")
        text_color_name = QApplication.palette().color(QPalette.ColorRole.Text).name()
        for group in grouped_refs:
            start_ref, end_ref = group[0], group[-1]
            ref_book, ref_chapter, ref_verse_start, ref_verse_end = start_ref[0], start_ref[1], start_ref[2], end_ref[2]
            book_abbr = self.data_loader.full_name_to_abbr_map.get(ref_book, "")
            ref_display = f"{book_abbr} {ref_chapter}:{ref_verse_start}" + (f"-{ref_verse_end}" if ref_verse_start != ref_verse_end else "")
            
            # --- 수정된 부분: self.crossref_style_mode에 따라 prefix 텍스트 결정 ---
            if self.crossref_style_mode == 0: # (창 1:1)
                prefix_text = f"({ref_display})"
            else: # 창 1:1
                prefix_text = ref_display
            
            prefix = f"<span style='font-weight:normal; color:{text_color_name};'>{prefix_text}</span>"
            # ------------------------------------------------------------------

            verse_html_parts = []
            for ref_book_item, ref_chapter_item, ref_verse_item in group:
                verse_text = self.data_loader.get_verse_text(translation, ref_book_item, ref_chapter_item, ref_verse_item)
                if verse_text:
                    if len(group) > 1:
                        part = f"<span style='font-weight:normal; color:{text_color_name};'>({ref_verse_item})</span> <span style='font-weight:normal;'>{verse_text}</span>"
                    else:
                        part = f"<span style='font-weight:normal;'>{verse_text}</span>"
                    verse_html_parts.append(part)
            html_content.append(f"<p style='line-height: 1.4;'>{prefix} {' '.join(verse_html_parts)}</p>")
        self.crossref_text_browser.setHtml("".join(html_content))

    def _set_word_wrap_mode(self, text_browser, translation_name):
        try:
            data = self.data_loader.load_translation_data(translation_name)
            language = data.get('language', 'unknown')
            wrap_mode = QTextOption.WrapAnywhere if language in ['korean', 'chinese'] else QTextOption.WrapAtWordBoundaryOrAnywhere
            text_browser.setWordWrapMode(wrap_mode)
        except Exception:
            text_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

    def update_all_content(self, book_name, chapter_num, current_verse_from_main=None):
        self.current_book = book_name
        self.current_chapter = chapter_num
        if current_verse_from_main is not None:
            self.current_verse = current_verse_from_main
        self.bible_view.update_content(book_name, chapter_num)
        self.update_crossref_display()
        self.update_location_status()

    def update_location_status(self):
        try:
            translation = self.bible_view.translation_combo.currentText()
            if not translation: return
            translation_data = self.data_loader.load_translation_data(translation)
            chapter_content = translation_data["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
            verse_count = len([line for line in chapter_content if not line.startswith('<')])
            status_text = f"{self.current_book} {self.current_chapter}장 (총 {verse_count}절)"
            self.status_label_left.setText(status_text)
        except Exception as e:
            self.status_label_left.setText(f"상태 정보 로드 오류: {e}")

    def show_temporary_message(self, message):
        self.status_timer.stop()
        self.status_label_left.setText(message)
        self.status_timer.start(5000)