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
import os
import re
import time
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QUrl, QTimer, Qt
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from html_utils import PlainCopyTextBrowser


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

# 프롬프트는 설정·AI 창에서 편집 가능하다. {reference} {passage} {translation} 자리표시자 사용.
DEFAULT_PROMPT_TEMPLATE = """당신은 전통적인 복음주의(evangelical) 관점에 서 있는, 신학교(seminary) 교수 수준의 개신교 성경 해석 전문가입니다. 성경 원어(히브리어·아람어·헬라어), 성경신학과 조직신학, 고대 근동 및 제2성전기 배경, 본문비평과 주해사(history of interpretation)에 정통합니다. 성경의 영감과 무오성, 최종 권위를 인정하고, 역사적·문법적(historical-grammatical) 해석 원리를 따르며, 성경 전체를 그리스도 중심으로 읽습니다.

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


def build_question_prompt(reference, passage, translation, question):
    """선택 구절에 대한 사용자의 자유 질문용 프롬프트."""
    version = f" · {translation}" if translation else ""
    return (
        "당신은 신학교(seminary) 교수 수준의 개신교 성경 해석 전문가입니다. "
        "원어와 성경신학·조직신학, 고대 근동 배경, 주해사에 정통합니다. "
        "아래 성경 본문에 관한 질문에 한국어로 답해 주세요. 본문과 성경 전체의 "
        "문맥에 근거해 설명하고, 본문에 없는 사실이나 존재하지 않는 성경 구절을 "
        "지어내지 마세요. 불확실하면 그렇다고 쓰세요.\n\n"
        f"[{reference}{version}]\n{passage}\n\n"
        f"질문: {question}"
    )


class GeminiClient(QObject):
    """generativelanguage.googleapis.com 에 비동기로 요청하고 결과를 시그널로 알린다.

    서버 혼잡(429/503 등 일시적 오류)일 때는 지연 후 자동으로 몇 차례 재시도한다.
    """

    finished = Signal(str)        # 설명 텍스트(markdown)
    failed = Signal(str)          # 오류 메시지
    retrying = Signal(int, int)   # (재시도 회차, 총 시도 횟수)
    log_line = Signal(str)        # API 통신 로그 한 줄

    LOG_FILE = "gemini_api.log"
    MAX_LOG_ENTRIES = 400

    MAX_ATTEMPTS = 3
    RETRY_DELAYS_MS = [5000, 12000]  # 2번째, 3번째 시도 전 대기
    _TRANSIENT_HTTP = {429, 500, 502, 503, 504}
    _TRANSIENT_KEYWORDS = (
        "high demand", "overloaded", "try again later", "unavailable",
        "resource_exhausted", "rate limit", "backend error", "internal error",
        "deadline", "timeout",
    )

    REQUEST_TIMEOUT_MS = 90000     # 서버 전송 타임아웃
    WATCHDOG_MS = 120000           # 그래도 안 끝나면 강제 중단

    HEARTBEAT_MS = 3000           # 대기 중 살아있음을 로그로 알리는 간격

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._reply = None
        self._request = None      # (api_key, model, prompt)
        self._attempt = 0
        self._req_started = 0.0
        self._uploaded = False
        self._first_byte = False
        self.log_entries = []     # 최근 통신 로그 (뷰어가 나중에 열려도 보이도록 보관)
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._send)
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_watchdog)
        self._heartbeat = QTimer(self)
        self._heartbeat.timeout.connect(self._on_heartbeat)

    def _on_heartbeat(self):
        if self._reply is None:
            self._heartbeat.stop()
            return
        elapsed = time.monotonic() - self._req_started
        self._log(f"   … 응답 대기 중 ({elapsed:.0f}초 경과)")

    def _log(self, text):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
        self.log_entries.append(line)
        if len(self.log_entries) > self.MAX_LOG_ENTRIES:
            del self.log_entries[:len(self.log_entries) - self.MAX_LOG_ENTRIES]
        self.log_line.emit(line)
        try:
            with open(self.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def clear_log(self):
        self.log_entries.clear()
        try:
            open(self.LOG_FILE, "w", encoding="utf-8").close()
        except OSError:
            pass

    def is_busy(self):
        return self._reply is not None or self._retry_timer.isActive()

    def cancel(self):
        self._retry_timer.stop()
        self._watchdog.stop()
        self._heartbeat.stop()
        self._request = None
        if self._reply is not None:
            reply, self._reply = self._reply, None
            try:
                reply.finished.disconnect(self._on_finished)
            except (RuntimeError, TypeError):
                pass
            reply.abort()
            reply.deleteLater()

    def _on_watchdog(self):
        """타임아웃/멈춤 방지: 응답이 안 오면 재시도 없이 즉시 중단·실패 처리."""
        self._log(f"⏱ 워치독: {self.WATCHDOG_MS // 1000}초간 응답 없음 — 중단")
        self._retry_timer.stop()
        self._heartbeat.stop()
        self._request = None
        if self._reply is not None:
            reply, self._reply = self._reply, None
            try:
                reply.finished.disconnect(self._on_finished)
            except (RuntimeError, TypeError):
                pass
            reply.abort()
            reply.deleteLater()
        self.failed.emit(
            "응답이 오지 않습니다. 네트워크(방화벽/프록시) 또는 서버 상태를 확인한 뒤 다시 시도하세요."
        )

    def explain(self, api_key, model, prompt):
        if not api_key:
            self._log("요청 취소: API 키 없음")
            self.failed.emit("API 키가 설정되지 않았습니다.")
            return
        self.cancel()
        self._request = (api_key, model or DEFAULT_MODEL, prompt)
        self._attempt = 0
        snippet = " ".join(prompt.split())[:200]
        self._log(f"── 새 요청 (모델 {self._request[1]}, 프롬프트 {len(prompt)}자)")
        self._log(f"   프롬프트: {snippet}{'…' if len(prompt) > 200 else ''}")
        self._send()

    def _send(self):
        if not self._request:
            return
        api_key, model, prompt = self._request
        self._attempt += 1
        self._req_started = time.monotonic()
        url = QUrl(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )
        self._log(f"→ POST {model}:generateContent  (시도 {self._attempt}/{self.MAX_ATTEMPTS})")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(b"x-goog-api-key", api_key.encode("utf-8"))
        try:
            request.setTransferTimeout(self.REQUEST_TIMEOUT_MS)
        except (AttributeError, TypeError):
            pass
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
        }).encode("utf-8")
        self._uploaded = False
        self._first_byte = False
        self._reply = self._nam.post(request, body)
        self._reply.finished.connect(self._on_finished)
        self._reply.uploadProgress.connect(self._on_upload_progress)
        self._reply.downloadProgress.connect(self._on_download_progress)
        self._watchdog.start(self.WATCHDOG_MS)
        self._heartbeat.start(self.HEARTBEAT_MS)

    def _on_upload_progress(self, sent, total):
        if not self._uploaded and total > 0 and sent >= total:
            self._uploaded = True
            elapsed = time.monotonic() - self._req_started
            self._log(f"   ↑ 요청 전송 완료 ({sent}바이트, {elapsed * 1000:.0f}ms) — 서버 응답 기다리는 중")

    def _on_download_progress(self, received, total):
        if not self._first_byte and received > 0:
            self._first_byte = True
            self._heartbeat.stop()
            elapsed = time.monotonic() - self._req_started
            self._log(f"   ↓ 응답 수신 시작 ({elapsed:.1f}초) — 정상 통신 중")

    def _is_transient(self, http_status, message):
        if http_status in self._TRANSIENT_HTTP:
            return True
        low = (message or "").lower()
        return any(keyword in low for keyword in self._TRANSIENT_KEYWORDS)

    def _retry_or_fail(self, message):
        if self._request and self._attempt < self.MAX_ATTEMPTS:
            delay = self.RETRY_DELAYS_MS[min(self._attempt - 1, len(self.RETRY_DELAYS_MS) - 1)]
            self._log(f"⟳ {delay // 1000}초 후 재시도 ({self._attempt + 1}/{self.MAX_ATTEMPTS}) — {message}")
            self.retrying.emit(self._attempt + 1, self.MAX_ATTEMPTS)
            self._retry_timer.start(delay)
            return
        self._request = None
        self._log(f"✗ 실패: {message}")
        self.failed.emit(message)

    def _on_finished(self):
        self._watchdog.stop()
        self._heartbeat.stop()
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        reply.deleteLater()
        raw = bytes(reply.readAll().data())
        net_error = reply.error()
        http_status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        elapsed = (time.monotonic() - self._req_started) * 1000 if self._req_started else 0
        self._log(f"← HTTP {http_status}  {elapsed:.0f}ms  ({len(raw)}바이트)")
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {}
            if raw:
                self._log(f"   (JSON 파싱 실패) {raw[:300].decode('utf-8', 'replace')}")

        if isinstance(data, dict) and data.get("error"):
            message = data["error"].get("message", "알 수 없는 오류")
            self._log(f"   API 오류: {message}")
            if self._is_transient(http_status, message):
                self._retry_or_fail(f"Gemini 오류: {message}")
                return
            if "no longer available" in message or "not found" in message.lower():
                message += "\n\n'설정 및 추출 → AI 설명 설정'에서 모델 이름을 바꿔 보세요."
            self._request = None
            self._log(f"✗ 실패: {message}")
            self.failed.emit(f"Gemini 오류: {message}")
            return

        if net_error != QNetworkReply.NetworkError.NoError:
            self._log(f"   네트워크 오류: {reply.errorString()}")
            if self._is_transient(http_status, reply.errorString()):
                self._retry_or_fail(f"네트워크 오류: {reply.errorString()}")
                return
            self._request = None
            self._log(f"✗ 실패: {reply.errorString()}")
            self.failed.emit(f"네트워크 오류: {reply.errorString()}")
            return

        text = self._extract_text(data)
        if not text:
            self._request = None
            finish_reason = ""
            try:
                finish_reason = data["candidates"][0].get("finishReason", "")
            except (KeyError, IndexError, TypeError):
                pass
            self._log(f"✗ 빈 응답 (finishReason={finish_reason or '없음'})")
            self.failed.emit("응답이 비어 있습니다. (안전 필터에 걸렸거나 토큰 한도를 초과했을 수 있습니다.)")
            return
        self._request = None
        self._log(f"✓ 완료 — 응답 {len(text)}자")
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

    regenerate_requested = Signal()   # 마지막 요청(기본 설명 또는 질문) 다시 실행
    default_requested = Signal()       # 기본 설명 프롬프트로 실행
    question_submitted = Signal(str)   # 선택 구절에 대한 사용자의 자유 질문
    save_requested = Signal()          # 현재 해설을 해당 구절에 저장(DB)
    delete_requested = Signal()        # 이 구절에 저장된 해설 삭제
    prompt_saved = Signal(str)         # 편집한 기본 프롬프트 저장

    _PANEL_HEIGHT = 200

    def __init__(self, parent=None, font_family="Malgun Gothic", font_size=13, prompt=""):
        super().__init__(parent)
        self.setWindowTitle("AI 구절 설명")
        self.resize(600, 720)
        self.setModal(False)
        self._raw_text = ""

        layout = QVBoxLayout(self)

        self.reference_label = QLabel()
        self.reference_label.setStyleSheet("font-weight: 700; font-size: 15px;")
        self.reference_label.setWordWrap(True)
        layout.addWidget(self.reference_label)

        self.browser = PlainCopyTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setFont(QFont(font_family, font_size))
        layout.addWidget(self.browser, 1)

        # 이 본문에 대해 직접 질문하기
        question_row = QHBoxLayout()
        self.question_edit = QLineEdit()
        self.question_edit.setPlaceholderText("이 본문에 대해 물어보기…  (비워두면 기본 설명)")
        self.ask_button = QPushButton("질문")
        self.ask_button.setProperty("primary", "true")
        self.explain_button = QPushButton("기본 설명")
        self.explain_button.setProperty("primary", "true")
        question_row.addWidget(self.question_edit, 1)
        question_row.addWidget(self.ask_button)
        question_row.addWidget(self.explain_button)
        layout.addLayout(question_row)

        button_row = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: palette(mid);")
        button_row.addWidget(self.status_label)
        button_row.addStretch(1)
        self.panel_toggle_button = QPushButton("로그·프롬프트 ▾")
        self.panel_toggle_button.setCheckable(True)
        self.panel_toggle_button.setChecked(True)
        self.panel_toggle_button.setToolTip("하단의 통신 로그 / 기본 프롬프트 영역을 접거나 폅니다")
        self.regenerate_button = QPushButton("다시 생성")
        self.copy_button = QPushButton("복사")
        self.save_button = QPushButton("구절에 저장")
        self.save_button.setToolTip("이 해설을 해당 구절에 연동해 저장합니다. 다음에 그 구절의 AI 해설을 열면 바로 표시됩니다.")
        self.delete_button = QPushButton("저장 삭제")
        self.delete_button.setToolTip("이 구절에 저장된 AI 해설을 삭제합니다.")
        self.delete_button.setVisible(False)
        self.export_button = QPushButton("파일로…")
        self.close_button = QPushButton("닫기")
        for button in (self.panel_toggle_button, self.regenerate_button, self.copy_button,
                       self.save_button, self.delete_button, self.export_button, self.close_button):
            button_row.addWidget(button)
        layout.addLayout(button_row)

        # ── 하단 영역: 통신 로그 / 기본 프롬프트 (별도 창 대신 여기서 실시간 표시) ──
        self.bottom_panel = QTabWidget()
        self.bottom_panel.setFixedHeight(self._PANEL_HEIGHT)

        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(4, 4, 4, 4)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log_layout.addWidget(self.log_view, 1)
        log_btns = QHBoxLayout()
        log_btns.addStretch(1)
        self.log_clear_button = QPushButton("지우기")
        self.log_copy_button = QPushButton("복사")
        log_btns.addWidget(self.log_clear_button)
        log_btns.addWidget(self.log_copy_button)
        log_layout.addLayout(log_btns)
        self.bottom_panel.addTab(log_tab, "통신 로그")

        prompt_tab = QWidget()
        prompt_layout = QVBoxLayout(prompt_tab)
        prompt_layout.setContentsMargins(4, 4, 4, 4)
        prompt_layout.addWidget(QLabel(
            "‘기본 설명’에 쓰이는 프롬프트입니다. 자리표시자: {reference} {passage} {translation}"
        ))
        self.prompt_edit = QPlainTextEdit(prompt.strip() if prompt and prompt.strip() else DEFAULT_PROMPT_TEMPLATE)
        self.prompt_edit.setTabChangesFocus(True)
        prompt_layout.addWidget(self.prompt_edit, 1)
        prompt_btns = QHBoxLayout()
        prompt_btns.addStretch(1)
        self.prompt_reset_button = QPushButton("기본값으로")
        self.prompt_save_button = QPushButton("프롬프트 저장")
        self.prompt_save_button.setProperty("primary", "true")
        prompt_btns.addWidget(self.prompt_reset_button)
        prompt_btns.addWidget(self.prompt_save_button)
        prompt_layout.addLayout(prompt_btns)
        self.bottom_panel.addTab(prompt_tab, "기본 프롬프트")

        layout.addWidget(self.bottom_panel)

        self.panel_toggle_button.toggled.connect(self._toggle_panel)
        self.regenerate_button.clicked.connect(self.regenerate_requested.emit)
        self.explain_button.clicked.connect(self.default_requested.emit)
        self.copy_button.clicked.connect(self._copy_text)
        self.save_button.clicked.connect(self.save_requested.emit)
        self.delete_button.clicked.connect(self.delete_requested.emit)
        self.export_button.clicked.connect(self._save_text)
        self.close_button.clicked.connect(self.close)
        self.ask_button.clicked.connect(self._submit_question)
        self.question_edit.returnPressed.connect(self._submit_question)
        self.log_clear_button.clicked.connect(self.log_view.clear)
        self.log_copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.log_view.toPlainText())
        )
        self.prompt_reset_button.clicked.connect(
            lambda: self.prompt_edit.setPlainText(DEFAULT_PROMPT_TEMPLATE)
        )
        self.prompt_save_button.clicked.connect(self._save_prompt)

    def _toggle_panel(self, shown):
        self.bottom_panel.setVisible(shown)
        self.panel_toggle_button.setText(
            "로그·프롬프트 ▾" if shown else "로그·프롬프트 ▸"
        )
        delta = self._PANEL_HEIGHT + 8
        self.resize(self.width(), self.height() + (delta if shown else -delta))

    def _save_prompt(self):
        text = self.prompt_edit.toPlainText().strip()
        self.prompt_saved.emit(text)
        self.bottom_panel.setTabText(1, "기본 프롬프트 ✓")
        QTimer.singleShot(2000, lambda: self.bottom_panel.setTabText(1, "기본 프롬프트"))

    def set_prompt(self, text):
        self.prompt_edit.setPlainText(
            text.strip() if text and text.strip() else DEFAULT_PROMPT_TEMPLATE
        )

    def set_log_entries(self, entries):
        self.log_view.setPlainText("\n".join(entries))
        self.log_view.moveCursor(self.log_view.textCursor().MoveOperation.End)

    def append_log_line(self, line):
        bar = self.log_view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self.log_view.appendPlainText(line)
        if at_bottom:
            self.log_view.moveCursor(self.log_view.textCursor().MoveOperation.End)

    def _submit_question(self):
        text = self.question_edit.text().strip()
        if text:
            self.question_submitted.emit(text)

    def _set_busy(self, busy):
        for widget in (self.regenerate_button, self.explain_button, self.ask_button,
                       self.question_edit, self.copy_button, self.save_button,
                       self.delete_button, self.export_button):
            widget.setEnabled(not busy)

    def _set_has_result(self, has_result):
        for widget in (self.regenerate_button, self.copy_button, self.save_button, self.export_button):
            widget.setEnabled(has_result)

    def prepare(self, reference, passage, saved_note=None):
        """답변 없이 대기 상태로 연다. 사용자가 '기본 설명' 또는 직접 질문을 선택한다.
        saved_note 가 있으면 그 해설을 바로 보여준다."""
        self.reference_label.setText(reference)
        self.status_label.setText("")
        self.question_edit.clear()
        self._set_busy(False)
        self.delete_button.setVisible(bool(saved_note))
        self.delete_button.setEnabled(bool(saved_note))
        if saved_note:
            self._raw_text = saved_note
            try:
                self.browser.setMarkdown(saved_note)
            except Exception:
                self.browser.setPlainText(saved_note)
            self.status_label.setText("저장된 해설")
            self._set_has_result(True)
        else:
            self._raw_text = ""
            body = (passage.strip() + "\n\n---\n\n") if passage and passage.strip() else ""
            self.browser.setMarkdown(
                body + "**[기본 설명]** 버튼을 누르거나, 아래 칸에 이 본문에 대한 질문을 입력하세요."
            )
            self._set_has_result(False)
        self.show()
        self.raise_()
        self.activateWindow()
        self.question_edit.setFocus()

    def mark_saved(self):
        self.status_label.setText("구절에 저장됨")
        self.delete_button.setVisible(True)
        self.delete_button.setEnabled(True)

    def mark_deleted(self):
        self.status_label.setText("저장된 해설을 삭제했습니다")
        self.delete_button.setVisible(False)

    def start(self, reference):
        self.reference_label.setText(reference)
        self.status_label.setText("생성 중…  (응답이 없으면 최대 2분 후 자동 중단)")
        self.browser.setPlainText("잠시만 기다려 주세요. Gemini가 답변을 준비하고 있습니다…")
        self._set_busy(True)
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
        self._set_busy(False)
        self._set_has_result(True)
        self.question_edit.clear()

    def show_error(self, message):
        self.status_label.setText("오류")
        self.browser.setPlainText(message)
        self._set_busy(False)
        self._set_has_result(False)

    def _copy_text(self):
        QApplication.clipboard().setText(self._raw_text or self.browser.toPlainText())

    def _save_text(self):
        content = self._raw_text or self.browser.toPlainText()
        if not content.strip():
            return
        reference = self.reference_label.text().strip() or "AI 설명"
        safe = re.sub(r'[\\/:*?"<>|]+', "_", reference)[:80].strip() or "AI 설명"
        base_dir = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.isdir(base_dir):
            base_dir = os.path.expanduser("~")
        default_path = os.path.join(base_dir, f"{safe}.md")
        path, selected = QFileDialog.getSaveFileName(
            self, "AI 설명 저장", default_path,
            "마크다운 (*.md);;텍스트 (*.txt);;모든 파일 (*)",
        )
        if not path:
            return
        if selected.startswith("텍스트") and not os.path.splitext(path)[1]:
            path += ".txt"
        elif not os.path.splitext(path)[1]:
            path += ".md"
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(f"# {reference}\n\n{content}\n")
        except OSError as error:
            QMessageBox.warning(self, "저장 실패", f"파일을 저장하지 못했습니다:\n{error}")
            return
        self.status_label.setText(f"저장됨: {os.path.basename(path)}")


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
