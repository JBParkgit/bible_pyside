# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

물댄동산 성경 (Mooldan Dongsang Bible Viewer) - A Korean Bible study desktop application built with Python and PySide6. Features multiple Bible translations, commentary, cross-references, search, highlighting, memos, and verse collections.

## Build and Run Commands

```bash
# Install dependencies
pip install PySide6==6.9.0 qdarktheme pywin32

# Pre-process Bible data for faster loading (optional, converts .btx to .pkl)
python preprocess.py

# Run the application
python main.py

# Build executable with PyInstaller
pyinstaller waterdbible.spec
```

## Architecture

### Core Components

**MainWindow (`main.py`)** - Central coordinator with toolbar and 7-tab interface:
- Composite Tab (통합) - Integrated commentary + crossref + Bible
- Read Tab (읽기) - Main reading with 1-4 split views
- Search Tab (검색) - Full-text search
- Commentary Tab (주석) - Hochma commentary
- CrossRef Tab (관주) - Cross-references
- Memo Tab (메모) - Note-taking
- Original Language Tab (원어) - Strong's-number Hebrew/Greek view (`original_language_tab.py`); needs a `strongs/` data folder, degrades gracefully without it

**SharedBibleView (`bible_view.py`)** - Reusable Bible text display widget used across all tabs. Supports verse clicking, reference parsing, copy formatting, and multi-instance coordination. Clicking verses selects a range and opens the selection action bar (copy / compare / original-language / AI-explain / highlight-color).

**RTL translations** - Some translations (e.g. `위구르어_아랍문자`) render right-to-left. Direction/language metadata comes from `BibleDataLoader._get_translation_metadata`; `html_utils.py` applies the layout. `build_uyghur_btx.py` converts the `bible-story` project's Uyghur JSON into `bible_data/*.btx`.

### Data Layer

**`data_loaders.py`** - Three data loaders:
- `BibleDataLoader` - Loads 20+ translations from `.btx`/`.pkl` files in `bible_data/`
- `CommentaryDataLoader` - Loads Hochma commentary from `add/Hochma.txt`
- `CrossrefDataLoader` - Loads cross-references from `add/Cross_ref.txt`

**`bible_database.py`** - SQLite persistence for highlights and memos with tables: `highlights`, `memos`, `schema_version`

### Data Flow

```
User Action → Tab Signal → MainWindow Handler → Data Loaders → .btx/.pkl files
                                              → BibleDatabase (SQLite) for highlights/memos
                                              → SharedBibleView display
```

### Settings

User preferences stored in `settings.json`:
- Current book/chapter, font settings, theme
- Translation selections per view
- Verse display mode (0: "(창1:1)", 1: "창1:1", 2: "1.") — chosen via the toolbar `verse_style_combo`
- `gemini_api_key` / `gemini_model` / `gemini_prompt` — for the AI verse-explanation feature (`gemini_prompt` empty ⇒ use `DEFAULT_PROMPT_TEMPLATE`)

### Theming (`ui_theme.py`)

Modern MS Office / Fluent look. Only **Light** and **Dark** exist (the old Sepia / Gray themes were retired; any stored `Sepia`/`Gray` value migrates via `resolve_mode()` — Gray→Dark, Sepia→Light). `ui_theme.py` holds:
- `TOKENS["light"|"dark"]` — design tokens (accent, surfaces, borders, text, fills, radii).
- `office_qss(mode)` — one comprehensive app-wide QSS string, layered on top of `qdarktheme.setup_theme(theme, corner_shape="rounded", custom_colors=..., additional_qss=office_qss(mode))`.
- `themed_icon(name, color)` — renders `assets/icons/<name>.svg` (the `COLOR` placeholder is swapped for `color`) into a multi-size `QIcon`.

`MainWindow.apply_theme()` is now token-driven: it sets the palette, clears the old per-widget stylesheets (global QSS covers toolbar/tabs/menus/scrollbars/dialogs), calls `_refresh_toolbar_icons()`, and pushes the mode to HTML-rendering views (`SharedBibleView._selected_verse_color`/`_verse_num_color`, `OriginalLanguageTab.set_theme_mode`). Objects the QSS targets by name: `QToolBar#mainToolBar`, `QFrame#viewControlBar` / `#subCommandBar`, `QFrame#selectionBar`, `QFrame#mainFrame`, `QPushButton#AddTabButton`, `QFrame#vsep`. Button roles via dynamic properties: `primary="true"` (accent fill), `subtle="true"`, `compact="true"` (tiny +/- buttons — kills padding), `iconButton="true"` (toolbar icon squares).

