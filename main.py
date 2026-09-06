# main.py
import sys
import re
import json
import os
try:
    import win32com.client
    import pythoncom
    from pywintypes import com_error
except ImportError:
    win32com = None

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTabWidget, QTextBrowser,
    QComboBox, QSplitter, QFrame,
    QRadioButton, QButtonGroup, QMenu, QMessageBox,
    QFontDialog, QDialog, QGridLayout, QFileDialog, QToolBar, QSizePolicy,
    QTabBar
)
from PySide6.QtCore import Qt, Signal, Slot, QEvent, QTimer, QSize
from PySide6.QtGui import (
    QFont, QCloseEvent, QPalette, QAction, QActionGroup, QTextOption,
    QIcon, QKeySequence, QShortcut, QColor, QPainter, QPen
)

from data_loaders import BibleDataLoader, CommentaryDataLoader, CrossrefDataLoader
from bible_view import SharedBibleView
from commentary_tab import CommentaryTab
from crossref_tab import CrossRefTab
from search_tab import SearchTab
from read_mode_viewer import ReadModeViewer
from memo_tab import MemoTab
from popups import BookChapterPopup
from additional_read_tab import AdditionalReadTab
from composite_tab import CompositeTab
from bible_database import BibleDatabase
from original_language_data import OriginalLanguageDataLoader
from original_language_tab import OriginalLanguageTab
from ai_explain import (
    GeminiClient, AiExplanationDialog, AiSettingsDialog,
    build_prompt, build_question_prompt, DEFAULT_MODEL, LEGACY_DEFAULT_MODELS,
)


import qdarktheme

from ui_theme import (
    TOKENS, office_qss, resolve_mode, themed_icon,
    FONT_FAMILY_PRIMARY, FONT_POINT_SIZE,
)
from body_style import body_style_from_settings, body_style_to_settings
from body_style_dialog import BodyStyleDialog

class CloseButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setToolTip("탭 닫기")
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color = self.palette().color(QPalette.ColorRole.Highlight if self._hovered else QPalette.ColorRole.Text)
        
        pen = QPen(color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        margin = 5
        rect = self.rect()
        painter.drawLine(rect.left() + margin, rect.top() + margin, rect.right() - margin, rect.bottom() - margin)
        painter.drawLine(rect.right() - margin, rect.top() + margin, rect.left() + margin, rect.bottom() - margin)

class TextExtractorDialog(QDialog):
    def __init__(self, data_loader, parent=None, initial_settings=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.initial_settings = initial_settings if initial_settings else {}
        self.setWindowTitle("본문 추출")
        self.setMinimumWidth(400)
        self.book_names = [book[2] for book in self.data_loader.book_definitions]
        self.init_ui()
        self.connect_signals()
        self.load_initial_values()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(1, 1)

        grid_layout.addWidget(QLabel("번역본 선택:"), 0, 0)
        self.translation_combo = QComboBox()
        self.translation_combo.addItems(self.data_loader.get_available_translations())
        grid_layout.addWidget(self.translation_combo, 0, 1)

        grid_layout.addWidget(QLabel("시작 책:"), 1, 0)
        self.start_book_combo = QComboBox()
        self.start_book_combo.addItems(self.book_names)
        grid_layout.addWidget(self.start_book_combo, 1, 1)

        grid_layout.addWidget(QLabel("시작 장:"), 2, 0)
        self.start_chapter_combo = QComboBox()
        grid_layout.addWidget(self.start_chapter_combo, 2, 1)

        grid_layout.addWidget(QLabel("끝 책:"), 3, 0)
        self.end_book_combo = QComboBox()
        self.end_book_combo.addItems(self.book_names)
        grid_layout.addWidget(self.end_book_combo, 3, 1)

        grid_layout.addWidget(QLabel("끝 장:"), 4, 0)
        self.end_chapter_combo = QComboBox()
        grid_layout.addWidget(self.end_chapter_combo, 4, 1)

        grid_layout.addWidget(QLabel("구절 표시:"), 5, 0)
        style_layout = QHBoxLayout()
        self.style_group = QButtonGroup(self)
        self.style_radio1 = QRadioButton("(창 1:1)")
        self.style_radio2 = QRadioButton("창 1:1")
        self.style_radio3 = QRadioButton("1.")
        self.style_group.addButton(self.style_radio1, 0)
        self.style_group.addButton(self.style_radio2, 1)
        self.style_group.addButton(self.style_radio3, 2)
        style_layout.addWidget(self.style_radio1); style_layout.addWidget(self.style_radio2); style_layout.addWidget(self.style_radio3)
        style_layout.addStretch()
        grid_layout.addLayout(style_layout, 5, 1)
        
        main_layout.addLayout(grid_layout)

        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.extract_button = QPushButton("본문 추출 및 저장")
        self.close_button = QPushButton("닫기")
        button_layout.addWidget(self.extract_button)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

    def connect_signals(self):
        self.start_book_combo.currentTextChanged.connect(self.update_start_chapter_combo)
        self.end_book_combo.currentTextChanged.connect(self.update_end_chapter_combo)
        self.extract_button.clicked.connect(self.extract_and_save)
        self.close_button.clicked.connect(self.accept)

    def load_initial_values(self):
        current_book = self.initial_settings.get('book', '창세기')
        current_chapter = self.initial_settings.get('chapter', 1)
        verse_display_mode = self.initial_settings.get('verse_display_mode', 0)
        
        self.start_book_combo.setCurrentText(current_book)
        self.end_book_combo.setCurrentText(current_book)
        
        self.update_start_chapter_combo(current_book)
        self.update_end_chapter_combo(current_book)
        
        self.start_chapter_combo.setCurrentText(str(current_chapter))
        self.end_chapter_combo.setCurrentText(str(current_chapter))
        
        radio_button = self.style_group.button(verse_display_mode)
        if radio_button:
            radio_button.setChecked(True)

    def update_start_chapter_combo(self, book_name):
        self.update_chapter_combo(book_name, self.start_chapter_combo)

    def update_end_chapter_combo(self, book_name):
        self.update_chapter_combo(book_name, self.end_chapter_combo)

    def update_chapter_combo(self, book_name, combo_box):
        if not book_name: return
        combo_box.blockSignals(True)
        current_chapter = combo_box.currentText()
        combo_box.clear()
        chapter_count = self.data_loader.global_book_chapter_counts.get(book_name, 0)
        combo_box.addItems([str(i) for i in range(1, chapter_count + 1)])
        if current_chapter and int(current_chapter) <= chapter_count:
            combo_box.setCurrentText(current_chapter)
        combo_box.blockSignals(False)

    def extract_and_save(self):
        translation = self.translation_combo.currentText()
        start_book, end_book = self.start_book_combo.currentText(), self.end_book_combo.currentText()
        start_chapter, end_chapter = int(self.start_chapter_combo.currentText()), int(self.end_chapter_combo.currentText())
        verse_style = self.style_group.checkedId()
        
        start_book_index, end_book_index = self.book_names.index(start_book), self.book_names.index(end_book)
        
        if start_book_index > end_book_index or (start_book_index == end_book_index and start_chapter > end_chapter):
            QMessageBox.warning(self, "범위 오류", "시작 위치가 끝 위치보다 뒤에 있을 수 없습니다.")
            return

        default_filename = f"{start_book}{start_chapter}-{end_book}{end_chapter}_{translation}.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "텍스트 파일로 저장", default_filename, "Text Files (*.txt);;All Files (*)")
        
        if not file_path: return
            
        try:
            bible_data = self.data_loader.load_translation_data(translation)['bible_data']
            lines_to_write = []
            is_first_chapter_in_loop = True

            for book_idx in range(start_book_index, end_book_index + 1):
                book_name = self.book_names[book_idx]
                book_abbr = self.data_loader.full_name_to_abbr_map.get(book_name, "")
                
                s_chap = start_chapter if book_idx == start_book_index else 1
                e_chap = end_chapter if book_idx == end_book_index else self.data_loader.global_book_chapter_counts.get(book_name, 0)
                
                book_content = bible_data.get(book_name, {})
                for chap_num in range(s_chap, e_chap + 1):
                    chapter_content = book_content.get(str(chap_num), [])
                    if not chapter_content: continue

                    if not is_first_chapter_in_loop:
                        lines_to_write.append("") 
                    
                    lines_to_write.append(f"{book_name} {chap_num}장")
                    is_first_chapter_in_loop = False

                    verse_counter = 1
                    
                    for line in chapter_content:
                        if re.match(r'<\s*(.+?)\s*>', line):
                            continue
                        
                        prefix = ""
                        if verse_style == 0: prefix = f"({book_abbr} {chap_num}:{verse_counter}) "
                        elif verse_style == 1: prefix = f"{book_abbr} {chap_num}:{verse_counter} "
                        elif verse_style == 2: prefix = f"{verse_counter}. "
                        
                        lines_to_write.append(f"{prefix}{line}")
                        verse_counter += 1
            
            final_text = "\n".join(lines_to_write)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_text)

            QMessageBox.information(self, "저장 완료", f"본문을 '{os.path.basename(file_path)}' 파일로 저장했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"본문 추출 중 오류가 발생했습니다: {e}")

class ReadTab(QWidget):
    view_count_changed = Signal(int)
    view_added = Signal(SharedBibleView)

    def __init__(self, data_loader, parent=None, initial_settings=None, bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.bible_db = bible_db
        self.available_translations = self.data_loader.get_available_translations()
        self._is_scrolling = False
        self.initial_settings = initial_settings if initial_settings else {}
        
        self.current_book = self.initial_settings.get('book', "창세기")
        self.current_chapter = self.initial_settings.get('chapter', 1)
        
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.update_location_status)
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1)

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
    
    def populate_initial_views(self):
        self.add_initial_bible_views()

    def set_font_family(self, font_name):
        for view in self.get_bible_views():
            view.set_font_family(font_name)

    def get_bible_views(self):
        return [self.splitter.widget(i) for i in range(self.splitter.count())]

    def add_initial_bible_views(self):
        num_views = self.initial_settings.get('num_views', 1)
        view_translations = self.initial_settings.get('view_translations', [])
        for i in range(num_views):
            settings = self.initial_settings.copy()
            settings['translation'] = view_translations[i] if i < len(view_translations) else self.available_translations[0]
            self.add_bible_view(initial_settings=settings)
        
    @Slot()
    def add_bible_view(self, initial_settings=None):
        if self.splitter.count() >= 4: return
        if initial_settings is None:
            initial_settings = {}
            if self.splitter.count() > 0:
                leftmost_view = self.splitter.widget(0)
                initial_settings = {
                    'translation': leftmost_view.translation_combo.currentText(),
                    'bible_font_size': leftmost_view.font_size,
                    'font_family': leftmost_view.font_family,
                    'verse_display_mode': leftmost_view.verse_display_mode
                }
            else:
                initial_settings = self.initial_settings
        new_view = SharedBibleView(self.data_loader, self.available_translations, initial_settings=initial_settings, is_main_reader=True, context='read', bible_db=self.bible_db)
        self.splitter.addWidget(new_view)
        new_view.scroll_changed.connect(self.sync_scroll)
        self.view_added.emit(new_view)
        self.view_count_changed.emit(self.splitter.count())

    @Slot()
    def remove_bible_view(self):
        if self.splitter.count() > 1:
            widget_to_remove = self.splitter.widget(self.splitter.count() - 1)
            # 위젯을 스플리터에서 즉시 분리하여 count()가 정확해지도록 함
            widget_to_remove.setParent(None) 
            widget_to_remove.deleteLater()
            # 이제 self.splitter.count()는 올바른 값을 반환함
            self.view_count_changed.emit(self.splitter.count())

    @Slot(int)
    def sync_scroll(self, value):
        if self._is_scrolling: return
        self._is_scrolling = True
        sender_widget = self.sender().parent()
        for view in self.get_bible_views():
            if view is not sender_widget:
                scrollbar = view.text_browser.verticalScrollBar()
                if scrollbar.value() != value:
                    scrollbar.setValue(value)
        self._is_scrolling = False

    @Slot(int)
    def on_verse_option_changed(self, option_id):
        for view in self.get_bible_views():
            view.set_verse_display_mode(option_id)

    def scroll_to_verse(self, verse_num: int):
        views = self.get_bible_views()
        if views:
            first_view = views[0]
            first_view.scroll_to_verse(verse_num)

    def update_all_views(self, book, chapter):
        self.current_book = book
        self.current_chapter = chapter
        for view in self.get_bible_views():
            view.update_content(book, chapter)
        self.update_location_status()

    def update_location_status(self):
        if not self.available_translations: return
        try:
            translation_data = self.data_loader.load_translation_data(self.available_translations[0])
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

    def handle_send_to_word_shortcut(self):
        for view in self.get_bible_views():
            if view.text_browser.hasFocus():
                view.trigger_send_to_word()
                break

    def handle_send_to_powerpoint_shortcut(self):
        for view in self.get_bible_views():
            if view.text_browser.hasFocus():
                view.trigger_send_to_powerpoint()
                break

class MainWindow(QMainWindow):
    SETTINGS_FILE = 'settings.json'

    def __init__(self):
        super().__init__()
        self.setWindowTitle("물댄동산 성경 V.5811.10")
        self.setWindowIcon(QIcon('book.ico'))
        self.setGeometry(100, 100, 1200, 800)
        self._settings = self.load_settings()
        self.font_family = self._settings.get('font_family', 'Malgun Gothic')
        self._body_style = body_style_from_settings(self._settings)
        # 비교창 폰트 크기 로드
        self.comparison_font_size = self._settings.get('comparison_font_size', 12)
        self.pending_scroll_info = None

        self.history = []
        self.history_index = -1
        self._is_navigating_history = False
        
        self.additional_read_tabs = []
        self.current_toolbar_stylesheet = ""
        
        self.history_back_long_press_timer = QTimer(self)
        self.history_back_long_press_timer.setSingleShot(True)
        self.history_back_long_press_timer.setInterval(500)

        self.history_forward_long_press_timer = QTimer(self)
        self.history_forward_long_press_timer.setSingleShot(True)
        self.history_forward_long_press_timer.setInterval(500)

        try:
            self.data_loader = BibleDataLoader()
            if not self.data_loader.get_available_translations():
                 raise FileNotFoundError("bible_data 폴더에 성경(.btx) 파일이 없습니다.")
            self.data_loader.load_translation_data(self.data_loader.get_available_translations()[0])
            self.commentary_data_loader = CommentaryDataLoader()
            self.crossref_data_loader = CrossrefDataLoader()
            self.original_language_data_loader = OriginalLanguageDataLoader(self.data_loader)
        except Exception as e:
            QMessageBox.critical(self, "초기화 오류", f"프로그램 시작 오류: {e}\n프로그램을 종료합니다.")
            sys.exit(1)
        
        # 데이터베이스 초기화
        try:
            self.bible_db = BibleDatabase()
        except Exception as e:
            QMessageBox.warning(self, "데이터베이스 오류", f"데이터베이스 초기화 중 오류가 발생했습니다: {e}\n하이라이트 및 메모 기능이 제한될 수 있습니다.")
            self.bible_db = None
        
        self.current_book = self._settings.get('book', "창세기")
        self.current_chapter = self._settings.get('chapter', 1)

        # AI 설명(Gemini)
        # 이전 기본 모델이 신규 사용자에게 더 이상 제공되지 않으므로 최신 기본값으로 이전
        if self._settings.get('gemini_model') in LEGACY_DEFAULT_MODELS:
            self._settings['gemini_model'] = DEFAULT_MODEL
        self.gemini_client = GeminiClient(self)
        self.gemini_client.finished.connect(self._on_ai_explanation_ready)
        self.gemini_client.failed.connect(self._on_ai_explanation_failed)
        self.gemini_client.retrying.connect(self._on_ai_explanation_retrying)
        self.gemini_client.log_line.connect(self._append_ai_log)
        self.ai_dialog = None
        self._last_ai_request = None

        self.init_ui()
        self.connect_signals()
        self.init_shortcuts()
        self.read_tab.populate_initial_views()
        self.read_tab.update_all_views(self.current_book, self.current_chapter)
        self.update_navigation_display()
        self.apply_global_font()
        
        self.commentary_tab.update_all_content(self.current_book, self.current_chapter, 1)
        self.crossref_tab.update_all_content(self.current_book, self.current_chapter, 1)
        self.original_language_tab.update_all_content(self.current_book, self.current_chapter, 1)
        self.apply_theme(self._settings.get('theme', 'Light'))

        self.add_to_history(self.current_book, self.current_chapter, 1)

        # 시작 시 기본 탭 적용 (통합/읽기 등 설정값)
        default_idx = self._settings.get('default_start_tab', 0)
        self.tab_widget.setCurrentIndex(min(default_idx, self.tab_widget.count() - 1))
        
        QTimer.singleShot(100, self.sync_aux_tabs_with_main_view)

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setAutoFillBackground(True)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.main_toolbar = self.create_main_toolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.main_toolbar)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        corner_widget = self.create_tab_corner_widget()
        self.tab_widget.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

        self.read_tab = ReadTab(self.data_loader, initial_settings=self._settings, bible_db=self.bible_db)
        self.search_tab = SearchTab(self.data_loader, initial_settings=self._settings)
        self.commentary_tab = CommentaryTab(self.data_loader, self.commentary_data_loader, initial_settings=self._settings, bible_db=self.bible_db)
        self.crossref_tab = CrossRefTab(self.data_loader, self.crossref_data_loader, initial_settings=self._settings, bible_db=self.bible_db)
        self.memo_tab = MemoTab(self.data_loader, initial_settings=self._settings, bible_db=self.bible_db)
        self.original_language_tab = OriginalLanguageTab(
            self.original_language_data_loader,
            original_display=self._settings.get('original_display_mode', 'strongs'),
        )
        self.original_language_tab.original_display_changed.connect(self.save_settings)
        
        self.composite_tab = CompositeTab(self.data_loader, self.commentary_data_loader, self.crossref_data_loader, initial_settings=self._settings, bible_db=self.bible_db)

        # <<< 수정됨: 탭 추가 순서 변경
        self.tab_widget.addTab(self.composite_tab, "통합")
        self.tab_widget.addTab(self.read_tab, "읽기")
        self.tab_widget.addTab(self.search_tab, "검색")
        self.tab_widget.addTab(self.commentary_tab, "주석")
        self.tab_widget.addTab(self.crossref_tab, "관주")
        self.tab_widget.addTab(self.memo_tab, "메모")
        self.tab_widget.addTab(self.original_language_tab, "원어")
        # --- 수정 끝
        
        # <<< 수정됨: 툴팁 설정 방식을 indexOf로 변경하여 순서에 무관하게 설정
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.composite_tab), "통합 탭으로 이동 (F10)")
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.read_tab), "읽기 탭으로 이동 (F2)")
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.search_tab), "검색 탭으로 이동 (F3)")
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.commentary_tab), "주석 탭으로 이동 (F4)")
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.crossref_tab), "관주 탭으로 이동 (F5)")
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.memo_tab), "메모 탭으로 이동 (F7)")
        self.tab_widget.setTabToolTip(self.tab_widget.indexOf(self.original_language_tab), "원어 탭으로 이동 (F11)")
        # --- 수정 끝

        # 기본 시작 탭 표시(·) 및 툴팁 갱신
        self.update_default_tab_indicator()

        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setToolTip("새 읽기 탭 추가 (최대 3개)")
        self.add_tab_btn.setFixedSize(24, 24)
        self.add_tab_btn.setObjectName("AddTabButton")
        self.tab_widget.setCornerWidget(self.add_tab_btn, Qt.Corner.TopLeftCorner)

        # 탭 바 우클릭으로 시작 시 기본 탭 설정
        self.tab_widget.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.tabBar().customContextMenuRequested.connect(self.show_tab_bar_context_menu)

        main_layout.addWidget(self.tab_widget)

    def _toolbar_vsep(self):
        sep = QFrame()
        sep.setObjectName("vsep")
        sep.setFrameShape(QFrame.Shape.NoFrame)
        sep.setFixedWidth(1)
        return sep

    def create_main_toolbar(self):
        main_toolbar = QToolBar("Main Toolbar")
        main_toolbar.setObjectName("mainToolBar")
        main_toolbar.setMovable(False)
        main_toolbar.setFloatable(False)

        self.prev_book_btn = QPushButton()
        self.prev_chap_btn = QPushButton()
        self.location_btn = QPushButton()
        self.location_btn.setObjectName("locationButton")
        self.location_btn.setFixedWidth(160)
        self.next_chap_btn = QPushButton()
        self.next_book_btn = QPushButton()
        self.nav_input = QLineEdit()
        self.nav_input.setMaximumWidth(90)
        self.go_btn = QPushButton("이동")

        self.history_back_btn = QPushButton()
        self.history_forward_btn = QPushButton()

        # 테마에 따라 다시 칠할 아이콘 버튼 등록: (버튼, svg 이름)
        self._toolbar_icon_buttons = [
            (self.prev_book_btn, "chevrons-left"),
            (self.prev_chap_btn, "chevron-left"),
            (self.next_chap_btn, "chevron-right"),
            (self.next_book_btn, "chevrons-right"),
            (self.history_back_btn, "arrow-undo"),
            (self.history_forward_btn, "arrow-redo"),
        ]
        for btn, _name in self._toolbar_icon_buttons:
            btn.setProperty("iconButton", "true")
            btn.setIconSize(QSize(16, 16))

        self.prev_chap_btn.setShortcut(QKeySequence("F8"))
        self.next_chap_btn.setShortcut(QKeySequence("F9"))
        self.history_back_btn.setShortcut(QKeySequence("Ctrl+F8"))
        self.history_forward_btn.setShortcut(QKeySequence("Ctrl+F9"))

        self.prev_book_btn.setToolTip("이전 책으로 이동")
        self.prev_chap_btn.setToolTip("이전 장으로 이동 (F8)")
        self.location_btn.setToolTip("책/장 목록 열기")
        self.next_chap_btn.setToolTip("다음 장으로 이동 (F9)")
        self.next_book_btn.setToolTip("다음 책으로 이동")
        self.nav_input.setToolTip("이동할 곳 입력 (예: 창1:1) 후 엔터 (Ctrl+D)")
        self.nav_input.setPlaceholderText("이동 (Ctrl+D)")
        self.go_btn.setToolTip("입력한 곳으로 이동")
        self.history_back_btn.setToolTip("이전 읽기 위치로 (Ctrl+F8, 길게 누르면 목록 표시)")
        self.history_forward_btn.setToolTip("다음 읽기 위치로 (Ctrl+F9, 길게 누르면 목록 표시)")

        main_toolbar.addWidget(self.prev_book_btn)
        main_toolbar.addWidget(self.prev_chap_btn)
        main_toolbar.addWidget(self.location_btn)
        main_toolbar.addWidget(self.next_chap_btn)
        main_toolbar.addWidget(self.next_book_btn)
        main_toolbar.addWidget(self._toolbar_vsep())
        main_toolbar.addWidget(self.nav_input)
        main_toolbar.addWidget(self.go_btn)

        main_toolbar.addWidget(self._toolbar_vsep())

        main_toolbar.addWidget(self.history_back_btn)
        main_toolbar.addWidget(self.history_forward_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_toolbar.addWidget(spacer)

        self.search_translation_combo = QComboBox()
        self.search_translation_combo.addItems(self.data_loader.get_available_translations())
        self.search_input = QLineEdit()
        self.search_input.setMaximumWidth(250)
        self.search_input.setClearButtonEnabled(True)
        self._search_input_action = self.search_input.addAction(
            themed_icon("search", TOKENS[resolve_mode(self._settings.get('theme', 'Light'))]["text_secondary"]),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_btn = QPushButton("검색")

        self.search_input.setToolTip("검색어 입력 후 엔터 (Ctrl+F)")
        self.search_input.setPlaceholderText("검색 (Ctrl+F)")
        self.search_btn.setToolTip("입력한 내용 검색")

        main_toolbar.addWidget(self.search_translation_combo)
        main_toolbar.addWidget(self.search_input)
        main_toolbar.addWidget(self.search_btn)

        return main_toolbar

    def _refresh_toolbar_icons(self):
        """현재 테마 색으로 툴바 아이콘을 다시 칠한다."""
        mode = getattr(self, "_theme_mode", None) or resolve_mode(self._settings.get('theme', 'Light'))
        color = TOKENS[mode]["text_secondary"]
        for btn, name in getattr(self, "_toolbar_icon_buttons", []):
            btn.setIcon(themed_icon(name, color))
        if hasattr(self, "location_btn"):
            self.location_btn.setIcon(themed_icon("book", color))
            self.location_btn.setIconSize(QSize(16, 16))
        if hasattr(self, "_search_input_action") and self._search_input_action is not None:
            self._search_input_action.setIcon(themed_icon("search", color))


    def create_tab_corner_widget(self):
        container = QWidget()
        container.setObjectName("CornerWidget") # Set object name for specific styling
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        sep0 = QFrame(); sep0.setFrameShape(QFrame.Shape.VLine); sep0.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep0)

        self.read_mode_btn = QPushButton("읽기 모드")
        layout.addWidget(self.read_mode_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep1)

        self.view_count_combo = QComboBox()
        self.view_count_combo.addItems([str(i) for i in range(1, 5)])
        self.view_count_combo.setToolTip("읽기 탭의 분할 창 개수 설정")
        layout.addWidget(self.view_count_combo)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        # 절 표시 스타일: 설정 메뉴 안에 있던 것을 툴바로 노출
        self.verse_style_combo = QComboBox()
        self.verse_style_combo.addItems(["(창 1:1)", "창 1:1", "1."])
        self.verse_style_combo.setToolTip("절 표시 스타일")
        layout.addWidget(self.verse_style_combo)

        sep_style = QFrame()
        sep_style.setFrameShape(QFrame.Shape.VLine)
        sep_style.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep_style)

        self.settings_btn = QPushButton("설정 및 추출")
        layout.addWidget(self.settings_btn)

        settings_menu = QMenu(self)
        self.settings_btn.setMenu(settings_menu)
        
        theme_menu = settings_menu.addMenu("테마")
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        
        themes = ["Light", "Dark"]
        # 예전 Sepia/Gray 설정값은 Light/Dark 로 이관
        current_theme = 'Dark' if resolve_mode(self._settings.get('theme', 'Light')) == 'dark' else 'Light'
        for theme_name in themes:
            action = QAction(theme_name, self, checkable=True)
            self.theme_action_group.addAction(action)
            theme_menu.addAction(action)
            if theme_name == current_theme:
                action.setChecked(True)

        # 절 표시 스타일은 툴바의 verse_style_combo 로 옮겼다. 다만 다른 코드들이
        # self.style_action_group.checkedAction() 로 현재 값을 읽으므로, 액션 그룹은
        # 메뉴에 노출하지 않은 채로 상태 보관용으로 유지한다.
        self.style_action_group = QActionGroup(self)
        self.style_action_group.setExclusive(True)
        initial_verse_display_mode = self._settings.get('verse_display_mode', 0)
        for i, text in enumerate(["(창 1:1)", "창 1:1", "1."]):
            action = QAction(text, self, checkable=True)
            action.setData(i)
            self.style_action_group.addAction(action)
            if i == initial_verse_display_mode: action.setChecked(True)
        self.verse_style_combo.setCurrentIndex(initial_verse_display_mode)
        
        self.font_settings_action = QAction("본문 및 글꼴 설정...", self)
        settings_menu.addAction(self.font_settings_action)

        self.ai_settings_action = QAction("AI 설명 설정 (Gemini)...", self)
        settings_menu.addAction(self.ai_settings_action)

        settings_menu.addSeparator()
        
        # 하이라이트/메모 관리 메뉴
        highlight_memo_menu = settings_menu.addMenu("하이라이트 및 메모")
        self.highlight_list_action = QAction("하이라이트 목록", self)
        self.memo_search_action = QAction("메모 검색", self)
        self.statistics_action = QAction("통계", self)
        highlight_memo_menu.addAction(self.highlight_list_action)
        highlight_memo_menu.addAction(self.memo_search_action)
        highlight_memo_menu.addSeparator()
        highlight_memo_menu.addAction(self.statistics_action)
        highlight_memo_menu.addSeparator()
        self.export_data_action = QAction("데이터 내보내기...", self)
        self.import_data_action = QAction("데이터 가져오기...", self)
        highlight_memo_menu.addAction(self.export_data_action)
        highlight_memo_menu.addAction(self.import_data_action)

        settings_menu.addSeparator()

        self.extract_action = QAction("본문 추출...", self)
        settings_menu.addAction(self.extract_action)
        
        return container

    def connect_signals(self):
        self.prev_book_btn.clicked.connect(self.go_to_prev_book); self.prev_chap_btn.clicked.connect(self.go_to_prev_chapter)
        self.next_chap_btn.clicked.connect(self.go_to_next_chapter); self.next_book_btn.clicked.connect(self.go_to_next_book)
        self.go_btn.clicked.connect(self.navigate_from_input); self.nav_input.returnPressed.connect(self.navigate_from_input)
        self.location_btn.clicked.connect(self.show_book_chapter_popup)
        self.search_btn.clicked.connect(self.perform_search); self.search_input.returnPressed.connect(self.perform_search)
        
        self.add_tab_btn.clicked.connect(self.add_new_read_tab)

        self.history_back_btn.pressed.connect(self.on_history_back_pressed)
        self.history_back_btn.released.connect(self.on_history_back_released)
        self.history_back_long_press_timer.timeout.connect(self.show_back_history_menu)

        self.history_forward_btn.pressed.connect(self.on_history_forward_pressed)
        self.history_forward_btn.released.connect(self.on_history_forward_released)
        self.history_forward_long_press_timer.timeout.connect(self.show_forward_history_menu)

        self.theme_action_group.triggered.connect(self.on_theme_action_triggered)
        self.font_settings_action.triggered.connect(self.open_appearance_dialog)
        self.ai_settings_action.triggered.connect(self.open_ai_settings_dialog)
        self.extract_action.triggered.connect(self.open_text_extractor)
        self.read_mode_btn.clicked.connect(self.open_read_mode)
        
        # 하이라이트/메모 관리 메뉴 연결
        self.highlight_list_action.triggered.connect(self.open_highlight_list_dialog)
        self.memo_search_action.triggered.connect(self.open_memo_search_dialog)
        self.statistics_action.triggered.connect(self.open_statistics_dialog)
        self.export_data_action.triggered.connect(self.export_data)
        self.import_data_action.triggered.connect(self.import_data)

        self.style_action_group.triggered.connect(self.on_style_action_triggered)
        self.verse_style_combo.currentIndexChanged.connect(self.on_verse_style_combo_changed)

        self.view_count_combo.currentIndexChanged.connect(self.on_view_count_selected)
        
        self.read_tab.view_count_changed.connect(self.update_view_count_display)
        self.read_tab.view_count_changed.connect(self.save_settings)
        self.read_tab.view_added.connect(self.on_bible_view_added)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        self.connect_aux_view_signals(self.commentary_tab.bible_view)
        self.connect_aux_view_signals(self.crossref_tab.bible_view)
        self.connect_aux_view_signals(self.memo_tab.bible_view)
        
        self.search_tab.request_commentary.connect(self.go_to_commentary_for_verse)
        self.search_tab.request_cross_ref.connect(self.go_to_crossref_for_verse)
        self.search_tab.request_navigation.connect(self.go_to_verse_in_read_tab)
        self.search_tab.request_new_read_tab.connect(self.go_to_verse_in_new_read_tab)
        self.search_tab.request_search.connect(self.perform_search_with_selection)
        self.search_tab.request_send_to_word.connect(self.on_request_send_to_word)
        self.search_tab.request_send_to_powerpoint.connect(self.on_request_send_to_powerpoint)

        self.commentary_tab.request_search.connect(self.perform_search_with_selection)
        self.commentary_tab.request_send_to_word.connect(self.on_request_send_to_word)
        self.commentary_tab.request_send_to_powerpoint.connect(self.on_request_send_to_powerpoint)

        self.crossref_tab.request_navigation.connect(self.go_to_verse_in_read_tab)
        self.crossref_tab.request_new_read_tab.connect(self.go_to_verse_in_new_read_tab)
        self.crossref_tab.request_search.connect(self.perform_search_with_selection)
        self.crossref_tab.request_send_to_word.connect(self.on_request_send_to_word)
        self.crossref_tab.request_send_to_powerpoint.connect(self.on_request_send_to_powerpoint)
        self.original_language_tab.request_navigation.connect(self.go_to_verse_in_read_tab)

        for tab in [self.commentary_tab, self.crossref_tab, self.search_tab, self.memo_tab]:
            if hasattr(tab, 'settings_changed'):
                tab.settings_changed.connect(self.save_settings)

        # <<< (4) 수정됨
        self.composite_tab.settings_changed.connect(self.save_settings)
        self.composite_tab.request_commentary.connect(self.go_to_commentary_for_verse)
        self.composite_tab.request_cross_ref.connect(self.go_to_crossref_for_verse)
        self.composite_tab.request_navigation.connect(self.go_to_verse_in_read_tab)
        self.composite_tab.request_new_read_tab.connect(self.go_to_verse_in_new_read_tab)
        self.composite_tab.request_search.connect(self.perform_search_with_selection)
        self.composite_tab.request_send_to_word.connect(self.on_request_send_to_word)
        self.composite_tab.request_send_to_powerpoint.connect(self.on_request_send_to_powerpoint)
        # --- (4) 수정 끝 ---

    def init_shortcuts(self):
        QShortcut(QKeySequence("F2"), self, lambda: self.tab_widget.setCurrentWidget(self.read_tab))
        QShortcut(QKeySequence("F3"), self, lambda: self.tab_widget.setCurrentWidget(self.search_tab))
        QShortcut(QKeySequence("F4"), self, lambda: self.tab_widget.setCurrentWidget(self.commentary_tab))
        QShortcut(QKeySequence("F5"), self, lambda: self.tab_widget.setCurrentWidget(self.crossref_tab))
        QShortcut(QKeySequence("F7"), self, lambda: self.tab_widget.setCurrentWidget(self.memo_tab))

        QShortcut(QKeySequence("F10"), self, lambda: self.tab_widget.setCurrentWidget(self.composite_tab)) # <<< (5) 수정됨
        QShortcut(QKeySequence("F11"), self, lambda: self.tab_widget.setCurrentWidget(self.original_language_tab))

        QShortcut(QKeySequence("Ctrl+D"), self, lambda: self.nav_input.setFocus())
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search_input.setFocus())

        QShortcut(QKeySequence("Ctrl+W"), self, self.on_send_to_word_shortcut)
        QShortcut(QKeySequence("Ctrl+P"), self, self.on_send_to_powerpoint_shortcut)
        QShortcut(QKeySequence("Ctrl+H"), self, self.on_highlight_shortcut)
        QShortcut(QKeySequence("Ctrl+H"), self, self.on_highlight_shortcut)

    @Slot()
    def on_send_to_word_shortcut(self):
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'handle_send_to_word_shortcut'):
            current_tab.handle_send_to_word_shortcut()

    @Slot()
    def on_send_to_powerpoint_shortcut(self):
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'handle_send_to_powerpoint_shortcut'):
            current_tab.handle_send_to_powerpoint_shortcut()
    
    @Slot()
    def on_highlight_shortcut(self):
        """하이라이트 토글 단축키 (Ctrl+H)"""
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'bible_view'):
            bible_view = current_tab.bible_view
            if bible_view.text_browser.hasFocus():
                cursor = bible_view.text_browser.textCursor()
                pos_cursor = bible_view.text_browser.cursorForPosition(bible_view.text_browser.mapFromGlobal(bible_view.text_browser.mapToGlobal(cursor.rect().topLeft())))
                href = pos_cursor.charFormat().anchorHref()
                if href and href.startswith('#'):
                    try:
                        verse_num = int(href[1:])
                        bible_view.toggle_highlight(verse_num)
                    except (ValueError, IndexError):
                        pass
        elif hasattr(current_tab, 'get_bible_views'):
            # ReadTab이나 AdditionalReadTab의 경우
            views = current_tab.get_bible_views()
            for view in views:
                if view.text_browser.hasFocus():
                    cursor = view.text_browser.textCursor()
                    pos_cursor = view.text_browser.cursorForPosition(view.text_browser.mapFromGlobal(view.text_browser.mapToGlobal(cursor.rect().topLeft())))
                    href = pos_cursor.charFormat().anchorHref()
                    if href and href.startswith('#'):
                        try:
                            verse_num = int(href[1:])
                            view.toggle_highlight(verse_num)
                        except (ValueError, IndexError):
                            pass
                    break

    @Slot()
    def open_text_extractor(self):
        bible_views = self.read_tab.get_bible_views()
        checked_style_action = self.style_action_group.checkedAction()
        verse_display_mode = checked_style_action.data() if checked_style_action else 0

        initial_settings = {
            'book': self.current_book,
            'chapter': self.current_chapter,
            'translation': bible_views[0].translation_combo.currentText() if bible_views else self.data_loader.get_available_translations()[0],
            'verse_display_mode': verse_display_mode
        }
        dialog = TextExtractorDialog(self.data_loader, self, initial_settings)
        dialog.exec()

    def connect_aux_view_signals(self, new_view):
        new_view.request_commentary.connect(self.go_to_commentary_for_verse)
        new_view.request_cross_ref.connect(self.go_to_crossref_for_verse)
        new_view.request_search.connect(self.perform_search_with_selection)
        new_view.request_send_to_word.connect(self.on_request_send_to_word)
        new_view.request_send_to_powerpoint.connect(self.on_request_send_to_powerpoint)
        new_view.request_original_language.connect(self.go_to_original_language_for_range)
        new_view.request_ai_explanation.connect(self.request_ai_explanation_for_selection)
        new_view.highlight_changed.connect(self.on_highlight_changed)
    
    @Slot()
    def on_highlight_changed(self):
        """하이라이트 변경 시 현재 보이는 성경 뷰만 스크롤 위치를 유지한 채 갱신한다.
        update_all_tabs_content() 는 update_all_views()/구절 재정렬을 거쳐 스크롤이
        튀므로 하이라이트 토글에는 쓰지 않는다."""
        for view in self._all_bible_views():
            view.update_content(preserve_scroll=True, realign_verse=False)

    def sync_aux_tabs_with_main_view(self):
        bible_views = self.read_tab.get_bible_views()
        if not bible_views: return
        self.sync_aux_tab_translation(bible_views[0].translation_combo.currentText())
        self.sync_font_size(bible_views[0].font_size)

    @Slot(str)
    def sync_aux_tab_translation(self, translation):
        self.commentary_tab.set_bible_translation(translation)
        self.crossref_tab.set_bible_translation(translation)
        self.save_settings()

    @Slot(int)
    def sync_font_size(self, size):
        for view in self.read_tab.get_bible_views(): view.set_font_size(size)
        self.commentary_tab.set_bible_font_size(size)
        self.crossref_tab.set_bible_font_size(size)
        self.memo_tab.set_font_size(size)
        self.composite_tab.bible_view.set_font_size(size) # <<< 수정됨
        self.save_settings()

    def _body_style_sample_verses(self):
        """현재 읽고 있는 본문 앞부분을 미리보기 표본으로 만든다 (실패 시 None)."""
        try:
            views = self.read_tab.get_bible_views()
            if not views:
                return None
            translation = views[0].translation_combo.currentText()
            data = self.data_loader.load_translation_data(translation)
            lines = data["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
            if not lines:
                return None
            import re as _re
            sub_re = _re.compile(r'<\s*(.+?)\s*>')
            out, num = [], 1
            for raw in lines:
                m = sub_re.match(raw)
                if m:
                    out.append({"kind": "subtitle", "text": m.group(1)})
                    continue
                if raw.strip():
                    out.append({"kind": "verse", "num": num, "text": raw})
                num += 1
                if sum(1 for x in out if x["kind"] == "verse") >= 5:
                    break
            return out or None
        except Exception:
            return None

    @Slot()
    def open_appearance_dialog(self):
        """'본문 및 글꼴 설정' 창 (글꼴 + 본문 타이포그래피 통합)."""
        t = getattr(self, '_theme_tokens', None) or TOKENS['light']
        colors = {
            "text": t["text"], "muted": t["text_secondary"],
            "accent": t["accent"], "bg": t["surface"],
        }
        views = self.read_tab.get_bible_views()
        bible_font_size = views[0].font_size if views else self._settings.get('bible_font_size', 14)
        aux_font_size = getattr(self.commentary_tab, 'font_size', 12)
        dialog = BodyStyleDialog(
            current_style=getattr(self, '_body_style', None) or body_style_from_settings(self._settings),
            sample_verses=self._body_style_sample_verses(),
            colors=colors,
            font_family=self.font_family,
            bible_font_size=bible_font_size,
            aux_font_size=aux_font_size,
            parent=self,
        )
        dialog.applied.connect(self._apply_appearance)
        dialog.exec()

    @Slot(dict)
    def _apply_appearance(self, values):
        values = dict(values)
        family = values.pop('font_family', None)
        bible_size = values.pop('bible_font_size', None)
        aux_size = values.pop('aux_font_size', None)

        if family and family != self.font_family:
            self.font_family = family
            self.apply_global_font()
        if bible_size:
            self.sync_font_size(int(bible_size))
        if aux_size:
            aux_size = int(aux_size)
            self.commentary_tab.set_commentary_font_size(aux_size)
            self.crossref_tab.set_crossref_font_size(aux_size)
            self.composite_tab.set_commentary_font_size(aux_size)
            self.composite_tab.set_crossref_font_size(aux_size)

        # 나머지 키는 본문 타이포그래피
        self._body_style = dict(values)
        for view in self._all_bible_views():
            if hasattr(view, 'apply_body_style'):
                view.apply_body_style(values)
        self.save_settings()

    # --- AI 설명 (Gemini) ---------------------------------------------------
    def open_ai_settings_dialog(self):
        dialog = AiSettingsDialog(
            self._settings.get('gemini_api_key', ''),
            self._settings.get('gemini_model', DEFAULT_MODEL),
            self._settings.get('gemini_prompt', ''),
            self,
        )
        if dialog.exec():
            key, model, prompt = dialog.values()
            self._settings['gemini_api_key'] = key
            self._settings['gemini_model'] = model or DEFAULT_MODEL
            self._settings['gemini_prompt'] = prompt
            self.save_settings()
            if self.ai_dialog is not None:
                self.ai_dialog.set_prompt(self._settings.get('gemini_prompt', ''))

    @Slot(str, str, str, str, int, int, int)
    def request_ai_explanation_for_selection(self, reference, passage, translation,
                                             book, chapter, start_verse, end_verse):
        api_key = self._settings.get('gemini_api_key', '')
        if not api_key:
            answer = QMessageBox.question(
                self, "AI 설명",
                "Gemini API 키가 설정되어 있지 않습니다.\n지금 설정하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.open_ai_settings_dialog()
            return

        self._last_ai_request = {
            'reference': reference, 'passage': passage, 'translation': translation,
            'question': None, 'book': book, 'chapter': chapter,
            'start': start_verse, 'end': end_verse,
        }
        if self.ai_dialog is None:
            self.ai_dialog = AiExplanationDialog(
                self, self.font_family, self._settings.get('bible_font_size', 13),
                self._settings.get('gemini_prompt', ''),
            )
            self.ai_dialog.regenerate_requested.connect(self._regenerate_ai_explanation)
            self.ai_dialog.default_requested.connect(self._run_default_ai_explanation)
            self.ai_dialog.question_submitted.connect(self._ask_ai_question)
            self.ai_dialog.save_requested.connect(self._save_ai_note)
            self.ai_dialog.delete_requested.connect(self._delete_ai_note)
            self.ai_dialog.prompt_saved.connect(self._save_ai_prompt)
            # 창을 닫으면 진행 중인 요청도 취소한다
            self.ai_dialog.close_button.clicked.connect(self.gemini_client.cancel)

        # 하단 로그 영역에 기존 통신 기록을 채워 넣는다(이후는 실시간 추가).
        self.ai_dialog.set_log_entries(self.gemini_client.log_entries)

        # 저장된 해설이 있으면 바로 보여주고, 없으면 '기본 설명/질문' 선택 화면을 연다.
        saved = None
        if self.bible_db is not None:
            note = self.bible_db.get_ai_note(book, chapter, start_verse, end_verse)
            saved = note['content'] if note else None
        self.ai_dialog.prepare(reference, passage, saved)

    def _send_ai_request(self):
        """_last_ai_request 상태(기본 설명 또는 질문)에 맞춰 Gemini 호출."""
        req = self._last_ai_request
        if not req:
            return
        api_key = self._settings.get('gemini_api_key', '')
        model = self._settings.get('gemini_model', DEFAULT_MODEL)
        if req['question']:
            prompt = build_question_prompt(req['reference'], req['passage'],
                                           req['translation'], req['question'])
        else:
            prompt = build_prompt(req['reference'], req['passage'], req['translation'],
                                  self._settings.get('gemini_prompt', ''))
        self.gemini_client.explain(api_key, model, prompt)

    @Slot()
    def _regenerate_ai_explanation(self):
        """'다시 생성' — 마지막 요청(기본 설명 또는 질문)을 그대로 재실행."""
        req = self._last_ai_request
        if not req or self.ai_dialog is None:
            return
        header = f"{req['reference']} — {req['question']}" if req['question'] else req['reference']
        self.ai_dialog.start(header)
        self._send_ai_request()

    @Slot()
    def _run_default_ai_explanation(self):
        """'기본 설명' — 질문 상태를 지우고 기본 프롬프트로 실행."""
        req = self._last_ai_request
        if not req or self.ai_dialog is None:
            return
        req['question'] = None
        self.ai_dialog.start(req['reference'])
        self._send_ai_request()

    @Slot(str)
    def _ask_ai_question(self, question):
        """사용자가 입력한 자유 질문을 선택 구절과 함께 전송."""
        req = self._last_ai_request
        if not req or self.ai_dialog is None:
            return
        req['question'] = question
        self.ai_dialog.start(f"{req['reference']} — {question}")
        self._send_ai_request()

    @Slot()
    def _save_ai_note(self):
        """현재 표시된 해설을 해당 구절 범위에 연동해 저장한다."""
        req = self._last_ai_request
        if not req or self.ai_dialog is None or self.bible_db is None:
            return
        content = self.ai_dialog._raw_text
        if not content or not content.strip():
            return
        ok = self.bible_db.save_ai_note(
            req['book'], req['chapter'], req['start'], req['end'],
            content, req['reference'], req['question'] or '',
        )
        if ok:
            self.ai_dialog.mark_saved()
            # 읽기 화면의 AI 해설 표시 갱신
            self._refresh_ai_note_markers()

    @Slot()
    def _delete_ai_note(self):
        """이 구절에 저장된 AI 해설을 삭제한다."""
        req = self._last_ai_request
        if not req or self.ai_dialog is None or self.bible_db is None:
            return
        answer = QMessageBox.question(
            self.ai_dialog, "AI 해설 삭제",
            f"'{req['reference']}' 에 저장된 AI 해설을 삭제할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.bible_db.delete_ai_note(req['book'], req['chapter'], req['start'], req['end']):
            self.ai_dialog.mark_deleted()
            self._refresh_ai_note_markers()

    def _refresh_ai_note_markers(self):
        for view in self._all_bible_views():
            view.update_content(preserve_scroll=True, realign_verse=False)

    def _all_bible_views(self):
        views = list(self.read_tab.get_bible_views())
        for tab in getattr(self, 'additional_read_tabs', []):
            views.extend(tab.get_bible_views())
        for aux in (self.commentary_tab, self.crossref_tab, self.memo_tab, self.composite_tab):
            bible_view = getattr(aux, 'bible_view', None)
            if bible_view is not None:
                views.append(bible_view)
        return views

    @Slot(str)
    def _on_ai_explanation_ready(self, text):
        if self.ai_dialog is not None:
            self.ai_dialog.show_result(text)

    @Slot(str)
    def _on_ai_explanation_failed(self, message):
        if self.ai_dialog is not None:
            self.ai_dialog.show_error(message)

    @Slot(int, int)
    def _on_ai_explanation_retrying(self, attempt, total):
        if self.ai_dialog is not None:
            self.ai_dialog.note_retry(attempt, total)

    @Slot(str)
    def _append_ai_log(self, line):
        if self.ai_dialog is not None:
            self.ai_dialog.append_log_line(line)

    @Slot(str)
    def _save_ai_prompt(self, text):
        """AI 창 하단에서 편집한 기본 프롬프트를 저장한다."""
        self._settings['gemini_prompt'] = text
        self.save_settings()

    def apply_global_font(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'set_font_family'):
                tab.set_font_family(self.font_family)
    
    @Slot(QAction)
    def on_theme_action_triggered(self, action):
        self.apply_theme(action.text())
        self.save_settings()

    def apply_theme(self, theme_name: str):
        """Office(Fluent) 스타일 테마 적용. Light / Dark 두 가지만 지원한다."""
        mode = resolve_mode(theme_name)            # 'light' | 'dark'
        canonical = 'Dark' if mode == 'dark' else 'Light'
        self._settings['theme'] = canonical
        self._theme_mode = mode
        t = TOKENS[mode]
        self._theme_tokens = t

        qdarktheme.setup_theme(
            theme=mode,
            corner_shape="rounded",
            custom_colors={
                "primary": t["accent"],
                "background": t["window"],
                "border": t["border"],
                "foreground": t["text"],
                "input.background": t["surface"],
            },
            additional_qss=office_qss(mode),
        )

        # 앱 기본(크롬) 글꼴. 본문/결과 영역은 각 위젯이 setFont() 로 사용자 글꼴을 덮어쓴다.
        QApplication.setFont(QFont(FONT_FAMILY_PRIMARY, FONT_POINT_SIZE))

        palette = QApplication.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(t["surface"]))
        palette.setColor(QPalette.ColorRole.Window, QColor(t["window"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(t["highlight"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["on_highlight"]))
        palette.setColor(QPalette.ColorRole.Link, QColor(t["accent"]))
        QApplication.setPalette(palette)

        # 전역 QSS(office_qss)가 대부분을 담당하므로 개별 위젯의 예전 스타일시트는 비운다.
        self.current_toolbar_stylesheet = ""
        self.setStyleSheet("")
        self.main_toolbar.setStyleSheet("")
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, AdditionalReadTab) and hasattr(widget, 'toolbar'):
                widget.toolbar.setStyleSheet("")

        if corner_widget := self.tab_widget.cornerWidget():
            corner_widget.setStyleSheet("")
        self.add_tab_btn.setStyleSheet("")
        self.tab_widget.setStyleSheet("")
        self.memo_tab.setStyleSheet("")
        for tab in (self.search_tab, self.commentary_tab, self.crossref_tab,
                    self.composite_tab, self.original_language_tab):
            tab.setStyleSheet("")
        if hasattr(self.original_language_tab, 'set_theme_mode'):
            self.original_language_tab.set_theme_mode(mode)

        all_bible_views = self.read_tab.get_bible_views() + \
                          [self.commentary_tab.bible_view, self.crossref_tab.bible_view,
                           self.memo_tab.bible_view, self.composite_tab.bible_view]
        for tab in self.additional_read_tabs:
            all_bible_views.extend(tab.get_bible_views())
        for view in all_bible_views:
            if hasattr(view, 'set_menu_stylesheet'):
                view.set_menu_stylesheet("")
            # 본문 HTML 색상(선택 배경·절번호)을 테마에 맞춘다. 재그리기는 아래에서 일괄 처리.
            if mode == 'dark':
                view._selected_verse_color = "#2a4b6b"
                view._verse_num_color = "#9aa7b4"
            else:
                from bible_view import SELECTED_VERSE_COLOR as _svc
                view._selected_verse_color = _svc
                view._verse_num_color = "#605E5C"

        self._refresh_toolbar_icons()
        self.update_all_tabs_content()

    @Slot(int)
    def change_bible_font_size(self, delta):
        pass

    def parse_navigation_input(self, text):
        return self.data_loader.parse_reference(text)

    def get_navigation_target(self):
        current_widget = self.tab_widget.currentWidget()
        
        if isinstance(current_widget, (SearchTab, AdditionalReadTab)):
            return self.read_tab
        
        # '통합' 탭도 메인 네비게이션 타겟이 되도록 추가
        if current_widget in [self.read_tab, self.commentary_tab, self.crossref_tab, self.memo_tab, self.composite_tab]:
            return current_widget
            
        return self.read_tab

    @Slot()
    def navigate_from_input(self):
        book, chapter, verse = self.parse_navigation_input(self.nav_input.text())
        if book and chapter:
            target_verse = verse if verse is not None else 1
            target_widget = self.get_navigation_target()
            self.go_to_verse(target_widget, book, chapter, target_verse)
            self.nav_input.clear()
        else:
            pass

    
    @Slot()
    def perform_search(self): self._perform_search_logic(self.search_input.text().strip(), self.search_translation_combo.currentText())
    
    @Slot(str, str)
    def perform_search_with_selection(self, k, t): 
        self.search_input.setText(k); self.search_translation_combo.setCurrentText(t); self._perform_search_logic(k, t)

    def _perform_search_logic(self, keyword_str, translation):
        if not keyword_str or not translation: return
        try: 
            bible_data = self.data_loader.load_translation_data(translation)["bible_data"]
            keywords = keyword_str.split()
            results = [(b, c, i+1, v) for b, chaps in bible_data.items() for c, verses in chaps.items() for i, v in enumerate([v for v in verses if not v.startswith('<')]) if all(kw in v for kw in keywords)]
            self.search_tab.display_results(results, keywords, keyword_str, translation)
            self.tab_widget.setCurrentWidget(self.search_tab)
        except Exception as e: 
            self.search_tab.status_label_left.setText(f"'{translation}' 로드 오류: {e}")

    def navigate_to(self, book, chapter):
        max_chapter = self.data_loader.global_book_chapter_counts.get(book, 0)
        if not (1 <= chapter <= max_chapter): return
        self.current_book, self.current_chapter = book, chapter
        self.update_navigation_display()
        self.update_all_tabs_content()
        self.save_settings()

    def update_all_tabs_content(self):
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget == self.read_tab:
                for view in widget.get_bible_views(): 
                    view.update_theme()
                    view.update_content(preserve_scroll=True)
                widget.update_all_views(self.current_book, self.current_chapter)
            elif widget == self.commentary_tab:
                widget.bible_view.update_theme()
                widget.bible_view.update_content(preserve_scroll=True)
                widget.update_all_content(self.current_book, self.current_chapter)
            elif widget == self.crossref_tab:
                widget.bible_view.update_theme()
                widget.bible_view.update_content(preserve_scroll=True)
                widget.update_all_content(self.current_book, self.current_chapter)
            elif widget == self.memo_tab:
                widget.bible_view.update_theme()
                widget.bible_view.update_content(preserve_scroll=True)
                widget.update_location(self.current_book, self.current_chapter)
            elif widget == self.original_language_tab:
                widget.update_all_content(self.current_book, self.current_chapter, widget.current_verse)
            
            # <<< (6) 수정됨
            elif widget == self.composite_tab:
                widget.bible_view.update_theme()
                widget.bible_view.update_content(preserve_scroll=True)
                widget.update_all_content(self.current_book, self.current_chapter, widget.current_verse)
            # --- (6) 수정 끝 ---
                
            elif widget == self.search_tab and widget.last_search_results:
                widget.update_display()
            elif isinstance(widget, AdditionalReadTab):
                for view in widget.get_bible_views():
                    view.update_theme()
                    view.update_content()
                widget.update_all_views(widget.current_book, widget.current_chapter)

    def update_navigation_display(self):
        book_num = next((num for num, _, full in self.data_loader.book_definitions if full == self.current_book), "")
        self.location_btn.setText(f"{book_num}{self.current_book} {self.current_chapter}장")

    @Slot(QAction)
    def on_style_action_triggered(self, action: QAction): self.on_style_radio_selected(action.data())

    @Slot(int)
    def on_verse_style_combo_changed(self, index):
        actions = self.style_action_group.actions()
        if 0 <= index < len(actions) and not actions[index].isChecked():
            actions[index].setChecked(True)
        self.on_style_radio_selected(index)

    @Slot(int)
    def on_style_radio_selected(self, mode_id):
        self.read_tab.on_verse_option_changed(mode_id)
        self.commentary_tab.set_verse_display_mode(mode_id)
        self.crossref_tab.set_verse_display_mode(mode_id)
        self.memo_tab.set_verse_display_mode(mode_id)
        
        self.composite_tab.set_verse_display_mode(mode_id) # <<< (7) 수정됨
        
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, AdditionalReadTab):
                widget.set_verse_display_mode(mode_id)
        self.save_settings()

    @Slot(int)
    def update_view_count_display(self, count):
        self.view_count_combo.blockSignals(True)
        self.view_count_combo.setCurrentIndex(count - 1)
        self.view_count_combo.blockSignals(False)

    @Slot(int)
    def on_view_count_selected(self, index):
        target_count = index + 1
        current_count = self.read_tab.splitter.count()
        while current_count < target_count:
            self.read_tab.add_bible_view(); current_count += 1
        while current_count > target_count:
            self.read_tab.remove_bible_view(); current_count -= 1

    def go_to_adjacent_chapter(self, delta):
        new_chapter = self.current_chapter + delta
        if 1 <= new_chapter <= self.data_loader.global_book_chapter_counts.get(self.current_book, 0):
             target_widget = self.get_navigation_target()
             self.go_to_verse(target_widget, self.current_book, new_chapter, 1)
        elif delta < 0: self.go_to_prev_book(move_to_last_chapter=True)
        else: self.go_to_next_book()
    
    @Slot()
    def go_to_prev_chapter(self): self.go_to_adjacent_chapter(-1)
    @Slot()
    def go_to_next_chapter(self): self.go_to_adjacent_chapter(1)

    def go_to_adjacent_book(self, delta, move_to_last_chapter=False):
        idx = next((i for i, (_, _, full) in enumerate(self.data_loader.book_definitions) if full == self.current_book), -1)
        if 0 <= idx + delta < len(self.data_loader.book_definitions):
            new_book_name = self.data_loader.book_definitions[idx + delta][2]
            chap = self.data_loader.global_book_chapter_counts.get(new_book_name, 1) if move_to_last_chapter else 1
            target_widget = self.get_navigation_target()
            self.go_to_verse(target_widget, new_book_name, chap, 1)

    @Slot()
    def go_to_prev_book(self, move_to_last_chapter=False): self.go_to_adjacent_book(-1, move_to_last_chapter)
    @Slot()
    def go_to_next_book(self): self.go_to_adjacent_book(1)

    @Slot()
    def show_book_chapter_popup(self):
        popup = BookChapterPopup(self.data_loader, self, self.current_book, self.current_chapter)
        target_widget = self.get_navigation_target()
        popup.selection_made.connect(lambda book, chap: self.go_to_verse(target_widget, book, chap, 1))
        popup.text_navigation.connect(self._navigate_from_popup_text)
        popup.move(self.location_btn.mapToGlobal(self.location_btn.rect().bottomLeft()))
        popup.show()
        popup.raise_()
        popup.activateWindow()

    @Slot(str)
    def _navigate_from_popup_text(self, text):
        book, chapter, verse = self.parse_navigation_input(text)
        if book and chapter:
            self.go_to_verse(self.get_navigation_target(), book, chapter,
                             verse if verse is not None else 1)

    @Slot(int)
    def on_comparison_font_size_changed(self, size):
        if self.comparison_font_size != size:
            self.comparison_font_size = size
            self.save_settings()

    def load_settings(self):
        if not os.path.exists(self.SETTINGS_FILE): return {}
        try:
            with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return {}

    def save_settings(self, *args):
        bible_views = self.read_tab.get_bible_views()
        checked_style_action = self.style_action_group.checkedAction()
        verse_display_mode = checked_style_action.data() if checked_style_action else 0
        checked_theme_action = self.theme_action_group.checkedAction()
        theme = checked_theme_action.text() if checked_theme_action else 'Light'
        
        settings = {
            'book': self.current_book, 
            'chapter': self.current_chapter, 
            'font_family': self.font_family, 
            'bible_font_size': bible_views[0].font_size if bible_views else 14,
            'verse_display_mode': verse_display_mode, 
            'num_views': len(bible_views), 
            'view_translations': [v.translation_combo.currentText() for v in bible_views], 
            'commentary_font_size': self.commentary_tab.font_size, 
            'crossref_display_font_size': self.crossref_tab.crossref_font_size, 
            'crossref_display_translation': self.crossref_tab.crossref_translation_combo.currentText(),
            'crossref_style_mode': self.crossref_tab.crossref_style_mode,

            # <<< (9) 수정됨
            'composite_commentary_font_size': self.composite_tab.commentary_font_size,
            'composite_crossref_font_size': self.composite_tab.crossref_font_size,
            'composite_crossref_translation': self.composite_tab.crossref_translation_combo.currentText(),
            'composite_crossref_style_mode': self.composite_tab.crossref_style_mode,
            
            'search_font_size': self.search_tab.font_size,
            'theme': theme,
            'comparison_font_size': self.comparison_font_size,
            'default_start_tab': self._settings.get('default_start_tab', 0),
            'gemini_api_key': self._settings.get('gemini_api_key', ''),
            'gemini_model': self._settings.get('gemini_model', DEFAULT_MODEL),
            'gemini_prompt': self._settings.get('gemini_prompt', ''),
            'original_display_mode': self.original_language_tab.get_original_display(),
        }
        settings.update(body_style_to_settings(
            getattr(self, '_body_style', None) or body_style_from_settings(self._settings)
        ))

        try:
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(settings, f, indent=4, ensure_ascii=False)
        except IOError as e: print(f"Error saving settings: {e}")

    def closeEvent(self, event: QCloseEvent): self.save_settings(); super().closeEvent(event)

    @Slot(SharedBibleView)
    def on_bible_view_added(self, new_view):
        self.connect_aux_view_signals(new_view)
        new_view.translation_changed.connect(self.save_settings)
        if self.read_tab.get_bible_views()[0] is new_view: new_view.translation_changed.connect(self.sync_aux_tab_translation)
        new_view.set_font_family(self.font_family); new_view.update_content(self.current_book, self.current_chapter)

    def _process_pending_scroll(self):
        if self.pending_scroll_info:
            target_tab, verse_to_scroll = self.pending_scroll_info["tab"], self.pending_scroll_info["verse"]
            if self.tab_widget.currentWidget() is target_tab:
                if isinstance(target_tab, ReadTab):
                    target_tab.scroll_to_verse(verse_to_scroll)
                elif isinstance(target_tab, MemoTab):
                    target_tab.bible_view.scroll_to_verse(verse_to_scroll)
                elif hasattr(target_tab, 'bible_view'): # '통합' 탭 포함
                    target_tab.bible_view.scroll_to_verse(verse_to_scroll)
                self.pending_scroll_info = None

    @Slot(int)
    def on_tab_changed(self, index): QTimer.singleShot(100, self._process_pending_scroll)

    def update_default_tab_indicator(self):
        """기본 시작 탭에 작은 점(·) 표시를 붙이고, 해당 탭 툴팁에 '시작 시 기본 탭' 문구를 추가."""
        DEFAULT_TAB_MARKER = " •"  # 불릿(·보다 약간 굵은 점)
        FIXED_TAB_LABELS = ("통합", "읽기", "검색", "주석", "관주", "메모", "원어")
        FIXED_TAB_TOOLTIPS = (
            "통합 탭으로 이동 (F10)", "읽기 탭으로 이동 (F2)", "검색 탭으로 이동 (F3)",
            "주석 탭으로 이동 (F4)", "관주 탭으로 이동 (F5)", "메모 탭으로 이동 (F7)", "원어 탭으로 이동 (F11)"
        )
        default_idx = min(self._settings.get('default_start_tab', 0), max(0, self.tab_widget.count() - 1))
        for i in range(self.tab_widget.count()):
            base = FIXED_TAB_LABELS[i] if i < len(FIXED_TAB_LABELS) else self.tab_widget.tabText(i).replace(DEFAULT_TAB_MARKER, "").strip()
            self.tab_widget.setTabText(i, base + (DEFAULT_TAB_MARKER if i == default_idx else ""))
        for i in range(min(len(FIXED_TAB_TOOLTIPS), self.tab_widget.count())):
            tip = FIXED_TAB_TOOLTIPS[i] + (" · 시작 시 기본 탭" if i == default_idx else "")
            self.tab_widget.setTabToolTip(i, tip)

    @Slot(object)
    def show_tab_bar_context_menu(self, pos):
        """탭 바 우클릭 시 '시작 시 이 탭을 기본으로' 메뉴 표시."""
        tab_bar = self.tab_widget.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        action = menu.addAction("시작 시 이 탭을 기본으로")
        if menu.exec(tab_bar.mapToGlobal(pos)) == action:
            self._settings['default_start_tab'] = index
            self.save_settings()
            self.update_default_tab_indicator()
            tab_name = self.tab_widget.tabText(index)
            self.statusBar().showMessage(f"'{tab_name}' 탭이 프로그램 시작 시 기본으로 열리도록 설정되었습니다.", 4000)

    def add_to_history(self, book, chapter, verse):
        if self._is_navigating_history: return
        location = (book, chapter, verse)
        if self.history_index >= 0 and self.history[self.history_index] == location: return
        if self.history_index < len(self.history) - 1: self.history = self.history[:self.history_index + 1]
        self.history.append(location)
        self.history_index = len(self.history) - 1
        self.update_history_buttons()

    def update_history_buttons(self):
        self.history_back_btn.setEnabled(self.history_index > 0)
        self.history_forward_btn.setEnabled(self.history_index < len(self.history) - 1)

    @Slot()
    def on_history_back_pressed(self): self.history_back_long_press_timer.start()
    @Slot()
    def on_history_forward_pressed(self): self.history_forward_long_press_timer.start()
    
    @Slot()
    def on_history_back_released(self):
        if self.history_back_long_press_timer.isActive():
            self.history_back_long_press_timer.stop()
            self.go_history_back()
            
    @Slot()
    def on_history_forward_released(self):
        if self.history_forward_long_press_timer.isActive():
            self.history_forward_long_press_timer.stop()
            self.go_history_forward()

    def go_history_back(self):
        if self.history_index > 0:
            self._is_navigating_history = True
            self.history_index -= 1
            book, chapter, verse = self.history[self.history_index]
            self.go_to_verse(self.read_tab, book, chapter, verse)
            self._is_navigating_history = False
            self.update_history_buttons()

    def go_history_forward(self):
        if self.history_index < len(self.history) - 1:
            self._is_navigating_history = True
            self.history_index += 1
            book, chapter, verse = self.history[self.history_index]
            self.go_to_verse(self.read_tab, book, chapter, verse)
            self._is_navigating_history = False
            self.update_history_buttons()
    
    @Slot()
    def show_back_history_menu(self):
        if not self.history_back_btn.isDown(): return
        menu = QMenu(self)
        back_history = self.history[:self.history_index]
        for i, (book, chapter, verse) in reversed(list(enumerate(back_history))):
            action = QAction(f"{book} {chapter}:{verse}", self)
            action.triggered.connect(lambda checked=False, index=i: self.go_to_history_item(index))
            menu.addAction(action)
        menu.exec(self.history_back_btn.mapToGlobal(self.history_back_btn.rect().bottomLeft()))

    @Slot()
    def show_forward_history_menu(self):
        if not self.history_forward_btn.isDown(): return
        menu = QMenu(self)
        forward_history = self.history[self.history_index + 1:]
        for i, (book, chapter, verse) in enumerate(forward_history):
            history_index = self.history_index + 1 + i
            action = QAction(f"{book} {chapter}:{verse}", self)
            action.triggered.connect(lambda checked=False, index=history_index: self.go_to_history_item(index))
            menu.addAction(action)
        menu.exec(self.history_forward_btn.mapToGlobal(self.history_forward_btn.rect().bottomLeft()))

    def go_to_history_item(self, index):
        self._is_navigating_history = True
        self.history_index = index
        book, chapter, verse = self.history[self.history_index]
        self.go_to_verse(self.read_tab, book, chapter, verse)
        self._is_navigating_history = False
        self.update_history_buttons()

    def go_to_verse(self, target_tab, book, chapter, verse):
        if isinstance(target_tab, AdditionalReadTab):
             target_tab.navigate_to(book, chapter)
             target_tab.scroll_to_verse(verse)
             return
        
        self.add_to_history(book, chapter, verse)
        self.navigate_to(book, chapter)
        if target_tab is self.commentary_tab: target_tab.update_all_content(book, chapter, verse); target_tab.set_commentary_display_mode(0)
        elif target_tab is self.crossref_tab: target_tab.update_all_content(book, chapter, verse)
        
        # <<< (8) 수정됨
        elif target_tab is self.composite_tab: 
            target_tab.update_all_content(book, chapter, verse)
        # --- (8) 수정 끝 ---

        self.pending_scroll_info = {"tab": target_tab, "verse": verse}
        if self.tab_widget.currentWidget() is not target_tab: self.tab_widget.setCurrentWidget(target_tab)
        else: QTimer.singleShot(100, self._process_pending_scroll)

    @Slot(str, int, int)
    def go_to_verse_in_read_tab(self, book: str, chapter: int, verse: int): self.go_to_verse(self.read_tab, book, chapter, verse)
    @Slot(str, int, int)
    def go_to_commentary_for_verse(self, book: str, chapter: int, verse: int): self.go_to_verse(self.commentary_tab, book, chapter, verse)
    @Slot(str, int, int)
    def go_to_crossref_for_verse(self, book: str, chapter: int, verse: int): self.go_to_verse(self.crossref_tab, book, chapter, verse)

    @Slot(str, int, int, int)
    def go_to_original_language_for_range(self, book: str, chapter: int, start_verse: int, end_verse: int):
        self.add_to_history(book, chapter, start_verse)
        self.navigate_to(book, chapter)
        self.original_language_tab.update_all_content(book, chapter, start_verse, highlight=True)
        if self.tab_widget.currentWidget() is not self.original_language_tab:
            self.tab_widget.setCurrentWidget(self.original_language_tab)

    @Slot(str, int, int)
    def go_to_verse_in_new_read_tab(self, book, chapter, verse):
        if len(self.additional_read_tabs) >= 3:
            QMessageBox.information(self, "알림", "읽기 탭은 최대 3개까지 추가할 수 있습니다.")
            return

        self.add_new_read_tab()
        new_tab = self.tab_widget.currentWidget()

        if isinstance(new_tab, AdditionalReadTab):
            QTimer.singleShot(0, lambda: new_tab.navigate_to(book, chapter))
            QTimer.singleShot(100, lambda: new_tab.scroll_to_verse(verse))

    @Slot(str)
    def on_request_send_to_word(self, text): self.send_to_word(text)

    def send_to_word(self, text: str):
        if win32com is None:
            QMessageBox.warning(self, "기능 오류", "이 기능을 사용하려면 pywin32 라이브러리가 필요합니다.\n'pip install pywin32'를 실행하여 설치하세요.")
            return
        try:
            pythoncom.CoInitialize()
            word_app = win32com.client.Dispatch("Word.Application")
            word_app.Visible = True
            if word_app.Documents.Count == 0: word_app.Documents.Add()
            selection = word_app.Selection
            selection.TypeText(Text=text)
            selection.TypeParagraph()
            word_app.Activate()
        except com_error as e: QMessageBox.critical(self, "MS Word 오류", f"Microsoft Word를 실행하거나 제어하는 중 오류가 발생했습니다.\n설치 여부를 확인하세요.\n\n오류: {e}")
        except Exception as e: QMessageBox.critical(self, "오류", f"알 수 없는 오류가 발생했습니다: {e}")
        finally: pythoncom.CoUninitialize()
            
    @Slot(object, str)
    def on_request_send_to_powerpoint(self, source, text):
        self.send_to_powerpoint(text)

    def send_to_powerpoint(self, text: str):
        if win32com is None:
            QMessageBox.warning(self, "기능 오류", "이 기능을 사용하려면 pywin32 라이브러리가 필요합니다.\n'pip install pywin32'를 실행하여 설치하세요.")
            return
        try:
            pythoncom.CoInitialize()
            pp_app = win32com.client.Dispatch("PowerPoint.Application")
            pp_app.Visible = True
            if pp_app.Presentations.Count == 0: presentation = pp_app.Presentations.Add()
            else: presentation = pp_app.ActivePresentation
            slide_index = presentation.Slides.Count + 1
            new_slide = presentation.Slides.Add(slide_index, 2)
            for shape in new_slide.Shapes:
                if shape.HasTextFrame and shape.PlaceholderFormat.Type != 1:
                    shape.TextFrame.TextRange.Text = text
                    break
            new_slide.Select()
            pp_app.Activate()
        except com_error as e: QMessageBox.critical(self, "MS PowerPoint 오류", f"Microsoft PowerPoint를 실행하거나 제어하는 중 오류가 발생했습니다.\n설치 여부를 확인하세요.\n\n오류: {e}")
        except Exception as e: QMessageBox.critical(self, "오류", f"알 수 없는 오류가 발생했습니다: {e}")
        finally: pythoncom.CoUninitialize()

    @Slot()
    def open_read_mode(self):
        bible_views = self.read_tab.get_bible_views()
        if not bible_views:
            QMessageBox.warning(self, "오류", "읽기 탭에 성경 보기 창이 하나 이상 있어야 합니다.")
            return

        primary_view = bible_views[0]
        checked_theme_action = self.theme_action_group.checkedAction()
        theme = checked_theme_action.text() if checked_theme_action else 'Light'
        
        checked_style_action = self.style_action_group.checkedAction()
        verse_display_mode = checked_style_action.data() if checked_style_action else 0

        read_mode_settings = {
            'book': self.current_book,
            'chapter': self.current_chapter,
            'translation': primary_view.translation_combo.currentText(),
            'font_family': self.font_family,
            'bible_font_size': primary_view.font_size + 4,
            'theme': theme,
            'verse_display_mode': verse_display_mode
        }

        read_mode_dialog = ReadModeViewer(
            self.data_loader, 
            read_mode_settings, 
            self.current_toolbar_stylesheet,
            self
        )
        read_mode_dialog.location_changed.connect(self.update_location_from_read_mode)
        read_mode_dialog.exec()

    @Slot(str, int)
    def update_location_from_read_mode(self, book, chapter):
        self.go_to_verse(self.read_tab, book, chapter, 1)

    @Slot()
    def add_new_read_tab(self):
        if len(self.additional_read_tabs) >= 3:
            QMessageBox.information(self, "알림", "읽기 탭은 최대 3개까지 추가할 수 있습니다.")
            return
        
        index_before_add = self.tab_widget.currentIndex()

        new_tab = AdditionalReadTab(self.data_loader, initial_settings=self._settings, bible_db=self.bible_db)
        self.additional_read_tabs.append(new_tab)
        
        new_tab.previous_index = index_before_add

        new_tab.location_changed.connect(self.update_additional_tab_title)
        new_tab.request_search.connect(self.perform_search_with_selection)
        new_tab.request_send_to_word.connect(self.on_request_send_to_word)
        new_tab.request_send_to_powerpoint.connect(self.on_request_send_to_powerpoint)
        new_tab.request_commentary.connect(self.go_to_commentary_for_verse)
        new_tab.request_cross_ref.connect(self.go_to_crossref_for_verse)
        new_tab.settings_changed.connect(self.save_settings)
        
        if hasattr(new_tab, 'toolbar'):
            new_tab.toolbar.setStyleSheet(self.current_toolbar_stylesheet)

        # 추가 읽기 탭은 고정 탭(통합~원어) 뒤, 즉 '원어' 탭 다음에 순서대로 쌓인다.
        # (예전엔 '메모' 다음에 끼워 넣어서 '원어' 탭보다 앞에 생기고, 첫 탭이 마침
        # update_default_tab_indicator() 의 고정 탭 인덱스(0~6)와 겹쳐 라벨이
        # "원어"로 덮어써지는 문제가 있었다.)
        original_language_index = self.tab_widget.indexOf(self.original_language_tab)
        insert_index = original_language_index + len(self.additional_read_tabs)
        
        actual_index = self.tab_widget.insertTab(insert_index, new_tab, "읽는 중...")
        
        close_btn = CloseButton()
        close_btn.clicked.connect(lambda: self.close_additional_tab(self.tab_widget.indexOf(new_tab)))
        self.tab_widget.tabBar().setTabButton(actual_index, QTabBar.ButtonPosition.RightSide, close_btn)
        
        new_tab.set_font_family(self.font_family)
        if checked_style_action := self.style_action_group.checkedAction():
            new_tab.set_verse_display_mode(checked_style_action.data())
            
        self.tab_widget.setCurrentIndex(actual_index)

    @Slot(object, str)
    def update_additional_tab_title(self, tab, new_title):
        index = self.tab_widget.indexOf(tab)
        if index != -1:
            self.tab_widget.setTabText(index, new_title)
            self.update_default_tab_indicator()

    @Slot(int)
    def close_additional_tab(self, index):
        if index < 0 or index >= self.tab_widget.count():
            return
            
        widget = self.tab_widget.widget(index)
        if isinstance(widget, AdditionalReadTab):
            index_to_restore = getattr(widget, 'previous_index', -1)

            if widget in self.additional_read_tabs:
                self.additional_read_tabs.remove(widget)

            self.tab_widget.removeTab(index)
            widget.deleteLater()

            if index_to_restore != -1 and index_to_restore < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(index_to_restore)
    
    # ========== 하이라이트/메모 관리 기능 ==========
    
    @Slot()
    def open_highlight_list_dialog(self):
        """하이라이트 목록 다이얼로그 열기"""
        if not self.bible_db:
            QMessageBox.warning(self, "오류", "데이터베이스가 초기화되지 않았습니다.")
            return
        
        from highlight_list_dialog import HighlightListDialog
        dialog = HighlightListDialog(self.bible_db, self.data_loader, self)
        dialog.verse_selected.connect(self.go_to_verse_in_read_tab)
        dialog.exec()
    
    @Slot()
    def open_memo_search_dialog(self):
        """메모 검색 다이얼로그 열기"""
        if not self.bible_db:
            QMessageBox.warning(self, "오류", "데이터베이스가 초기화되지 않았습니다.")
            return
        
        from memo_search_dialog import MemoSearchDialog
        dialog = MemoSearchDialog(self.bible_db, self.data_loader, self)
        dialog.verse_selected.connect(self.go_to_verse_in_read_tab)
        dialog.exec()
    
    @Slot()
    def open_statistics_dialog(self):
        """통계 다이얼로그 열기"""
        if not self.bible_db:
            QMessageBox.warning(self, "오류", "데이터베이스가 초기화되지 않았습니다.")
            return
        
        from statistics_dialog import StatisticsDialog
        dialog = StatisticsDialog(self.bible_db, self)
        dialog.exec()
    
    @Slot()
    def export_data(self):
        """데이터 내보내기"""
        if not self.bible_db:
            QMessageBox.warning(self, "오류", "데이터베이스가 초기화되지 않았습니다.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "데이터 내보내기", "bible_data_export.json", 
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if self.bible_db.export_to_json(file_path):
                QMessageBox.information(self, "내보내기 완료", f"데이터가 '{file_path}'에 저장되었습니다.")
            else:
                QMessageBox.warning(self, "내보내기 실패", "데이터 내보내기 중 오류가 발생했습니다.")
    
    @Slot()
    def import_data(self):
        """데이터 가져오기"""
        if not self.bible_db:
            QMessageBox.warning(self, "오류", "데이터베이스가 초기화되지 않았습니다.")
            return
        
        reply = QMessageBox.question(
            self, "데이터 가져오기", 
            "기존 데이터와 병합됩니다. 계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "데이터 가져오기", "", 
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            if self.bible_db.import_from_json(file_path):
                QMessageBox.information(self, "가져오기 완료", "데이터가 성공적으로 가져와졌습니다.")
                # 화면 갱신
                self.update_all_tabs_content()
            else:
                QMessageBox.warning(self, "가져오기 실패", "데이터 가져오기 중 오류가 발생했습니다.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    
    window.show()
    sys.exit(app.exec())
