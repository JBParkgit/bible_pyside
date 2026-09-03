# data_loaders.py
import os
import re
import json
import pickle
from collections import deque

class BibleDataLoader:
    def __init__(self, base_data_path="bible_data"):
        self.base_data_path = base_data_path
        self.all_translation_data = {}
        self.book_definitions = [
            ('01', '창', '창세기'), ('02', '출', '출애굽기'), ('03', '레', '레위기'),
            ('04', '민', '민수기'), ('05', '신', '신명기'), ('06', '수', '여호수아'),
            ('07', '삿', '사사기'), ('08', '룻', '룻기'), ('09', '삼상', '사무엘상'),
            ('10', '삼하', '사무엘하'), ('11', '왕상', '열왕기상'), ('12', '왕하', '열왕기하'),
            ('13', '대상', '역대기상'), ('14', '대하', '역대기하'), ('15', '스', '에스라'),
            ('16', '느', '느헤미야'), ('17', '더', '에스더'), ('18', '욥', '욥기'),
            ('19', '시', '시편'), ('20', '잠', '잠언'), ('21', '전', '전도서'),
            ('22', '아', '아가'), ('23', '사', '이사야'), ('24', '렘', '예레미야'),
            ('25', '애', '예레미야애가'), ('26', '겔', '에스겔'), ('27', '단', '다니엘'),
            ('28', '호', '호세아'), ('29', '욜', '요엘'), ('30', '암', '아모스'),
            ('31', '옵', '오바댜'), ('32', '욘', '요나'), ('33', '미', '미가'),
            ('34', '나', '나훔'), ('35', '합', '하박국'), ('36', '습', '스바냐'),
            ('37', '학', '학개'), ('38', '슥', '스가랴'), ('39', '말', '말라기'),
            ('40', '마', '마태복음'), ('41', '막', '마가복음'), ('42', '눅', '누가복음'),
            ('43', '요', '요한복음'), ('44', '행', '사도행전'), ('45', '롬', '로마서'),
            ('46', '고전', '고린도전서'), ('47', '고후', '고린도후서'), ('48', '갈', '갈라디아서'),
            ('49', '엡', '에베소서'), ('50', '빌', '빌립보서'), ('51', '골', '골로새서'),
            ('52', '살전', '데살로니가전서'), ('53', '살후', '데살로니가후서'), ('54', '딤전', '디모데전서'),
            ('55', '딤후', '디모데후서'), ('56', '딛', '디도서'), ('57', '몬', '빌레몬서'),
            ('58', '히', '히브리서'), ('59', '약', '야고보서'), ('60', '벧전', '베드로전서'),
            ('61', '벧후', '베드로후서'), ('62', '요일', '요한일서'), ('63', '요이', '요한이서'),
            ('64', '요삼', '요한삼서'), ('65', '유', '유다서'), ('66', '계', '요한계시록')
        ]
        self.book_order_map = {num: full for num, abbr, full in self.book_definitions}
        self.book_abbr_map = {abbr: full for num, abbr, full in self.book_definitions}
        self.full_name_to_abbr_map = {full: abbr for num, abbr, full in self.book_definitions}
        self.book_alias_map = self._create_book_alias_map()
        self.full_book_names = {}
        for alias, full_name in self.book_alias_map.items():
            self.full_book_names[alias] = full_name
        for num, abbr, full_name in self.book_definitions:
            self.full_book_names[num] = full_name
            self.full_book_names[abbr] = full_name
            self.full_book_names[full_name] = full_name
        self.numbered_full_book_names = {full: f"{num}{full}" for num, abbr, full in self.book_definitions}

        # 언어별 성경책 전체 이름 (book_definitions 순서: 01 창세기 … 66 요한계시록)
        _english_full_names = [
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
            "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
            "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
            "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
            "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
            "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
            "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
            "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
            "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
        ]
        _chinese_full_names = [
            "創世記", "出埃及記", "利未記", "民數記", "申命記", "約書亞記", "士師記", "路得記",
            "撒母耳記上", "撒母耳記下", "列王紀上", "列王紀下", "歷代志上", "歷代志下", "以斯拉記",
            "尼希米記", "以斯帖記", "約伯記", "詩篇", "箴言", "傳道書", "雅歌", "以賽亞書",
            "耶利米書", "耶利米哀歌", "以西結書", "但以理書", "何西阿書", "約珥書", "阿摩司書",
            "俄巴底亞書", "約拿書", "彌迦書", "那鴻書", "哈巴谷書", "西番雅書", "哈該書",
            "撒迦利亞書", "瑪拉基書", "馬太福音", "馬可福音", "路加福音", "約翰福音", "使徒行傳",
            "羅馬書", "哥林多前書", "哥林多後書", "加拉太書", "以弗所書", "腓立比書", "歌羅西書",
            "帖撒羅尼迦前書", "帖撒羅尼迦後書", "提摩太前書", "提摩太後書", "提多書", "腓利門書",
            "希伯來書", "雅各書", "彼得前書", "彼得後書", "約翰一書", "約翰二書", "約翰三書",
            "猶大書", "啟示錄",
        ]
        # 중국어 표준 단자(單字) 약어 (和合本 관용)
        _chinese_abbrs = [
            "創", "出", "利", "民", "申", "書", "士", "得",
            "撒上", "撒下", "王上", "王下", "代上", "代下", "拉",
            "尼", "斯", "伯", "詩", "箴", "傳", "歌", "賽",
            "耶", "哀", "結", "但", "何", "珥", "摩",
            "俄", "拿", "彌", "鴻", "哈", "番", "該",
            "亞", "瑪", "太", "可", "路", "約", "徒",
            "羅", "林前", "林後", "加", "弗", "腓", "西",
            "帖前", "帖後", "提前", "提後", "多", "門",
            "來", "雅", "彼前", "彼後", "約壹", "約貳", "約參",
            "猶", "啟",
        ]
        _korean_full_names = [full for num, abbr, full in self.book_definitions]
        self.full_name_to_english_full_map = dict(zip(_korean_full_names, _english_full_names))
        self.full_name_to_chinese_full_map = dict(zip(_korean_full_names, _chinese_full_names))
        self.full_name_to_chinese_abbr_map = dict(zip(_korean_full_names, _chinese_abbrs))

        self.translation_file_map = self._get_translation_file_map()
        self.loaded_translations = {}
        self.global_book_chapter_counts = {}

    def _create_book_alias_map(self):
        mapping = {}
        self.full_name_to_english_abbr_map = {}
        book_mappings_raw = """
            GN,창,ckd,창세기
            Ex,출,cnf,출애굽기
            Lv,레,fp,레위기
            Nm,민,als,민수기
            Dt,신,tls,신명기
            Jos,수,tn,여호수아
            Jdg,삿,tkt,사사기
            Ru,룻,fnt,룻기
            1Sm,삼상,tkatkd,사무엘상
            2Sm,삼하,tkagk,사무엘하
            1Kg,왕상,dhkdtkd,열왕기상
            2Kg,왕하,dhkdgk,열왕기하
            1Ch,대상,eotkd,역대기상
            2Ch,대하,eogk,역대기하
            Ezr,스,tm,에스라
            Neh,느,sm,느헤미야
            Est,더,ej,에스더
            Jb,욥,dhq,욥기
            Ps,시,tl,시편
            Pr,잠,wka,잠언
            Ec,전,wjs,전도서
            Sg,아,dk,아가
            Is,사,tk,이사야
            Jr,렘,fpa,예레미야
            Lm,애,do,예레미야애가
            Ezk,겔,rpf,에스겔
            Dn,단,eks,다니엘
            Hs,호,gh,호세아
            Jl,욜,dyf,요엘
            Am,암,dka,아모스
            Ob,옵,dhq,오바댜
            Jnh,욘,dys,요나
            Mc,미,al,미가
            Nah,나,sk,나훔
            Hab,합,하박국
            Zph,습,tmq,스바냐
            Hg,학,gkr,학개
            Zch,슥,스가랴
            Mal,말,akf,말라기
            Mt,마,ak,마태복음
            Mk,막,akr,마가복음
            Lk,눅,snr,누가복음
            Jn,요,dy,요한복음
            Ac,행,god,사도행전
            Rm,롬,fha,로마서
            1Co,고전,rhwjs,고린도전서
            2Co,고후,rhgn,고린도후서
            Gl,갈,rkf,갈라디아서
            Eph,엡,dpq,에베소서
            Php,빌,qlf,빌립보서
            Col,골,rhf,골로새서
            1Th,살전,tkfwjs,데살로니가전서
            2Th,살후,tkfgn,데살로니가후서
            1Tm,딤전,elawjs,디모데전서
            2Tm,딤후,elagn,디모데후서
            Ti,딛,ele,디도서
            Phm,몬,ahs,빌레몬서
            Heb,히,gl,히브리서
            Jms,약,dir,야고보서
            1Pt,벧전,qpewjs,베드로전서
            2Pt,벧후,qpegn,베드로후서
            1Jn,요일,dydlf,요한일서
            2Jn,요이,dydl,요한이서
            3Jn,요삼,dytka,요한삼서
            Jd,유,db,유다서
            Rv,계,rP,요한계시록
        """.strip().split('\n')
        for line in book_mappings_raw:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) == 4:
                english_abbr, korean_abbr, phonetic_korean, full_korean_name = parts
            elif len(parts) == 3:
                english_abbr, korean_abbr, full_korean_name = parts
                phonetic_korean = None
            else:
                continue
            self.full_name_to_english_abbr_map[full_korean_name] = english_abbr
            mapping[english_abbr.lower()] = full_korean_name
            mapping[korean_abbr.lower()] = full_korean_name
            if phonetic_korean:
                mapping[phonetic_korean.lower()] = full_korean_name
            mapping[full_korean_name.lower()] = full_korean_name
            mapping[english_abbr] = full_korean_name
            mapping[korean_abbr] = full_korean_name
            mapping[full_korean_name] = full_korean_name
        return mapping

    def get_book_abbr(self, full_name, translation_name=None, language=None):
        """번역본 언어에 맞는 성경책 약어를 돌려준다.
        영어 번역본이면 영어 약어(Gen, Jn ...), 중국어면 단자 약어(創, 約 ...),
        그 외에는 한글 약어(창, 요 ...).
        """
        if language is None and translation_name:
            try:
                language = self.load_translation_data(translation_name).get('language', 'unknown')
            except Exception:
                language = 'unknown'
        if language == 'english':
            return self.full_name_to_english_abbr_map.get(
                full_name, self.full_name_to_abbr_map.get(full_name, full_name))
        if language == 'chinese':
            return self.full_name_to_chinese_abbr_map.get(
                full_name, self.full_name_to_abbr_map.get(full_name, full_name))
        return self.full_name_to_abbr_map.get(full_name, full_name)

    def get_book_full_name(self, full_name, translation_name=None, language=None):
        """번역본 언어에 맞는 성경책 전체 이름을 돌려준다.
        영어 번역본이면 'Genesis', 중국어 번역본이면 '創世記', 그 외에는 한글 이름 그대로.
        `full_name` 은 한글 전체 이름(예: '창세기').
        """
        if language is None and translation_name:
            try:
                language = self.load_translation_data(translation_name).get('language', 'unknown')
            except Exception:
                language = 'unknown'
        if language == 'english':
            return self.full_name_to_english_full_map.get(full_name, full_name)
        if language == 'chinese':
            return self.full_name_to_chinese_full_map.get(full_name, full_name)
        return full_name

    def _get_translation_file_map(self):
        translation_map = {}
        if os.path.exists(self.base_data_path):
            file_info = """
            개역개정,kNKRV.btx
            개역한글,kHRV.btx
            새번역,kNRSV.btx
            새번역_각주,kNRSV_footnote.btx
            공동번역개정,kNKCB.btx
            개역개정_국한문,cNKRV.btx
            개역한글_국한문,cHRV.btx
            바른성경,kKTV.btx
            쉬운말성경,kEasym.btx
            쉬운성경,kEASY.btx
            가톨릭성경,kCath.btx
            우리말성경,kDOB.btx
            킹제임스흠정역,kHKJV.btx
            한글킹제임스,kKKJV.btx
            현대인의 성경,kKLB.btx
            ESV,eESV.btx
            GNT,eGNT.btx
            HCSB,eHCSB.btx
            KJV,eKJV.btx
            MSG,eMSG.btx
            ISV,eISV.btx
            NIV2011,eNIV2011.btx
            NIV1984,eNIV1984.btx
            NASB,eNASB.btx
            NKJV,eNKJV.btx
            NLT,eNLT.btx
            NRSV,eNRSV.btx
            中文和合本,CUV.btx
            위구르어_키릴문자,uUYGCyr.btx
            위구르어_아랍문자,uUYGAra.btx
            """.strip().split('\n')
            for line in file_info:
                parts = line.strip().split(',')
                if len(parts) != 2:
                    continue
                translation_name, filename = parts
                btx_path = os.path.join(self.base_data_path, filename)
                pkl_path = os.path.join(self.base_data_path, os.path.splitext(filename)[0] + '.pkl')
                if os.path.exists(pkl_path):
                    translation_map[translation_name] = pkl_path
                elif os.path.exists(btx_path):
                    translation_map[translation_name] = btx_path
        return translation_map

    def _get_translation_metadata(self, translation_name, base_filename):
        metadata = {
            "uUYGCyr": {"language": "uyghur_cyrillic", "direction": "ltr"},
            "uUYGAra": {"language": "uyghur_arabic", "direction": "rtl"},
        }
        if base_filename in metadata:
            return metadata[base_filename]

        language = "unknown"
        if base_filename.startswith("k"):
            language = "korean"
        elif base_filename.startswith("e"):
            language = "english"
        elif base_filename.startswith("C"):
            language = "chinese"

        return {"language": language, "direction": "ltr"}

    def load_translation_data(self, translation_name):
        if translation_name in self.loaded_translations:
            return self.loaded_translations[translation_name]

        btx_filepath = self.translation_file_map.get(translation_name)
        if not btx_filepath:
            if self.translation_file_map:
                default_translation_name = list(self.translation_file_map.keys())[0]
                print(f"경고: '{translation_name}' 번역본 파일을 찾을 수 없습니다. 기본 '{default_translation_name}'으로 대체합니다.")
                btx_filepath = self.translation_file_map.get(default_translation_name)
                if not btx_filepath:
                     raise ValueError(f"기본 번역본 파일도 찾을 수 없습니다.")
            else:
                raise ValueError(f"사용 가능한 번역본 파일이 없습니다.")

        base_filename = os.path.splitext(os.path.basename(btx_filepath))[0]
        pkl_filepath = os.path.join(self.base_data_path, f"{base_filename}.pkl")

        metadata = self._get_translation_metadata(translation_name, base_filename)
        language = metadata["language"]
        direction = metadata["direction"]


        if os.path.exists(pkl_filepath):
            try:
                with open(pkl_filepath, 'rb') as f:
                    result = pickle.load(f)
                    result['language'] = result.get('language', language)
                    result['direction'] = result.get('direction', direction)
                    self.loaded_translations[translation_name] = result
                    self.global_book_chapter_counts = result["book_chapter_counts"]
                    return result
            except Exception as e:
                print(f"경고: 전처리된 '{os.path.basename(pkl_filepath)}' 파일 로딩 실패({e}). 원본 텍스트 파일로 다시 시도합니다.")

        print(f"알림: 원본 텍스트 파일 '{os.path.basename(btx_filepath)}'을(를) 로딩합니다. preprocess.py를 실행하면 시작 속도가 향상됩니다.")

        bible_data = {}
        book_chapter_counts = {}

        known_headers = ["개역개정", "개역한글", "새번역", "새번역_각주", "공동번역개정", "개역개정_국한문", "개역한글_국한문",
                         "바른성경", "쉬운말성경", "쉬운성경", "가톨릭성경", "우리말성경",
                         "킹제임스흠정역", "한글킹제임스", "현대인의 성경",
                         "ESV", "GNT", "HCSB", "KJV", "MSG", "ISV",
                         "NIV2011", "NIV1984", "NASB", "NKJV", "NLT", "NRSV",
                         "中文和合本"]

        try:
            with open(btx_filepath, 'r', encoding='utf-8-sig') as f:
                subtitle_buffer = []
                for original_line in f:
                    line = original_line.strip()
                    line = line.lstrip('\ufeff')
                    if not line or line in known_headers:
                        continue

                    if re.match(r'^<\s*(.+?)\s*>$', line):
                        subtitle_buffer.append(line)
                        continue

                    match = re.match(r'(\d{2})\s*(\d+):(\d+)\s*(.*)', line)
                    if match:
                        parsed_book_num_str, parsed_chapter_str, _, verse_text = match.groups()
                        inferred_book_name = self.book_order_map.get(parsed_book_num_str)

                        if not inferred_book_name:
                            print(f"경고: 알 수 없는 책 번호: '{parsed_book_num_str}' (원문: {line}) - 건너김")
                            subtitle_buffer.clear()
                            continue

                        chapter_list = bible_data.setdefault(inferred_book_name, {}).setdefault(parsed_chapter_str, [])

                        if subtitle_buffer:
                            chapter_list.extend(subtitle_buffer)
                            subtitle_buffer.clear()

                        chapter_list.append(verse_text)

                        current_max_chapter = book_chapter_counts.get(inferred_book_name, 0)
                        book_chapter_counts[inferred_book_name] = max(current_max_chapter, int(parsed_chapter_str))

            for full_name in self.book_order_map.values():
                if full_name not in bible_data: bible_data[full_name] = {}
                if full_name not in book_chapter_counts or book_chapter_counts[full_name] == 0:
                    book_chapter_counts[full_name] = 1

            result = {
                "bible_data": bible_data,
                "book_chapter_counts": book_chapter_counts,
                "language": language,
                "direction": direction,
            }
            self.loaded_translations[translation_name] = result
            self.global_book_chapter_counts = book_chapter_counts
            return result
        except FileNotFoundError:
            raise FileNotFoundError(f"'{btx_filepath}' 파일을 찾을 수 없습니다.")
        except Exception as e:
            raise Exception(f"'{translation_name}' 로딩 중 오류: {e}")

    def get_available_translations(self):
        return list(self.translation_file_map.keys())

    def get_verse_text(self, translation_name, book_name, chapter_num, verse_num):
        try:
            data = self.load_translation_data(translation_name)
            bible_data = data["bible_data"]

            chapter_content = bible_data.get(book_name, {}).get(str(chapter_num), [])

            verses_only = [v for v in chapter_content if not re.match(r'<\s*(.+?)\s*>', v)]

            if 0 <= verse_num - 1 < len(verses_only):
                return verses_only[verse_num - 1]
            else:
                return None
        except (KeyError, IndexError):
            return None
        except Exception as e:
            print(f"구절 텍스트 로드 중 오류 발생 ({translation_name}, {book_name} {chapter_num}:{verse_num}): {e}")
            return None

    def parse_reference(self, ref_string):
        """'요3:16'과 같은 문자열을 (책, 장, 절) 튜플로 변환합니다."""
        text = ref_string.strip().lower()
        # 공백이 있는 경우 (예: 창 1:1)와 없는 경우(예: 창1:1) 모두 처리
        
        # --- 수정된 부분 시작 ---
        # 수정 전 정규식: match = re.match(r'([a-zA-Z0-9가-힣]+)\s*(\d+)(?:\s*:\s*(\d+))?', text)
        # '창10' 입력 시 '창10' 전체를 책 이름으로 인식하는 문제 해결을 위해
        # 책 이름 부분의 탐욕적(greedy) 매칭을 비탐욕적(non-greedy)으로 변경합니다.
        # [a-zA-Z0-9가-힣]+ -> [a-zA-Z0-9가-힣]+?
        match = re.match(r'([a-zA-Z0-9가-힣]+?)\s*(\d+)(?:\s*:\s*(\d+))?', text)
        # --- 수정된 부분 끝 ---
        
        if not match:
            return None, None, None

        book_query, chapter_str, verse_str = match.groups()
        
        # 정의된 모든 별칭에서 책 전체 이름 찾기
        book_name = self.full_book_names.get(book_query, self.book_alias_map.get(book_query))
        
        if not book_name:
            return None, None, None
            
        chapter_num = int(chapter_str)
        verse_num = int(verse_str) if verse_str else None
        
        return book_name, chapter_num, verse_num