### Appearance / body-text typography (`body_style.py`, `body_style_dialog.py`)

**설정 및 추출 → 본문 및 글꼴 설정...** opens `BodyStyleDialog` — the merged font + body-text dialog (the old separate "폰트 및 글자 크기 설정" `FontSettingsDialog` was removed). Left: **글꼴** (`QFontComboBox` family, 성경 본문 크기, 주석·관주 크기 — one size for commentary/crossref/composite instead of the old 5 sliders) and **본문 모양** (행간, 절 간격, 절 번호 크기·색, 소제목 정렬·강조색, 본문 여백). Right: live preview of the current passage. `저장` emits `applied(dict)` → `MainWindow._apply_appearance`: pops `font_family` (→ `apply_global_font`), `bible_font_size` (→ `sync_font_size`), `aux_font_size` (→ commentary/crossref/composite setters); the rest are body-style keys pushed to every `SharedBibleView.apply_body_style()` and persisted as flat `body_*` keys (defaults in `DEFAULT_BODY_STYLE`). `SharedBibleView.update_content()` reads `self.body_style` for line-height / verse spacing / verse-number size / subtitle style, and `document().setDocumentMargin()` for the page margin. Body font family is just the app-wide `font_family` (no separate serif toggle).

### AI verse explanation (`ai_explain.py`)

The selection action bar's **설명** button (and the text context menu's "이 절 AI 해설" / "선택 범위 AI 해설") opens a reusable non-modal `AiExplanationDialog` for the selected verse range. It does **not** answer immediately — the user chooses **기본 설명** or types their own question. `DEFAULT_PROMPT_TEMPLATE` frames the model as a seminary-professor-level evangelical exegete. The dialog has a **bottom `QTabWidget` panel** (toggle with the 로그·프롬프트 button): **통신 로그** (`GeminiClient.log_line` appended live — no separate window) and **기본 프롬프트** (edit + `프롬프트 저장` → `prompt_saved` → `MainWindow._save_ai_prompt` persists `gemini_prompt`). The API key (free, https://aistudio.google.com/apikey) is set via **설정 및 추출 → AI 설명 설정 (Gemini)** (also model + a second copy of the prompt editor). Calls are async via `QNetworkAccessManager` (`GeminiClient`) with auto-retry on transient (429/503) errors; no extra dependency (QtNetwork ships with PySide6).

Results can be saved: **구절에 저장** writes to `bible_data.db` `ai_notes` (keyed by book/chapter/start_verse/end_verse); **파일로…** exports a `.md`/`.txt`. Verses with a saved note show a 💬 marker in the reading view (`ai:<start>-<end>` anchor); clicking it reopens that saved explanation. `SharedBibleView.request_ai_explanation(reference, passage, translation, book, chapter, start, end)` → `MainWindow.request_ai_explanation_for_selection`.

## Key Patterns

- **Signal/Slot Architecture**: All inter-widget communication via PySide6 signals
- **Lazy Loading with Pickle Caching**: Translations cached as `.pkl` for fast startup
- **Multi-Instance Views**: Multiple SharedBibleView instances can display different translations
- **Korean UI**: All labels and strings in Korean

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| F2-F5, F7, F10, F11 | Switch tabs (F6/편집 removed; F7 = 메모, F11 = 원어) |
| F8/F9 | Previous/Next chapter |
| Ctrl+F8/F9 | History navigation |
| Ctrl+D | Focus navigation input |
| Ctrl+F | Focus search |
| Ctrl+H | Toggle highlight |
| Ctrl+W | Send to Word |
| Ctrl+P | Send to PowerPoint |

## Data Files

- `bible_data/*.btx` - Bible translation text files
- `bible_data/*.pkl` - Cached pickle versions (auto-generated)
- `add/Hochma.txt` - Commentary data
- `add/Cross_ref.txt` - Cross-reference data
