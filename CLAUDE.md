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
- Verse Collection Tab (편집) - User verse collections
- Memo Tab (메모) - Note-taking

**SharedBibleView (`bible_view.py`)** - Reusable Bible text display widget used across all tabs. Supports verse clicking, reference parsing, copy formatting, and multi-instance coordination.

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
- Verse display mode (0: "(창1:1)", 1: "창1:1", 2: "1.")

## Key Patterns

- **Signal/Slot Architecture**: All inter-widget communication via PySide6 signals
- **Lazy Loading with Pickle Caching**: Translations cached as `.pkl` for fast startup
- **Multi-Instance Views**: Multiple SharedBibleView instances can display different translations
- **Korean UI**: All labels and strings in Korean

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| F2-F7, F10 | Switch tabs |
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
