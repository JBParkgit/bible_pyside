# bible_database.py
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class BibleDatabase:
    """성경 하이라이트 및 메모를 관리하는 데이터베이스 클래스"""
    
    def __init__(self, db_path='bible_data.db'):
        self.db_path = db_path
        self.initialize_database()
    
    def get_connection(self):
        """데이터베이스 연결 반환"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        return conn
    
    def initialize_database(self):
        """데이터베이스 초기화 및 스키마 생성"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 스키마 버전 관리 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 하이라이트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS highlights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                color TEXT DEFAULT '#fff9c4',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book, chapter, verse)
            )
        ''')
        
        # 메모 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_highlights_book_chapter 
            ON highlights(book, chapter)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_highlights_verse 
            ON highlights(book, chapter, verse)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_memos_book_chapter 
            ON memos(book, chapter)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_memos_verse 
            ON memos(book, chapter, verse)
        ''')
        
        # 스키마 버전 확인 및 업데이트
        cursor.execute('SELECT MAX(version) FROM schema_version')
        result = cursor.fetchone()
        current_version = result[0] if result[0] else 0
        
        if current_version < 1:
            cursor.execute('INSERT INTO schema_version (version) VALUES (1)')
        
        conn.commit()
        conn.close()
    
    # ========== 하이라이트 관련 메서드 ==========
    
    def add_highlight(self, book: str, chapter: int, verse: int, color: str = '#fff9c4') -> bool:
        """하이라이트 추가"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO highlights (book, chapter, verse, color, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (book, chapter, verse, color))
            conn.commit()
            return True
        except Exception as e:
            print(f"하이라이트 추가 오류: {e}")
            return False
        finally:
            conn.close()
    
    def remove_highlight(self, book: str, chapter: int, verse: int) -> bool:
        """하이라이트 제거"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                DELETE FROM highlights 
                WHERE book = ? AND chapter = ? AND verse = ?
            ''', (book, chapter, verse))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"하이라이트 제거 오류: {e}")
            return False
        finally:
            conn.close()
    
    def toggle_highlight(self, book: str, chapter: int, verse: int, color: str = '#fff9c4') -> bool:
        """하이라이트 토글 (있으면 제거, 없으면 추가)"""
        if self.is_highlighted(book, chapter, verse):
            return self.remove_highlight(book, chapter, verse)
        else:
            return self.add_highlight(book, chapter, verse, color)
    
    def get_highlights(self, book: str = None, chapter: int = None) -> List[Dict]:
        """하이라이트 조회"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if book and chapter:
                cursor.execute('''
                    SELECT book, chapter, verse, color, created_at, updated_at
                    FROM highlights
                    WHERE book = ? AND chapter = ?
                    ORDER BY verse
                ''', (book, chapter))
            elif book:
                cursor.execute('''
                    SELECT book, chapter, verse, color, created_at, updated_at
                    FROM highlights
                    WHERE book = ?
                    ORDER BY chapter, verse
                ''', (book,))
            else:
                cursor.execute('''
                    SELECT book, chapter, verse, color, created_at, updated_at
                    FROM highlights
                    ORDER BY book, chapter, verse
                ''')
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"하이라이트 조회 오류: {e}")
            return []
        finally:
            conn.close()
    
    def is_highlighted(self, book: str, chapter: int, verse: int) -> bool:
        """특정 구절이 하이라이트되어 있는지 확인"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM highlights
                WHERE book = ? AND chapter = ? AND verse = ?
            ''', (book, chapter, verse))
            result = cursor.fetchone()
            return result['count'] > 0
        except Exception as e:
            print(f"하이라이트 확인 오류: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_highlights(self) -> List[Dict]:
        """모든 하이라이트 조회"""
        return self.get_highlights()
    
    def get_highlight_color(self, book: str, chapter: int, verse: int) -> Optional[str]:
        """특정 구절의 하이라이트 색상 반환"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT color
                FROM highlights
                WHERE book = ? AND chapter = ? AND verse = ?
            ''', (book, chapter, verse))
            result = cursor.fetchone()
            return result['color'] if result else None
        except Exception as e:
            print(f"하이라이트 색상 조회 오류: {e}")
            return None
        finally:
            conn.close()
    
    # ========== 메모 관련 메서드 ==========
    
    def save_memo(self, book: str, chapter: int, content: str, verse: int = None) -> bool:
        """메모 저장 (절이 None이면 장 전체 메모)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 기존 메모 확인
            if verse is None:
                cursor.execute('''
                    SELECT id FROM memos
                    WHERE book = ? AND chapter = ? AND verse IS NULL
                ''', (book, chapter))
            else:
                cursor.execute('''
                    SELECT id FROM memos
                    WHERE book = ? AND chapter = ? AND verse = ?
                ''', (book, chapter, verse))
            
            existing = cursor.fetchone()
            
            if existing:
                # 업데이트
                if verse is None:
                    cursor.execute('''
                        UPDATE memos
                        SET content = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE book = ? AND chapter = ? AND verse IS NULL
                    ''', (content, book, chapter))
                else:
                    cursor.execute('''
                        UPDATE memos
                        SET content = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE book = ? AND chapter = ? AND verse = ?
                    ''', (content, book, chapter, verse))
            else:
                # 삽입
                cursor.execute('''
                    INSERT INTO memos (book, chapter, verse, content)
                    VALUES (?, ?, ?, ?)
                ''', (book, chapter, verse, content))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"메모 저장 오류: {e}")
            return False
        finally:
            conn.close()
    
    def get_memo(self, book: str, chapter: int, verse: int = None) -> Optional[str]:
        """메모 조회"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if verse is None:
                cursor.execute('''
                    SELECT content FROM memos
                    WHERE book = ? AND chapter = ? AND verse IS NULL
                ''', (book, chapter))
            else:
                cursor.execute('''
                    SELECT content FROM memos
                    WHERE book = ? AND chapter = ? AND verse = ?
                ''', (book, chapter, verse))
            
            result = cursor.fetchone()
            return result['content'] if result else None
        except Exception as e:
            print(f"메모 조회 오류: {e}")
            return None
        finally:
            conn.close()
    
    def delete_memo(self, book: str, chapter: int, verse: int = None) -> bool:
        """메모 삭제"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if verse is None:
                cursor.execute('''
                    DELETE FROM memos
                    WHERE book = ? AND chapter = ? AND verse IS NULL
                ''', (book, chapter))
            else:
                cursor.execute('''
                    DELETE FROM memos
                    WHERE book = ? AND chapter = ? AND verse = ?
                ''', (book, chapter, verse))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"메모 삭제 오류: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_memos(self, book: str = None, chapter: int = None) -> List[Dict]:
        """모든 메모 조회"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if book and chapter:
                cursor.execute('''
                    SELECT id, book, chapter, verse, content, created_at, updated_at
                    FROM memos
                    WHERE book = ? AND chapter = ?
                    ORDER BY verse NULLS LAST
                ''', (book, chapter))
            elif book:
                cursor.execute('''
                    SELECT id, book, chapter, verse, content, created_at, updated_at
                    FROM memos
                    WHERE book = ?
                    ORDER BY chapter, verse NULLS LAST
                ''', (book,))
            else:
                cursor.execute('''
                    SELECT id, book, chapter, verse, content, created_at, updated_at
                    FROM memos
                    ORDER BY book, chapter, verse NULLS LAST
                ''')
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"메모 조회 오류: {e}")
            return []
        finally:
            conn.close()
    
    def search_memos(self, keyword: str) -> List[Dict]:
        """메모 내용 검색"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, book, chapter, verse, content, created_at, updated_at
                FROM memos
                WHERE content LIKE ?
                ORDER BY book, chapter, verse NULLS LAST
            ''', (f'%{keyword}%',))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"메모 검색 오류: {e}")
            return []
        finally:
            conn.close()
    
    # ========== 통계 관련 메서드 ==========
    
    def get_highlight_statistics(self) -> Dict:
        """하이라이트 통계"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 전체 하이라이트 개수
            cursor.execute('SELECT COUNT(*) as total FROM highlights')
            total = cursor.fetchone()['total']
            
            # 책별 하이라이트 개수
            cursor.execute('''
                SELECT book, COUNT(*) as count
                FROM highlights
                GROUP BY book
                ORDER BY count DESC
            ''')
            by_book = [dict(row) for row in cursor.fetchall()]
            
            # 장별 하이라이트 개수 (상위 10개)
            cursor.execute('''
                SELECT book, chapter, COUNT(*) as count
                FROM highlights
                GROUP BY book, chapter
                ORDER BY count DESC
                LIMIT 10
            ''')
            by_chapter = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total': total,
                'by_book': by_book,
                'top_chapters': by_chapter
            }
        except Exception as e:
            print(f"하이라이트 통계 오류: {e}")
            return {'total': 0, 'by_book': [], 'top_chapters': []}
        finally:
            conn.close()
    
    def get_memo_statistics(self) -> Dict:
        """메모 통계"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 전체 메모 개수
            cursor.execute('SELECT COUNT(*) as total FROM memos')
            total = cursor.fetchone()['total']
            
            # 책별 메모 개수
            cursor.execute('''
                SELECT book, COUNT(*) as count
                FROM memos
                GROUP BY book
                ORDER BY count DESC
            ''')
            by_book = [dict(row) for row in cursor.fetchall()]
            
            # 장 메모 vs 절 메모 개수
            cursor.execute('SELECT COUNT(*) as count FROM memos WHERE verse IS NULL')
            chapter_memos = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM memos WHERE verse IS NOT NULL')
            verse_memos = cursor.fetchone()['count']
            
            return {
                'total': total,
                'by_book': by_book,
                'chapter_memos': chapter_memos,
                'verse_memos': verse_memos
            }
        except Exception as e:
            print(f"메모 통계 오류: {e}")
            return {'total': 0, 'by_book': [], 'chapter_memos': 0, 'verse_memos': 0}
        finally:
            conn.close()
    
    # ========== 내보내기/가져오기 ==========
    
    def export_to_json(self, file_path: str) -> bool:
        """데이터를 JSON 파일로 내보내기"""
        import json
        try:
            data = {
                'highlights': self.get_all_highlights(),
                'memos': self.get_all_memos()
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"내보내기 오류: {e}")
            return False
    
    def import_from_json(self, file_path: str) -> bool:
        """JSON 파일에서 데이터 가져오기"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 하이라이트 가져오기
            if 'highlights' in data:
                for highlight in data['highlights']:
                    cursor.execute('''
                        INSERT OR REPLACE INTO highlights 
                        (book, chapter, verse, color, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        highlight['book'],
                        highlight['chapter'],
                        highlight['verse'],
                        highlight.get('color', '#fff9c4'),
                        highlight.get('created_at', datetime.now().isoformat()),
                        highlight.get('updated_at', datetime.now().isoformat())
                    ))
            
            # 메모 가져오기
            if 'memos' in data:
                for memo in data['memos']:
                    cursor.execute('''
                        INSERT OR REPLACE INTO memos 
                        (book, chapter, verse, content, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        memo['book'],
                        memo['chapter'],
                        memo.get('verse'),
                        memo['content'],
                        memo.get('created_at', datetime.now().isoformat()),
                        memo.get('updated_at', datetime.now().isoformat())
                    ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"가져오기 오류: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
