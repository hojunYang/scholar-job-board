import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import crawler
from sources import load_sources, find_origin, register_sources


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / 'test.db'
        self.db_patch = patch.object(crawler, 'DB_PATH', str(self.db_path))
        self.db_patch.start()
        self.boards = {b['id']: b for b in load_sources()}
        self.result = dict(organizer='학생지원팀', target_audience='학부 재학생', benefits='시급 11000원',
                           schedule={'deadline': None}, category='교내장학', main_category='근로·알바·학생조교',
                           subcategory='교내근로', classification_reason='학생의 근로 업무 모집',
                           classification_evidence=['근로학생 모집'], needs_review=False)

    def tearDown(self):
        self.db_patch.stop()
        self.directory.cleanup()

    def import_notice(self, board, article=2, body='지원대상: 학부 재학생\n휴학생 불가', has_images=False):
        notice = dict(article_no=article, title='근로학생 모집', url=board['url']+f'?mode=view&articleNo={article}')
        detail = dict(title=notice['title'], full_text=body, source_url=notice['url'], attachments=[], has_images=has_images)
        with patch.object(crawler, 'get_notice_detail', return_value=detail), \
             patch.object(crawler.CompletionExecutor, 'execute', return_value=self.result) as llm:
            count = crawler.save_to_db([notice], 'jobs', 'job', board=board, download_files=False)
        return count, llm.call_count

    def test_article_numbers_do_not_collide_across_sources(self):
        self.import_notice(self.boards['skku-main'])
        self.import_notice(self.boards['cse-undergraduate'], body='지원대상: 대학원 재학생\n휴학생 불가')
        self.import_notice(self.boards['sw-undergraduate'], body='지원대상: 학부 3학년 재학생\n휴학생 불가')
        with sqlite3.connect(self.db_path) as db:
            ids = [row[0] for row in db.execute('SELECT notice_id FROM notice_origins WHERE article_no=2')]
            self.assertEqual(len(set(ids)), 3)
            self.assertIn(2, ids)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notice_eligibility').fetchone()[0], 3)
        self.assertEqual(self.import_notice(self.boards['cse-undergraduate']), (0, 0))

    def test_main_board_reuses_scholarship_only_rows_and_merges_old_sources(self):
        db=crawler.get_db_connection()
        db.execute("INSERT INTO scholarships (id,target_audience,organizer,deadline,benefit,category,title,full_text) VALUES (42,'학부 재학생','대학교','미정','장학금','기타','기존 장학','원문')")
        db.execute("INSERT INTO notice_boards VALUES ('skku-scholarships','성균관대학교',NULL,NULL,'이전 장학','https://www.skku.edu/old')")
        db.execute("INSERT INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url) VALUES ('skku-scholarships',42,42,'scholarship','https://www.skku.edu/old?articleNo=42')")
        db.commit();db.close()
        self.assertEqual(self.import_notice(self.boards['skku-main'],article=42),(0,0))
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs WHERE id=42').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT notice_type FROM notice_origins WHERE board_id='skku-main' AND article_no=42").fetchone()[0],'scholarship')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM notice_boards WHERE id='skku-scholarships'").fetchone()[0],0)
            self.assertEqual(db.execute('SELECT title FROM scholarships WHERE id=42').fetchone()[0],'기존 장학')

    def test_consolidated_category_source_retains_its_notices(self):
        db=crawler.get_db_connection()
        db.execute("INSERT INTO jobs (id,target_audience,organizer,deadline,benefit,category,title,full_text) VALUES (99,'학부','대학','미정','지원','기타','카테고리 공지','원문')")
        db.execute("INSERT INTO notice_boards VALUES ('category-alias','성균관대학교',NULL,NULL,'학사 탭','https://enc.skku.edu/enc/notice.do?boardId=1')")
        db.execute("INSERT INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url) VALUES ('category-alias','notice99',99,'job','https://enc.skku.edu/post99')")
        board={**self.boards['enc-undergraduate'],'replaces':['category-alias']}
        register_sources(db,[board])
        row=db.execute("SELECT notice_id,source_url FROM notice_origins WHERE board_id=? AND article_no='notice99'",(board['id'],)).fetchone()
        self.assertEqual(tuple(row),(99,'https://enc.skku.edu/post99'))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM notice_boards WHERE id='category-alias'").fetchone()[0],0)
        self.assertEqual(db.execute('SELECT title FROM jobs WHERE id=99').fetchone()[0],'카테고리 공지')
        db.close()

    def test_exact_crosspost_retains_sources_without_duplicate_card_or_llm(self):
        self.import_notice(self.boards['cse-undergraduate'])
        self.assertEqual(self.import_notice(self.boards['sw-undergraduate']), (0, 0))
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notices').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notice_origins').fetchone()[0], 2)

    def test_image_posts_are_not_merged_by_their_text_alone(self):
        self.import_notice(self.boards['cse-undergraduate'], has_images=True)
        self.import_notice(self.boards['sw-undergraduate'], has_images=True)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notices').fetchone()[0], 2)

    def test_failed_attachment_download_keeps_original_link(self):
        db=crawler.get_db_connection()
        attachment=dict(source_attach_no=1,original_filename='신청서.hwp',download_url='https://cse.skku.edu/file?attachNo=1',display_order=1)
        with patch.object(crawler,'download_attachment',side_effect=ValueError('download unavailable')):
            crawler.save_notice_attachments(db.cursor(),'job',1,[attachment])
        row=db.execute('SELECT storage_path,download_url FROM notice_attachments').fetchone()
        self.assertEqual(tuple(row),('',attachment['download_url']))
        db.close()

    def test_failed_notice_is_rolled_back_and_retried(self):
        with patch.object(crawler, 'save_profile', side_effect=ValueError('invalid profile')):
            with self.assertRaises(RuntimeError): self.import_notice(self.boards['cse-undergraduate'])
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notice_origins').fetchone()[0], 0)
        self.assertEqual(self.import_notice(self.boards['cse-undergraduate']), (1, 1))

    def test_list_includes_pinned_notices_and_does_not_stop_at_ten(self):
        html = ''.join(f'<dl class="board-list-content-wrap"><dt><a href="?mode=view&amp;articleNo={i}">공지 {i}</a></dt><dd>2026-11-12</dd></dl>' for i in range(14))
        rows = crawler.parse_notice_list(html, 'https://cse.skku.edu/cse/notice.do')
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[-1]['article_no'], 13)
        self.assertEqual(rows[0]['published_at'], '2026-11-12')
        self.assertTrue(rows[0]['url'].startswith('https://cse.skku.edu/cse/notice.do?'))

    def test_item_id_boards_keep_opaque_identity(self):
        href='?mode=view&viewBoardId=138885&itemId=CFB05AE6F541E3D065FBA66E658A915B'
        self.assertEqual(crawler.extract_article_no(href), '138885:CFB05AE6F541E3D065FBA66E658A915B')
        self.assertEqual(crawler.extract_article_no(href+'ABCDEF'), crawler.extract_article_no(href+'UVWXYZ'))
        html=f'<dl class="board-list-content-wrap"><a href="{href}">공지</a></dl>'
        self.assertEqual(len(crawler.parse_notice_list(html, 'https://enc.skku.edu/enc/notice.do')), 1)
        self.import_notice(self.boards['enc-undergraduate'], article='138885:opaque')
        with sqlite3.connect(self.db_path) as db:
            self.assertIsNotNone(find_origin(db,self.boards['enc-undergraduate'],'138885:opaque'))

    def test_department_detail_title_body_and_attachment(self):
        html='''<div class="board-view-title-wrap"><h4><span>[장학]</span>장학생 모집</h4></div>
          <div class="board-view-content-wrap"><p>2학년 재학생</p><p>소득 4구간 이하</p></div>
          <ul class="filedown_list"><li><a href="?mode=download&amp;attachNo=3">신청서.hwp</a></li></ul>'''
        row=crawler.parse_notice_detail(html, 'https://cse.skku.edu/cse/notice.do?mode=view&articleNo=2')
        self.assertEqual(row['title'], '장학생 모집')
        self.assertIn('2학년 재학생\n소득 4구간 이하',row['full_text'])
        self.assertEqual(row['attachments'][0]['source_attach_no'],3)
        self.assertTrue(row['attachments'][0]['download_url'].startswith('https://cse.skku.edu/'))
        with self.assertRaises(ValueError): crawler.parse_notice_detail('<html>오류 페이지</html>', 'https://cse.skku.edu/')

    def test_image_only_notice_does_not_fabricate_body(self):
        html='<div class="board-view-title-wrap"><h4>포스터 공지</h4></div><div class="fr-view"><img src="poster.jpg"></div>'
        row=crawler.parse_notice_detail(html,'https://cse.skku.edu/cse/notice.do')
        self.assertIn('이미지 공지',row['full_text'])


if __name__ == '__main__': unittest.main()
