# build_uyghur_btx.py
"""bible-story 프로젝트의 위구르어 성경 JSON을 이 앱의 .btx 형식으로 변환합니다.

원본: <SOURCE_ROOT>/content/bible/uygara/*.json, .../uygcyr/*.json
출력: bible_data/uUYGAra.btx, bible_data/uUYGCyr.btx

각 .btx 줄 형식: "NN C:V 본문" (NN = 2자리 책 번호). 본문이 없는 절은
위치 정렬을 위해 빈 문자열로 채웁니다. heading(소제목)이 있으면 "<소제목>"
줄을 해당 절 앞에 넣습니다.

※ 원본(eBible Mukeddes Kalam)은 각 장 마지막 절 뒤에 그 장의 각주/해설
   블록이 붙어 있다(파서가 제거하지 못함). "책이름 < 장번호 >" 머리말이나
   각주 기호(◼ ◘ ◙)로 시작하므로 그 지점부터 잘라낸다.
"""
import json
import os
import re
from collections import Counter

# 해설 블록의 확실한 시작 표지: 각주 기호(◼ ◘ ◙), 저작권(©), "< 장번호 >" 마커.
NOTE_MARK_RE = re.compile(r"[◼◘◙©]|<\s*\d+\s*>")
# 양방향 서식 제어문자(원문에 섞여 있음)
BIDI_RE = re.compile(r"[​-‏‪-‮⁦-⁩]")
# 실제 절 본문은 문장부호(닫는 인용부호 » 는 선택적으로 동반)로 끝난다.
# 여기에 » 를 단독으로 넣으면 "«1»" 같은 표기까지 본문으로 남으므로 넣지 않는다.
SENT_END_RE = re.compile(r"^(.*[.!?…؟؛;]»?)", re.DOTALL)
# 책이름 앞뒤에 붙는 «1» «2» 같은 표기 (문자열 끝)
GUILLEMET_NUM_RE = re.compile(r"(?:\s*[«»‹›]\s*\d+\s*[«»‹›])+\s*$")


def guess_book_name(chapters):
    """각 장 마지막 절의 "… <책이름> < 장번호 >" 패턴에서 위구르어 책이름을 추정한다."""
    counter = Counter()
    for chapter in chapters.values():
        verses = chapter.get("verses") or []
        if not verses:
            continue
        raw = BIDI_RE.sub("", verses[-1])
        mark = NOTE_MARK_RE.search(raw)
        if not mark:
            continue
        head = GUILLEMET_NUM_RE.sub("", raw[: mark.start()])
        cut = max((head.rfind(p) for p in ".!?…؟؛:"), default=-1)
        words = head[cut + 1:].split()
        for size in (1, 2):
            if len(words) >= size:
                counter[" ".join(words[-size:])] += 1
    if not counter:
        return None
    max_count = max(counter.values())
    # 같은 빈도라면 더 긴(단어 수 많은) 후보 = 실제 책이름
    return max(
        (name for name, cnt in counter.items() if cnt == max_count),
        key=len,
    )


def strip_notes(text, book_name=None):
    """절 본문 뒤에 붙은 장 각주/해설 블록을 제거한다.

    원문 구조: "[실제 절 본문]. [소제목?] [책이름] < 장번호 > ◼각주…".
    1) 확실한 해설 표지에서 자르고,
    2) 그 앞에 남은 책이름/소제목 잡음을 마지막 문장부호 기준으로 다시 자른다.
       (잘리는 양이 100자를 넘으면 진짜 본문일 수 있으므로 보존)
    3) 문장부호로 못 자른 경우엔 뒤에 붙은 책이름/«n» 표기만 떼어낸다.
    """
    if not text:
        return text
    mark = NOTE_MARK_RE.search(text)
    if not mark:
        return text
    head = BIDI_RE.sub("", text[: mark.start()])
    head = GUILLEMET_NUM_RE.sub("", head).rstrip()

    tail_end = SENT_END_RE.match(head)
    if tail_end and (len(head) - len(tail_end.group(1))) <= 100:
        return tail_end.group(1).rstrip()

    # 문장부호로 못 자른 경우: 뒤에 붙은 책이름/«n» 표기만 떼어낸다.
    for _ in range(2):
        if book_name and head.endswith(book_name):
            head = head[: -len(book_name)].rstrip()
        head = GUILLEMET_NUM_RE.sub("", head).rstrip()
    return head

SOURCE_ROOT = r"C:\web\bible-story"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "bible_data")

# 개신교 정경 순서(1~66)에 맞춘 book_id 목록. 위구르어 JSON 파일명과 일치.
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
BOOK_NUM = {book_id: f"{index + 1:02d}" for index, book_id in enumerate(BOOK_IDS)}


def convert_version(version_id, output_filename):
    source_dir = os.path.join(SOURCE_ROOT, "content", "bible", version_id)
    if not os.path.isdir(source_dir):
        print(f"건너뜀: '{source_dir}' 폴더가 없습니다.")
        return

    lines = []
    book_count = 0
    verse_count = 0

    for book_id in BOOK_IDS:
        path = os.path.join(source_dir, f"{book_id}.json")
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        book_num = BOOK_NUM[book_id]
        book_count += 1
        book_name = guess_book_name(data["chapters"])

        for chapter_str, chapter in sorted(data["chapters"].items(), key=lambda item: int(item[0])):
            verses = [strip_notes(v, book_name) for v in chapter.get("verses", [])]
            verse_numbers = chapter.get("verseNumbers") or list(range(1, len(verses) + 1))

            # 시편 표제(superscription)를 절 1로 세느냐 마느냐 때문에 일부 편에서
            # 번호가 2(또는 2·3)만 건너뛴 채 뒤로 밀려 있다. 시편에 한해, 본문 개수와
            # 번호 개수가 같고 빠진 번호가 정확히 {2} 또는 {2,3} 이면(3만 빠진 것은
            # 실제 절 병합이므로 제외) 표제 번호매김 잡음으로 보고 1..n 으로 재정렬한다.
            if book_id == "psalms" and len(verses) == len(verse_numbers) and verse_numbers:
                missing = set(range(1, max(verse_numbers) + 1)) - set(verse_numbers)
                if missing in ({2}, {2, 3}):
                    verse_numbers = list(range(1, len(verses) + 1))

            text_by_number = {int(num): (verses[i] if i < len(verses) else "") for i, num in enumerate(verse_numbers)}
            headings_by_verse = {}
            for heading in chapter.get("headings", []) or []:
                headings_by_verse.setdefault(int(heading["beforeVerse"]), []).append(heading["text"])

            last = max(text_by_number) if text_by_number else 0
            for verse_num in range(1, last + 1):
                for heading_text in headings_by_verse.get(verse_num, []):
                    cleaned = " ".join(str(heading_text).split())
                    if cleaned:
                        lines.append(f"<{cleaned}>")
                text = " ".join(str(text_by_number.get(verse_num, "")).split())
                lines.append(f"{book_num} {chapter_str}:{verse_num} {text}")
                verse_count += 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    with open(output_path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")

    print(f"{output_filename}: {book_count}권 / {verse_count}절 -> {output_path}")


def main():
    convert_version("uygara", "uUYGAra.btx")
    convert_version("uygcyr", "uUYGCyr.btx")


if __name__ == "__main__":
    main()
