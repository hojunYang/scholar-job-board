import concurrent.futures
import json
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import crawler
import discover_sources
import llm
from sources import load_sources


class DiscoveryTests(unittest.TestCase):
    def test_only_official_public_urls_are_candidates(self):
        clean=discover_sources.official_url
        self.assertEqual(clean('http://ase.skku.edu/ase/notice.do;JSESSIONID=secret?mode=list&article.offset=10#top'), 'https://ase.skku.edu/ase/notice.do')
        for value in ['https://skku.edu.evil.test/notice','https://evilskku.edu/notice','javascript:alert(1)','https://ase.skku.edu:8443/notice','https://ase.skku.edu/a.pdf','https://ase.skku.edu/ase/notice.do?mode=view&articleNo=1']:
            self.assertIsNone(clean(value))
        self.assertEqual(clean('?bo_table=notice','https://pharm.skku.edu/bbs/board.php'),'https://pharm.skku.edu/bbs/board.php?bo_table=notice')

    def test_category_views_consolidate_without_losing_source_ids(self):
        boards=[{'id':'enc','url':'https://enc.skku.edu/enc/notice.do'}, {'id':'enc-category','url':'https://enc.skku.edu/enc/notice.do?boardId=1'}]
        merged=discover_sources.consolidate_sources(boards)
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0]['replaces'],['enc-category'])

    def test_directory_uses_actual_homepage_links(self):
        html='<a href="https://ase.skku.edu/"><img alt="홈페이지"></a><a href="https://evil.test"><img alt="홈페이지"></a>'
        self.assertEqual(discover_sources.directory_sites(html,'https://www.skku.edu/')[0]['url'],'https://ase.skku.edu/')
        self.assertEqual(len(discover_sources.directory_sites(html,'https://www.skku.edu/')),1)

    def test_shared_cms_aliases_are_not_counted_as_extra_boards(self):
        self.assertEqual(discover_sources.board_key('https://cse.skku.edu/cse/notice.do'),discover_sources.board_key('https://skb.skku.edu/cse/notice.do'))
        self.assertEqual(discover_sources.board_key('https://enc.skku.edu/enc/notice.do?boardId=138879'),discover_sources.board_key('https://enc.skku.edu/enc/notice.do'))
        self.assertNotEqual(discover_sources.board_key('https://cse.skku.edu/cse/notice.do'),discover_sources.board_key('https://cse.skku.edu/cse/notice_grad.do'))

    def test_thumbnail_notice_list_and_confirmed_empty_board(self):
        html='<dl class="board-thumb-content-wrap"><dt><a href="?mode=view&articleNo=1">안내</a></dt></dl>'
        self.assertEqual(crawler.parse_notice_list(html,'https://ase.skku.edu/notice.do')[0]['article_no'],1)
        self.assertEqual(crawler.parse_notice_list('<title>공지사항 게시판목록</title><p>등록된 글이 없습니다.</p>','https://ase.skku.edu/notice.do'),[])
        with self.assertRaises(ValueError):crawler.parse_notice_list('<title>오류</title><p>로그인 필요</p>','https://ase.skku.edu/notice.do')

    def test_gnuboard_list_and_detail(self):
        html='<ol class="bo_lst"><li><a href="?bo_table=notice&wr_id=2"><article class="bo_info"><h2><span class="category notice">공지</span>새 공지</h2><p>2026-11-12</p></article></a></li></ol>'
        row=crawler.parse_notice_list(html,'https://pharm.skku.edu/bbs/board.php?bo_table=notice')[0]
        self.assertEqual(row['article_no'],'gnu:notice:2')
        self.assertEqual(row['title'],'새 공지')
        detail='<h2 id="bo_v_title"><span class="bo_v_tit"><span>새 공지</span></span></h2><div id="bo_v_con">학부 재학생 대상</div>'
        self.assertEqual(crawler.parse_notice_detail(detail,row['url'])['title'],'새 공지')

    def test_legacy_and_route_notice_templates(self):
        nano='<table><tr><td><a href="?tbl=bbs42&mode=VIEW&num=470">장학생 모집</a></td><td>2026-10-28</td></tr></table>'
        row=crawler.parse_notice_list(nano,'https://nano.skku.edu/bbs/board.php?tbl=bbs42')[0]
        self.assertEqual(row['article_no'],'legacy:bbs42:470')
        html='<div class="conbody"><table><tr><td><strong>장학생 모집</strong></td></tr></table><div id="DivContents">학부 1~4학년</div></div>'
        self.assertEqual(crawler.parse_notice_detail(html,row['url'])['full_text'],'학부 1~4학년')
        route='<ul><li><a href="/board/notice/1196"><span class="leading-snug">참가자 모집</span><time>2026-11-06</time></a></li></ul>'
        row=crawler.parse_notice_list(route,'https://does.skku.edu/board/notice')[0]
        self.assertEqual(row['article_no'],'route:notice:1196')
        detail='<article><header><h1>참가자 모집</h1></header><img src="/poster.png"><div class="board-body"></div></article>'
        parsed=crawler.parse_notice_detail(detail,row['url'])
        self.assertTrue(parsed['has_images'])
        self.assertIn('이미지 공지',parsed['full_text'])

    def test_retired_source_duplicates_remain_in_storage_but_not_board_view(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(crawler,'DB_PATH',directory+'/test.db'):
            db=crawler.get_db_connection()
            for id in [1000000001,1000000002]:
                db.execute("INSERT INTO jobs (id,target_audience,organizer,deadline,benefit,category,title,full_text) VALUES (?,'학부','대학','미정','혜택','기타','공지','원문')",(id,))
            db.execute("INSERT INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url) VALUES ('cse-undergraduate',1,1000000001,'job','https://cse.skku.edu/post1')")
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notices').fetchone()[0],1)
            db.close()

    def test_concurrent_crossposts_share_one_card(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(crawler,'DB_PATH',directory+'/test.db'):
            boards={b['id']:b for b in load_sources()}
            detail=dict(title='근로학생 모집',full_text='지원대상: 학부 재학생\n휴학생 불가',source_url='https://cse.skku.edu/notice',attachments=[])
            result=dict(organizer='대학',target_audience='학부 재학생',benefits='시급 11000원',schedule={},category='기타',main_category='근로·알바·학생조교',subcategory='교내근로',needs_review=False,classification_evidence=['근로학생 모집'])
            barrier=threading.Barrier(2)
            def complete(*args):barrier.wait(timeout=10);return result
            def save(board):return crawler.save_to_db([dict(article_no=1,title=detail['title'],url=board['url'],detail=detail)],'jobs','job',board=board,download_files=False)
            with patch.object(crawler.CompletionExecutor,'execute',side_effect=complete):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    counts=list(pool.map(save,[boards['cse-undergraduate'],boards['sw-undergraduate']]))
            self.assertEqual(sum(counts),1)
            db=crawler.get_db_connection()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notices').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notice_origins').fetchone()[0],2)
            db.close()