class CommentaryDataLoader:
    def __init__(self, base_data_path="add"):
        self.base_data_path = base_data_path
        self.commentary_file = os.path.join(self.base_data_path, "Hochma.txt")
        self.loaded_commentary_data = {}
        self.book_num_to_full_name = {}

    def set_book_definitions(self, book_definitions):
        self.book_num_to_full_name = {num: full for num, abbr, full in book_definitions}

    def load_commentary_data(self):
        if self.loaded_commentary_data:
            return self.loaded_commentary_data

        pkl_file = os.path.join(self.base_data_path, "Hochma.pkl")
        if os.path.exists(pkl_file):
            try:
                with open(pkl_file, 'rb') as f:
                    self.loaded_commentary_data = pickle.load(f)
                    return self.loaded_commentary_data
            except Exception as e:
                print(f"경고: 전처리된 '{os.path.basename(pkl_file)}' 파일 로딩 실패({e}). 원본 텍스트 파일로 다시 시도합니다.")

        if os.path.exists(self.commentary_file):
             print(f"알림: 원본 텍스트 파일 '{os.path.basename(self.commentary_file)}'을(를) 로딩합니다. preprocess.py를 실행하면 시작 속도가 향상됩니다.")

        commentary_data = {}
        try:
            with open(self.commentary_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split(';', 3)

                    if len(parts) == 4:
                        book_num_str, chapter_num_str, verse_num_str, commentary_part = parts
                        commentary_text = commentary_part.rstrip('; \t\n\r')
                    else:
                        print(f"경고: 주석 파일 형식 오류 감지: {line}")
                        continue

                    full_book_name = self.book_num_to_full_name.get(book_num_str)
                    if not full_book_name:
                        print(f"경고: 알 수 없는 책 번호 '{book_num_str}' (주석 파일: {line.strip()}) - 건너김")
                        continue

                    chapter_num = int(chapter_num_str)
                    verse_num = int(verse_num_str)

                    commentary_data.setdefault(full_book_name, {}) \
                                   .setdefault(chapter_num, {}) \
                                   .setdefault(verse_num, []).append(commentary_text.strip())

            self.loaded_commentary_data = commentary_data
            return self.loaded_commentary_data

        except FileNotFoundError:
            print(f"주석 파일 '{self.commentary_file}'을 찾을 수 없습니다. 주석 탭 기능이 제한됩니다.")
            return {}
        except Exception as e:
            import traceback
            print(f"주석 파일 로딩 중 오류 발생: {e}\n{traceback.format_exc()}")
            return {}


class CrossrefDataLoader:
    def __init__(self, base_data_path="add"):
        self.base_data_path = base_data_path
        self.crossref_file = os.path.join(self.base_data_path, "Cross_ref.txt")
        self.loaded_crossref_data = {}
        self.book_abbr_to_full_name = {}
        self.full_name_to_abbr = {}

    def set_book_definitions(self, book_definitions):
        self.book_abbr_to_full_name = {abbr: full for num, abbr, full in book_definitions}
        self.full_name_to_abbr = {full: abbr for num, abbr, full in book_definitions}

    def load_crossref_data(self):
        if self.loaded_crossref_data:
            return self.loaded_crossref_data

        pkl_file = os.path.join(self.base_data_path, "Cross_ref.pkl")
        if os.path.exists(pkl_file):
            try:
                with open(pkl_file, 'rb') as f:
                    self.loaded_crossref_data = pickle.load(f)
                    return self.loaded_crossref_data
            except Exception as e:
                print(f"경고: 전처리된 '{os.path.basename(pkl_file)}' 파일 로딩 실패({e}). 원본 텍스트 파일로 다시 시도합니다.")

        if os.path.exists(self.crossref_file):
            print(f"알림: 원본 텍스트 파일 '{os.path.basename(self.crossref_file)}'을(를) 로딩합니다. preprocess.py를 실행하면 시작 속도가 향상됩니다.")

        crossref_data = {}
        try:
            with open(self.crossref_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split(';', 4)
                    if len(parts) == 5:
                        book_num_str, chapter_num_str, verse_num_str, base_ref, cross_refs_str = parts

                        book_name = self.book_abbr_to_full_name.get(base_ref.split(' ')[0])
                        if not book_name:
                            print(f"경고: 알 수 없는 책 약어 '{base_ref.split(' ')[0]}' (관주 파일: {line.strip()}) - 건너김")
                            continue

                        chapter_num = int(chapter_num_str)
                        verse_num = int(verse_num_str)

                        parsed_cross_refs = []
                        for ref_part in cross_refs_str.split('.'):
                            ref_part = ref_part.strip()
                            if not ref_part: continue

                            match = re.match(r'([가-힣A-Za-z]+)\s*(\d+):(\d+)(?:-(\d+))?', ref_part)
                            if match:
                                ref_book_abbr, ref_chapter_str, ref_verse_start_str, ref_verse_end_str = match.groups()

                                ref_full_book_name = self.book_abbr_to_full_name.get(ref_book_abbr)
                                if not ref_full_book_name:
                                    print(f"경고: 알 수 없는 관주 책 약어 '{ref_book_abbr}' (관주 파일: {line.strip()}) - 건너김")
                                    continue

                                ref_chapter = int(ref_chapter_str)
                                ref_verse_start = int(ref_verse_start_str)
                                ref_verse_end = int(ref_verse_end_str) if ref_verse_end_str else ref_verse_start

                                for v in range(ref_verse_start, ref_verse_end + 1):
                                    parsed_cross_refs.append((ref_full_book_name, ref_chapter, v))
                            else:
                                print(f"경고: 잘못된 관주 형식 '{ref_part}' (원문: {line.strip()})")

                        crossref_data.setdefault(book_name, {}) \
                                     .setdefault(chapter_num, {}) \
                                     .setdefault(verse_num, []).extend(parsed_cross_refs)

            self.loaded_crossref_data = crossref_data
            return self.loaded_crossref_data

        except FileNotFoundError:
            print(f"관주 파일 '{self.crossref_file}'을 찾을 수 없습니다. 관주 탭 기능이 제한됩니다.")
            return {}
        except Exception as e:
            import traceback
            print(f"관주 파일 로딩 중 오류 발생: {e}\n{traceback.format_exc()}")
            return {}
