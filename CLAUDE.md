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

**MainWindow (`main.py`)** - Central coordinator with toolbar and 8-tab interface:
- Composite Tab (통합) - Integrated commentary + crossref + Bible
- Read Tab (읽기) - Main reading with 1-4 split views
- Search Tab (검색) - Full-text search
- Commentary Tab (주석) - Hochma commentary
- CrossRef Tab (관주) - Cross-references
- Verse Collection Tab (편집) - User verse collections
- Memo Tab (메모) - Note-taking
- Original Language Tab (원어) - Strong's-number Hebrew/Greek view (`original_language_tab.py`); needs a `strongs/` data folder, degrades gracefully without it

**SharedBibleView (`bible_view.py`)** - Reusable Bible text display widget used across all tabs. Supports verse clicking, reference parsing, copy formatting, and multi-instance coordination. Clicking verses selects a range and opens the selection action bar (copy / share / compare / original-language / highlight-color).

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

### AI verse explanation (`ai_explain.py`)

The selection action bar's **설명** button (and the text context menu's "이 절 AI 해설" / "선택 범위 AI 해설") sends the selected verses to the Google Gemini API and shows a markdown explanation in a reusable non-modal `AiExplanationDialog`. The user supplies their own free API key (https://aistudio.google.com/apikey) via **설정 및 추출 → AI 설명 설정 (Gemini)**, where they can also pick the model and **edit the prompt template** (`{reference}` `{passage}` `{translation}` placeholders; "기본값으로" resets). Calls are async via `QNetworkAccessManager` (`GeminiClient`) with auto-retry on transient (429/503/overloaded) errors; no extra dependency (QtNetwork ships with PySide6). `SharedBibleView.request_ai_explanation(reference, passage, translation)` → `MainWindow.request_ai_explanation_for_selection`; verse text is built by `SharedBibleView.emit_ai_explanation_for(verse_numbers)`.

## Key Patterns

- **Signal/Slot Architecture**: All inter-widget communication via PySide6 signals
- **Lazy Loading with Pickle Caching**: Translations cached as `.pkl` for fast startup
- **Multi-Instance Views**: Multiple SharedBibleView instances can display different translations
- **Korean UI**: All labels and strings in Korean

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| F2-F7, F10, F11 | Switch tabs (F11 = 원어) |
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