class RateLimitTests(unittest.TestCase):
    def test_429_waits_for_reset_and_retries(self):
        limited=Mock(status_code=429,headers={'x-ratelimit-reset-tokens':'1s'})
        success=Mock(status_code=200,headers={})
        success.json.return_value={'result':{'message':{'content':'{"ok":true}'}}}
        executor=llm.CompletionExecutor('https://example.test','key','request')
        with patch.object(llm,'_remaining_tokens',None),patch.object(llm,'_remaining_requests',None),patch.object(llm,'_reset_at',0),patch.object(llm,'_pause') as pause,patch('llm.requests.post',side_effect=[limited,success]) as post:
            result=executor._complete({},[])
            self.assertTrue(result['ok']);self.assertEqual(post.call_count,2);pause.assert_called_once()

    def test_low_token_budget_waits_before_calling_provider(self):
        response=Mock(status_code=200,headers={})
        response.json.return_value={'result':{'message':{'content':'{"ok":true}'}}}
        with patch.object(llm,'_remaining_tokens',1),patch.object(llm,'_remaining_requests',10),patch.object(llm,'_reset_at',llm.time.monotonic()+10),patch.object(llm,'_pause') as pause,patch('llm.requests.post',return_value=response):
            llm.CompletionExecutor('https://example.test','key','request')._complete({},[])
            pause.assert_called_once()
