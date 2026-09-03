from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption


CHAR_WRAP_LANGUAGES = {"korean", "chinese"}


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
