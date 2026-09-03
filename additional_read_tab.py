# additional_read_tab.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QSplitter, QComboBox, QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from bible_view import SharedBibleView
from popups import BookChapterPopup

class AdditionalReadTab(QWidget):
    """
    독립적인 탐색 기능을 가진 추가 읽기 탭 위젯 클래스.
    """
    # MainWindow와 통신하기 위한 시그널
    request_search = Signal(str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)
    request_commentary = Signal(str, int, int)
    request_cross_ref = Signal(str, int, int)
    location_changed = Signal(object, str) # 탭 제목 변경을 위한 신호 추가
    settings_changed = Signal()

    def __init__(self, data_loader, parent=None, initial_settings=None, bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.bible_db = bible_db
        self.available_translations = self.data_loader.get_available_translations()
        self.initial_settings = initial_settings if initial_settings else {}
        self._is_scrolling = False

        # 독립적인 상태 변수
        self.current_book = self.initial_settings.get('book', "창세기")
        self.current_chapter = self.initial_settings.get('chapter', 1)
        self.font_family = self.initial_settings.get('font_family', 'Malgun Gothic')
        self.font_size = self.initial_settings.get('bible_font_size', 14) 
        
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.update_location_status)

        self.init_ui()
        self.connect_signals()
        
        # 초기 뷰 생성 및 콘텐츠 로드
        self.update_navigation_display()
        self.add_bible_view()
        self.update_all_views(self.current_book, self.current_chapter)
        
        # 생성 시점에 초기 탭 제목을 설정하도록 신호 발생 (QTimer를 사용하여 안정적으로 처리)
        QTimer.singleShot(0, self.update_tab_title)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        # 툴바를 인스턴스 변수로 저장하여 외부에서 접근 가능하도록 함
        self.toolbar = self.create_toolbar()
        main_layout.addWidget(self.toolbar)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1)

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

    def create_toolbar(self):
        toolbar = QToolBar("AdditionalReadTab Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)

        # 네비게이션 컨트롤
        self.prev_book_btn = QPushButton("<<"); self.prev_chap_btn = QPushButton("<")
        self.location_btn = QPushButton(); self.next_chap_btn = QPushButton(">"); self.next_book_btn = QPushButton(">>")
        self.nav_input = QLineEdit(); self.go_btn = QPushButton("이동")
        self.prev_book_btn.setToolTip("이전 책"); self.prev_chap_btn.setToolTip("이전 장")
        self.location_btn.setToolTip("책/장 목록 열기"); self.next_chap_btn.setToolTip("다음 장")
        self.next_book_btn.setToolTip("다음 책"); self.nav_input.setPlaceholderText("이동 (예: 창1:1)")
        self.nav_input.setMaximumWidth(90)
        toolbar.addWidget(self.prev_book_btn); toolbar.addWidget(self.prev_chap_btn)
        toolbar.addWidget(self.location_btn); toolbar.addWidget(self.next_chap_btn)
        toolbar.addWidget(self.next_book_btn); toolbar.addWidget(self.nav_input)
        toolbar.addWidget(self.go_btn); toolbar.addSeparator()

        # 창 분할 컨트롤
        toolbar.addWidget(QLabel("창 분할:")); self.view_count_combo = QComboBox()
        self.view_count_combo.addItems([str(i) for i in range(1, 5)])
        toolbar.addWidget(self.view_count_combo); toolbar.addSeparator()

        # 폰트 크기 컨트롤
        self.font_minus_button = QPushButton("-"); self.font_size_label = QLabel(str(self.font_size))
        self.font_plus_button = QPushButton("+")
        for _b in (self.font_minus_button, self.font_plus_button):
            _b.setProperty("compact", "true"); _b.setFixedSize(26, 26)
        toolbar.addWidget(self.font_minus_button); toolbar.addWidget(self.font_size_label)
        toolbar.addWidget(self.font_plus_button)
        
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar.addWidget(spacer)
        return toolbar

    def connect_signals(self):
        self.prev_book_btn.clicked.connect(self.go_to_prev_book); self.prev_chap_btn.clicked.connect(self.go_to_prev_chapter)
        self.next_chap_btn.clicked.connect(self.go_to_next_chapter); self.next_book_btn.clicked.connect(self.go_to_next_book)
        self.go_btn.clicked.connect(self.navigate_from_input); self.nav_input.returnPressed.connect(self.navigate_from_input)
        self.location_btn.clicked.connect(self.show_book_chapter_popup)
        self.view_count_combo.currentIndexChanged.connect(self.on_view_count_selected)
        self.font_plus_button.clicked.connect(lambda: self.change_font_size(1)); self.font_minus_button.clicked.connect(lambda: self.change_font_size(-1))
    
    def update_tab_title(self):
        """현재 위치를 기반으로 탭 제목을 생성하고 신호를 발생시키는 메서드."""
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, "")
        new_title = f"{book_abbr} {self.current_chapter}"
        self.location_changed.emit(self, new_title)

    def navigate_to(self, book, chapter):
        if self.current_book == book and self.current_chapter == chapter: return
        max_chapter = self.data_loader.global_book_chapter_counts.get(book, 0)
        if not (1 <= chapter <= max_chapter): return
        self.current_book, self.current_chapter = book, chapter
        self.update_navigation_display()
        self.update_all_views(book, chapter)
        self.update_tab_title() # 위치 변경 시 탭 제목 업데이트

    def update_navigation_display(self):
        book_num = next((num for num, _, full in self.data_loader.book_definitions if full == self.current_book), "")
        self.location_btn.setText(f"{book_num}{self.current_book} {self.current_chapter}장")

    @Slot()
    def navigate_from_input(self):
        text = self.nav_input.text().strip().lower()
        match = re.match(r'([a-zA-Z가-힣]+)\s*(\d+)(?:\s*:\s*(\d+))?', text)
        if not match: match = re.match(r'([a-zA-Z가-힣]+)(\d+)(?:\s*:\s*(\d+))?', text)
        if not match: return
        book_query, chapter_str, verse_str = match.groups()
        book_name = self.data_loader.full_book_names.get(book_query, self.data_loader.book_alias_map.get(book_query))
        if book_name:
            self.navigate_to(book_name, int(chapter_str))
            if verse_str: self.scroll_to_verse(int(verse_str))
            self.nav_input.clear()

    @Slot()
    def go_to_prev_chapter(self): self.go_to_adjacent_chapter(-1)
    @Slot()
    def go_to_next_chapter(self): self.go_to_adjacent_chapter(1)

    def go_to_adjacent_chapter(self, delta):
        new_chapter = self.current_chapter + delta
        if 1 <= new_chapter <= self.data_loader.global_book_chapter_counts.get(self.current_book, 0):
             self.navigate_to(self.current_book, new_chapter)
        else:
            idx = next((i for i, (_, _, full) in enumerate(self.data_loader.book_definitions) if full == self.current_book), -1)
            if delta < 0 and idx > 0:
                prev_book_name = self.data_loader.book_definitions[idx - 1][2]
                last_chapter = self.data_loader.global_book_chapter_counts.get(prev_book_name, 1)
                self.navigate_to(prev_book_name, last_chapter)
            elif delta > 0 and 0 <= idx < len(self.data_loader.book_definitions) - 1:
                next_book_name = self.data_loader.book_definitions[idx + 1][2]
                self.navigate_to(next_book_name, 1)

    @Slot()
    def go_to_prev_book(self): self.go_to_adjacent_book(-1)
    @Slot()
    def go_to_next_book(self): self.go_to_adjacent_book(1)
    
    def go_to_adjacent_book(self, delta):
        idx = next((i for i, (_, _, full) in enumerate(self.data_loader.book_definitions) if full == self.current_book), -1)
        if 0 <= idx + delta < len(self.data_loader.book_definitions):
            new_book_name = self.data_loader.book_definitions[idx + delta][2]
            self.navigate_to(new_book_name, 1)

    @Slot()
    def show_book_chapter_popup(self):
        popup = BookChapterPopup(self.data_loader, self)
        popup.selection_made.connect(self.navigate_to)
        popup.move(self.location_btn.mapToGlobal(self.location_btn.rect().bottomLeft())); popup.show()

    def get_bible_views(self): return [self.splitter.widget(i) for i in range(self.splitter.count())]

    @Slot()
    def add_bible_view(self):
        if self.splitter.count() >= 4: return
        view_settings = {'translation': self.available_translations[0], 'bible_font_size': self.font_size, 'font_family': self.font_family, 'verse_display_mode': 0}
        new_view = SharedBibleView(self.data_loader, self.available_translations, initial_settings=view_settings, context='read', bible_db=self.bible_db)
        new_view.request_search.connect(self.request_search)
        new_view.request_send_to_word.connect(self.request_send_to_word); new_view.request_send_to_powerpoint.connect(self.request_send_to_powerpoint)
        new_view.request_commentary.connect(self.request_commentary); new_view.request_cross_ref.connect(self.request_cross_ref)
        new_view.scroll_changed.connect(self.sync_scroll)
        self.splitter.addWidget(new_view)
        new_view.update_content(self.current_book, self.current_chapter)
        self.update_view_count_display(self.splitter.count())

    @Slot()
    def remove_bible_view(self):
        if self.splitter.count() > 1:
            widget = self.splitter.widget(self.splitter.count() - 1)
            widget.setParent(None)  # 스플리터에서 즉시 분리하여 count()가 줄어들도록 함 (무한루프 방지)
            widget.deleteLater()
            self.update_view_count_display(self.splitter.count())

    @Slot(int)
    def on_view_count_selected(self, index):
        target_count = index + 1
        while self.splitter.count() < target_count: self.add_bible_view()
        while self.splitter.count() > target_count: self.remove_bible_view()

    def update_view_count_display(self, count):
        self.view_count_combo.blockSignals(True)
        self.view_count_combo.setCurrentIndex(count - 1)
        self.view_count_combo.blockSignals(False)

    def update_all_views(self, book, chapter):
        self.current_book, self.current_chapter = book, chapter
        for view in self.get_bible_views(): view.update_content(book, chapter)
        self.update_location_status()

    def update_location_status(self):
        if not self.available_translations: return
        try:
            chapter_content = self.data_loader.load_translation_data(self.available_translations[0])["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
            verse_count = len([line for line in chapter_content if not line.startswith('<')])
            self.status_label_left.setText(f"{self.current_book} {self.current_chapter}장 (총 {verse_count}절)")
        except Exception as e: self.status_label_left.setText(f"상태 정보 로드 오류: {e}")

    def scroll_to_verse(self, verse_num):
        if views := self.get_bible_views(): views[0].scroll_to_verse(verse_num)

    @Slot(int)
    def sync_scroll(self, value):
        if self._is_scrolling: return
        self._is_scrolling = True
        sender_widget = self.sender().parent()
        for view in self.get_bible_views():
            if view is not sender_widget:
                if (scrollbar := view.text_browser.verticalScrollBar()).value() != value: scrollbar.setValue(value)
        self._is_scrolling = False

    def set_font_family(self, font_name):
        self.font_family = font_name
        for view in self.get_bible_views(): view.set_font_family(font_name)

    def change_font_size(self, delta):
        self.font_size = max(8, self.font_size + delta)
        self.font_size_label.setText(str(self.font_size))
        for view in self.get_bible_views(): view.set_font_size(self.font_size)
        self.settings_changed.emit()

    def set_verse_display_mode(self, mode_id):
        for view in self.get_bible_views(): view.set_verse_display_mode(mode_id)
        
    def show_temporary_message(self, message):
        self.status_timer.stop()
        self.status_label_left.setText(message)
        self.status_timer.start(5000)

    def handle_send_to_word_shortcut(self):
        for view in self.get_bible_views():
            if view.text_browser.hasFocus(): view.trigger_send_to_word(); break
    def handle_send_to_powerpoint_shortcut(self):
        for view in self.get_bible_views():
            if view.text_browser.hasFocus(): view.trigger_send_to_powerpoint(); break