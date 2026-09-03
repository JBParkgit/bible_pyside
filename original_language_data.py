import json
from collections import Counter
from pathlib import Path


BOOK_IDS = [
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges", "ruth",
    "1samuel", "2samuel", "1kings", "2kings", "1chronicles", "2chronicles", "ezra", "nehemiah",
    "esther", "job", "psalms", "proverbs", "ecclesiastes", "songofsongs", "isaiah", "jeremiah",
    "lamentations", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah",
    "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi", "matthew", "mark",
    "luke", "john", "acts", "romans", "1corinthians", "2corinthians", "galatians", "ephesians",
    "philippians", "colossians", "1thessalonians", "2thessalonians", "1timothy", "2timothy",
    "titus", "philemon", "hebrews", "james", "1peter", "2peter", "1john", "2john", "3john",
    "jude", "revelation",
]


class OriginalLanguageDataLoader:
    def __init__(self, bible_data_loader, base_path="strongs"):
        self.bible_data_loader = bible_data_loader
        self.base_path = Path(base_path)
        self.kjv_path = self.base_path / "kjv"
        self.original_path = self.base_path / "original"
        self.lexicon_path = self.base_path / "lexicon.json"
        self.korean_path = self.base_path / "korean.json"

        self.book_id_to_name = {}
        self.book_name_to_id = {}
        for book_id, definition in zip(BOOK_IDS, self.bible_data_loader.book_definitions):
            _, _, full_name = definition
            self.book_id_to_name[book_id] = full_name
            self.book_name_to_id[full_name] = book_id

        self._book_cache = {}
        self._lexicon_cache = None
        self._usage_cache = {}

    def is_available(self):
        return (
            self.kjv_path.is_dir()
            and self.original_path.is_dir()
            and self.lexicon_path.exists()
        )

    def get_book_id(self, book_name):
        return self.book_name_to_id.get(book_name)

    def _read_json(self, path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _load_book(self, collection, book_id):
        cache_key = (collection, book_id)
        if cache_key not in self._book_cache:
            base = self.kjv_path if collection == "kjv" else self.original_path
            path = base / f"{book_id}.json"
            self._book_cache[cache_key] = self._read_json(path) if path.exists() else None
        return self._book_cache[cache_key]

    def _summarize_tokens(self, tokens):
        summary = {}
        for token in tokens or []:
            text = token.get("text", "")
            for code in token.get("strongs", []) or []:
                item = summary.setdefault(code, {"code": code, "count": 0, "words": []})
                item["count"] += 1
                if text and text not in item["words"]:
                    item["words"].append(text)
        return summary

    def get_chapter(self, book_name, chapter):
        if not self.is_available():
            return None

        book_id = self.get_book_id(book_name)
        if not book_id:
            return None

        kjv_book = self._load_book("kjv", book_id)
        original_book = self._load_book("original", book_id)
        if not kjv_book:
            return None

        # chapters 는 {"1": {...}, "2": {...}} 형태의 dict 이고, verse 는 number 필드를 가진다.
        kjv_chapter = (kjv_book.get("chapters") or {}).get(str(int(chapter)))
        if not kjv_chapter:
            return None

        original_chapters = (original_book.get("chapters") or {}) if original_book else {}
        original_chapter = original_chapters.get(str(int(chapter))) or {}

        original_by_verse = {
            item.get("number"): item
            for item in original_chapter.get("verses", [])
            if item.get("number") is not None
        }

        default_language = (original_book or {}).get("language", "")
        default_direction = (original_book or {}).get("direction", "ltr")

        chapter_counts = Counter()
        verses = []

        for kjv_verse in kjv_chapter.get("verses", []):
            verse_number = kjv_verse.get("number")
            original_verse = original_by_verse.get(verse_number, {})
            kjv_tokens = kjv_verse.get("tokens", []) or []
            original_tokens = original_verse.get("tokens", []) or []

            strongs = self._summarize_tokens(kjv_tokens)
            original_summary = self._summarize_tokens(original_tokens)
            for code, item in original_summary.items():
                if code not in strongs:
                    strongs[code] = item
                else:
                    for word in item["words"]:
                        if word not in strongs[code]["words"]:
                            strongs[code]["words"].append(word)
                    strongs[code]["count"] += item["count"]

            for code, item in strongs.items():
                chapter_counts[code] += item["count"]

            hrv_text = self.bible_data_loader.get_verse_text("개역한글", book_name, chapter, verse_number)

            verses.append({
                "number": verse_number,
                "kjvText": kjv_verse.get("text", ""),
                "kjvTokens": kjv_tokens,
                "hrvText": hrv_text,
                "originalLanguage": original_verse.get("language", default_language),
                "originalDirection": original_verse.get("direction", default_direction),
                "originalTokens": original_tokens,
                "strongs": sorted(strongs.values(), key=lambda item: item["code"]),
            })

        for verse in verses:
            for item in verse["strongs"]:
                item["chapterCount"] = chapter_counts[item["code"]]

        return {
            "book": book_name,
            "bookId": book_id,
            "chapter": chapter,
            "verses": verses,
        }

    def get_lexicon(self):
        if self._lexicon_cache is None:
            lexicon = self._read_json(self.lexicon_path) if self.lexicon_path.exists() else {}
            korean = self._read_json(self.korean_path) if self.korean_path.exists() else {}
            for code, korean_entry in korean.items():
                merged = dict(lexicon.get(code, {"code": code}))
                merged.update(korean_entry)
                lexicon[code] = merged
            self._lexicon_cache = lexicon
        return self._lexicon_cache

    def get_lexicon_entry(self, code):
        return self.get_lexicon().get(code)

    def get_strong_usage(self, code):
        if code in self._usage_cache:
            return self._usage_cache[code]

        usages = []
        total = 0
        if not self.kjv_path.is_dir():
            return {"total": 0, "items": usages}

        for path in sorted(self.kjv_path.glob("*.json")):
            book_id = path.stem
            book = self._read_json(path)
            book_name = self.book_id_to_name.get(book_id, book.get("name", book_id))
            for chapter_key, chapter in (book.get("chapters") or {}).items():
                try:
                    chapter_number = int(chapter_key)
                except (TypeError, ValueError):
                    continue
                for verse in chapter.get("verses", []):
                    count = 0
                    for token in verse.get("tokens", []) or []:
                        count += (token.get("strongs", []) or []).count(code)
                    if count:
                        total += count
                        usages.append({
                            "book": book_name,
                            "chapter": chapter_number,
                            "verse": verse.get("number"),
                            "text": verse.get("text", ""),
                            "count": count,
                        })

        result = {"total": total, "items": usages}
        self._usage_cache[code] = result
        return result
