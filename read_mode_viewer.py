# read_mode_viewer.py
import re
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QComboBox, QTextBrowser, QFrame,
    QRadioButton, QButtonGroup, QListWidget, QListWidgetItem,
    QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QEvent
from PySide6.QtGui import QFont, QKeyEvent, QTextOption, QPalette, QKeySequence, QShortcut

# BookChapterPopup 클래스 정의를 삭제하고 아래 import 문으로 대체합니다.
from popups import BookChapterPopup

class ReadModeViewer(QDialog):
    """
    성경 본문을 전체 화면으로 보여주는 읽기 모드 전용 뷰어 클래스.
    """
    location_changed = Signal(str, int)

    def __init__(self, data_loader, initial_settings, toolbar_stylesheet="", parent=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.settings = initial_settings
        self.toolbar_stylesheet = toolbar_stylesheet

        # 초기 설정값 추출
        self.current_book = self.settings.get('book', '창세기')
        self.current_chapter = self.settings.get('chapter', 1)
        self.current_translation = self.settings.get('translation', self.data_loader.get_available_translations()[0])
        self.font_family = self.settings.get('font_family', 'Malgun Gothic')
        self.font_size = self.settings.get('bible_font_size', 20)
        self.verse_display_mode = self.settings.get('verse_display_mode', 0)

        # 창 테두리 제거 플래그 추가
        self.setWindowFlags(Qt.FramelessWindowHint | self.windowFlags())

        self.init_ui()
        self.connect_signals()
        self.update_content()
        self.setWindowTitle(f"읽기 모드: {self.current_book} {self.current_chapter}장")
        self.setWindowState(Qt.WindowState.WindowFullScreen) # 작업 표시줄까지 숨기는 전체 화면

    def init_ui(self):
        """UI 요소를 초기화하고 배치합니다."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # 1. 상단 메뉴 바 생성 (QToolBar로 변경)
        menu_bar = self.create_menu_bar()
        # 전달받은 메인 프로그램의 툴바 스타일을 그대로 적용
        menu_bar.setStyleSheet(self.toolbar_stylesheet)
        main_layout.addWidget(menu_bar)

        # 2. 본문 표시를 위한 텍스트 브라우저
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setFont(QFont(self.font_family, self.font_size))
        # QTextBrowser 자체에 여백 설정
        self.text_browser.setViewportMargins(200, 20, 200, 20) # left, top, right, bottom
        main_layout.addWidget(self.text_browser, 1)

    def create_menu_bar(self):
        """읽기 모드 상단의 메뉴 바를 QToolBar로 생성합니다."""
        menu_toolbar = QToolBar()
        menu_toolbar.setMovable(False)
        menu_toolbar.setFloatable(False)

        # 번역본 선택
        menu_toolbar.addWidget(QLabel("번역본:"))
        self.translation_combo = QComboBox()
        self.translation_combo.addItems(self.data_loader.get_available_translations())
        self.translation_combo.setCurrentText(self.current_translation)
        menu_toolbar.addWidget(self.translation_combo)

        # 글자 크기 조절
        menu_toolbar.addSeparator()
        self.font_minus_btn = QPushButton("-")
        self.font_size_label = QLabel(str(self.font_size))
        self.font_plus_btn = QPushButton("+")
        menu_toolbar.addWidget(self.font_minus_btn)
        menu_toolbar.addWidget(self.font_size_label)
        menu_toolbar.addWidget(self.font_plus_btn)
        
        # 구절 표시 스타일
        menu_toolbar.addSeparator()
        menu_toolbar.addWidget(QLabel("절 표시:"))
        self.style_group = QButtonGroup(self)
        self.style_radio1 = QRadioButton("(창 1:1)")
        self.style_radio2 = QRadioButton("창 1:1")
        self.style_radio3 = QRadioButton("1.")
        # 라디오 버튼들을 QToolBar에 직접 추가할 수 없으므로, 위젯으로 감싸서 추가합니다.
        style_widget = QWidget()
        style_layout = QHBoxLayout(style_widget)
        style_layout.setContentsMargins(0,0,0,0)
        style_layout.addWidget(self.style_radio1)
        style_layout.addWidget(self.style_radio2)
        style_layout.addWidget(self.style_radio3)
        self.style_group.addButton(self.style_radio1, 0)
        self.style_group.addButton(self.style_radio2, 1)
        self.style_group.addButton(self.style_radio3, 2)
        menu_toolbar.addWidget(style_widget)
        
        radio_to_check = self.style_group.button(self.verse_display_mode)
        if radio_to_check:
            radio_to_check.setChecked(True)

        # 네비게이션
        menu_toolbar.addSeparator()
        self.prev_chap_btn = QPushButton("< 이전 장")
        self.location_btn = QPushButton(f"{self.current_book} {self.current_chapter}장")
        self.location_btn.setFixedWidth(140)
        self.next_chap_btn = QPushButton("다음 장 >")
        self.nav_input = QLineEdit()
        self.nav_input.setPlaceholderText("예: 창1:1")
        self.nav_input.setFixedWidth(100)
        self.go_btn = QPushButton("이동")
        
        menu_toolbar.addWidget(self.prev_chap_btn)
        menu_toolbar.addWidget(self.location_btn)
        menu_toolbar.addWidget(self.next_chap_btn)
        menu_toolbar.addWidget(self.nav_input)
        menu_toolbar.addWidget(self.go_btn)

        # --- 중앙 빈 공간 ---
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        menu_toolbar.addWidget(spacer)

        # --- 우측 정렬 위젯 ---
        self.close_btn = QPushButton("읽기 모드 닫기 (Esc)")
        menu_toolbar.addWidget(self.close_btn)
        
        return menu_toolbar

    def connect_signals(self):
        """위젯들의 시그널-슬롯을 연결합니다."""
        self.close_btn.clicked.connect(self.accept)
        self.translation_combo.currentTextChanged.connect(self.on_translation_changed)
        self.font_plus_btn.clicked.connect(lambda: self.change_font_size(1))
        self.font_minus_btn.clicked.connect(lambda: self.change_font_size(-1))
        self.prev_chap_btn.clicked.connect(self.go_to_prev_chapter)
        self.next_chap_btn.clicked.connect(self.go_to_next_chapter)
        self.go_btn.clicked.connect(self.navigate_from_input)
        self.nav_input.returnPressed.connect(self.navigate_from_input)
        self.style_group.idClicked.connect(self.on_style_changed)
        self.location_btn.clicked.connect(self.show_book_chapter_popup)

        # 포커스와 상관없이 좌/우 화살표 키가 동작하도록 QShortcut을 사용합니다.
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.go_to_prev_chapter)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.go_to_next_chapter)

    def update_content(self):
        """현재 책, 장에 맞는 성경 본문을 불러와 화면에 표시합니다."""
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
        
        html_body_content = []
        palette = self.palette()
        text_color_name = palette.color(QPalette.ColorRole.Text).name()
        
        verse_counter = 1
        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, "")
        
        is_after_subtitle = False

        for line in chapter_content:
            subtitle_match = re.match(r'<\s*(.+?)\s*>', line)
            if subtitle_match:
                html_body_content.append(f"<p style='text-align:center; font-weight:bold; font-size: 1.2em; color:{text_color_name}; margin-top:20px; margin-bottom:15px;'>{subtitle_match.group(1)}</p>")
                is_after_subtitle = True
            else:
                verse_prefix = ""
                if self.verse_display_mode == 0:
                    verse_prefix = f"<span style='color: {text_color_name};'>({book_abbr} {self.current_chapter}:{verse_counter})</span>"
                elif self.verse_display_mode == 1:
                    verse_prefix = f"<span style='color: {text_color_name};'>{book_abbr} {self.current_chapter}:{verse_counter}</span>"
                elif self.verse_display_mode == 2:
                    verse_prefix = f"<span style='color: {text_color_name};'>{verse_counter}.</span>"
                
                margin_top_style = ""
                if is_after_subtitle:
                    margin_top_style = "margin-top: 30px;"
                    is_after_subtitle = False

                verse_html = f"""
                <table style="border-collapse: collapse; margin-bottom: 8px; {margin_top_style}">
                    <tr>
                        <td style="width: 1px; white-space: nowrap; padding-right: 15px; vertical-align: top;">
                           {verse_prefix}
                        </td>
                        <td style="vertical-align: top; line-height: 1.6; color:{text_color_name};">
                           {line}
                        </td>
                    </tr>
                </table>
                """
                html_body_content.append(verse_html)
                verse_counter += 1
        
        self.text_browser.setHtml("".join(html_body_content))
        
        book_num = next((num for num, _, full in self.data_loader.book_definitions if full == self.current_book), "")
        self.location_btn.setText(f"{book_num}{self.current_book} {self.current_chapter}장")
        self.setWindowTitle(f"읽기 모드: {self.current_book} {self.current_chapter}장")
        self.set_word_wrap_mode(translation)

    def set_word_wrap_mode(self, translation_name):
        """번역본 언어에 따라 줄 바꿈 모드를 설정합니다."""
        try:
            data = self.data_loader.load_translation_data(translation_name)
            language = data.get('language', 'unknown')
            wrap_mode = QTextOption.WrapAnywhere if language in ['korean', 'chinese'] else QTextOption.WrapAtWordBoundaryOrAnywhere
            self.text_browser.setWordWrapMode(wrap_mode)
        except Exception:
            self.text_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

    @Slot(str)
    def on_translation_changed(self, text):
        """번역본 콤보박스 선택이 변경되었을 때 호출됩니다."""
        self.current_translation = text
        self.update_content()
        
    @Slot(int)
    def on_style_changed(self, mode_id):
        """구절 표시 스타일이 변경되었을 때 호출됩니다."""
        self.verse_display_mode = mode_id
        self.update_content()

    @Slot(int)
    def change_font_size(self, delta):
        """글자 크기를 조절합니다."""
        self.font_size = max(10, self.font_size + delta)
        self.font_size_label.setText(str(self.font_size))
        self.text_browser.setFont(QFont(self.font_family, self.font_size))

    def navigate_to(self, book, chapter):
        """지정된 책과 장으로 이동합니다."""
        max_chapter = self.data_loader.global_book_chapter_counts.get(book, 0)
        if not (1 <= chapter <= max_chapter): return
        
        self.current_book = book
        self.current_chapter = chapter
        self.update_content()
        self.location_changed.emit(self.current_book, self.current_chapter)

    @Slot()
    def go_to_prev_chapter(self):
        """이전 장으로 이동합니다."""
        new_chapter = self.current_chapter - 1
        if new_chapter > 0:
            self.navigate_to(self.current_book, new_chapter)
        else:  # 이전 책으로 이동
            idx = next((i for i, (_, _, full) in enumerate(self.data_loader.book_definitions) if full == self.current_book), -1)
            if idx > 0:
                prev_book_name = self.data_loader.book_definitions[idx - 1][2]
                last_chapter = self.data_loader.global_book_chapter_counts.get(prev_book_name, 1)
                self.navigate_to(prev_book_name, last_chapter)

    @Slot()
    def go_to_next_chapter(self):
        """다음 장으로 이동합니다."""
        new_chapter = self.current_chapter + 1
        if new_chapter <= self.data_loader.global_book_chapter_counts.get(self.current_book, 0):
            self.navigate_to(self.current_book, new_chapter)
        else:  # 다음 책으로 이동
            idx = next((i for i, (_, _, full) in enumerate(self.data_loader.book_definitions) if full == self.current_book), -1)
            if 0 <= idx < len(self.data_loader.book_definitions) - 1:
                next_book_name = self.data_loader.book_definitions[idx + 1][2]
                self.navigate_to(next_book_name, 1)

    @Slot()
    def navigate_from_input(self):
        """입력창의 내용으로 이동합니다."""
        text = self.nav_input.text().strip().lower()
        match = re.match(r'([a-zA-Z가-힣]+)\s*(\d+)(?:\s*:\s*(\d+))?', text)
        if not match:
            match = re.match(r'([a-zA-Z가-힣]+)(\d+)(?:\s*:\s*(\d+))?', text)
        if not match: return
        
        book_query, chapter_str, _ = match.groups()
        book_name = self.data_loader.full_book_names.get(book_query, self.data_loader.book_alias_map.get(book_query))
        if book_name:
            self.navigate_to(book_name, int(chapter_str))
            self.nav_input.clear()
            
    @Slot()
    def show_book_chapter_popup(self):
        """책/장 선택 팝업을 표시합니다."""
        popup = BookChapterPopup(self.data_loader, self)
        popup.selection_made.connect(self.navigate_to)
        popup.move(self.location_btn.mapToGlobal(self.location_btn.rect().bottomLeft()))
        popup.show()

    def keyPressEvent(self, event: QKeyEvent):
        """키보드 입력을 처리합니다 (Esc)."""
        # QShortcut으로 처리하므로 좌/우 키 처리는 제거합니다.
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)