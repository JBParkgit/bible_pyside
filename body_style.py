# body_style.py
"""성경 본문(읽기 화면) 타이포그래피 설정.

settings.json 에 flat 키(`body_*`)로 저장하고, 여기서 dict 로 모은다.
bible_view.update_content() 와 미리보기 다이얼로그가 같은 규칙을 쓴다.
"""

SERIF_STACK = (
    "'Noto Serif KR', '본명조', 'Source Han Serif K', 'Nanum Myeongjo', "
    "'바탕', 'Batang', 'AppleMyungjo', serif"
)

DEFAULT_BODY_STYLE = {
    "line_height": 1.6,       # 행간 배수
    "verse_spacing": 6,       # 절 사이 간격(px)
    "font_kind": "sans",      # "sans" | "serif"
    "num_scale": 85,          # 절번호 상대 크기(%)
    "num_muted": True,        # 절번호를 은은한 색으로
    "subtitle_align": "left", # "left" | "center"
    "subtitle_accent": True,  # 소제목에 강조색
    "doc_margin": 18,         # 본문 문서 안쪽 여백(px)
}

_KEYS = tuple(DEFAULT_BODY_STYLE.keys())


def body_style_from_settings(settings):
    """settings dict -> 완전한 body_style dict (누락값은 기본값)."""
    out = dict(DEFAULT_BODY_STYLE)
    if not settings:
        return out
    for k in _KEYS:
        sk = f"body_{k}"
        if sk in settings and settings[sk] is not None:
            out[k] = settings[sk]
    # 타입 보정
    try:
        out["line_height"] = float(out["line_height"])
        out["verse_spacing"] = int(out["verse_spacing"])
        out["num_scale"] = int(out["num_scale"])
        out["doc_margin"] = int(out["doc_margin"])
        out["num_muted"] = bool(out["num_muted"])
        out["subtitle_accent"] = bool(out["subtitle_accent"])
    except (TypeError, ValueError):
        return dict(DEFAULT_BODY_STYLE)
    if out["font_kind"] not in ("sans", "serif"):
        out["font_kind"] = "sans"
    if out["subtitle_align"] not in ("left", "center"):
        out["subtitle_align"] = "left"
    return out


def body_style_to_settings(style):
    """body_style dict -> settings 에 병합할 flat 키 dict."""
    return {f"body_{k}": style.get(k, DEFAULT_BODY_STYLE[k]) for k in _KEYS}
