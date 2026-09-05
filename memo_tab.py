# memo_tab.py
import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QSplitter, QLabel, QFrame,
    QMenu, QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QPoint
from PySide6.QtGui import QFont, QAction

from bible_view import SharedBibleView
from html_utils import _PlainCopyMixin

class MemoEditor(_PlainCopyMixin, QTextEdit):
    def insertFromMimeData(self, source):
        # 붙여넣기 시 서식 없는 텍스트만 입력
        if source.hasText():
            self.insertPlainText(source.text())
        # 이미지 등 다른 데이터는 무시
        # super().insertFromMimeData(source) 호출하지 않음
    """
    컨텍스트 메뉴를 통해 성경 구절로 이동하는 기능을 가진 커스텀 QTextEdit.
    """
    # 탐색 요청 시그널 (책, 장, 절)
    navigation_requested = Signal(str, int, int)

    def __init__(self, data_loader, parent=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    @Slot(QPoint)
    def show_context_menu(self, pos):
        menu = QMenu(self)

        # 표준 액션 추가 (복사, 붙여넣기 등)
        undo_action = menu.addAction("되돌리기")
        undo_action.setEnabled(self.isUndoRedoEnabled())
        undo_action.triggered.connect(self.undo)
        
        redo_action = menu.addAction("다시 실행")
        redo_action.setEnabled(self.isUndoRedoEnabled())
        redo_action.triggered.connect(self.redo)
        
        menu.addSeparator()
        
        cut_action = menu.addAction("잘라내기")
        cut_action.setEnabled(self.textCursor().hasSelection())
        cut_action.triggered.connect(self.cut)
        
        copy_action = menu.addAction("복사")
        copy_action.setEnabled(self.textCursor().hasSelection())
        copy_action.triggered.connect(self.copy)
        
        paste_action = menu.addAction("붙여넣기")
        paste_action.setEnabled(self.canPaste())
        paste_action.triggered.connect(self.paste)
        
        select_all_action = menu.addAction("모두 선택")
        select_all_action.triggered.connect(self.selectAll)

        # 선택된 텍스트에서 성경 위치 패턴을 찾아 이동 메뉴 제공
        cursor = self.textCursor()
        selected_text = cursor.selectedText().strip()
        bible_ref_pattern = r"([가-힣A-Za-z]+)\s*([0-9]+)\s*[:\.]\s*([0-9]+)"  # 예: 창세기 1:1, 요3:16, 마 5.3
        import re
        found = None
        if selected_text:
            for m in re.finditer(bible_ref_pattern, selected_text):
                book, chapter, verse = m.group(1), m.group(2), m.group(3)
                # data_loader의 parse_reference로 실제 유효성 확인
                b, c, v = self.data_loader.parse_reference(f"{book} {chapter}:{verse}")
                if b:
                    found = (m.group(0), b, c, v)
                    break
        if found:
            menu.addSeparator()
            go_to_action = QAction(f"'{found[0]}'(으)로 이동", self)
            go_to_action.triggered.connect(
                lambda: self.navigation_requested.emit(found[1], found[2], found[3] if found[3] else 1)
            )
            menu.addAction(go_to_action)

        menu.exec(self.mapToGlobal(pos))


class MemoTab(QWidget):
    """
    좌측에는 성경 뷰, 우측에는 메모장이 있는 탭 위젯.
    """
    settings_changed = Signal()

    def __init__(self, data_loader, parent=None, initial_settings=None, bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.bible_db = bible_db
        if initial_settings is None: initial_settings = {}
        
        self.current_book = initial_settings.get('book', '창세기')
        self.current_chapter = initial_settings.get('chapter', 1)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.font_size = initial_settings.get('bible_font_size', 14)

        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.setInterval(2000) # 2초 후 자동 저장

        # [추가] 상태 메시지용 타이머 (주석/관주 탭과 동일)
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.update_location_status)

        self.init_ui(initial_settings)
        self.connect_signals()

    def init_ui(self, initial_settings):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1) # [수정] splitter가 남은 공간을 모두 차지하도록 stretch factor 추가

        # --- 좌측: 성경 뷰 ---
        bible_view_settings = {
            'translation': self.data_loader.get_available_translations()[0],
            'bible_font_size': self.font_size,
            'font_family': self.font_family,
            'verse_display_mode': initial_settings.get('verse_display_mode', 0)
        }
        self.bible_view = SharedBibleView(
            self.data_loader, self.data_loader.get_available_translations(),
            initial_settings=bible_view_settings, context='memo', bible_db=self.bible_db
        )
        
        # --- 우측: 메모 에디터 ---
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        
        # === 제목 + 버튼을 담을 레이아웃 ===
        title_layout = QHBoxLayout()
        self.location_label = QLabel()
        self.location_label.setStyleSheet("font-weight: bold; font-size: 10pt; margin-top: 4px; margin-bottom: 4px;")
        self.go_to_chapter_btn = QPushButton("이 장으로 이동")
        self.go_to_chapter_btn.setObjectName("MemoTabGoToChapterButton")
        self.go_to_chapter_btn.setToolTip("왼쪽 성경 뷰를 현재 메모의 장으로 이동시킵니다.")
        
        title_layout.addWidget(self.location_label)
        title_layout.addStretch()
        title_layout.addWidget(self.go_to_chapter_btn)
        # ==================================

        self.editor = MemoEditor(self.data_loader, self)
        self.editor.setPlaceholderText("이곳에 메모를 입력하세요.\n성경 구절(예: 요3:16)을 선택하고 우클릭하면 해당 위치로 이동할 수 있습니다.")
        
        editor_layout.addLayout(title_layout) # 제목 레이아웃 추가
        editor_layout.addWidget(self.editor)

        # === 저장 버튼 영역 ===
        save_btn_layout = QHBoxLayout()
        self.save_book_btn = QPushButton("이 책 전체 메모 저장")
        self.save_book_btn.setObjectName("MemoTabSaveBookButton")
        save_btn_layout.addStretch()
        save_btn_layout.addWidget(self.save_book_btn)
        editor_layout.addLayout(save_btn_layout)

        # --- 스플리터에 위젯 추가 ---
        self.splitter.addWidget(self.bible_view)
        self.splitter.addWidget(editor_container)
        self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])

        # [추가] 주석/관주 탭과 동일한 푸터(상태 표시줄) 추가
        status_container = QHBoxLayout()
        self.status_label_left = QLabel()
        self.status_label_left.setContentsMargins(5, 2, 0, 2)
        self.status_label_right = QLabel("이 말씀은 곧 하나님이시니라(요 1:1)")
        self.status_label_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label_right.setContentsMargins(0, 2, 5, 2)
        
        status_container.addWidget(self.status_label_left)
        status_container.addStretch(1)
        status_container.addWidget(self.status_label_right)
        
        main_layout.addLayout(status_container) # 메인 레이아웃에 푸터 추가

    def connect_signals(self):
        self.editor.textChanged.connect(self.auto_save_timer.start)
        self.auto_save_timer.timeout.connect(self.save_memo)
        self.editor.navigation_requested.connect(self.navigate_bible_view)
        self.go_to_chapter_btn.clicked.connect(self.go_to_memo_chapter) # 버튼 시그널 연결

        self.save_book_btn.clicked.connect(self.save_whole_book_merged_dialog)

    # [추가] 주석/관주 탭과 동일한 메서드
    def update_location_status(self):
        """하단 상태 표시줄의 위치 정보를 업데이트합니다."""
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

    # [추가] 주석/관주 탭과 동일한 메서드
    def show_temporary_message(self, message):
        """하단 상태 표시줄에 임시 메시지를 표시합니다."""
        self.status_timer.stop()
        self.status_label_left.setText(message)
        self.status_timer.start(5000) # 5초 후 원래 상태로 복원

    def save_whole_book_merged_dialog(self):
        """현재 책의 모든 장 메모를 하나의 파일로 합쳐 저장 (파일 다이얼로그 사용)"""
        if not self.bible_db:
            QMessageBox.warning(self, "오류", "데이터베이스가 초기화되지 않았습니다.")
            return
        
        default_filename = f"{self.current_book}_전체메모.txt"
        path, _ = QFileDialog.getSaveFileName(self, "책 전체 메모 저장", default_filename, "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        
        try:
            chapter_count = self.data_loader.global_book_chapter_counts.get(self.current_book, 150)
        except Exception:
            chapter_count = 150  # fallback
        
        # 현재 장 메모를 먼저 저장
        current_content = self.editor.toPlainText()
        if current_content.strip():
            self.bible_db.save_memo(self.current_book, self.current_chapter, current_content)
        
        merged_content = []
        memos = self.bible_db.get_all_memos(self.current_book)
        memo_dict = {(m['chapter'], m.get('verse')): m['content'] for m in memos}
        
        for chapter in range(1, chapter_count + 1):
            title = f"{self.current_book} {chapter}장"
            content = memo_dict.get((chapter, None), "").strip()
            if content:
                merged_content.append(f"{title}\n{content}")
            else:
                merged_content.append(f"{title}")
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(merged_content))
            QMessageBox.information(self, "저장 완료", f"{self.current_book} 전체 메모가 저장되었습니다:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", f"전체 메모 저장 실패: {e}")

    @Slot()
    def save_memo(self):
        """DB에 메모 저장"""
        if not self.bible_db:
            return
        content = self.editor.toPlainText()
        self.bible_db.save_memo(self.current_book, self.current_chapter, content)

    def load_memo(self):
        """DB에서 메모 로드"""
        if not self.bible_db:
            content = ""
        else:
            content = self.bible_db.get_memo(self.current_book, self.current_chapter) or ""

        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)

    def set_font_family(self, font_name):
        self.font_family = font_name
        font = QFont(self.font_family, self.font_size)
        self.editor.setFont(font)
        self.bible_view.set_font_family(font_name)
        
        # 라벨의 폰트 패밀리만 변경하고, 크기는 고정값을 유지하도록 함
        label_font = self.location_label.font()
        label_font.setFamily(font_name)
        self.location_label.setFont(label_font)

    def set_font_size(self, size):
        self.font_size = size
        font = QFont(self.font_family, self.font_size)
        self.editor.setFont(font)
        self.bible_view.set_font_size(size)
        # 라벨의 폰트 크기가 내용물 크기에 따라 변경되지 않도록 관련 코드 삭제

    @Slot(int)
    def set_verse_display_mode(self, mode_id):
        """절 표시 스타일을 변경하는 슬롯"""
        self.bible_view.set_verse_display_mode(mode_id)

    @Slot(str, int)
    def update_location(self, book, chapter):
        if self.auto_save_timer.isActive():
            self.auto_save_timer.stop()
            self.save_memo()

        self.current_book = book
        self.current_chapter = chapter
        
        self.location_label.setText(f"{self.current_book} {self.current_chapter}장 메모")
        
        self.bible_view.update_content(book, chapter)
        self.load_memo()
        self.update_location_status() # [추가] 위치 변경 시 상태 표시줄 업데이트

    @Slot(str, int, int)
    def navigate_bible_view(self, book, chapter, verse):
        self.bible_view.update_content(book, chapter)
        if verse:
            QTimer.singleShot(50, lambda: self.bible_view.scroll_to_verse(verse))

    @Slot()
    def go_to_memo_chapter(self):
        """'이 장으로 이동' 버튼 클릭 시 호출되는 슬롯."""
        self.bible_view.update_content(self.current_book, self.current_chapter)
        self.bible_view.scroll_to_verse(1) # 해당 장의 처음으로 스크롤