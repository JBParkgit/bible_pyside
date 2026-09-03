# bible_view.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QComboBox, QLabel, QPushButton, QFrame, QApplication, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QPoint, QSize, QTimer
from PySide6.QtGui import QFont, QTextOption, QPalette, QTextCursor, QKeySequence, QKeyEvent, QIcon

from html_utils import apply_text_layout, get_text_alignment, get_text_direction, html_escape
from body_style import body_style_from_settings, SERIF_STACK


HIGHLIGHT_COLORS = {
    "yellow": ("노랑", "#fff59d"),
    "green": ("초록", "#c8e6c9"),
    "blue": ("파랑", "#bbdefb"),
    "pink": ("분홍", "#f8bbd0"),
}
SELECTED_VERSE_COLOR = "#dbeafe"


class CustomTextBrowser(QTextBrowser):
    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.custom_copy()
            event.accept()
        else:
            super().keyPressEvent(event)

    def custom_copy(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return

        raw_text = cursor.selection().toPlainText()
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]

        final_lines = []
        i = 0
        while i < len(lines):
            current_line = lines[i]
            
            m1 = re.match(r'^\(?\s*[가-힣A-Za-z]+\s*\d+:(\d+)\s*\)?', current_line)
            m2 = re.match(r'^\s*(\d+)\.', current_line)
            is_only_a_ref = (m1 or m2) and len(current_line) < 35

            if is_only_a_ref and i + 1 < len(lines):
                next_line = lines[i+1]
                nm1 = re.match(r'^\(?\s*[가-힣A-Za-z]+\s*\d+:(\d+)\s*\)?', next_line)
                nm2 = re.match(r'^\s*(\d+)\.', next_line)
                
                if not (nm1 or nm2):
                    merged_line = current_line + " " + next_line
                    final_lines.append(merged_line)
                    i += 2
                    continue
            
            final_lines.append(current_line)
            i += 1
        
        final_processed_lines = [re.sub(r'\s+', ' ', line) for line in final_lines]
        processed_text = '\n'.join(final_processed_lines)

        clipboard = QApplication.clipboard()
        clipboard.setText(processed_text)

