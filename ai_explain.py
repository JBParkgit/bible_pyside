# ai_explain.py
"""Google Gemini API 를 이용한 '선택 구절 AI 설명' 기능.

사용자가 https://aistudio.google.com/apikey 에서 무료 API 키를 발급받아
'AI 설명 설정' 대화상자에 입력하면, 성경 읽기 화면에서 구절을 선택한 뒤
액션바의 '설명' 버튼으로 해당 본문의 해설을 받아볼 수 있다.

- GeminiClient   : QNetworkAccessManager 기반 비동기 REST 호출
- AiExplanationDialog : 결과(마크다운)를 보여주는 비모달 대화상자
- AiSettingsDialog    : API 키 / 모델 입력 대화상자
"""
import json

from PySide6.QtCore import QObject, Signal, QUrl, QTimer, Qt
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QTextBrowser, QVBoxLayout,
)


API_KEY_URL = "https://aistudio.google.com/apikey"
# 모델 콤보는 편집 가능하므로 여기 없는 이름도 직접 입력할 수 있다.
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.6-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]
DEFAULT_MODEL = "gemini-3.6-flash"
# 신규 사용자에게 더 이상 제공되지 않는 모델 → 대체 모델.
# (사용자가 명시적으로 다른 값을 넣으면 그대로 사용된다.)
LEGACY_DEFAULT_MODELS = {"gemini-2.5-flash", "gemini-1.5-flash"}

# 프롬프트는 설정에서 편집 가능하다. {reference} {passage} {translation} 자리표시자 사용.
DEFAULT_PROMPT_TEMPLATE = """당신은 전통적인 복음주의(evangelical) 관점에 서 있는 개신교 성경 교사입니다. 성경의 영감과 무오성, 최종 권위를 인정하고, 역사적·문법적(historical-grammatical) 해석 원리를 따르며, 성경 전체를 그리스도 중심으로 읽습니다.

아래 본문을 한국어로 해설해 주세요.

[{reference} · {translation}]
{passage}

작성 지침:
- 본문의 장르(내러티브·율법·시가·지혜·예언·복음서·서신·묵시)에 맞게 설명의 초점을 맞추세요.
- 아래 항목을 markdown 소제목(##)으로 구분하세요.
  ## 문맥
  이 본문이 속한 책·단락에서의 위치와, 이해에 꼭 필요한 배경(저자·수신자·상황)만.
  ## 본문 풀이
  절의 흐름을 따라가며 각 구절의 뜻을 자세히 설명. 중요한 단어는 원어(히브리어/헬라어) 음역과 뜻을 곁들이되, 확실하지 않으면 언급하지 마세요.

각 항목은 필요한 만큼 충분히 설명해 주세요. 분량 제한은 없습니다.
복음주의 안에서도 이견이 있는 세부 사항은 주요 견해를 균형 있게 소개하세요.
본문에 없는 사실이나 존재하지 않는 성경 구절을 지어내지 마세요. 불확실하면 그렇다고 쓰세요."""


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def build_prompt(reference, passage, translation="", template=None):
    template = (template or DEFAULT_PROMPT_TEMPLATE).strip()
    if "{passage}" not in template:
        # 사용자가 자리표시자를 지웠어도 본문은 반드시 전달되도록 보완
        template += "\n\n[{reference} · {translation}]\n{passage}"
    return template.format_map(_SafeDict(
        reference=reference, passage=passage, translation=translation or "번역본 미상"
    ))


