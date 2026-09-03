# ui_theme.py
"""최신 MS Office(Fluent) 스타일 디자인 시스템.

- TOKENS       : 라이트/다크 두 모드의 디자인 토큰(색·반경·간격·폰트)
- office_qss() : 토큰으로 만든 앱 전역 QSS (qdarktheme 위에 얹는다)
- themed_icon(): assets/icons/*.svg 를 지정 색으로 렌더한 QIcon
"""
import os

from PySide6.QtCore import QByteArray, QRectF, Qt, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")

FONT_STACK = '"Segoe UI Variable Text", "Segoe UI", "맑은 고딕", "Malgun Gothic", sans-serif'
FONT_FAMILY_PRIMARY = "Segoe UI Variable Text"
FONT_POINT_SIZE = 10

TOKENS = {
    "light": {
        "accent": "#0F6CBD",
        "accent_hover": "#115EA3",
        "accent_pressed": "#0E4775",
        "accent_subtle": "#EBF3FC",      # 강조색 옅은 채움
        "on_accent": "#FFFFFF",
        "window": "#FAF9F8",
        "surface": "#FFFFFF",
        "subtle": "#F3F2F1",             # 커맨드바·컨트롤바 배경
        "border": "#E1DFDD",
        "border_strong": "#C8C6C4",
        "text": "#201F1E",
        "text_secondary": "#605E5C",
        "text_disabled": "#A19F9D",
        "fill_hover": "#F0EFEE",
        "fill_pressed": "#E6E4E2",
        "fill_selected": "#EDEBE9",
        "verse_selected": "#CCE4F7",
        "highlight": "#0F6CBD",
        "on_highlight": "#FFFFFF",
        "scrollbar": "#C8C6C4",
        "qdt": "light",
    },
    "dark": {
        "accent": "#479EF5",
        "accent_hover": "#62ABF5",
        "accent_pressed": "#2886DE",
        "accent_subtle": "#0B2A47",
        "on_accent": "#FFFFFF",
        "window": "#1F1F1F",
        "surface": "#292929",
        "subtle": "#2B2B2B",
        "border": "#3D3D3D",
        "border_strong": "#4A4A4A",
        "text": "#F3F2F1",
        "text_secondary": "#C8C6C4",
        "text_disabled": "#797775",
        "fill_hover": "#333333",
        "fill_pressed": "#3D3D3D",
        "fill_selected": "#383838",
        "verse_selected": "#2A4B6B",
        "highlight": "#479EF5",
        "on_highlight": "#0A1220",
        "scrollbar": "#5A5A5A",
        "qdt": "dark",
    },
}


def resolve_mode(theme_name):
    """예전 테마명(Sepia/Gray 포함)을 라이트/다크 모드로 매핑."""
    return "dark" if str(theme_name).lower() in ("dark", "gray") else "light"


