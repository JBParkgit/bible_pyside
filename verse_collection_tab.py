# verse_collection_tab.py
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QLabel, QFrame
)
from PySide6.QtGui import QTextOption, QFont, QTextCursor, QPalette
from PySide6.QtCore import Qt, Signal, Slot, QPoint

class VerseCollectionTab(QWidget):
    settings_changed = Signal()
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)

    def __init__(self, file_path="my_verse_collection.txt", parent=None, initial_settings=None):
        super().__init__(parent)
        self.file_path = file_path
        if initial_settings is None: initial_settings = {}
        self.font_size = initial_settings.get('verse_collection_font_size', 12)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        self.init_ui()
        self.load_text()
        self.connect_signals()
        
    def show_themed_message(self, title, text, icon=QMessageBox.Information, buttons=QMessageBox.Ok):
        """테마를 따르는 메시지 박스를 표시합니다."""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.setStandardButtons(buttons)
        
        # 시스템 팔레트의 색상을 가져옴
        base_color = self.palette().color(QPalette.Base)
        text_color = self.palette().color(QPalette.Text)
        
        # 메시지 박스 스타일 설정
        msg.setStyleSheet(f"""
            QMessageBox {{
                background-color: {base_color.name()};
                color: {text_color.name()};
            }}
            QMessageBox QLabel {{
                color: {text_color.name()};
            }}
            QMessageBox QPushButton {{
                background-color: {base_color.name()};
                color: {text_color.name()};
                border: 1px solid {text_color.name()};
                padding: 5px 15px;
                border-radius: 3px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {text_color.name()};
                color: {base_color.name()};
            }}
        """)
        
        return msg.exec()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.text_editor = QTextEdit()
        self.text_editor.setWordWrapMode(QTextOption.WrapAnywhere)
        self.text_editor.setFont(QFont(self.font_family, self.font_size))
        self.text_editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # --- 하단 컨트롤 바를 QFrame으로 감싸기 ---
        control_bar = QFrame()
        control_bar.setObjectName("VerseCollectionControlBar")
        control_layout = QHBoxLayout(control_bar)
        
        self.font_size_label = QLabel(str(self.font_size))
        self.font_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_size_label.setMinimumWidth(25)
        self.font_plus_button = QPushButton("+")
        self.font_plus_button.setFixedSize(24, 24)
        self.font_minus_button = QPushButton("-")
        self.font_minus_button.setFixedSize(24, 24)
        control_layout.addWidget(self.font_minus_button)
        control_layout.addWidget(self.font_size_label)
        control_layout.addWidget(self.font_plus_button)
        control_layout.addStretch(1)

        self.word_button = QPushButton("워드로 보내기")
        self.ppt_button = QPushButton("파워포인트로 보내기")
        self.word_button.setToolTip("전체 내용을 MS Word로 보냅니다 (Ctrl+W로 선택영역 보내기 가능)")
        self.ppt_button.setToolTip("전체 내용을 MS PowerPoint로 보냅니다 (Ctrl+P로 선택영역 보내기 가능)")
        control_layout.addWidget(self.word_button)
        control_layout.addWidget(self.ppt_button)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        control_layout.addWidget(separator)

        self.load_button = QPushButton("불러오기")
        self.load_button.setFixedSize(80, 24)
        self.save_button = QPushButton("저장")
        self.save_button.setFixedSize(60, 24)
        self.clear_button = QPushButton("초기화")
        self.clear_button.setFixedSize(60, 24)
        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.save_button)
        control_layout.addWidget(self.clear_button)

        main_layout.addWidget(self.text_editor)
        main_layout.addWidget(control_bar) # QFrame 위젯 추가

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

    def connect_signals(self):
        self.save_button.clicked.connect(self.save_text)
        self.load_button.clicked.connect(self.select_and_load_text)
        self.clear_button.clicked.connect(self.clear_text)
        self.font_plus_button.clicked.connect(lambda: self.change_font_size(1))
        self.font_minus_button.clicked.connect(lambda: self.change_font_size(-1))
        self.text_editor.customContextMenuRequested.connect(self.show_context_menu)
        
        self.word_button.clicked.connect(self.on_send_to_word_clicked)
        self.ppt_button.clicked.connect(self.on_send_to_powerpoint_clicked)

    # --- 단축키 핸들러 추가 ---
    def handle_send_to_word_shortcut(self):
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection():
            self.request_send_to_word.emit(cursor.selection().toPlainText().strip())

    def handle_send_to_powerpoint_shortcut(self):
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection():
            self.request_send_to_powerpoint.emit(self, cursor.selection().toPlainText().strip())
    # ----------------------------------------

    @Slot(QPoint)
    def show_context_menu(self, pos):
        menu = self.text_editor.createStandardContextMenu()
        menu.addSeparator()
        cursor = self.text_editor.textCursor()
        has_selection = cursor.hasSelection()
        word_action = menu.addAction("MS Word로 보내기 (Ctrl+W)")
        ppt_action = menu.addAction("MS PowerPoint로 보내기 (Ctrl+P)")
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)
        if has_selection:
            selected_text = cursor.selection().toPlainText().strip()
            word_action.triggered.connect(lambda: self.request_send_to_word.emit(selected_text))
            ppt_action.triggered.connect(lambda: self.request_send_to_powerpoint.emit(self, selected_text))
        menu.exec(self.text_editor.mapToGlobal(pos))

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.text_editor.setFont(QFont(self.font_family, self.font_size))

    @Slot(int)
    def change_font_size(self, delta):
        self.font_size = max(8, self.font_size + delta)
        self.font_size_label.setText(str(self.font_size))
        self.text_editor.setFont(QFont(self.font_family, self.font_size))
        self.settings_changed.emit()

    @Slot()
    def clear_text(self):
        reply = self.show_themed_message(
            "내용 초기화",
            "정말로 모든 내용을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.text_editor.clear()

    def load_text(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.text_editor.setPlainText(f.read())
            except Exception as e:
                self.show_themed_message(
                    "파일 로드 오류",
                    f"파일을 로드하는 중 오류가 발생했습니다: {e}",
                    QMessageBox.Warning
                )
        else:
            self.text_editor.setPlainText("") 

    def save_text(self):
        """편집창의 내용을 사용자가 선택한 위치에 새 파일로 저장합니다."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            self.show_themed_message("알림", "저장할 내용이 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "저장할 파일 선택",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.show_themed_message("저장 완료", f"'{os.path.basename(file_path)}' 파일로 성공적으로 저장되었습니다.")
            except Exception as e:
                self.show_themed_message(
                    "파일 저장 오류",
                    f"파일을 저장하는 중 오류가 발생했습니다: {e}",
                    QMessageBox.Warning
                )

    @Slot()
    def select_and_load_text(self):
        selected_file_path, _ = QFileDialog.getOpenFileName(self, "불러올 파일 선택", "", "Text Files (*.txt);;All Files (*)")
        if selected_file_path:
            self.file_path = selected_file_path
            self.load_text()
            self.show_themed_message("불러오기 완료", f"'{os.path.basename(selected_file_path)}' 파일이 성공적으로 불러와졌습니다.")
            self.settings_changed.emit()
            
    @Slot()
    def on_send_to_word_clicked(self):
        """'워드로 보내기' 버튼 클릭 시 전체 내용을 Word로 보냅니다."""
        full_text = self.text_editor.toPlainText()
        if not full_text.strip():
            self.show_themed_message("알림", "보낼 내용이 없습니다.")
            return
        self.request_send_to_word.emit(full_text)

    @Slot()
    def on_send_to_powerpoint_clicked(self):
        """'파워포인트로 보내기' 버튼 클릭 시 전체 내용을 PowerPoint로 보냅니다."""
        full_text = self.text_editor.toPlainText()
        if not full_text.strip():
            self.show_themed_message("알림", "보낼 내용이 없습니다.")
            return
        self.request_send_to_powerpoint.emit(self, full_text)

    @Slot(str)
    def append_text(self, text_to_append):
        current_text = self.text_editor.toPlainText()
        if current_text:
            self.text_editor.append("\n" + text_to_append)
        else:
            self.text_editor.setPlainText(text_to_append)
        self.text_editor.moveCursor(QTextCursor.MoveOperation.End)