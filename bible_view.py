# bible_view.py
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QComboBox, QLabel, QPushButton, QFrame, QApplication, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QPoint, QSize, QTimer
from PySide6.QtGui import QFont, QTextOption, QPalette, QTextCursor, QKeySequence, QKeyEvent, QIcon

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
    request_add_to_collection = Signal(object, str, str)
    request_send_to_word = Signal(str)
    request_send_to_powerpoint = Signal(object, str)

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
        if initial_settings is None: initial_settings = {}
        self.verse_display_mode = initial_settings.get('verse_display_mode', 0)
        self.font_size = initial_settings.get('bible_font_size', 14)
        self.font_family = initial_settings.get('font_family', 'Malgun Gothic')
        
        self.menu_stylesheet = ""
        
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
        control_bar_layout = QHBoxLayout(control_bar)
        control_bar_layout.setContentsMargins(2, 2, 2, 2)
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
        
        palette = self.text_browser.palette()
        palette.setColor(QPalette.Base, QApplication.palette().color(QPalette.Base))
        self.text_browser.setPalette(palette)
        
        layout.addWidget(control_bar)
        layout.addWidget(self.text_browser)

    def connect_signals(self):
        self.translation_combo.currentTextChanged.connect(self.on_translation_changed)
        self.text_browser.verticalScrollBar().valueChanged.connect(self.scroll_changed.emit)
        self.text_browser.customContextMenuRequested.connect(self.show_context_menu)
        self.text_browser.anchorClicked.connect(self.verse_anchor_clicked.emit)
        self.text_browser.selectionChanged.connect(self.update_action_buttons_state)
        self.send_to_word_button.clicked.connect(self.trigger_send_to_word)
        self.send_to_ppt_button.clicked.connect(self.trigger_send_to_powerpoint)

    @Slot()
    def update_action_buttons_state(self):
        has_selection = self.text_browser.textCursor().hasSelection()
        self.send_to_word_button.setEnabled(has_selection)
        self.send_to_ppt_button.setEnabled(has_selection)

    def set_menu_stylesheet(self, stylesheet):
        self.menu_stylesheet = stylesheet

    def set_font_family(self, font_name):
        self.font_family = font_name
        self.text_browser.setFont(QFont(self.font_family, self.font_size))

    @Slot(int)
    def set_font_size(self, size):
        if self.font_size == size: return
        self.font_size = max(8, size)
        self.text_browser.setFont(QFont(self.font_family, self.font_size))
        self.update_content()

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

    def update_theme(self):
        palette = self.text_browser.palette()
        palette.setColor(QPalette.Base, QApplication.palette().color(QPalette.Base))
        self.text_browser.setPalette(palette)

    def _get_highlight_color(self):
        """테마에 맞는 하이라이트 색상 반환"""
        if not self.bible_db:
            return '#fff9c4'
        
        # MainWindow에서 현재 테마 확인
        main_window = self.window()
        if hasattr(main_window, '_settings'):
            theme = main_window._settings.get('theme', 'Dark')
        else:
            theme = 'Dark'
        
        # 테마별 하이라이트 색상
        theme_colors = {
            'Light': '#fff9c4',    # 연한 노란색
            'Dark': '#8b6914',     # 어두운 노란색
            'Sepia': '#d4c5a9',    # 세피아 톤
            'Gray': '#6a6a6a'       # 회색 계열
        }
        return theme_colors.get(theme, '#fff9c4')
    
    def update_content(self, book=None, chapter=None, preserve_scroll=False):
        if book: self.current_book = book
        if chapter: self.current_chapter = chapter
        translation = self.translation_combo.currentText()
        if not translation: return
        
        # 스크롤 위치 저장 (하이라이트 업데이트 시 위치 유지)
        scroll_position = None
        if preserve_scroll:
            scroll_position = self.text_browser.verticalScrollBar().value()
            # 현재 보이는 구절 번호도 저장 (더 정확한 복원을 위해)
            cursor = self.text_browser.cursorForPosition(QPoint(10, self.text_browser.viewport().height() // 2))
            href = cursor.charFormat().anchorHref()
            visible_verse = None
            if href and href.startswith('#'):
                try:
                    visible_verse = int(href[1:])
                except (ValueError, IndexError):
                    pass
        
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
        
        # 하이라이트된 구절 목록 가져오기
        highlighted_verses = set()
        if self.bible_db:
            highlights = self.bible_db.get_highlights(self.current_book, self.current_chapter)
            highlighted_verses = {h['verse'] for h in highlights}
        
        highlight_color = self._get_highlight_color()
        
        # CSS 스타일 추가: 링크와 일반 텍스트의 폰트 굵기를 일치시키기
        html_content.append(f"<style>a {{ font-weight: normal !important; }} td {{ font-weight: normal !important; }} table {{ font-weight: normal !important; }}</style>")
        
        is_after_subtitle = False

        for line in chapter_content:
            subtitle_match = re.match(r'<\s*(.+?)\s*>', line)
            if subtitle_match:
                html_content.append(f"<p style='text-align:center; font-weight:bold; color:{text_color_name}; margin-top:15px; margin-bottom:10px;'>{subtitle_match.group(1)}</p>")
                is_after_subtitle = True
            else:
                verse_prefix = ""
                if self.verse_display_mode == 0: verse_prefix = f"<span style='color: {text_color_name}; font-weight: normal;'>({book_abbr} {self.current_chapter}:{verse_counter})</span>"
                elif self.verse_display_mode == 1: verse_prefix = f"<span style='color: {text_color_name}; font-weight: normal;'>{book_abbr} {self.current_chapter}:{verse_counter}</span>"
                elif self.verse_display_mode == 2: verse_prefix = f"<span style='color: {text_color_name}; font-weight: normal;'>{verse_counter}.</span>"
                
                margin_top_style = ""
                if is_after_subtitle:
                    margin_top_style = "margin-top: 25px;"
                    is_after_subtitle = False
                
                # 하이라이트 배경색 적용
                bg_color_style = ""
                if verse_counter in highlighted_verses:
                    bg_color_style = f"background-color: {highlight_color};"
                
                # <<< 수정됨: 하이라이트 배경색 추가
                verse_html = f"""
                <table style="border-collapse: collapse; margin-bottom: 8px; font-weight: normal; {margin_top_style}">
                    <tr>
                        <td style="width: 1px; white-space: nowrap; padding-right: 5px; vertical-align: top; font-weight: normal; {bg_color_style}">
                            <a href='#{verse_counter}' style='text-decoration:none; color:{text_color_name}; font-weight: normal !important;'>{verse_prefix}</a>
                        </td>
                        <td style="vertical-align: top; line-height: 1.2; font-weight: normal; {bg_color_style}">
                            <a href='#{verse_counter}' style='text-decoration:none; color:{text_color_name}; font-weight: normal !important;'>{line}</a>
                        </td>
                    </tr>
                </table>
                """
                # --- 수정 끝
                html_content.append(verse_html)
                
                verse_counter += 1
                
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
            book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, "")
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
                menu.addSeparator()
        
        copy_action = menu.addAction("복사하기 (Ctrl+C)")
        copy_action.setEnabled(has_selection)
        if has_selection:
            copy_action.triggered.connect(self.text_browser.custom_copy)
        menu.addSeparator()
        
        s_action = menu.addAction("검색")
        col_action = menu.addAction("편집으로 보내기 (Ctrl+L)")
        word_action = menu.addAction("MS Word로 보내기 (Ctrl+W)")
        ppt_action = menu.addAction("MS PowerPoint로 보내기 (Ctrl+P)")
        
        s_action.setEnabled(has_selection)
        col_action.setEnabled(has_selection)
        word_action.setEnabled(has_selection)
        ppt_action.setEnabled(has_selection)
        
        if has_selection:
            selected_text_for_search = self.text_browser.textCursor().selectedText()
            s_action.triggered.connect(lambda: self.request_search.emit(selected_text_for_search, self.translation_combo.currentText()))
            col_action.triggered.connect(self.trigger_add_to_collection)
            word_action.triggered.connect(self.trigger_send_to_word)
            ppt_action.triggered.connect(self.trigger_send_to_powerpoint)
            
        menu.exec(self.text_browser.mapToGlobal(pos))
    
    @Slot()
    def open_comparison_view(self):
        from comparison_view import ComparisonDialog
        
        if not hasattr(self, 'current_verse_for_context') or not self.current_verse_for_context:
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
            self.current_verse_for_context,
            self,
            stylesheet=stylesheet,
            font_family=self.font_family,
            font_size=comparison_font_size 
        )
        
        if hasattr(main_window, 'on_comparison_font_size_changed'):
            dialog.font_size_changed.connect(main_window.on_comparison_font_size_changed)
            
        dialog.exec()

    @Slot()
    def trigger_add_to_collection(self):
        text_to_send, range_str = self._get_formatted_selection()
        if text_to_send:
            self.request_add_to_collection.emit(self, text_to_send, range_str)

    @Slot()
    def trigger_send_to_word(self):
        text_to_send, _ = self._get_formatted_selection()
        if text_to_send:
            self.request_send_to_word.emit(text_to_send)

    @Slot()
    def trigger_send_to_powerpoint(self):
        text_to_send, _ = self._get_formatted_selection()
        if text_to_send:
            self.request_send_to_powerpoint.emit(self, text_to_send)
    
    def toggle_highlight(self, verse_num: int):
        """하이라이트 토글"""
        if not self.bible_db:
            return
        
        highlight_color = self._get_highlight_color()
        self.bible_db.toggle_highlight(self.current_book, self.current_chapter, verse_num, highlight_color)
        # 화면 갱신 (스크롤 위치 유지)
        self.update_content(preserve_scroll=True)
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
        
        # 화면 갱신 (스크롤 위치 유지)
        self.update_content(preserve_scroll=True)
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

        book_abbr = self.data_loader.full_name_to_abbr_map.get(self.current_book, "")
        
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
        else:
            print(f"경고: 스크롤할 구절의 접두사 '{prefix_to_find}'를 찾지 못했습니다.")