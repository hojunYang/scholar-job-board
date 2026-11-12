import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import crawler


class CrawlerTests(unittest.TestCase):
    def test_missing_lower_id_is_retried_and_new_fields_are_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / 'scholar.db'
            detail = dict(title='근로학생 모집', full_text='지원대상: 학부 재학생\n휴학생 불가',
                          source_url='https://example.test/notice/2', attachments=[])
            result = dict(organizer='학생지원팀', target_audience='학부 재학생', benefits='시급 11000원',
                          schedule={'deadline': None}, category='교내장학', main_category='근로·알바·학생조교',
                          subcategory='교내근로', classification_reason='학생의 근로 업무 모집',
                          classification_evidence=['근로학생 모집'], needs_review=False)
            with patch.object(crawler, 'DB_PATH', str(db_path)):
                conn = crawler.get_db_connection()
                conn.execute("INSERT INTO jobs (id,target_audience,organizer,deadline,benefit,category,title,full_text) VALUES (3,'대상','대학','미정','혜택','기타','기존 공지','본문')")
                conn.commit()
                conn.close()
                with patch.object(crawler, 'get_notice_detail', return_value=detail) as fetch, \
                     patch.object(crawler.CompletionExecutor, 'execute', return_value=result):
                    crawler.save_to_db([{'article_no': 2, 'title': detail['title'], 'url': detail['source_url']},
                                        {'article_no': 3, 'title': '기존 공지', 'url': 'https://example.test/notice/3'}],
                                       table_name='jobs', notice_type='job')
                    fetch.assert_called_once()
            with sqlite3.connect(db_path) as conn:
                row = conn.execute('SELECT main_category,subcategory,eligibility_conditions FROM jobs WHERE id=2').fetchone()
                self.assertEqual(row[:2], ('근로·알바·학생조교', '교내근로'))
                self.assertIn('휴학생 불가', row[2])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 2)
                self.assertEqual(conn.execute('SELECT source_url FROM notice_sources WHERE notice_id=2').fetchone()[0], detail['source_url'])


if __name__ == '__main__':
    unittest.main()