class GeminiClient(QObject):
    """generativelanguage.googleapis.com 에 비동기로 요청하고 결과를 시그널로 알린다.

    서버 혼잡(429/503 등 일시적 오류)일 때는 지연 후 자동으로 몇 차례 재시도한다.
    """

    finished = Signal(str)        # 설명 텍스트(markdown)
    failed = Signal(str)          # 오류 메시지
    retrying = Signal(int, int)   # (재시도 회차, 총 시도 횟수)

    MAX_ATTEMPTS = 3
    RETRY_DELAYS_MS = [5000, 12000]  # 2번째, 3번째 시도 전 대기
    _TRANSIENT_HTTP = {429, 500, 502, 503, 504}
    _TRANSIENT_KEYWORDS = (
        "high demand", "overloaded", "try again later", "unavailable",
        "resource_exhausted", "rate limit", "backend error", "internal error",
        "deadline", "timeout",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._reply = None
        self._request = None      # (api_key, model, prompt)
        self._attempt = 0
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._send)

    def is_busy(self):
        return self._reply is not None or self._retry_timer.isActive()

    def cancel(self):
        self._retry_timer.stop()
        self._request = None
        if self._reply is not None:
            reply, self._reply = self._reply, None
            try:
                reply.finished.disconnect(self._on_finished)
            except (RuntimeError, TypeError):
                pass
            reply.abort()
            reply.deleteLater()

    def explain(self, api_key, model, prompt):
        if not api_key:
            self.failed.emit("API 키가 설정되지 않았습니다.")
            return
        self.cancel()
        self._request = (api_key, model or DEFAULT_MODEL, prompt)
        self._attempt = 0
        self._send()

    def _send(self):
        if not self._request:
            return
        api_key, model, prompt = self._request
        self._attempt += 1
        url = QUrl(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(b"x-goog-api-key", api_key.encode("utf-8"))
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
        }).encode("utf-8")
        self._reply = self._nam.post(request, body)
        self._reply.finished.connect(self._on_finished)

    def _is_transient(self, http_status, message):
        if http_status in self._TRANSIENT_HTTP:
            return True
        low = (message or "").lower()
        return any(keyword in low for keyword in self._TRANSIENT_KEYWORDS)

    def _retry_or_fail(self, message):
        if self._request and self._attempt < self.MAX_ATTEMPTS:
            delay = self.RETRY_DELAYS_MS[min(self._attempt - 1, len(self.RETRY_DELAYS_MS) - 1)]
            self.retrying.emit(self._attempt + 1, self.MAX_ATTEMPTS)
            self._retry_timer.start(delay)
            return
        self._request = None
        self.failed.emit(message)

    def _on_finished(self):
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        reply.deleteLater()
        raw = bytes(reply.readAll().data())
        net_error = reply.error()
        http_status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {}

        if isinstance(data, dict) and data.get("error"):
            message = data["error"].get("message", "알 수 없는 오류")
            if self._is_transient(http_status, message):
                self._retry_or_fail(f"Gemini 오류: {message}")
                return
            if "no longer available" in message or "not found" in message.lower():
                message += "\n\n'설정 및 추출 → AI 설명 설정'에서 모델 이름을 바꿔 보세요."
            self._request = None
            self.failed.emit(f"Gemini 오류: {message}")
            return

        if net_error != QNetworkReply.NetworkError.NoError:
            if self._is_transient(http_status, reply.errorString()):
                self._retry_or_fail(f"네트워크 오류: {reply.errorString()}")
                return
            self._request = None
            self.failed.emit(f"네트워크 오류: {reply.errorString()}")
            return

        text = self._extract_text(data)
        if not text:
            self._request = None
            self.failed.emit("응답이 비어 있습니다. (안전 필터에 걸렸거나 토큰 한도를 초과했을 수 있습니다.)")
            return
        self._request = None
        self.finished.emit(text)

    @staticmethod
    def _extract_text(data):
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return ""
        return "".join(part.get("text", "") for part in parts).strip()


class AiExplanationDialog(QDialog):
    """AI 설명 결과를 보여주는 비모달 창. 같은 창을 재사용한다."""

    regenerate_requested = Signal()

    def __init__(self, parent=None, font_family="Malgun Gothic", font_size=13):
        super().__init__(parent)
        self.setWindowTitle("AI 구절 설명")
        self.resize(560, 640)
        self.setModal(False)
        self._raw_text = ""

        layout = QVBoxLayout(self)

        self.reference_label = QLabel()
        self.reference_label.setStyleSheet("font-weight: 700; font-size: 15px;")
        self.reference_label.setWordWrap(True)
        layout.addWidget(self.reference_label)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setFont(QFont(font_family, font_size))
        layout.addWidget(self.browser, 1)

        button_row = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #57606a;")
        button_row.addWidget(self.status_label)
        button_row.addStretch(1)
        self.regenerate_button = QPushButton("다시 생성")
        self.copy_button = QPushButton("복사")
        self.close_button = QPushButton("닫기")
        for button in (self.regenerate_button, self.copy_button, self.close_button):
            button_row.addWidget(button)
        layout.addLayout(button_row)

        self.regenerate_button.clicked.connect(self.regenerate_requested.emit)
        self.copy_button.clicked.connect(self._copy_text)
        self.close_button.clicked.connect(self.close)

    def start(self, reference):
        self.reference_label.setText(reference)
        self.status_label.setText("생성 중…")
        self.browser.setPlainText("잠시만 기다려 주세요. Gemini가 본문을 설명하고 있습니다…")
        self.regenerate_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.show()
        self.raise_()
        self.activateWindow()

    def note_retry(self, attempt, total):
        self.status_label.setText(f"서버 혼잡 — 잠시 후 재시도 중 ({attempt}/{total})…")

    def show_result(self, text):
        self._raw_text = text
        self.status_label.setText("")
        try:
            self.browser.setMarkdown(text)
        except Exception:
            self.browser.setPlainText(text)
        self.regenerate_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def show_error(self, message):
        self.status_label.setText("오류")
        self.browser.setPlainText(message)
        self.regenerate_button.setEnabled(True)
        self.copy_button.setEnabled(False)

    def _copy_text(self):
        QApplication.clipboard().setText(self._raw_text or self.browser.toPlainText())


