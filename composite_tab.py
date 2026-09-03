# composite_tab.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextBrowser,
    QRadioButton, QButtonGroup, QLabel, QPushButton, QApplication, QMenu, QFrame,
    QComboBox
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QTimer, QPoint
from PySide6.QtGui import QFont, QTextOption, QPalette

from bible_view import SharedBibleView

class CompositeTab(QWidget):
    # 모든 자식 위젯의 시그널을 중계합니다.
    settings_changed = Signal()
    request_search = Signal(str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)
    request_navigation = Signal(str, int, int)
    request_new_read_tab = Signal(str, int, int)
    request_commentary = Signal(str, int, int)
    request_cross_ref = Signal(str, int, int)

    def __init__(self, data_loader, commentary_data_loader, crossref_data_loader, parent=None, initial_settings=None, bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.commentary_data_loader = commentary_data_loader
        self.crossref_data_loader = crossref_data_loader
        self.bible_db = bible_db
        
        if initial_settings is None: initial_settings = {}
        
        # 공통 상태
        self.current_book = initial_settings.get('book', '창세기')
        self.current_chapter = initial_settings.get('chapter', 1)
        self.current_verse = 1
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.available_translations = self.data_loader.get_available_translations()
        default_translation = self.available_translations[0] if self.available_translations else ""

        # 주석 탭 상태 (고유 설정값 사용)
        self.commentary_display_mode = 0 # 0: 절, 1: 장
        self.commentary_font_size = initial_settings.get('composite_commentary_font_size', 12)

        # 관주 탭 상태 (고유 설정값 사용)
        self.crossref_font_size = initial_settings.get('composite_crossref_font_size', 12)
        self.crossref_translation = initial_settings.get('composite_crossref_translation', default_translation)
        self.crossref_style_mode = initial_settings.get('composite_crossref_style_mode', 0)

        # 접기/펼치기 상태 변수
        self.commentary_collapsed = False
        self.crossref_collapsed = False
        self.commentary_saved_size = 1000
        self.crossref_saved_size = 1000
        self.MIN_COLLAPSED_WIDTH = 150  # 접힘 상태 최소 폭

        # 상태 표시줄 타이머
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.update_location_status)
        
        self.init_ui(initial_settings)
        self.connect_signals()

    def init_ui(self, initial_settings):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1)

        # 1. 성경 뷰 위젯 (SharedBibleView)
        bible_view_settings = {
            'translation': self.available_translations[0],
            'bible_font_size': initial_settings.get('bible_font_size', 14),
            'font_family': self.font_family,
            'verse_display_mode': initial_settings.get('verse_display_mode', 0)
        }
        self.bible_view = SharedBibleView(
            self.data_loader, self.available_translations,
            initial_settings=bible_view_settings, is_main_reader=True, context='composite', bible_db=self.bible_db
        )
        self.splitter.addWidget(self.bible_view)

        # 2. 주석 뷰 위젯 (commentary_tab.py에서 복사 및 수정)
        self.commentary_widget = self._create_commentary_view_widget()
        self.splitter.addWidget(self.commentary_widget)

        # 3. 관주 뷰 위젯 (crossref_tab.py에서 복사 및 수정)
        self.crossref_widget = self._create_crossref_view_widget()
        self.splitter.addWidget(self.crossref_widget)
        
        # 상태 표시줄
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
        
        # <<< 수정됨: 세 창의 크기를 동일하게 1:1:1 비율로 설정 (큰 값으로)
        self.splitter.setSizes([1000, 1000, 1000])
        
        # 최소 폭 설정 (접기 시 컨트롤 바만 보이도록)
        self.commentary_widget.setMinimumWidth(self.MIN_COLLAPSED_WIDTH)
        self.crossref_widget.setMinimumWidth(self.MIN_COLLAPSED_WIDTH)

    # --- commentary_tab.py에서 복사 ---
    def _create_commentary_view_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        control_bar = QHBoxLayout()
        control_bar.setContentsMargins(2, 2, 2, 2)
        
        # 접기/펼치기 버튼 추가
        self.commentary_collapse_btn = QPushButton("▼")
        self.commentary_collapse_btn.setFixedSize(24, 24); self.commentary_collapse_btn.setProperty("compact", "true")
        self.commentary_collapse_btn.setToolTip("주석 영역 접기/펼치기")
        control_bar.addWidget(self.commentary_collapse_btn)
        control_bar.addSpacing(5)
        
        self.hokma_label = QLabel("호크마주석")
        self.hokma_label.setStyleSheet("font-weight: bold;")
        control_bar.addWidget(self.hokma_label)
        control_bar.addSpacing(10)
        
        self.verse_commentary_radio = QRadioButton("절")
        self.chapter_commentary_radio = QRadioButton("장")
        self.commentary_mode_group = QButtonGroup(self)
        self.commentary_mode_group.addButton(self.verse_commentary_radio, 0)
        self.commentary_mode_group.addButton(self.chapter_commentary_radio, 1)
        self.verse_commentary_radio.setChecked(True)
        
        control_bar.addWidget(self.verse_commentary_radio)
        control_bar.addWidget(self.chapter_commentary_radio)
        
        self.commentary_location_label = QLabel("")
        self.commentary_location_label.setStyleSheet("font-weight: bold; font-size: 10pt; margin-top: 4px; margin-bottom: 4px;")
        self.commentary_location_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        control_bar.addStretch(1)
        control_bar.addWidget(self.commentary_location_label)
        
        # 접기/펼치기 시 표시/숨김을 위한 위젯 목록 저장
        self.commentary_control_widgets = [
            self.verse_commentary_radio,
            self.chapter_commentary_radio,
            self.commentary_location_label
        ]

        layout.addLayout(control_bar)
        
        self.commentary_text_browser = QTextBrowser()
        self.commentary_text_browser.setFont(QFont(self.font_family, self.commentary_font_size))
        self.commentary_text_browser.setOpenExternalLinks(False)
        self.commentary_text_browser.setWordWrapMode(QTextOption.WrapAnywhere)
        self.commentary_text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # QTextBrowser가 남은 공간을 모두 차지하도록 stretch factor 설정
        layout.addWidget(self.commentary_text_browser, 1)
        # 접기 상태에서 버튼과 라벨이 위쪽에 위치하도록 stretch 추가
        layout.addStretch()
        
        return widget

    # --- crossref_tab.py에서 복사 ---
    def _create_crossref_view_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        control_bar = QFrame()
        control_bar.setObjectName("subCommandBar")
        control_bar_layout = QHBoxLayout(control_bar)
        control_bar_layout.setContentsMargins(6, 4, 6, 4)

        # 접기/펼치기 버튼 추가
        self.crossref_collapse_btn = QPushButton("▼")
        self.crossref_collapse_btn.setFixedSize(24, 24); self.crossref_collapse_btn.setProperty("compact", "true")
        self.crossref_collapse_btn.setToolTip("관주 영역 접기/펼치기")
        control_bar_layout.addWidget(self.crossref_collapse_btn)
        control_bar_layout.addSpacing(5)
        
        # 관주 제목 라벨 추가
        self.crossref_title_label = QLabel("관주")
        self.crossref_title_label.setStyleSheet("font-weight: bold;")
        control_bar_layout.addWidget(self.crossref_title_label)
        control_bar_layout.addSpacing(10)
        
        self.crossref_translation_combo = QComboBox()
        self.crossref_translation_combo.addItems(self.available_translations)
        self.crossref_translation_combo.setCurrentText(self.crossref_translation)
        
        control_bar_layout.addWidget(self.crossref_translation_combo)
        control_bar_layout.addSpacing(10)
        self.crossref_style_option_group = QButtonGroup(self)
        self.crossref_style_radio1 = QRadioButton("(1:1)")
        self.crossref_style_radio2 = QRadioButton("1:1")
        self.crossref_style_option_group.addButton(self.crossref_style_radio1, 0)
        self.crossref_style_option_group.addButton(self.crossref_style_radio2, 1)
        
        if self.crossref_style_mode == 1:
            self.crossref_style_radio2.setChecked(True)
        else:
            self.crossref_style_radio1.setChecked(True)
            
        control_bar_layout.addWidget(self.crossref_style_radio1)
        control_bar_layout.addWidget(self.crossref_style_radio2)

        self.crossref_current_verse_label = QLabel("")
        self.crossref_current_verse_label.setStyleSheet("font-weight: bold; font-size: 10pt; margin-top: 4px; margin-bottom: 4px;")
        self.crossref_current_verse_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        control_bar_layout.addStretch(1)
        control_bar_layout.addWidget(self.crossref_current_verse_label)
        
        # 접기/펼치기 시 표시/숨김을 위한 위젯 목록 저장
        self.crossref_control_widgets = [
            self.crossref_translation_combo,
            self.crossref_style_radio1,
            self.crossref_style_radio2,
            self.crossref_current_verse_label
        ]

        self.crossref_text_browser = QTextBrowser()
        self.crossref_text_browser.setFont(QFont(self.font_family, self.crossref_font_size))
        self.crossref_text_browser.setReadOnly(True)
        self.crossref_text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        layout.addWidget(control_bar)
        # QTextBrowser가 남은 공간을 모두 차지하도록 stretch factor 설정
        layout.addWidget(self.crossref_text_browser, 1)
        # 접기 상태에서 버튼과 라벨이 위쪽에 위치하도록 stretch 추가
        layout.addStretch()
        
        return widget

    def connect_signals(self):
        # 1. 성경 뷰 시그널
        self.bible_view.verse_anchor_clicked.connect(self.on_verse_clicked)
        # 성경 뷰의 컨텍스트 메뉴 시그널을 중계
        self.bible_view.request_commentary.connect(self.request_commentary)
        self.bible_view.request_cross_ref.connect(self.request_cross_ref)
        self.bible_view.request_search.connect(self.request_search)
        self.bible_view.request_send_to_word.connect(self.request_send_to_word)
        self.bible_view.request_send_to_powerpoint.connect(self.request_send_to_powerpoint)
        
        # 2. 주석 뷰 시그널
        self.commentary_mode_group.idClicked.connect(self.set_commentary_display_mode)
        self.commentary_text_browser.customContextMenuRequested.connect(self.show_commentary_context_menu)

        # 3. 관주 뷰 시그널
        self.crossref_translation_combo.currentTextChanged.connect(self.on_crossref_translation_changed)
        self.crossref_style_option_group.idClicked.connect(self.on_crossref_style_option_changed)
        self.crossref_text_browser.customContextMenuRequested.connect(self.show_crossref_context_menu)
        
        # 4. 접기/펼치기 버튼 시그널
        self.commentary_collapse_btn.clicked.connect(self.toggle_commentary)
        self.crossref_collapse_btn.clicked.connect(self.toggle_crossref)

    # --- 공통 로직 ---

    @Slot(QUrl)
    def on_verse_clicked(self, url):
        """성경 뷰에서 절을 클릭하면 주석과 관주를 모두 업데이트합니다."""
        verse_num_str = url.fragment()
        if verse_num_str:
            try:
                verse_num = int(verse_num_str)
                self.current_verse = verse_num
                # 절 모드일 때만 주석 업데이트
                if self.commentary_display_mode == 0:
                    self.update_commentary_display()
                # 관주는 항상 업데이트
                self.update_crossref_display()
            except (ValueError) as e:
                print(f"Warning: Could not parse verse number: {e}")

    def update_all_content(self, book_name, chapter_num, current_verse_from_main=None):
        """MainWindow에서 호출되는 메인 업데이트 함수"""
        self.current_book = book_name
        self.current_chapter = chapter_num
        if current_verse_from_main is not None:
            self.current_verse = current_verse_from_main
        
        self.bible_view.update_content(book_name, chapter_num)
        self.update_commentary_display()
        self.update_crossref_display()
        self.update_location_status()

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.bible_view.set_font_family(font_name)
        self.commentary_text_browser.setFont(QFont(self.font_family, self.commentary_font_size))
        self.crossref_text_browser.setFont(QFont(self.font_family, self.crossref_font_size))
        # 라벨 폰트도 업데이트
        self.commentary_location_label.setFont(QFont(self.font_family, self.commentary_location_label.font().pointSize(), QFont.Bold))
        self.crossref_current_verse_label.setFont(QFont(self.font_family, self.crossref_current_verse_label.font().pointSize(), QFont.Bold))


    def set_verse_display_mode(self, mode_id):
        """(MainWindow에서 호출) 성경 뷰의 절 표시 스타일 변경"""
        self.bible_view.set_verse_display_mode(mode_id)

    # --- 주석 로직 (commentary_tab.py에서 복사) ---

    @Slot(int)
    def set_commentary_display_mode(self, mode_id):
        self.commentary_display_mode = mode_id
        self.update_commentary_display()
        
    def set_commentary_font_size(self, size):
        """외부에서 주석 폰트 크기를 설정하는 메서드"""
        self.commentary_font_size = max(8, min(30, size))
        self.commentary_text_browser.setFont(QFont(self.font_family, self.commentary_font_size))
        self.settings_changed.emit()

    def update_commentary_display(self):
        commentary_html = []
        commentaries = self.commentary_data_loader.loaded_commentary_data.get(self.current_book, {})
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, self.current_book)

        if self.commentary_display_mode == 0: # 절 모드
            header_text = f"{book_abbr} {self.current_chapter}:{self.current_verse}"
            self.commentary_location_label.setText(header_text)
            verse_commentary = commentaries.get(int(self.current_chapter), {}).get(self.current_verse, [])
            if verse_commentary:
                for text in verse_commentary:
                    commentary_html.append(f"<p style='line-height: 1.4;'>{text}</p>")
            else:
                commentary_html.append(f"<p>'{header_text}'에 대한 주석이 없습니다.</p>")
        else: # 장 모드
            header_text = f"{book_abbr} {self.current_chapter}장"
            self.commentary_location_label.setText(header_text)
            chapter_commentaries = commentaries.get(int(self.current_chapter), {})
            if chapter_commentaries:
                for verse_num in sorted(chapter_commentaries.keys()):
                    commentary_html.append(f"<p style='font-weight:bold; margin-top: 10px; line-height: 1.2;'>{verse_num}절:</p>")
                    for text in chapter_commentaries[verse_num]:
                        commentary_html.append(f"<p style='margin-left: 15px; line-height: 1.2;'>{text}</p>")
            else:
                commentary_html.append(f"<p>'{header_text}'에 대한 주석이 없습니다.</p>")
        self.commentary_text_browser.setHtml("".join(commentary_html))

    @Slot(QPoint)
    def show_commentary_context_menu(self, pos):
        menu = QMenu(self)
        text_cursor = self.commentary_text_browser.textCursor()
        has_selection = text_cursor.hasSelection()

        copy_action = menu.addAction("복사하기")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.commentary_text_browser.copy)
        menu.addSeparator()

        search_action = menu.addAction("검색")
        word_action = menu.addAction("MS Word로 보내기 (Ctrl+W)")
        ppt_action = menu.addAction("MS PowerPoint로 보내기 (Ctrl+P)")
        search_action.setEnabled(has_selection)
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)

        if has_selection:
            selected_text = text_cursor.selection().toPlainText().strip()
            search_translation = self.bible_view.translation_combo.currentText()
            search_action.triggered.connect(lambda: self.request_search.emit(selected_text, search_translation))
            word_action.triggered.connect(lambda: self.request_send_to_word.emit(selected_text))
            ppt_action.triggered.connect(lambda: self.request_send_to_powerpoint.emit(self, selected_text))
        menu.exec(self.commentary_text_browser.mapToGlobal(pos))

    # --- 관주 로직 (crossref_tab.py에서 복사) ---

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

    @Slot(int)
    def on_crossref_style_option_changed(self, style_id):
        self.crossref_style_mode = style_id
        self.update_crossref_display()
        self.settings_changed.emit()

    def update_crossref_display(self):
        self.crossref_text_browser.clear()
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, self.current_book)
        self.crossref_current_verse_label.setText(f"{book_abbr} {self.current_chapter}:{self.current_verse}")
        
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
            
            prefix_text = f"({ref_display})" if self.crossref_style_mode == 0 else ref_display
            prefix = f"<span style='font-weight:normal; color:{text_color_name};'>{prefix_text}</span>" 
            
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

    @Slot(QPoint)
    def show_crossref_context_menu(self, pos):
        menu = QMenu(self)
        pos_cursor = self.crossref_text_browser.cursorForPosition(pos)
        block_text = pos_cursor.block().text()
        
        verse_match = re.match(r'^\(?\s*([가-힣A-Za-z]+)\s*(\d+):(\d+)', block_text)
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

        copy_action = menu.addAction("복사하기")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.crossref_text_browser.copy)
        menu.addSeparator()

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

    # --- 상태 표시줄 및 단축키 핸들러 ---

    def update_location_status(self):
        """하단 상태 표시줄의 좌측 텍스트를 업데이트합니다."""
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
        """하단 상태 표시줄에 임시 메시지를 표시합니다."""
        self.status_timer.stop()
        self.status_label_left.setText(message)
        self.status_timer.start(5000)

    def handle_send_to_word_shortcut(self):
        if self.bible_view.text_browser.hasFocus():
            self.bible_view.trigger_send_to_word()
        elif self.commentary_text_browser.hasFocus():
            cursor = self.commentary_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_word.emit(cursor.selection().toPlainText().strip())
        elif self.crossref_text_browser.hasFocus():
            cursor = self.crossref_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_word.emit(cursor.selection().toPlainText().strip())

    def handle_send_to_powerpoint_shortcut(self):
        if self.bible_view.text_browser.hasFocus():
            self.bible_view.trigger_send_to_powerpoint()
        elif self.commentary_text_browser.hasFocus():
            cursor = self.commentary_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_powerpoint.emit(self, cursor.selection().toPlainText().strip())
        elif self.crossref_text_browser.hasFocus():
            cursor = self.crossref_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_powerpoint.emit(self, cursor.selection().toPlainText().strip())
    
    def toggle_commentary(self):
        """주석 영역 접기/펼치기"""
        current_sizes = self.splitter.sizes()
        
        if self.commentary_collapsed:
            # 펼치기: 펼쳐진 창의 개수에 따라 동적으로 너비 계산
            self.commentary_collapsed = False
            total_width = sum(current_sizes)
            
            # 펼쳐진 창의 개수 확인 (성경 본문은 항상 펼쳐져 있음)
            expanded_count = 1  # 성경 본문
            if not self.crossref_collapsed:
                expanded_count += 1  # 관주
            expanded_count += 1  # 주석 (지금 펼치는 중)
            
            # 접힌 창의 너비 계산
            collapsed_width = 0
            if self.crossref_collapsed:
                collapsed_width += self.MIN_COLLAPSED_WIDTH
            
            # 펼쳐진 창들이 사용할 수 있는 너비
            available_width = total_width - collapsed_width
            
            if expanded_count == 3:
                # 3개 모두 펼쳐져 있으면 각각 1/3씩
                each_width = int(available_width / 3)
                bible_width = each_width
                commentary_width = each_width
                crossref_width = each_width if not self.crossref_collapsed else self.MIN_COLLAPSED_WIDTH
            elif expanded_count == 2:
                # 2개만 펼쳐져 있으면 각각 1/2씩
                each_width = int(available_width / 2)
                bible_width = each_width
                commentary_width = each_width
                crossref_width = self.MIN_COLLAPSED_WIDTH if self.crossref_collapsed else each_width
            else:
                # 1개만 펼쳐져 있으면 모든 너비 차지
                bible_width = available_width
                commentary_width = available_width
                crossref_width = self.MIN_COLLAPSED_WIDTH
            
            self.splitter.setSizes([bible_width, commentary_width, crossref_width])
            self.commentary_collapse_btn.setText("▼")
            # 펼침 상태에서 텍스트 브라우저 및 컨트롤 보이기
            self.commentary_text_browser.setVisible(True)
            for widget in self.commentary_control_widgets:
                widget.setVisible(True)
        else:
            # 접기: 현재 크기 저장 후 최소 폭으로 축소
            self.commentary_saved_size = current_sizes[1]
            self.commentary_collapsed = True
            
            # 나머지 영역이 공간을 차지하도록 크기 조정
            total_width = sum(current_sizes)
            available_width = total_width - self.MIN_COLLAPSED_WIDTH
            
            # 관주가 이미 접혀있는지 확인
            if self.crossref_collapsed:
                # 관주도 접혀있으면 성경 본문만 확장
                bible_width = available_width
                crossref_width = self.MIN_COLLAPSED_WIDTH
            else:
                # 관주가 펼쳐져 있으면 성경 본문과 관주의 비율 유지
                bible_ratio = current_sizes[0] / (current_sizes[0] + current_sizes[2]) if (current_sizes[0] + current_sizes[2]) > 0 else 0.5
                crossref_ratio = current_sizes[2] / (current_sizes[0] + current_sizes[2]) if (current_sizes[0] + current_sizes[2]) > 0 else 0.5
                bible_width = int(available_width * bible_ratio)
                crossref_width = int(available_width * crossref_ratio)
            
            self.splitter.setSizes([bible_width, self.MIN_COLLAPSED_WIDTH, crossref_width])
            self.commentary_collapse_btn.setText("▶")
            # 접힘 상태에서 텍스트 브라우저 및 컨트롤 숨기기
            self.commentary_text_browser.setVisible(False)
            for widget in self.commentary_control_widgets:
                widget.setVisible(False)
    
    def toggle_crossref(self):
        """관주 영역 접기/펼치기"""
        current_sizes = self.splitter.sizes()
        
        if self.crossref_collapsed:
            # 펼치기: 펼쳐진 창의 개수에 따라 동적으로 너비 계산
            self.crossref_collapsed = False
            total_width = sum(current_sizes)
            
            # 펼쳐진 창의 개수 확인 (성경 본문은 항상 펼쳐져 있음)
            expanded_count = 1  # 성경 본문
            if not self.commentary_collapsed:
                expanded_count += 1  # 주석
            expanded_count += 1  # 관주 (지금 펼치는 중)
            
            # 접힌 창의 너비 계산
            collapsed_width = 0
            if self.commentary_collapsed:
                collapsed_width += self.MIN_COLLAPSED_WIDTH
            
            # 펼쳐진 창들이 사용할 수 있는 너비
            available_width = total_width - collapsed_width
            
            if expanded_count == 3:
                # 3개 모두 펼쳐져 있으면 각각 1/3씩
                each_width = int(available_width / 3)
                bible_width = each_width
                commentary_width = each_width if not self.commentary_collapsed else self.MIN_COLLAPSED_WIDTH
                crossref_width = each_width
            elif expanded_count == 2:
                # 2개만 펼쳐져 있으면 각각 1/2씩
                each_width = int(available_width / 2)
                bible_width = each_width
                commentary_width = self.MIN_COLLAPSED_WIDTH if self.commentary_collapsed else each_width
                crossref_width = each_width
            else:
                # 1개만 펼쳐져 있으면 모든 너비 차지
                bible_width = available_width
                commentary_width = self.MIN_COLLAPSED_WIDTH
                crossref_width = available_width
            
            self.splitter.setSizes([bible_width, commentary_width, crossref_width])
            self.crossref_collapse_btn.setText("▼")
            # 펼침 상태에서 텍스트 브라우저 및 컨트롤 보이기
            self.crossref_text_browser.setVisible(True)
            for widget in self.crossref_control_widgets:
                widget.setVisible(True)
        else:
            # 접기: 현재 크기 저장 후 최소 폭으로 축소
            self.crossref_saved_size = current_sizes[2]
            self.crossref_collapsed = True
            
            # 나머지 영역이 공간을 차지하도록 크기 조정
            total_width = sum(current_sizes)
            available_width = total_width - self.MIN_COLLAPSED_WIDTH
            
            # 주석이 이미 접혀있는지 확인
            if self.commentary_collapsed:
                # 주석도 접혀있으면 성경 본문만 확장
                bible_width = available_width
                commentary_width = self.MIN_COLLAPSED_WIDTH
            else:
                # 주석이 펼쳐져 있으면 성경 본문과 주석의 비율 유지
                bible_ratio = current_sizes[0] / (current_sizes[0] + current_sizes[1]) if (current_sizes[0] + current_sizes[1]) > 0 else 0.5
                commentary_ratio = current_sizes[1] / (current_sizes[0] + current_sizes[1]) if (current_sizes[0] + current_sizes[1]) > 0 else 0.5
                bible_width = int(available_width * bible_ratio)
                commentary_width = int(available_width * commentary_ratio)
            
            self.splitter.setSizes([bible_width, commentary_width, self.MIN_COLLAPSED_WIDTH])
            self.crossref_collapse_btn.setText("▶")
            # 접힘 상태에서 텍스트 브라우저 및 컨트롤 숨기기
            self.crossref_text_browser.setVisible(False)
            for widget in self.crossref_control_widgets:
                widget.setVisible(False)