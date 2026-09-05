# commentary_tab.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextBrowser,
    QRadioButton, QButtonGroup, QLabel, QPushButton, QApplication, QMenu, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QTimer, QPoint
from PySide6.QtGui import QFont, QTextOption, QPalette

from bible_view import SharedBibleView
from html_utils import PlainCopyTextBrowser

class CommentaryTab(QWidget):
    settings_changed = Signal()
    request_search = Signal(str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)

    def __init__(self, data_loader, commentary_data_loader, parent=None, initial_settings=None, bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.commentary_data_loader = commentary_data_loader
        self.bible_db = bible_db
        if initial_settings is None: initial_settings = {}
        self.current_book = initial_settings.get('book', '창세기')
        self.current_chapter = initial_settings.get('chapter', 1)
        self.current_verse = 1
        self.commentary_display_mode = 0
        self.font_size = initial_settings.get('commentary_font_size', 12)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.update_location_status)
        self.init_ui(initial_settings)
        self.connect_signals()
        self.commentary_data_loader.set_book_definitions(self.data_loader.book_definitions)
        self.commentary_data_loader.load_commentary_data()

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
            'translation': self.data_loader.get_available_translations()[0],
            'bible_font_size': initial_settings.get('bible_font_size', 14),
            'font_family': self.font_family,
            'verse_display_mode': initial_settings.get('verse_display_mode', 0)
        }
        self.bible_view = SharedBibleView(
            self.data_loader, self.data_loader.get_available_translations(),
            initial_settings=bible_view_settings, is_main_reader=True, context='commentary', bible_db=self.bible_db
        )
        bible_view_layout.addWidget(self.bible_view)
        self.splitter.addWidget(bible_view_container)

        commentary_widget = QWidget()
        commentary_layout = QVBoxLayout(commentary_widget)
        commentary_layout.setContentsMargins(2, 2, 2, 2)
        commentary_layout.setSpacing(2)
        
        # 주석 탭 컨트롤 바
        control_bar = QHBoxLayout()
        control_bar.setContentsMargins(2, 2, 2, 2)
        
        # '호크마주석' 라벨 추가 (위치 변경)
        self.hokma_label = QLabel("호크마주석")
        self.hokma_label.setStyleSheet("font-weight: bold;")
        control_bar.addWidget(self.hokma_label)
        control_bar.addSpacing(10) # 간격 추가
        
        self.verse_commentary_radio = QRadioButton("절")
        self.chapter_commentary_radio = QRadioButton("장")
        self.commentary_mode_group = QButtonGroup(self)
        self.commentary_mode_group.addButton(self.verse_commentary_radio, 0)
        self.commentary_mode_group.addButton(self.chapter_commentary_radio, 1)
        self.verse_commentary_radio.setChecked(True)
        
        control_bar.addWidget(self.verse_commentary_radio)
        control_bar.addWidget(self.chapter_commentary_radio)
        
        # 장절 정보 라벨 (기존 commentary_header_label의 위치를 변경)
        self.commentary_location_label = QLabel("")
        self.commentary_location_label.setStyleSheet("font-weight: bold; font-size: 10pt; margin-top: 4px; margin-bottom: 4px;")
        self.commentary_location_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        control_bar.addStretch(1) # 우측 정렬을 위해 stretch 추가
        control_bar.addWidget(self.commentary_location_label)

        commentary_layout.addLayout(control_bar)
        
        self.commentary_text_browser = PlainCopyTextBrowser()
        self.commentary_text_browser.setFont(QFont(self.font_family, self.font_size))
        self.commentary_text_browser.setOpenExternalLinks(False)
        self.commentary_text_browser.setWordWrapMode(QTextOption.WrapAnywhere)
        self.commentary_text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        commentary_layout.addWidget(self.commentary_text_browser)
        self.splitter.addWidget(commentary_widget)

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
        
        main_layout.addLayout(status_container) # 레이아웃 추가
        
        self.splitter.setSizes([self.width() * 0.5, self.width() * 0.5])

    def connect_signals(self):
        self.commentary_mode_group.idClicked.connect(self.set_commentary_display_mode)
        self.bible_view.verse_anchor_clicked.connect(self.on_verse_clicked)
        self.commentary_text_browser.customContextMenuRequested.connect(self.show_commentary_context_menu)

    # --- 단축키 핸들러 추가 ---
    def handle_send_to_word_shortcut(self):
        if self.bible_view.text_browser.hasFocus():
            self.bible_view.trigger_send_to_word()
        elif self.commentary_text_browser.hasFocus():
            cursor = self.commentary_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_word.emit(cursor.selection().toPlainText().strip())

    def handle_send_to_powerpoint_shortcut(self):
        if self.bible_view.text_browser.hasFocus():
            self.bible_view.trigger_send_to_powerpoint()
        elif self.commentary_text_browser.hasFocus():
            cursor = self.commentary_text_browser.textCursor()
            if cursor.hasSelection():
                self.request_send_to_powerpoint.emit(self, cursor.selection().toPlainText().strip())
    # ----------------------------------------

    @Slot(QPoint)
    def show_commentary_context_menu(self, pos):
        menu = QMenu(self)
        text_cursor = self.commentary_text_browser.textCursor()
        has_selection = text_cursor.hasSelection()

        # --- 복사하기 액션 추가 ---
        copy_action = menu.addAction("복사하기")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.commentary_text_browser.copy)
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
            search_translation = self.bible_view.translation_combo.currentText()
            search_action.triggered.connect(lambda: self.request_search.emit(selected_text, search_translation))
            word_action.triggered.connect(lambda: self.request_send_to_word.emit(selected_text))
            ppt_action.triggered.connect(lambda: self.request_send_to_powerpoint.emit(self, selected_text))
        menu.exec(self.commentary_text_browser.mapToGlobal(pos))

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.bible_view.set_font_family(font_name)
        # self.commentary_header_label.setFont(QFont(self.font_family, self.font_size, QFont.Bold)) # 삭제
        self.commentary_text_browser.setFont(QFont(self.font_family, self.font_size))

    @Slot(int)
    def set_bible_font_size(self, size):
        self.bible_view.set_font_size(size)

    @Slot(str)
    def set_bible_translation(self, translation):
        self.bible_view.set_translation(translation)
        
    @Slot(int)
    def set_verse_display_mode(self, mode_id):
        self.bible_view.set_verse_display_mode(mode_id)

    def set_commentary_font_size(self, size):
        """외부에서 주석 폰트 크기를 설정하는 메서드"""
        self.font_size = max(8, min(30, size))
        self.commentary_text_browser.setFont(QFont(self.font_family, self.font_size))
        self.settings_changed.emit()

    @Slot(int)
    def set_commentary_display_mode(self, mode_id):
        self.commentary_display_mode = mode_id
        self.update_commentary_display()
        
    @Slot(QUrl)
    def on_verse_clicked(self, url):
        verse_num_str = url.fragment()
        if verse_num_str:
            try:
                verse_num = int(verse_num_str)
                self.current_verse = verse_num
                if self.commentary_display_mode == 0:
                    self.update_commentary_display()
            except (ValueError) as e:
                print(f"Warning: Could not parse verse number from URL fragment '{verse_num_str}': {e}")

    def update_commentary_display(self):
        commentary_html = []
        # CSS 스타일 추가: 폰트 굵기 일관성 유지
        commentary_html.append("<style>a { font-weight: normal !important; } p { font-weight: normal; }</style>")
        commentaries = self.commentary_data_loader.loaded_commentary_data.get(self.current_book, {})
        
        # --- 수정된 부분 ---
        # self.current_book (풀네임)의 약어를 가져옵니다.
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, self.current_book)
        # ----------------

        if self.commentary_display_mode == 0:
            # --- 수정된 부분 ---
            # 라벨 텍스트를 풀네임 대신 약어로 설정합니다.
            header_text = f"{book_abbr} {self.current_chapter}:{self.current_verse}"
            # ----------------
            self.commentary_location_label.setText(header_text) # 라벨 업데이트
            verse_commentary = commentaries.get(int(self.current_chapter), {}).get(self.current_verse, [])
            if verse_commentary:
                for text in verse_commentary:
                    commentary_html.append(f"<p style='font-weight:normal; line-height: 1.4;'>{text}</p>")
            else:
                commentary_html.append(f"<p>'{header_text}'에 대한 주석이 없습니다.</p>")
        else:
            # --- 수정된 부분 ---
            # 라벨 텍스트를 풀네임 대신 약어로 설정합니다.
            header_text = f"{book_abbr} {self.current_chapter}장"
            # ----------------
            self.commentary_location_label.setText(header_text) # 라벨 업데이트
            chapter_commentaries = commentaries.get(int(self.current_chapter), {})
            if chapter_commentaries:
                for verse_num in sorted(chapter_commentaries.keys()):
                    commentary_html.append(f"<p style='font-weight:bold; margin-top: 10px; line-height: 1.2;'>{verse_num}절:</p>")
                    for text in chapter_commentaries[verse_num]:
                        commentary_html.append(f"<p style='font-weight:normal; margin-left: 15px; line-height: 1.2;'>{text}</p>")
            else:
                commentary_html.append(f"<p>'{header_text}'에 대한 주석이 없습니다.</p>")
        self.commentary_text_browser.setHtml("".join(commentary_html))

    def update_all_content(self, book_name, chapter_num, current_verse_from_main=None):
        self.current_book = book_name
        self.current_chapter = chapter_num
        if current_verse_from_main is not None:
            self.current_verse = current_verse_from_main
        self.bible_view.update_content(book_name, chapter_num)
        self.update_commentary_display()
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