class AiSettingsDialog(QDialog):
    """Gemini API 키 / 모델 / 프롬프트 편집."""

    def __init__(self, api_key="", model=DEFAULT_MODEL, prompt="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 설명 설정 (Gemini)")
        self.resize(620, 720)

        layout = QVBoxLayout(self)

        info = QLabel(
            "<b>무료 API 키 발급 방법</b>"
            "<ol style='margin-left:-18px;'>"
            "<li>웹 브라우저에서 <b>Google 계정</b>으로 로그인합니다.</li>"
            f"<li>아래 <b>[발급 페이지 열기]</b> 버튼을 누르거나 "
            f"<a href='{API_KEY_URL}'>{API_KEY_URL}</a> 로 접속합니다.</li>"
            "<li><b>[API 키 만들기 / Create API key]</b> 버튼을 클릭합니다.</li>"
            "<li>프로젝트를 고르라고 하면 아무 프로젝트나 선택합니다 "
            "(없으면 <i>[새 프로젝트에서 API 키 만들기]</i> 를 누르면 자동으로 만들어집니다).</li>"
            "<li>잠시 후 <code>AIza…</code> 로 시작하는 키가 나타나면 <b>복사</b>합니다.</li>"
            "<li>아래 <b>‘API 키’</b> 칸에 붙여넣고 <b>[OK]</b> 를 누릅니다.</li>"
            "</ol>"
            "· 신용카드 등록이나 결제 설정 없이 <b>무료</b>로 바로 사용할 수 있습니다.<br>"
            "· 입력한 키는 이 PC의 <code>settings.json</code> 에만 저장되며, "
            "성경 본문을 설명받을 때 Google 서버로만 전송됩니다.<br>"
            "· 한도(분당·일일 요청 수)를 넘으면 잠시 후 자동으로 회복되며, 요금은 청구되지 않습니다."
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        open_button = QPushButton("발급 페이지 열기")
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(API_KEY_URL)))
        open_row = QHBoxLayout()
        open_row.addWidget(open_button)
        open_row.addStretch(1)
        layout.addLayout(open_row)

        layout.addWidget(QLabel("API 키:"))
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit(api_key)
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("AIza...")
        self.show_button = QPushButton("표시")
        self.show_button.setCheckable(True)
        self.show_button.setFixedWidth(52)
        self.show_button.toggled.connect(
            lambda on: self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        key_row.addWidget(self.key_edit)
        key_row.addWidget(self.show_button)
        layout.addLayout(key_row)

        layout.addWidget(QLabel("모델:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(GEMINI_MODELS)
        if model and model not in GEMINI_MODELS:
            self.model_combo.insertItem(0, model)
        self.model_combo.setCurrentText(model or DEFAULT_MODEL)
        layout.addWidget(self.model_combo)

        prompt_header = QHBoxLayout()
        prompt_header.addWidget(QLabel("프롬프트 (자리표시자: {reference} {passage} {translation}):"))
        prompt_header.addStretch(1)
        self.reset_prompt_button = QPushButton("기본값으로")
        self.reset_prompt_button.setFixedWidth(90)
        self.reset_prompt_button.clicked.connect(
            lambda: self.prompt_edit.setPlainText(DEFAULT_PROMPT_TEMPLATE)
        )
        prompt_header.addWidget(self.reset_prompt_button)
        layout.addLayout(prompt_header)

        self.prompt_edit = QPlainTextEdit(prompt.strip() if prompt and prompt.strip() else DEFAULT_PROMPT_TEMPLATE)
        self.prompt_edit.setTabChangesFocus(True)
        layout.addWidget(self.prompt_edit, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        prompt = self.prompt_edit.toPlainText().strip()
        # 기본값과 같으면 빈 문자열로 저장해 향후 기본 프롬프트 개선을 자동 반영
        if prompt == DEFAULT_PROMPT_TEMPLATE.strip():
            prompt = ""
        return (
            self.key_edit.text().strip(),
            self.model_combo.currentText().strip(),
            prompt,
        )
