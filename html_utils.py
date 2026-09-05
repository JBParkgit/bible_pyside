from html import escape

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QTextBrowser, QTextEdit


CHAR_WRAP_LANGUAGES = {"korean", "chinese"}


class _PlainCopyMixin:
    """선택 영역을 복사할 때 서식(HTML)을 빼고 일반 텍스트만 클립보드에 담는다.
    다른 프로그램(워드·메모장 등)에 붙여넣을 때 색상·글꼴이 딸려가지 않도록 한다.
    Ctrl+C 와 컨텍스트 메뉴의 기본 복사(.copy()) 모두 이 메서드를 거친다."""
    def createMimeDataFromSelection(self):
        data = QMimeData()
        data.setText(self.textCursor().selection().toPlainText())
        return data


class PlainCopyTextBrowser(_PlainCopyMixin, QTextBrowser):
    pass


class PlainCopyTextEdit(_PlainCopyMixin, QTextEdit):
    pass


def html_escape(value):
    return escape("" if value is None else str(value), quote=False)


def html_attr_escape(value):
    return escape("" if value is None else str(value), quote=True)


def get_text_direction(data):
    return "rtl" if data.get("direction") == "rtl" else "ltr"


def get_text_alignment(data):
    return "right" if get_text_direction(data) == "rtl" else "left"


def get_direction_style(data):
    direction = get_text_direction(data)
    alignment = get_text_alignment(data)
    return f"dir='{direction}' style='direction: {direction}; text-align: {alignment};'"


def apply_text_layout(text_browser, data):
    if get_text_direction(data) == "rtl":
        text_browser.setLayoutDirection(Qt.RightToLeft)
    else:
        text_browser.setLayoutDirection(Qt.LeftToRight)

    language = data.get("language", "unknown")
    if language in CHAR_WRAP_LANGUAGES:
        text_browser.setWordWrapMode(QTextOption.WrapAnywhere)
    else:
        text_browser.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