class SharedBibleView(QWidget):
    translation_changed = Signal(str)
    font_size_changed = Signal(int)
    verse_anchor_clicked = Signal(QUrl)
    scroll_changed = Signal(int)
    highlight_changed = Signal()  # 하이라이트 변경 시그널

    request_commentary = Signal(str, int, int)
    request_cross_ref = Signal(str, int, int)
    request_search = Signal(str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)
    request_original_language = Signal(str, int, int, int)
    # (참조, 본문, 번역본이름, 책, 장, 시작절, 끝절)
    request_ai_explanation = Signal(str, str, str, str, int, int, int)

    def __init__(self, data_loader, available_translations, parent=None, initial_settings=None, is_main_reader=False, context='read', bible_db=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.available_translations = available_translations
        self.is_main_reader = is_main_reader
        self.context = context
        self.bible_db = bible_db
        self.current_book = "창세기"
        self.current_chapter = 1
        self.current_verse_for_context = 1
        self.selected_verse_anchor = None
        self.selected_verse_focus = None
        if initial_settings is None: initial_settings = {}
        self.verse_display_mode = initial_settings.get('verse_display_mode', 0)
        self.font_size = initial_settings.get('bible_font_size', 14)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        
        self.menu_stylesheet = ""
        # 테마에 따라 갱신되는 본문 색 (set_theme_mode 로 교체)
        self._selected_verse_color = SELECTED_VERSE_COLOR
        self._verse_num_color = "#605E5C"
        # 본문 타이포그래피 (본문 보기 설정 창에서 조정)
        self.body_style = body_style_from_settings(initial_settings)

        self.init_ui()
        self.connect_signals()
        initial_translation = initial_settings.get('translation')
        if initial_translation and initial_translation in self.available_translations:
            self.translation_combo.setCurrentText(initial_translation)
        self.text_browser.setFont(QFont(self.font_family, self.font_size))
        self.set_word_wrap_mode(self.translation_combo.currentText())

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        control_bar = QFrame()
        control_bar.setObjectName("viewControlBar")
        control_bar_layout = QHBoxLayout(control_bar)
        control_bar_layout.setContentsMargins(6, 4, 6, 4)
        self.translation_combo = QComboBox()
        self.translation_combo.addItems(self.available_translations)
        self.translation_combo.setToolTip("번역본을 선택하세요.")

        control_bar_layout.addWidget(self.translation_combo)
        control_bar_layout.addStretch(1)
        
        self.send_to_word_button = QPushButton()
        self.send_to_word_button.setIcon(QIcon("Icon_word.svg"))
        self.send_to_word_button.setIconSize(QSize(30, 30))
        self.send_to_word_button.setFixedSize(30, 30)
        self.send_to_word_button.setToolTip("선택한 본문을 MS Word로 보내기 (Ctrl+W)")
        self.send_to_word_button.setEnabled(False)
        control_bar_layout.addWidget(self.send_to_word_button)

        self.send_to_ppt_button = QPushButton()
        self.send_to_ppt_button.setIcon(QIcon("Icon_PPT.svg"))
        self.send_to_ppt_button.setIconSize(QSize(30, 30))
        self.send_to_ppt_button.setFixedSize(30, 30)
        self.send_to_ppt_button.setToolTip("선택한 본문을 MS PowerPoint로 보내기 (Ctrl+P)")
        self.send_to_ppt_button.setEnabled(False)
        control_bar_layout.addWidget(self.send_to_ppt_button)
        
        self.text_browser = CustomTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_browser.document().setDocumentMargin(self.body_style.get("doc_margin", 18))
        
        palette = self.text_browser.palette()
        palette.setColor(QPalette.Base, QApplication.palette().color(QPalette.Base))
        self.text_browser.setPalette(palette)
        
        layout.addWidget(control_bar)
        layout.addWidget(self.text_browser)
        self.init_selection_bar(layout)

    def init_selection_bar(self, layout):
        self.selection_bar = QFrame()
        self.selection_bar.setObjectName("selectionBar")
        selection_layout = QHBoxLayout(self.selection_bar)
        selection_layout.setContentsMargins(8, 6, 8, 6)
        selection_layout.setSpacing(6)

        self.selection_reference_label = QLabel()
        self.selection_reference_label.setObjectName("selectionReferenceLabel")
        selection_layout.addWidget(self.selection_reference_label)
        selection_layout.addStretch(1)

        self.selection_copy_button = QPushButton("복사")
        self.selection_copy_button.setProperty("primary", "true")
        self.selection_compare_button = QPushButton("비교")
        self.selection_original_button = QPushButton("원어")
        self.selection_ai_button = QPushButton("설명")
        self.selection_ai_button.setToolTip("선택한 구절에 대한 AI 해설 보기 (Gemini)")
        self.selection_word_button = QPushButton("워드")
        self.selection_word_button.setToolTip("선택한 구절을 MS Word로 보내기")
        self.selection_ppt_button = QPushButton("PPT")
        self.selection_ppt_button.setToolTip("선택한 구절을 MS PowerPoint로 보내기")
        for button in [
            self.selection_copy_button,
            self.selection_compare_button,
            self.selection_original_button,
            self.selection_ai_button,
            self.selection_word_button,
            self.selection_ppt_button,
        ]:
            button.setFixedHeight(28)
            selection_layout.addWidget(button)

        self.highlight_color_buttons = {}
        for key, (label, color) in HIGHLIGHT_COLORS.items():
            button = QPushButton()
            button.setFixedSize(28, 28)
            button.setToolTip(f"{label} 하이라이트")
            button.setStyleSheet(f"background-color: {color}; border: 1px solid #8c959f;")
            self.highlight_color_buttons[key] = button
            selection_layout.addWidget(button)

        self.selection_clear_button = QPushButton("닫기")
        self.selection_clear_button.setFixedHeight(28)
        selection_layout.addWidget(self.selection_clear_button)

        self.selection_bar.hide()
        layout.addWidget(self.selection_bar)

    def connect_signals(self):
        self.translation_combo.currentTextChanged.connect(self.on_translation_changed)
        self.text_browser.verticalScrollBar().valueChanged.connect(self.scroll_changed.emit)
        self.text_browser.customContextMenuRequested.connect(self.show_context_menu)
        self.text_browser.anchorClicked.connect(self.on_verse_anchor_clicked)
        self.text_browser.selectionChanged.connect(self.update_action_buttons_state)
        self.send_to_word_button.clicked.connect(self.trigger_send_to_word)
        self.send_to_ppt_button.clicked.connect(self.trigger_send_to_powerpoint)
        self.selection_copy_button.clicked.connect(self.copy_selected_verses)
        self.selection_compare_button.clicked.connect(self.open_selected_comparison)
        self.selection_original_button.clicked.connect(self.open_selected_original_language)
        self.selection_ai_button.clicked.connect(self.open_selected_ai_explanation)
        self.selection_word_button.clicked.connect(self.send_selected_to_word)
        self.selection_ppt_button.clicked.connect(self.send_selected_to_powerpoint)
        self.selection_clear_button.clicked.connect(lambda: self.clear_verse_selection())
        for key, button in self.highlight_color_buttons.items():
            button.clicked.connect(lambda checked=False, color_key=key: self.set_selected_highlight_color(color_key))

    @Slot()
    def update_action_buttons_state(self):
        has_selection = (
            self.text_browser.textCursor().hasSelection()
            or bool(self._selected_verse_numbers())
        )
        self.send_to_word_button.setEnabled(has_selection)
        self.send_to_ppt_button.setEnabled(has_selection)

    def set_menu_stylesheet(self, stylesheet):
        self.menu_stylesheet = stylesheet

    def set_theme_mode(self, mode):
        """'light' / 'dark' 에 맞춰 본문 HTML 색상을 조정하고 다시 그린다."""
        if mode == "dark":
            self._selected_verse_color = "#2a4b6b"
            self._verse_num_color = "#9aa7b4"
        else:
            self._selected_verse_color = SELECTED_VERSE_COLOR
            self._verse_num_color = "#605E5C"
        try:
            self.update_content(preserve_scroll=True, realign_verse=False)
        except Exception:
            pass

    def _selected_verse_numbers(self):
        if self.selected_verse_anchor is None or self.selected_verse_focus is None:
            return []
        start = min(self.selected_verse_anchor, self.selected_verse_focus)
        end = max(self.selected_verse_anchor, self.selected_verse_focus)
        return list(range(start, end + 1))

    def _format_reference(self, verse_numbers, full=False):
        """구절 번호 목록 → 참조 문자열.
        full=True 이면 성경책 전체 이름(창세기), False 이면 약칭(창)을 쓴다.
        - 1구절: '창세기 1:4'
        - 인접 2구절: '창세기 1:4, 5'
        - 3구절 이상: '창세기 1:4-7'
        """
        verse_numbers = sorted(v for v in verse_numbers if v)
        if not verse_numbers:
            return ""
        if full:
            book = self.data_loader.get_book_full_name(
                self.current_book, translation_name=self.translation_combo.currentText())
        else:
            book = self.data_loader.get_book_abbr(
                self.current_book, translation_name=self.translation_combo.currentText())
        if len(verse_numbers) == 1:
            verses = f"{verse_numbers[0]}"
        elif len(verse_numbers) == 2:
            verses = f"{verse_numbers[0]}, {verse_numbers[1]}"
        else:
            verses = f"{verse_numbers[0]}-{verse_numbers[-1]}"
        return f"{book} {self.current_chapter}:{verses}"

    def _selected_reference(self, full=False):
        return self._format_reference(self._selected_verse_numbers(), full=full)

    def _get_verses_only(self, translation=None):
        translation = translation or self.translation_combo.currentText()
        data = self.data_loader.load_translation_data(translation)
        chapter_content = data["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
        verses = [line for line in chapter_content if not re.match(r'<\s*(.+?)\s*>', line)]
        return data, verses

    def on_verse_anchor_clicked(self, url: QUrl):
        verse_num = None
        href = url.toString()
        if href.startswith("ai:"):
            match = re.match(r"ai:(\d+)-(\d+)", href)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                self.emit_ai_explanation_for(list(range(start, end + 1)))
            return
        if href.startswith("#"):
            href = href[1:]
        try:
            verse_num = int(href)
        except (TypeError, ValueError):
            pass

        if verse_num:
            self.current_verse_for_context = verse_num
            if self.selected_verse_anchor == verse_num and self.selected_verse_focus == verse_num:
                self.clear_verse_selection(update=False)
            elif self.selected_verse_anchor is None:
                self.selected_verse_anchor = verse_num
                self.selected_verse_focus = verse_num
            else:
                self.selected_verse_focus = verse_num
            self.update_selection_bar()
            # 구절 선택 시 스크롤이 조금도 움직이지 않도록 재정렬을 끈다.
            self.update_content(preserve_scroll=True, realign_verse=False)

        self.verse_anchor_clicked.emit(url)

    def clear_verse_selection(self, update=True):
        self.selected_verse_anchor = None
        self.selected_verse_focus = None
        self.selection_bar.hide()
        self.update_action_buttons_state()
        if update:
            self.update_content(preserve_scroll=True, realign_verse=False)

    def update_selection_bar(self):
        selected = self._selected_verse_numbers()
        self.update_action_buttons_state()
        if not selected:
            self.selection_bar.hide()
            return
        self.selection_reference_label.setText(self._selected_reference(full=True))
        self.selection_bar.show()

    def _build_verse_text(self, verse_numbers):
        """구절 번호 목록 → (참조 헤더 + 본문 텍스트, 참조 헤더)."""
        verse_numbers = sorted(set(v for v in verse_numbers if v))
        if not verse_numbers:
            return None, None

        _, verses = self._get_verses_only()
        header = self._format_reference(verse_numbers, full=True)
        lines = [header]
        single = len(verse_numbers) == 1
        for verse_num in verse_numbers:
            if 0 <= verse_num - 1 < len(verses):
                verse_text = verses[verse_num - 1]
                if not verse_text:
                    continue
                lines.append(verse_text if single else f"{verse_num} {verse_text}")

        return "\n".join(lines), header

    def _build_selected_verse_text(self):
        return self._build_verse_text(self._selected_verse_numbers())

    def _show_selection_message(self, message):
        self.selection_reference_label.setText(f"{self._selected_reference(full=True)} - {message}")
        QTimer.singleShot(1800, self.update_selection_bar)

    @Slot()
    def copy_selected_verses(self):
        text, _ = self._build_selected_verse_text()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._show_selection_message("복사됨")

    @Slot()
    def open_selected_comparison(self):
        selected = self._selected_verse_numbers()
        if not selected:
            return
        self.current_verse_for_context = selected[0]
        self.open_comparison_view(selected[0], selected[-1])

    @Slot()
    def open_selected_original_language(self):
        selected = self._selected_verse_numbers()
        if not selected:
            return
        self.request_original_language.emit(self.current_book, self.current_chapter, selected[0], selected[-1])

    def emit_ai_explanation_for(self, verse_numbers):
        """주어진 구절 목록에 대한 AI 해설을 요청한다. (액션바·우클릭 공용)"""
        verse_numbers = sorted(set(v for v in verse_numbers if v))
        if not verse_numbers:
            return
        text, header = self._build_verse_text(verse_numbers)
        if not text:
            return
        passage = text.split("\n", 1)[1] if "\n" in text else text
        self.request_ai_explanation.emit(
            header, passage, self.translation_combo.currentText(),
            self.current_book, self.current_chapter, verse_numbers[0], verse_numbers[-1],
        )

    @Slot()
    def open_selected_ai_explanation(self):
        self.emit_ai_explanation_for(self._selected_verse_numbers())

    @Slot()
    def send_selected_to_word(self):
        text, _ = self._build_selected_verse_text()
        if not text:
            return
        self.request_send_to_word.emit(text)
        self._show_selection_message("워드로 보냄")

    @Slot()
    def send_selected_to_powerpoint(self):
        text, _ = self._build_selected_verse_text()
        if not text:
            return
        self.request_send_to_powerpoint.emit(self, text)
        self._show_selection_message("PPT로 보냄")

    def set_selected_highlight_color(self, color_key):
        selected = self._selected_verse_numbers()
        if not selected or not self.bible_db:
            return

        _, color = HIGHLIGHT_COLORS.get(color_key, HIGHLIGHT_COLORS["yellow"])
        all_same_color = all(
            self.bible_db.is_highlighted(self.current_book, self.current_chapter, verse)
            and self.bible_db.get_highlight_color(self.current_book, self.current_chapter, verse) == color
            for verse in selected
        )

        for verse_num in selected:
            if all_same_color:
                self.bible_db.remove_highlight(self.current_book, self.current_chapter, verse_num)
            else:
                self.bible_db.add_highlight(self.current_book, self.current_chapter, verse_num, color)

        self.update_content(preserve_scroll=True, realign_verse=False)
        self.highlight_changed.emit()

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.text_browser.setFont(QFont(self.font_family, self.font_size))

    @Slot(int)
    def set_font_size(self, size):
        if self.font_size == size: return
        self.font_size = max(8, size)
        self.text_browser.setFont(QFont(self.font_family, self.font_size))
        self.update_content()

    def apply_body_style(self, style):
        """본문 타이포그래피(행간·절 간격·글꼴 등)를 갱신하고 다시 그린다."""
        if not style:
            return
        self.body_style = dict(self.body_style)
        self.body_style.update(style)
        try:
            self.text_browser.document().setDocumentMargin(self.body_style.get("doc_margin", 18))
        except Exception:
            pass
        self.update_content(preserve_scroll=True, realign_verse=False)

    @Slot(int)
    def set_verse_display_mode(self, mode):
        if self.verse_display_mode != mode:
            self.verse_display_mode = mode
            self.update_content()

    def set_word_wrap_mode(self, translation_name):
        try:
            data = self.data_loader.load_translation_data(translation_name)
            apply_text_layout(self.text_browser, data)
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

    def update_theme(self):
        palette = self.text_browser.palette()
        palette.setColor(QPalette.Base, QApplication.palette().color(QPalette.Base))
        self.text_browser.setPalette(palette)

    def _get_highlight_color(self):
        return HIGHLIGHT_COLORS["yellow"][1]
    
    def update_content(self, book=None, chapter=None, preserve_scroll=False, realign_verse=True):
        if (book and book != self.current_book) or (chapter and chapter != self.current_chapter):
            self.selected_verse_anchor = None
            self.selected_verse_focus = None
            if hasattr(self, "selection_bar"):
                self.selection_bar.hide()
        if book: self.current_book = book
        if chapter: self.current_chapter = chapter
        translation = self.translation_combo.currentText()
        if not translation: return
        
        # 스크롤 위치 저장 (하이라이트 업데이트 시 위치 유지)
        scroll_position = None
        visible_verse = None
        if preserve_scroll:
            scroll_position = self.text_browser.verticalScrollBar().value()
            # 현재 보이는 구절 번호도 저장 (더 정확한 복원을 위해).
            # 단, 구절 선택/하이라이트처럼 스크롤이 조금도 움직이면 안 되는 경우엔
            # realign_verse=False 로 호출해서 구절 재정렬을 건너뛴다.
            if realign_verse:
                cursor = self.text_browser.cursorForPosition(QPoint(10, self.text_browser.viewport().height() // 2))
                href = cursor.charFormat().anchorHref()
                if href and href.startswith('#'):
                    try:
                        visible_verse = int(href[1:])
                    except (ValueError, IndexError):
                        pass
        
        try:
            data = self.data_loader.load_translation_data(translation)
            chapter_content = data["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
            apply_text_layout(self.text_browser, data)
        except Exception as e:
            self.text_browser.setHtml(f"<p style='color:red;'>'{html_escape(translation)}' 로드 중 오류 발생:<br>{html_escape(e)}</p>")
            return
        if not chapter_content:
            self.text_browser.setHtml(f"<p>'{html_escape(self.current_book)} {self.current_chapter}장' 데이터를 찾을 수 없습니다.</p>")
            return
        
        html_content, verse_counter = [], 1
        book_abbr = self.data_loader.get_book_abbr(self.current_book, language=data.get('language'))
        text_color_name = QApplication.palette().color(QPalette.ColorRole.Text).name()
        direction = get_text_direction(data)
        text_align = get_text_alignment(data)
        prefix_padding = "padding-left: 5px;" if direction == "rtl" else "padding-right: 5px;"
        
        highlight_color_map = {}
        ai_note_ranges = {}  # 시작절 -> (시작절, 끝절)
        if self.bible_db:
            highlights = self.bible_db.get_highlights(self.current_book, self.current_chapter)
            highlight_color_map = {
                h["verse"]: h.get("color") or self._get_highlight_color()
                for h in highlights
            }
            try:
                for note in self.bible_db.get_ai_notes(self.current_book, self.current_chapter):
                    ai_note_ranges.setdefault(note["start_verse"], (note["start_verse"], note["end_verse"]))
            except Exception:
                ai_note_ranges = {}
        selected_verses = set(self._selected_verse_numbers())

        # 본문 타이포그래피 설정
        bstyle = getattr(self, "body_style", None) or {}
        line_height = bstyle.get("line_height", 1.6)
        verse_spacing = bstyle.get("verse_spacing", 6)
        num_scale = bstyle.get("num_scale", 85)
        num_muted = bstyle.get("num_muted", True)
        subtitle_align = bstyle.get("subtitle_align", "left")
        subtitle_accent = bstyle.get("subtitle_accent", True)
        accent_color = QApplication.palette().color(QPalette.ColorRole.Link).name()
        subtitle_color = accent_color if subtitle_accent else text_color_name
        font_family_css = f"font-family: {SERIF_STACK};" if bstyle.get("font_kind") == "serif" else ""

        # CSS 스타일 추가: 링크와 일반 텍스트의 폰트 굵기를 일치시키기
        html_content.append(
            "<style>"
            "a { font-weight: normal !important; } "
            "td { font-weight: normal !important; } "
            "table { font-weight: normal !important; } "
            f"body {{ direction: {direction}; {font_family_css} }}"
            "</style>"
        )
        
        is_after_subtitle = False

        subtitle_re = re.compile(r'<\s*(.+?)\s*>')
        items = list(chapter_content)
        n_items = len(items)
        idx = 0
        while idx < n_items:
            line = items[idx]
            subtitle_match = subtitle_re.match(line)
            if subtitle_match:
                html_content.append(f"<p style='text-align:{subtitle_align}; font-weight:bold; color:{subtitle_color}; margin-top:22px; margin-bottom:6px;'>{html_escape(subtitle_match.group(1))}</p>")
                is_after_subtitle = True
                idx += 1
                continue

            start_verse = verse_counter
            # 뒤따르는 빈 절(다른 번역본과 번호를 맞추려고 넣은 자리)을 이 절의
            # 번호 범위에 흡수한다. 소제목은 넘지 않는다.
            span = 1
            if line.strip():
                j = idx + 1
                while j < n_items and not subtitle_re.match(items[j]) and items[j].strip() == "":
                    span += 1
                    j += 1
            end_verse = start_verse + span - 1
            num_label = f"{start_verse}" if start_verse == end_verse else f"{start_verse}-{end_verse}"

            safe_book_abbr = html_escape(book_abbr)
            num_color = getattr(self, "_verse_num_color", text_color_name) if num_muted else text_color_name
            num_style = f"color: {num_color}; font-weight: normal; font-size: {num_scale}%;"
            if self.verse_display_mode == 0:
                verse_prefix = f"<span style='{num_style}'>({safe_book_abbr} {self.current_chapter}:{num_label})</span>"
            elif self.verse_display_mode == 1:
                verse_prefix = f"<span style='{num_style}'>{safe_book_abbr} {self.current_chapter}:{num_label}</span>"
            else:
                verse_prefix = f"<span style='{num_style}'>{num_label}.</span>"

            # 저장된 AI 해설이 있는 구절에 작은 표시(클릭 시 그 해설을 다시 연다)
            ai_marker = ""
            note_range = next((ai_note_ranges[v] for v in range(start_verse, end_verse + 1)
                               if v in ai_note_ranges), None)
            if note_range:
                ai_marker = (
                    f"<a href='ai:{note_range[0]}-{note_range[1]}' "
                    f"style='text-decoration:none;' title='저장된 AI 해설 보기'>&nbsp;💬</a>"
                )

            margin_top_style = ""
            if is_after_subtitle:
                margin_top_style = "margin-top: 25px;"
                is_after_subtitle = False

            # 하이라이트/선택 배경색 (범위 내 아무 절이나 해당되면 적용)
            verse_span = range(start_verse, end_verse + 1)
            bg_color_style = ""
            if any(v in selected_verses for v in verse_span):
                bg_color_style = f"background-color: {getattr(self, '_selected_verse_color', SELECTED_VERSE_COLOR)};"
            else:
                hl = next((highlight_color_map[v] for v in verse_span if v in highlight_color_map), None)
                if hl:
                    bg_color_style = f"background-color: {hl};"

            # QTextBrowser(Qt 리치텍스트)는 CSS width:100% / direction 을 무시한다.
            # - 테이블 width 는 HTML 속성으로 준다.
            # - 구절번호 칸은 width="1" + nowrap 으로 내용 크기만큼만 차지하게 한다.
            # - RTL 은 셀 순서를 뒤집고 본문을 오른쪽 정렬한다.
            safe_line = html_escape(line) or "&nbsp;"
            num_cell = (
                f'<td width="1" style="white-space: nowrap; {prefix_padding} vertical-align: top; font-weight: normal; {bg_color_style}">'
                f"<a href='#{start_verse}' style='text-decoration:none; color:{text_color_name}; font-weight: normal !important;'>{verse_prefix}</a>{ai_marker}"
                "</td>"
            )
            align_attr = ' align="right"' if direction == "rtl" else ""
            text_cell = (
                f'<td{align_attr} dir="{direction}" style="vertical-align: top; line-height: {line_height}; font-weight: normal; {bg_color_style}">'
                f"<a href='#{start_verse}' style='text-decoration:none; color:{text_color_name}; font-weight: normal !important;'>{safe_line}</a>"
                "</td>"
            )
            cells = f"{text_cell}{num_cell}" if direction == "rtl" else f"{num_cell}{text_cell}"
            verse_html = (
                f'<table width="100%" border="0" cellspacing="0" cellpadding="0" '
                f'style="border-collapse: collapse; margin-bottom: {verse_spacing}px; font-weight: normal; {margin_top_style}">'
                f"<tr>{cells}</tr></table>"
            )
            html_content.append(verse_html)

            verse_counter += span
            idx += span
                
        # 하이라이트 업데이트 시 깜박임 최소화
        if preserve_scroll and scroll_position is not None:
            # 화면 업데이트를 일시 중지하여 깜박임 방지
            self.text_browser.setUpdatesEnabled(False)
            self.text_browser.setHtml("".join(html_content))
            # 즉시 업데이트 활성화
            self.text_browser.setUpdatesEnabled(True)
        else:
            self.text_browser.setHtml("".join(html_content))
        
        # 스크롤 위치 복원
        if preserve_scroll and scroll_position is not None and not realign_verse:
            # 선택/하이라이트 재렌더: 본문 높이가 사실상 동일하므로 재정렬 없이
            # 정확히 같은 스크롤 위치로 즉시 복원한다. (retry/QTimer 없이)
            scrollbar = self.text_browser.verticalScrollBar()
            scrollbar.setValue(scroll_position)
            QTimer.singleShot(0, lambda pos=scroll_position: scrollbar.setValue(pos))
            return

        if preserve_scroll and scroll_position is not None:
            # QTimer를 사용하여 HTML 렌더링 완료 후 스크롤 위치 복원
            # 여러 번 시도하여 확실하게 복원
            attempt_count = [0]
            max_attempts = 10
            
            def restore_scroll():
                attempt_count[0] += 1
                scrollbar = self.text_browser.verticalScrollBar()
                
                # 최대값이 설정되었는지 확인 (렌더링 완료 여부)
                if scrollbar.maximum() > 0:
                    # 저장된 위치로 복원
                    if scrollbar.maximum() >= scroll_position:
                        scrollbar.setValue(scroll_position)
                        # 보이는 구절 번호로도 복원 시도 (더 정확함)
                        if visible_verse:
                            QTimer.singleShot(5, lambda: self.scroll_to_verse(visible_verse))
                    elif attempt_count[0] < max_attempts:
                        # 아직 렌더링 중이면 다시 시도
                        QTimer.singleShot(50, restore_scroll)
                elif attempt_count[0] < max_attempts:
                    # 최대값이 아직 설정되지 않았으면 다시 시도
                    QTimer.singleShot(50, restore_scroll)
            
            # 더 빠르게 복원 시도
            QTimer.singleShot(1, restore_scroll)

    def _get_formatted_selection(self):
        text_cursor = self.text_browser.textCursor()
        if not text_cursor.hasSelection():
            return None, None
            
        raw_text = text_cursor.selection().toPlainText()
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]

        final_lines = []
        i = 0
        while i < len(lines):
            current_line = lines[i]
            m1 = re.match(r'^\(?\s*[가-힣A-Za-z]+\s*\d+:(\d+)\s*\)?', current_line)
            m2 = re.match(r'^\s*(\d+)\.', current_line)
            is_only_a_ref = (m1 or m2) and len(current_line) < 35

            if is_only_a_ref and i + 1 < len(lines):
                next_line = lines[i+1]
                nm1 = re.match(r'^\(?\s*[가-힣A-Za-z]+\s*\d+:(\d+)\s*\)?', next_line)
                nm2 = re.match(r'^\s*(\d+)\.', next_line)
                if not (nm1 or nm2):
                    merged_line = current_line + " " + next_line
                    final_lines.append(merged_line)
                    i += 2
                    continue
            final_lines.append(current_line)
            i += 1
        
        final_processed_lines = [re.sub(r'\s+', ' ', line) for line in final_lines]
        text_to_send = '\n'.join(final_processed_lines)

        def get_verse_num_from_line(line_text):
            m1 = re.match(r'^\(?\s*[가-힣A-Za-z]+\s*\d+:(\d+)\s*\)?', line_text)
            if m1: return m1.group(1)
            m2 = re.match(r'^\s*(\d+)\.', line_text)
            if m2: return m2.group(1)
            return None

        range_str = ""
        if final_processed_lines:
            first_verse = get_verse_num_from_line(final_processed_lines[0])
            last_verse = get_verse_num_from_line(final_processed_lines[-1]) if len(final_processed_lines) > 1 else first_verse
            book_abbr = self.data_loader.get_book_abbr(
                self.current_book, translation_name=self.translation_combo.currentText())
            if first_verse:
                if not last_verse or first_verse == last_verse:
                    range_str = f"{book_abbr} {self.current_chapter}:{first_verse}"
                else:
                    range_str = f"{book_abbr} {self.current_chapter}:{first_verse}-{last_verse}"
        
        return text_to_send, range_str
    
    def _extract_verse_numbers_from_selection(self):
        """선택된 텍스트에서 구절 번호들을 추출하여 범위 반환"""
        cursor = self.text_browser.textCursor()
        if not cursor.hasSelection():
            return []
        
        # 선택 범위의 시작과 끝 위치
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        
        # 선택 범위 내의 모든 블록을 순회하며 구절 번호 추출
        verse_numbers = set()
        
        # 시작 블록부터 끝 블록까지 순회
        start_block = self.text_browser.document().findBlock(selection_start)
        end_block = self.text_browser.document().findBlock(selection_end)
        
        current_block = start_block
        while current_block.isValid():
            # 블록 내의 각 문자를 확인하여 HTML 앵커 링크 찾기
            block_start = current_block.position()
            block_end = block_start + current_block.length()
            
            # 선택 범위와 블록의 교집합 확인
            check_start = max(selection_start, block_start)
            check_end = min(selection_end, block_end)
            
            if check_start < check_end:
                # 블록 내의 선택된 부분에서 구절 번호 찾기
                # 여러 위치를 샘플링하여 앵커 링크 확인
                check_positions = [check_start, (check_start + check_end) // 2, check_end - 1]
                
                for pos in check_positions:
                    if pos < block_end:
                        test_cursor = QTextCursor(self.text_browser.document())
                        test_cursor.setPosition(pos)
                        char_format = test_cursor.charFormat()
                        href = char_format.anchorHref()
                        if href and href.startswith('#'):
                            try:
                                verse_num = int(href[1:])
                                verse_numbers.add(verse_num)
                            except (ValueError, IndexError):
                                pass
            
            # 마지막 블록에 도달하면 종료
            if current_block == end_block:
                break
            current_block = current_block.next()
        
        # 앵커에서 찾지 못한 경우, 선택된 텍스트에서 패턴으로 찾기
        if not verse_numbers:
            selected_text = cursor.selection().toPlainText()
            lines = [line.strip() for line in selected_text.split('\n') if line.strip()]
            
            def get_verse_num_from_line(line_text):
                """라인에서 구절 번호 추출"""
                # 패턴 1: (창 1:1) 또는 (1:1)
                match1 = re.search(r'\([가-힣A-Za-z]+\s*\d+:(\d+)\)|\(\d+:(\d+)\)', line_text)
                if match1:
                    return int(match1.group(1) or match1.group(2))
                # 패턴 2: 창 1:1 또는 1:1
                match2 = re.search(r'[가-힣A-Za-z]+\s*\d+:(\d+)|^\s*(\d+):(\d+)', line_text)
                if match2:
                    return int(match2.group(1) or match2.group(3))
                # 패턴 3: 1. (절 번호만)
                match3 = re.match(r'^\s*(\d+)\.', line_text)
                if match3:
                    return int(match3.group(1))
                return None
            
            for line in lines:
                verse_num = get_verse_num_from_line(line)
                if verse_num:
                    verse_numbers.add(verse_num)
        
        # 구절 번호가 여러 개인 경우, 범위로 확장
        if len(verse_numbers) > 0:
            sorted_verses = sorted(verse_numbers)
            # 시작과 끝 구절 사이의 모든 구절 포함
            if len(sorted_verses) >= 2:
                start_verse = sorted_verses[0]
                end_verse = sorted_verses[-1]
                return list(range(start_verse, end_verse + 1))
            else:
                return sorted_verses
        
        return []

    def show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        
        if self.menu_stylesheet:
            menu.setStyleSheet(self.menu_stylesheet)
            
        pos_cursor = self.text_browser.cursorForPosition(pos)
        
        verse_num = None
        href = pos_cursor.charFormat().anchorHref()
        if href and href.startswith('#'):
            try:
                verse_num = int(href[1:])
            except (ValueError, IndexError):
                verse_num = None
                
        position_actions_added = False
        if verse_num:
            self.current_verse_for_context = verse_num
            c_action = menu.addAction("이 절 주석 보기")
            cr_action = menu.addAction("이 절 관주 보기")
            
            menu.addSeparator()
            compare_action = menu.addAction("번역본 비교")
            compare_action.triggered.connect(self.open_comparison_view)

            ai_action = menu.addAction("이 절 AI 해설")
            ai_action.triggered.connect(lambda: self.emit_ai_explanation_for([verse_num]))

            if self.context == 'commentary': c_action.setEnabled(False)
            elif self.context == 'crossref': cr_action.setEnabled(False)
            c_action.triggered.connect(lambda: self.request_commentary.emit(self.current_book, self.current_chapter, self.current_verse_for_context))
            cr_action.triggered.connect(lambda: self.request_cross_ref.emit(self.current_book, self.current_chapter, self.current_verse_for_context))
            
            # 하이라이트 토글 메뉴 추가
            if self.bible_db:
                menu.addSeparator()
                is_highlighted = self.bible_db.is_highlighted(self.current_book, self.current_chapter, verse_num)
                highlight_action = menu.addAction("하이라이트 제거" if is_highlighted else "하이라이트 추가")
                highlight_action.triggered.connect(lambda: self.toggle_highlight(verse_num))
            
            position_actions_added = True
        
        if position_actions_added: menu.addSeparator()

        text_to_send, range_str = self._get_formatted_selection()
        has_selection = text_to_send is not None
        
        # 선택 범위 하이라이트 기능
        selected_verses = []
        if has_selection and self.bible_db:
            selected_verses = self._extract_verse_numbers_from_selection()
            if selected_verses:
                menu.addSeparator()
                # 선택된 구절 중 하이라이트된 것과 안 된 것 확인
                highlighted_count = sum(1 for v in selected_verses if self.bible_db.is_highlighted(self.current_book, self.current_chapter, v))
                all_highlighted = highlighted_count == len(selected_verses)
                some_highlighted = highlighted_count > 0 and highlighted_count < len(selected_verses)
                
                if all_highlighted:
                    range_highlight_action = menu.addAction(f"선택 범위 하이라이트 제거 ({len(selected_verses)}개 구절)")
                elif some_highlighted:
                    range_highlight_action = menu.addAction(f"선택 범위 하이라이트 추가 ({len(selected_verses)}개 구절, {highlighted_count}개 이미 하이라이트됨)")
                else:
                    range_highlight_action = menu.addAction(f"선택 범위 하이라이트 추가 ({len(selected_verses)}개 구절)")
                
                range_highlight_action.triggered.connect(lambda: self.toggle_highlight_range(selected_verses))
                ai_range_action = menu.addAction(f"선택 범위 AI 해설 ({len(selected_verses)}개 구절)")
                ai_range_action.triggered.connect(lambda: self.emit_ai_explanation_for(selected_verses))
                menu.addSeparator()
        
        copy_action = menu.addAction("복사하기 (Ctrl+C)")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.text_browser.custom_copy)
        menu.addSeparator()
        
        s_action = menu.addAction("검색")
        word_action = menu.addAction("MS Word로 보내기 (Ctrl+W)")
        ppt_action = menu.addAction("MS PowerPoint로 보내기 (Ctrl+P)")

        s_action.setEnabled(has_selection)
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)

        if has_selection:
            selected_text_for_search = self.text_browser.textCursor().selectedText()
            s_action.triggered.connect(lambda: self.request_search.emit(selected_text_for_search, self.translation_combo.currentText()))
            word_action.triggered.connect(self.trigger_send_to_word)
            ppt_action.triggered.connect(self.trigger_send_to_powerpoint)
            
        menu.exec(self.text_browser.mapToGlobal(pos))
    
    @Slot()
    def open_comparison_view(self, start_verse=None, end_verse=None):
        from comparison_view import ComparisonDialog
        
        verse_to_open = start_verse or getattr(self, 'current_verse_for_context', None)
        if not verse_to_open:
            return

        main_window = self.window()
        stylesheet = ""
        comparison_font_size = 12 
        if hasattr(main_window, 'comparison_font_size'):
            comparison_font_size = main_window.comparison_font_size
            
        if hasattr(main_window, 'current_toolbar_stylesheet'):
            stylesheet = main_window.current_toolbar_stylesheet

        dialog = ComparisonDialog(
            self.data_loader,
            self.current_book,
            self.current_chapter,
            verse_to_open,
            self,
            stylesheet=stylesheet,
            font_family=self.font_family,
            font_size=comparison_font_size,
            end_verse=end_verse or verse_to_open,
        )
        
        if hasattr(main_window, 'on_comparison_font_size_changed'):
            dialog.font_size_changed.connect(main_window.on_comparison_font_size_changed)
            
        dialog.exec()

    @Slot()
    def trigger_send_to_word(self):
        text_to_send, _ = self._get_formatted_selection()
        if not text_to_send:
            text_to_send, _ = self._build_selected_verse_text()
        if text_to_send:
            self.request_send_to_word.emit(text_to_send)

    @Slot()
    def trigger_send_to_powerpoint(self):
        text_to_send, _ = self._get_formatted_selection()
        if not text_to_send:
            text_to_send, _ = self._build_selected_verse_text()
        if text_to_send:
            self.request_send_to_powerpoint.emit(self, text_to_send)
    
    def toggle_highlight(self, verse_num: int):
        """하이라이트 토글"""
        if not self.bible_db:
            return
        
        highlight_color = self._get_highlight_color()
        self.bible_db.toggle_highlight(self.current_book, self.current_chapter, verse_num, highlight_color)
        # 화면 갱신 (스크롤 위치 정확히 유지 - 구절 재정렬 안 함)
        self.update_content(preserve_scroll=True, realign_verse=False)
        self.highlight_changed.emit()
    
    def toggle_highlight_range(self, verse_numbers: list):
        """여러 구절을 한꺼번에 하이라이트 토글"""
        if not self.bible_db or not verse_numbers:
            return
        
        highlight_color = self._get_highlight_color()
        
        # 선택된 구절들의 하이라이트 상태 확인
        highlighted_verses = [v for v in verse_numbers if self.bible_db.is_highlighted(self.current_book, self.current_chapter, v)]
        all_highlighted = len(highlighted_verses) == len(verse_numbers)
        
        if all_highlighted:
            # 모두 하이라이트되어 있으면 모두 제거
            for verse_num in verse_numbers:
                self.bible_db.remove_highlight(self.current_book, self.current_chapter, verse_num)
        else:
            # 일부 또는 모두 하이라이트되지 않았으면 모두 추가
            for verse_num in verse_numbers:
                self.bible_db.add_highlight(self.current_book, self.current_chapter, verse_num, highlight_color)
        
        # 화면 갱신 (스크롤 위치 정확히 유지 - 구절 재정렬 안 함)
        self.update_content(preserve_scroll=True, realign_verse=False)
        self.highlight_changed.emit()

    @Slot(int)
    def scroll_to_verse(self, verse_num):
        if verse_num == 1:
            translation = self.translation_combo.currentText()
            if translation:
                try:
                    chapter_content = self.data_loader.load_translation_data(translation)["bible_data"].get(self.current_book, {}).get(str(self.current_chapter), [])
                    if chapter_content and re.match(r'<\s*(.+?)\s*>', chapter_content[0]):
                        self.text_browser.moveCursor(QTextCursor.MoveOperation.Start)
                        self.text_browser.ensureCursorVisible()
                        return
                except Exception as e:
                    print(f"소제목 확인 중 오류 발생: {e}")

        book_abbr = self.data_loader.get_book_abbr(
            self.current_book, translation_name=self.translation_combo.currentText())

        prefix_to_find = ""
        if self.verse_display_mode == 0:
            prefix_to_find = f"({book_abbr} {self.current_chapter}:{verse_num})"
        elif self.verse_display_mode == 1:
            prefix_to_find = f"{book_abbr} {self.current_chapter}:{verse_num}"
        elif self.verse_display_mode == 2:
            prefix_to_find = f"{verse_num}."
        
        if not prefix_to_find:
            return

        self.text_browser.moveCursor(QTextCursor.MoveOperation.Start)
        if self.text_browser.find(prefix_to_find):
            self.text_browser.ensureCursorVisible()
            cursor_rect = self.text_browser.cursorRect()
            scrollbar = self.text_browser.verticalScrollBar()
            scrollbar.setValue(scrollbar.value() + cursor_rect.top())
            # find() 가 남기는 선택 음영을 제거한다 (구절 표시에 회색 배경이 남는 문제)
            cursor = self.text_browser.textCursor()
            cursor.setPosition(cursor.selectionStart())
            self.text_browser.setTextCursor(cursor)
        else:
            print(f"경고: 스크롤할 구절의 접두사 '{prefix_to_find}'를 찾지 못했습니다.")