def themed_icon(name, color):
    """assets/icons/<name>.svg 를 color 로 칠해 QIcon 으로 반환."""
    path = os.path.join(ICON_DIR, f"{name}.svg")
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()
    except OSError:
        return QIcon()
    svg = svg.replace("COLOR", color).replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon = QIcon()
    for size in (16, 20, 24, 32):
        pixmap = QPixmap(size, size)
        pixmap.setDevicePixelRatio(1)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def office_qss(mode):
    t = TOKENS[mode]
    return f"""
* {{
    font-family: {FONT_STACK};
}}
QWidget {{ color: {t['text']}; }}
QMainWindow, QDialog {{ background-color: {t['window']}; }}

/* ---------- 상단 커맨드 바 ---------- */
QToolBar#mainToolBar {{
    background-color: {t['subtle']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar#mainToolBar QPushButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 30px;
    color: {t['text']};
}}
QToolBar#mainToolBar QPushButton:hover {{ background-color: {t['fill_hover']}; }}
QToolBar#mainToolBar QPushButton:pressed {{ background-color: {t['fill_pressed']}; }}
QToolBar#mainToolBar QPushButton:menu-indicator {{ image: none; }}
QToolBar#mainToolBar QPushButton[iconButton="true"] {{
    min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px;
    padding: 0;
}}
QToolBar#mainToolBar QPushButton#locationButton {{
    font-weight: 600;
    padding: 4px 14px;
    text-align: left;
}}
QToolBar#mainToolBar QLineEdit, QToolBar#mainToolBar QComboBox {{
    background-color: {t['surface']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 30px;
    selection-background-color: {t['accent']};
}}
QToolBar#mainToolBar QLineEdit:focus, QToolBar#mainToolBar QComboBox:focus {{
    border: 1px solid {t['accent']};
}}
QFrame#vsep {{ background-color: {t['border']}; max-width: 1px; min-width: 1px; margin: 6px 4px; border: none; }}

/* ---------- 탭 ---------- */
QTabWidget::pane {{
    background-color: {t['surface']};
    border: none;
    border-top: 1px solid {t['border']};
}}
QTabBar {{ background-color: {t['window']}; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    margin: 0;
    font-weight: 500;
}}
QTabBar::tab:hover:!selected {{ color: {t['text']}; background-color: {t['fill_hover']}; }}
QTabBar::tab:selected {{
    color: {t['accent']};
    border-bottom: 2px solid {t['accent']};
    font-weight: 600;
}}

/* ---------- 코너 위젯(우측 상단 도구) ---------- */
QWidget#CornerWidget {{ background-color: {t['window']}; }}
QWidget#CornerWidget QPushButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 28px;
    color: {t['text']};
}}
QWidget#CornerWidget QPushButton:hover {{ background-color: {t['fill_hover']}; }}
QWidget#CornerWidget QPushButton:pressed {{ background-color: {t['fill_pressed']}; }}
QWidget#CornerWidget QPushButton:menu-indicator {{ image: none; }}
QWidget#CornerWidget QComboBox {{
    background-color: {t['surface']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 26px;
}}
QPushButton#AddTabButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    min-width: 28px; min-height: 28px;
    padding: 0;
    font-size: 16px;
    color: {t['text']};
}}
QPushButton#AddTabButton:hover {{ background-color: {t['fill_hover']}; }}

/* ---------- 탭 내부 컨트롤 바 ---------- */
QFrame#viewControlBar, QFrame#subCommandBar {{
    background-color: {t['subtle']};
    border: none;
    border-bottom: 1px solid {t['border']};
}}

/* ---------- 버튼(전역) ---------- */
QPushButton {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 26px;
}}
QPushButton:hover {{ background-color: {t['fill_hover']}; }}
QPushButton:pressed {{ background-color: {t['fill_pressed']}; }}
QPushButton:disabled {{ color: {t['text_disabled']}; border-color: {t['border']}; background-color: {t['subtle']}; }}
QPushButton:default {{ border-color: {t['accent']}; }}
QPushButton[primary="true"] {{
    background-color: {t['accent']};
    color: {t['on_accent']};
    border: 1px solid {t['accent']};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background-color: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
QPushButton[primary="true"]:pressed {{ background-color: {t['accent_pressed']}; border-color: {t['accent_pressed']}; }}
QPushButton[primary="true"]:disabled {{ background-color: {t['border']}; border-color: {t['border']}; color: {t['text_disabled']}; }}
QPushButton[subtle="true"] {{ background-color: transparent; border-color: transparent; }}
QPushButton[subtle="true"]:hover {{ background-color: {t['fill_hover']}; }}
/* 작은 정사각형 버튼(+ / - / 접기 등): 넉넉한 패딩이 글리프를 자르지 않도록 */
QPushButton[compact="true"] {{
    padding: 0; min-width: 0; min-height: 0;
    font-weight: 600;
}}

/* ---------- 입력 ---------- */
QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {t['accent']};
    selection-color: {t['on_accent']};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border: 1px solid {t['accent']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    selection-background-color: {t['fill_selected']};
    selection-color: {t['text']};
    padding: 4px;
    outline: none;
}}

/* ---------- 리스트 / 텍스트 영역 ---------- */
QListWidget, QListView, QTreeView {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 4px; }}
QListWidget::item:hover {{ background-color: {t['fill_hover']}; }}
QListWidget::item:selected {{ background-color: {t['fill_selected']}; color: {t['text']}; }}
QTextBrowser, QTextEdit {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    selection-background-color: {t['verse_selected']};
}}

/* ---------- 메뉴 ---------- */
QMenu {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 28px 6px 12px; border-radius: 4px; color: {t['text']}; }}
QMenu::item:selected {{ background-color: {t['fill_selected']}; }}
QMenu::item:disabled {{ color: {t['text_disabled']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}

/* ---------- 스크롤바 ---------- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['scrollbar']}; border-radius: 4px; min-height: 28px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['scrollbar']}; border-radius: 4px; min-width: 28px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {t['text_secondary']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- 툴팁 / 상태바 ---------- */
QToolTip {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border_strong']};
    border-radius: 4px;
    padding: 4px 8px;
}}
QStatusBar {{ background-color: {t['subtle']}; border-top: 1px solid {t['border']}; color: {t['text_secondary']}; }}
QStatusBar::item {{ border: none; }}

/* ---------- 선택 구절 액션 바 (플로팅 카드) ---------- */
QFrame#selectionBar {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}
QFrame#selectionBar QPushButton {{
    border: 1px solid transparent;
    background-color: transparent;
    border-radius: 6px;
    padding: 4px 10px;
}}
QFrame#selectionBar QPushButton:hover {{ background-color: {t['fill_hover']}; }}
QFrame#selectionBar QPushButton[primary="true"] {{
    background-color: {t['accent']}; color: {t['on_accent']}; border-color: {t['accent']};
}}
QFrame#selectionBar QPushButton[primary="true"]:hover {{ background-color: {t['accent_hover']}; }}
QLabel#selectionReferenceLabel {{ font-weight: 600; color: {t['text']}; }}

/* ---------- 팝업 프레임 ---------- */
QFrame#mainFrame {{
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: 8px;
}}
"""
