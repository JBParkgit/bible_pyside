from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from html_utils import html_attr_escape, html_escape, PlainCopyTextBrowser


class OriginalLanguageTab(QWidget):
    request_navigation = Signal(str, int, int)

    def __init__(self, data_loader, parent=None):
        super().__init__(parent)
        self.data_loader = data_loader
        self.current_book = None
        self.current_chapter = None
        self.current_verse = None
        # 파란색 배경(하이라이트)은 특정 구절을 선택해 원어 보기를 했을 때만 표시한다.
        self.highlight_verse = False
        self.current_chapter_data = None
        self.theme_mode = "light"
        self.init_ui()
        self.connect_signals()

    def set_theme_mode(self, mode):
        self.theme_mode = "dark" if mode == "dark" else "light"
        try:
            self.render_content()
        except Exception:
            pass

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.location_label = QLabel("원어")
        self.location_label.setObjectName("originalLocationLabel")

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("KJV 원어", "kjv")
        self.mode_combo.addItem("개역한글 원어", "hrv")

        toolbar_layout.addWidget(self.location_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.mode_combo)
        layout.addWidget(toolbar)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)

        self.content_browser = PlainCopyTextBrowser()
        self.content_browser.setOpenLinks(False)
        self.content_browser.setOpenExternalLinks(False)

        self.detail_browser = PlainCopyTextBrowser()
        self.detail_browser.setOpenExternalLinks(False)

        splitter.addWidget(self.content_browser)
        splitter.addWidget(self.detail_browser)
        splitter.setSizes([700, 320])
        layout.addWidget(splitter, 1)

    def connect_signals(self):
        self.mode_combo.currentIndexChanged.connect(self.render_content)
        self.content_browser.anchorClicked.connect(self.handle_anchor_clicked)
        self.detail_browser.anchorClicked.connect(self.handle_anchor_clicked)

    def update_all_content(self, book, chapter, current_verse=None, highlight=False):
        same_location = (book == self.current_book and chapter == self.current_chapter)
        self.current_book = book
        self.current_chapter = chapter
        self.current_verse = current_verse
        # 파란 배경 강조는 액션바 '원어' 버튼이나 구절 번호 클릭처럼 구절을 명시적으로
        # 골랐을 때만. 장이 바뀌면 해제하고, 같은 장을 다시 그리는 경우(내비게이션
        # 연쇄 등)에는 기존 강조 상태를 유지한다.
        if highlight and current_verse is not None:
            self.highlight_verse = True
        elif not same_location:
            self.highlight_verse = False
        self.location_label.setText(f"{book} {chapter}장")
        self.current_chapter_data = self.data_loader.get_chapter(book, chapter)
        self.render_content()

    def render_content(self):
        if not self.current_book or not self.current_chapter:
            self.content_browser.setHtml("<p>구절을 선택하면 원어 정보가 표시됩니다.</p>")
            return

        if not self.data_loader.is_available():
            self.content_browser.setHtml("<p>원어 데이터가 없습니다. strongs 폴더를 확인하세요.</p>")
            return

        if not self.current_chapter_data:
            self.content_browser.setHtml("<p>이 장의 원어 데이터를 찾을 수 없습니다.</p>")
            return

        mode = self.mode_combo.currentData()
        dark = getattr(self, "theme_mode", "light") == "dark"
        c_border = "#3d3d3d" if dark else "#d0d7de"
        c_current = "#2a4b6b" if dark else "#dbeafe"
        c_link = "#5CB2FF" if dark else "#0969da"
        c_muted = "#9aa7b4" if dark else "#57606a"
        html = [
            "<html><head><style>",
            "body { font-family: 'Malgun Gothic', Arial, sans-serif; font-size: 15px; line-height: 1.6; }",
            f".verse {{ border-bottom: 1px solid {c_border}; padding: 12px 4px; }}",
            f".verse.current {{ background-color: {c_current}; }}",
            f".verse-number {{ font-weight: 700; color: {c_link}; text-decoration: none; margin-right: 6px; }}",
            ".source-text { font-size: 16px; margin: 4px 0 10px 0; }",
            ".tokens { margin-top: 6px; line-height: 2.0; }",
            ".token-word { font-size: 18px; }",
            f".token-code {{ font-size: 12px; text-decoration: none; color: {c_link}; }}",
            f".token-gloss {{ font-size: 12px; color: {c_muted}; }}",
            "</style></head><body>",
        ]

        for verse in self.current_chapter_data["verses"]:
            number = verse["number"]
            css_class = "verse current" if (self.highlight_verse and self.current_verse == number) else "verse"
            source_text = verse["kjvText"] if mode == "kjv" else verse["hrvText"]
            html.append(f"<div class='{css_class}' id='v{number}'>")
            html.append(
                f"<div class='source-text'>"
                f"<a class='verse-number' href='verse:{number}'>{number}.</a>"
                f"{html_escape(source_text)}</div>"
            )
            html.append(self.render_original_tokens(verse))
            html.append("</div>")

        html.append("</body></html>")
        self.content_browser.setHtml("".join(html))
        if self.highlight_verse and self.current_verse:
            QTimer.singleShot(0, lambda: self.content_browser.scrollToAnchor(f"v{self.current_verse}"))

    def render_original_tokens(self, verse):
        direction = "rtl" if verse.get("originalDirection") == "rtl" else "ltr"
        align = "right" if direction == "rtl" else "left"

        # QTextBrowser 는 inline-block/flex 를 지원하지 않아 토큰마다 <br> 를 넣으면
        # 단어별로 세로로 길게 늘어난다. 원어 단어 + (스트롱번호 뜻) 을 한 덩어리로
        # 인라인 배치하고 토큰 사이 간격만 벌려 자연스럽게 줄바꿈되도록 한다.
        rendered = []
        for token in verse.get("originalTokens", []):
            token_text = html_escape(token.get("text", ""))
            if not token_text:
                continue
            codes = token.get("strongs", []) or []
            code_links = " ".join(
                f"<a class='token-code' href='strong:{html_attr_escape(code)}'>{html_escape(code)}</a>"
                for code in codes
            )
            gloss = self.get_token_gloss(codes)
            piece = [f"<span class='token-word'>{token_text}</span>"]
            meta = []
            if code_links:
                meta.append(code_links)
            if gloss:
                meta.append(f"<span class='token-gloss'>{html_escape(gloss)}</span>")
            if meta:
                piece.append(" <span class='token-code'>[</span>" + " ".join(meta) + "<span class='token-code'>]</span>")
            rendered.append("<span class='token'>" + "".join(piece) + "</span>")

        if not rendered:
            return ""

        body = "&nbsp;&nbsp; ".join(rendered)
        return (
            f"<div class='tokens' dir='{direction}' "
            f"style='direction:{direction}; text-align:{align};'>{body}</div>"
        )

    def get_token_gloss(self, codes):
        glosses = []
        for code in codes or []:
            entry = self.data_loader.get_lexicon_entry(code)
            if not entry:
                continue
            gloss = entry.get("glossKo") or entry.get("gloss") or entry.get("transliterationKo") or entry.get("transliteration")
            if gloss and gloss not in glosses:
                glosses.append(gloss)
        return ", ".join(glosses)

    def handle_anchor_clicked(self, url: QUrl):
        scheme = url.scheme()
        target = url.path() or url.toString().split(":", 1)[-1]
        if scheme == "strong":
            self.show_strong_detail(target)
            return
        if scheme == "verse":
            try:
                verse = int(target)
            except ValueError:
                return
            self.current_verse = verse
            self.highlight_verse = True
            self.render_content()
            self.request_navigation.emit(self.current_book, self.current_chapter, verse)

    def show_strong_detail(self, code):
        entry = self.data_loader.get_lexicon_entry(code)
        if not entry:
            self.detail_browser.setHtml(f"<p>{html_escape(code)} 항목을 찾을 수 없습니다.</p>")
            return

        usage = self.data_loader.get_strong_usage(code)
        original = entry.get("original", "")
        original_dir = "rtl" if entry.get("language") == "Hebrew" else "ltr"
        usage_items = usage["items"][:200]

        dark = getattr(self, "theme_mode", "light") == "dark"
        c_border = "#3d3d3d" if dark else "#d0d7de"
        c_link = "#5CB2FF" if dark else "#0969da"
        c_muted = "#9aa7b4" if dark else "#57606a"
        html = [
            "<html><head><style>",
            "body { font-family: 'Malgun Gothic', Arial, sans-serif; line-height: 1.55; }",
            "h2 { margin: 0 0 8px 0; }",
            f".code {{ color: {c_link}; font-weight: 700; }}",
            ".original { font-size: 28px; margin: 8px 0; }",
            f".label {{ color: {c_muted}; font-size: 12px; margin-top: 12px; }}",
            f".usage {{ margin: 8px 0; padding-bottom: 8px; border-bottom: 1px solid {c_border}; }}",
            "</style></head><body>",
            f"<h2><span class='code'>{html_escape(code)}</span></h2>",
            f"<div class='original' dir='{original_dir}'>{html_escape(original)}</div>",
        ]

        for label, key in [
            ("한글 음역", "transliterationKo"),
            ("음역", "transliteration"),
            ("한글 뜻", "glossKo"),
            ("뜻", "gloss"),
            ("한글 설명", "definitionKo"),
            ("설명", "definition"),
            ("형태", "morphology"),
            ("출처", "source"),
        ]:
            value = entry.get(key)
            if value:
                html.append(f"<div class='label'>{label}</div><div>{html_escape(value)}</div>")

        html.append(f"<div class='label'>사용 구절</div><div>총 {usage['total']}회</div>")
        for item in usage_items:
            ref = f"{item['book']} {item['chapter']}:{item['verse']}"
            html.append(
                "<div class='usage'>"
                f"<span>{html_escape(ref)}</span> "
                f"<span>({item['count']}회)</span><br>"
                f"{html_escape(item['text'])}"
                "</div>"
            )
        if len(usage["items"]) > len(usage_items):
            html.append(f"<p>{len(usage['items']) - len(usage_items)}개 구절은 생략했습니다.</p>")

        html.append("</body></html>")
        self.detail_browser.setHtml("".join(html))
