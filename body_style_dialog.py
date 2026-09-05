# body_style_dialog.py
"""본문 및 글꼴 설정 창 (글꼴 + 본문 타이포그래피, 실시간 미리보기 + 저장).

기존의 '폰트 및 글자 크기 설정'과 '본문 보기 설정'을 하나로 합친 창.
글자 크기는 두 가지로 단순화했다: 성경 본문 / 주석·관주.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QFontComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QLabel, QTextBrowser, QGroupBox
)
from PySide6.QtGui import QFont

from body_style import DEFAULT_BODY_STYLE, body_style_from_settings
from html_utils import PlainCopyTextBrowser
from html_utils import html_escape


SAMPLE_VERSES = [
    {"kind": "subtitle", "text": "천지 창조"},
    {"kind": "verse", "num": 1, "text": "태초에 하나님이 천지를 창조하시니라"},
    {"kind": "verse", "num": 2, "text": "땅이 혼돈하고 공허하며 흑암이 깊음 위에 있고 하나님의 영은 수면 위에 운행하시니라"},
    {"kind": "verse", "num": 3, "text": "하나님이 이르시되 빛이 있으라 하시니 빛이 있었고"},
    {"kind": "verse", "num": 4, "text": "빛이 하나님이 보시기에 좋았더라 하나님이 빛과 어둠을 나누사"},
    {"kind": "verse", "num": 5, "text": "하나님이 빛을 낮이라 부르시고 어둠을 밤이라 부르시니라 저녁이 되고 아침이 되니 이는 첫째 날이니라"},
]


def render_body_html(style, verses, colors, font_family, base_font_size=14):
    """body_style + 표본 구절 -> 미리보기 HTML (bible_view.update_content 규칙 축약)."""
    text_c = colors["text"]
    num_c = colors["muted"] if style["num_muted"] else text_c
    sub_c = colors["accent"] if style["subtitle_accent"] else text_c
    lh = style["line_height"]
    vs = style["verse_spacing"]
    # Qt 리치텍스트는 중첩 <span> 의 백분율 font-size 를 반영하지 않으므로 pt 로 환산
    num_pt = max(6, round(base_font_size * style["num_scale"] / 100.0, 1))
    sub_align = style["subtitle_align"]
    fam = html_escape(font_family)

    parts = [
        "<style>",
        f"body {{ font-family: '{fam}'; color: {text_c}; }}",
        "a { text-decoration: none; }",
        "</style>",
    ]
    for item in verses:
        if item["kind"] == "subtitle":
            parts.append(
                f"<p style='text-align:{sub_align}; font-weight:bold; color:{sub_c}; "
                f"margin:22px 0 6px 0;'>{html_escape(item['text'])}</p>"
            )
            continue
        num = item["num"]
        parts.append(
            f'<table width="100%" border="0" cellspacing="0" cellpadding="0" '
            f'style="border-collapse:collapse; margin-bottom:{vs}px;">'
            f'<tr>'
            f'<td width="1" style="white-space:nowrap; padding-right:6px; vertical-align:top;">'
            f"<span style='color:{num_c}; font-size:{num_pt}pt;'>{num}.</span></td>"
            f'<td style="vertical-align:top; line-height:{lh};">'
            f"<span style='color:{text_c};'>{html_escape(item['text'])}</span></td>"
            f"</tr></table>"
        )
    return "".join(parts)


class BodyStyleDialog(QDialog):
    # 저장 시: body_style 키 + font_family / bible_font_size / aux_font_size
    applied = Signal(dict)

    def __init__(self, current_style=None, sample_verses=None, colors=None,
                 font_family="Malgun Gothic", bible_font_size=14, aux_font_size=12,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("본문 및 글꼴 설정")
        self.setModal(True)
        self.resize(780, 580)

        self._colors = colors or {
            "text": "#201F1E", "muted": "#605E5C",
            "accent": "#0F6CBD", "bg": "#FFFFFF",
        }
        self._sample = sample_verses or SAMPLE_VERSES
        style = body_style_from_settings(None)
        if current_style:
            style.update({k: current_style[k] for k in style if k in current_style})

        root = QHBoxLayout(self)
        left = QVBoxLayout()

        # ---- 글꼴 ----
        font_group = QGroupBox("글꼴")
        font_form = QFormLayout(font_group)

        self.font_combo = QFontComboBox()
        # 비트맵/레거시 글꼴(Terminal, System, Small Fonts 등)은 DirectWrite 로드 실패
        # 경고를 유발하므로 벡터(스케일러블) 글꼴만 노출한다.
        self.font_combo.setFontFilters(QFontComboBox.FontFilter.ScalableFonts)
        self.font_combo.setCurrentFont(QFont(font_family))

        self.bible_size_spin = QSpinBox()
        self.bible_size_spin.setRange(8, 40)
        self.bible_size_spin.setSuffix(" pt")
        self.bible_size_spin.setValue(int(bible_font_size))

        self.aux_size_spin = QSpinBox()
        self.aux_size_spin.setRange(8, 40)
        self.aux_size_spin.setSuffix(" pt")
        self.aux_size_spin.setValue(int(aux_font_size))

        font_form.addRow("글꼴", self.font_combo)
        font_form.addRow("성경 본문 크기", self.bible_size_spin)
        font_form.addRow("주석 · 관주 크기", self.aux_size_spin)
        left.addWidget(font_group)

        # ---- 본문 모양 ----
        body_group = QGroupBox("본문 모양")
        body_form = QFormLayout(body_group)

        self.lh_spin = QDoubleSpinBox()
        self.lh_spin.setRange(1.2, 2.4)
        self.lh_spin.setSingleStep(0.1)
        self.lh_spin.setDecimals(1)

        self.vs_spin = QSpinBox()
        self.vs_spin.setRange(0, 24)
        self.vs_spin.setSuffix(" px")

        self.num_spin = QSpinBox()
        self.num_spin.setRange(60, 110)
        self.num_spin.setSuffix(" %")

        self.num_muted_chk = QCheckBox("절 번호를 은은한 색으로")

        self.sub_align_combo = QComboBox()
        self.sub_align_combo.addItem("왼쪽", "left")
        self.sub_align_combo.addItem("가운데", "center")

        self.sub_accent_chk = QCheckBox("소제목에 강조색")

        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 48)
        self.margin_spin.setSuffix(" px")

        body_form.addRow("행간", self.lh_spin)
        body_form.addRow("절 간격", self.vs_spin)
        body_form.addRow("절 번호 크기", self.num_spin)
        body_form.addRow("", self.num_muted_chk)
        body_form.addRow("소제목 정렬", self.sub_align_combo)
        body_form.addRow("", self.sub_accent_chk)
        body_form.addRow("본문 여백", self.margin_spin)
        left.addWidget(body_group)
        left.addStretch(1)

        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("기본값")
        self.save_btn = QPushButton("저장")
        self.save_btn.setProperty("primary", "true")
        self.cancel_btn = QPushButton("취소")
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        left.addLayout(btn_row)

        # ---- 미리보기 ----
        right = QVBoxLayout()
        right.addWidget(QLabel("미리보기"))
        self.preview = PlainCopyTextBrowser()
        self.preview.setOpenExternalLinks(False)
        right.addWidget(self.preview, 1)

        root.addLayout(left, 0)
        root.addLayout(right, 1)

        self._set_body_controls(style)
        self._connect()
        self._render()

    # ------------------------------------------------------------------
    def _connect(self):
        self.font_combo.currentFontChanged.connect(self._render)
        self.sub_align_combo.currentIndexChanged.connect(self._render)
        self.lh_spin.valueChanged.connect(self._render)
        for w in (self.vs_spin, self.num_spin, self.margin_spin,
                  self.bible_size_spin, self.aux_size_spin):
            w.valueChanged.connect(self._render)
        for w in (self.num_muted_chk, self.sub_accent_chk):
            w.toggled.connect(self._render)
        self.reset_btn.clicked.connect(self._on_reset)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._on_save)

    def _set_body_controls(self, style):
        self.lh_spin.setValue(float(style["line_height"]))
        self.vs_spin.setValue(int(style["verse_spacing"]))
        self.num_spin.setValue(int(style["num_scale"]))
        self.num_muted_chk.setChecked(bool(style["num_muted"]))
        self.sub_align_combo.setCurrentIndex(0 if style["subtitle_align"] == "left" else 1)
        self.sub_accent_chk.setChecked(bool(style["subtitle_accent"]))
        self.margin_spin.setValue(int(style["doc_margin"]))

    def _body_style(self):
        return {
            "line_height": round(self.lh_spin.value(), 2),
            "verse_spacing": self.vs_spin.value(),
            "num_scale": self.num_spin.value(),
            "num_muted": self.num_muted_chk.isChecked(),
            "subtitle_align": self.sub_align_combo.currentData(),
            "subtitle_accent": self.sub_accent_chk.isChecked(),
            "doc_margin": self.margin_spin.value(),
        }

    def collect(self):
        out = self._body_style()
        out["font_family"] = self.font_combo.currentFont().family()
        out["bible_font_size"] = self.bible_size_spin.value()
        out["aux_font_size"] = self.aux_size_spin.value()
        return out

    def _render(self):
        style = self._body_style()
        family = self.font_combo.currentFont().family()
        self.preview.setFont(QFont(family, self.bible_size_spin.value()))
        self.preview.document().setDocumentMargin(style["doc_margin"])
        self.preview.setHtml(render_body_html(
            style, self._sample, self._colors, family, self.bible_size_spin.value()
        ))

    def _on_reset(self):
        self._set_body_controls(dict(DEFAULT_BODY_STYLE))
        self._render()

    def _on_save(self):
        self.applied.emit(self.collect())
        self.accept()
