import argparse
import time
from pathlib import Path
import json
import os
import re
import sqlite3
from urllib.parse import parse_qs, urljoin, urlparse, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from llm import CompletionExecutor
from classification import classification_fields
from notice_schema import ensure_notice_schema
from eligibility import extract_profile, save_profile
from sources import load_sources, register_sources, find_origin, save_origin, next_notice_id

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 경로
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'scholar.db')
ATTACHMENTS_ROOT = os.path.join(PROJECT_ROOT, 'data', 'attachments')
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def ensure_support_tables(conn):
    """첨부파일 메타 테이블 생성"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notice_sources (
            notice_type TEXT NOT NULL,
            notice_id INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            source_title TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (notice_type, notice_id)
        );

        CREATE TABLE IF NOT EXISTS notice_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_type TEXT NOT NULL,
            notice_id INTEGER NOT NULL,
            source_attach_no INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            download_url TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            mime_type TEXT,
            file_size INTEGER,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (notice_type, notice_id, source_attach_no)
        );
    """)


def get_db_connection():
    """데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    ensure_support_tables(conn)
    with conn:
        ensure_notice_schema(conn)
        register_sources(conn, [board for board in load_sources() if board['enabled']])
    return conn


def get_latest_article_no(table_name):
    """DB에서 가장 최신 articleNo 가져오기"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f'SELECT MAX(id) as max_id FROM {table_name}')
    result = cursor.fetchone()
    conn.close()

    return result['max_id'] if result['max_id'] else 0


def extract_article_no(url_or_href):
    """URL 또는 href에서 articleNo 추출"""
    parsed = urlparse(url_or_href)
    query = parse_qs(parsed.query)
    if query.get('wr_id', [''])[0].isdigit():
        return f"gnu:{query.get('bo_table',[''])[0]}:{query['wr_id'][0]}"
    if query.get('tbl') and query.get('num', [''])[0].isdigit():
        return f"legacy:{query['tbl'][0]}:{query['num'][0]}"
    route = re.fullmatch(r'/board/notice/(\d+)/?', parsed.path)
    if route:return f'route:notice:{route[1]}'
    article_no = query.get('articleNo', [None])[0]

    if not article_no:
        item_id = parse_qs(parsed.query).get('itemId', [None])[0]
        board_id = parse_qs(parsed.query).get('viewBoardId', [''])[0]
        # This CMS appends a changing six-letter token to the stable 32-hex document ID.
        stable = re.fullmatch(r'([0-9A-Fa-f]{32})[A-Z]{6}', item_id or '')
        return f'{board_id}:{stable.group(1) if stable else item_id}' if item_id else None

    try:
        return int(article_no)
    except ValueError:
        return None


def extract_attach_no(download_url):
    """다운로드 URL에서 attachNo 추출"""
    parsed = urlparse(download_url)
    attach_no = parse_qs(parsed.query).get('attachNo', [None])[0]

    if not attach_no:
        return parse_qs(parsed.query).get('fileId', [None])[0] or parse_qs(parsed.query).get('no', [None])[0]

    try:
        return int(attach_no)
    except ValueError:
        return None


def fetch_page(url):
    for attempt in range(3):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=(10, 30))
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError):
            if attempt == 2: raise
            time.sleep(attempt + 1)


def parse_notice_list(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    wraps = soup.select('dl.board-list-content-wrap, dl.board-thumb-content-wrap, .b-list-box > li, .bo_lst > li, .bo_tit, table tr')
    wraps += soup.select('a[href^="/board/notice/"]')
    notices, seen = [], set()
    for wrap in wraps:
        link = next((a for a in ([wrap] if wrap.name=='a' else wrap.select('a[href]')) if extract_article_no(a['href']) is not None
                     and (parse_qs(urlparse(a['href']).query).get('mode', [''])[0].lower() == 'view' or parse_qs(urlparse(a['href']).query).get('wr_id') or re.fullmatch(r'/board/notice/\d+/?',urlparse(a['href']).path))), None)
        if not link: continue
        article_no = extract_article_no(link['href'])
        if article_no in seen: continue
        seen.add(article_no)
        date = re.search(r'20[0-9]{2}[-.]\s*[01][0-9][-.]\s*[0-3][0-9]', wrap.get_text(' ', strip=True))
        heading=link.select_one('.bo_info h2, .leading-snug') or link
        for badge in heading.select('.category.notice'):badge.decompose()
        notices.append(dict(article_no=article_no, title=heading.get_text(' ', strip=True),
                            url=urljoin(base_url, link['href']),
                            published_at=re.sub(r'\s+', '', date.group()).replace('.', '-') if date else None))
    empty = soup.find(string=re.compile(r'^\s*등록된 (?:글|게시물)이 없습니다\.?\s*$'))
    empty_list = bool(empty and soup.title and '게시판목록' in soup.title.get_text())
    if not notices and not empty_list and not soup.select_one('.b-no-post, .board-no-data, .no-data'):
        raise ValueError(f'공지 목록 구조를 확인할 수 없습니다: {base_url}')
    return notices


def crawl_notices(url, notice_type="공지", pages=1, delay=0.5):
    print(f"크롤링 ({notice_type}): {url}, {pages}페이지")
    notices, seen = [], set()
    for page in range(pages):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if 'bo_table' in query or 'tbl' in query or parsed.path.rstrip('/')=='/board/notice':
            query.update({'page':[str(page+1)]})
        else:
            query.update({'article.offset': [str(page * 10)], 'articleLimit': ['10']})
        page_url = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
        response = fetch_page(page_url)
        rows = parse_notice_list(response.text, response.url)
        added = [row for row in rows if row['article_no'] not in seen]
        notices.extend(added)
        seen.update(row['article_no'] for row in added)
        if not added: break
        if page + 1 < pages: time.sleep(delay)
    print(f"수집 목록: {len(notices)}개 (고정 공지 포함)")
    return notices


def parse_notice_attachments(soup, base_url):
    """공지사항 첨부파일 메타데이터 추출"""
    attachments = []

    for index, link in enumerate(soup.select('ul.filedown_list a[href], .b-file-box a[href], .board-view-file-wrap a[href], #bo_v_file a[href*="download"], .bo_file a[href*="download"]'), start=1):
        download_url = urljoin(base_url, link.get('href', ''))
        attach_no = extract_attach_no(download_url)
        filename = link.get_text(' ', strip=True)

        if attach_no is None or not filename:
            continue

        attachments.append({
            'source_attach_no': attach_no,
            'original_filename': filename,
            'download_url': download_url,
            'display_order': index,
        })

    return attachments


def parse_notice_detail(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    content_node = soup.select_one('.board-view-content-wrap .fr-view, .board-view-content-wrap pre, .b-content-box, .fr-view, pre, .board-view-content-wrap, #bo_v_con, #hwpEditorBoardContent, #DivContents, .board-body')
    title_node = soup.select_one('.board-view-title-wrap h4, em.ellipsis, .b-title-box, #bo_v_title .bo_v_tit, #bo_v_title, #bo_view .tite_group h1, .conbody table strong, article header h1')
    if content_node is None or title_node is None:
        raise ValueError(f'공지 상세 구조를 확인할 수 없습니다: {source_url}')
    # The category badge is metadata rather than part of the actual notice title.
    for badge in title_node.select('span'):
        if 'c-board-view-category' in badge.get('class',[]) or re.fullmatch(r'\[[^\]]+\]',badge.get_text(' ',strip=True)):
            badge.decompose()
    for element in content_node.select('script, style'): element.decompose()
    text = content_node.get_text('\n', strip=True)
    images = [urljoin(source_url, image['src']) for image in content_node.select('img[src]')]
    if re.fullmatch(r'/board/notice/\d+/?',urlparse(source_url).path):
        article=content_node.find_parent('article')
        if article:images.extend(urljoin(source_url,n['src']) for n in article.select(':scope > img[src]'))
    if not text and images:
        text = '[이미지 공지: 대상·일정은 원문 이미지 확인]'
    if not text:
        raise ValueError(f'공지 본문이 비어 있습니다: {source_url}')
    return dict(full_text=text, title=title_node.get_text(' ', strip=True),
                attachments=parse_notice_attachments(soup, source_url), source_url=source_url, has_images=bool(images))


def get_notice_detail(source_url):
    response = fetch_page(source_url)
    return parse_notice_detail(response.text, response.url)


def sanitize_filename(filename):
    """파일 시스템에 안전한 파일명으로 변환"""
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized or 'attachment'


def download_attachment(notice_type, article_no, attachment):
    """첨부파일 다운로드 후 저장 경로 반환"""
    response = requests.get(attachment['download_url'], headers=REQUEST_HEADERS, timeout=(10, 60))
    response.raise_for_status()

    notice_dir = os.path.join(ATTACHMENTS_ROOT, notice_type, str(article_no))
    os.makedirs(notice_dir, exist_ok=True)

    safe_filename = sanitize_filename(attachment['original_filename'])
    relative_path = os.path.join(
        'data',
        'attachments',
        notice_type,
        str(article_no),
        f"{attachment['source_attach_no']}__{safe_filename}",
    )
    absolute_path = os.path.join(PROJECT_ROOT, relative_path)

    with open(absolute_path, 'wb') as file:
        file.write(response.content)

    content_length = response.headers.get('Content-Length')
    file_size = int(content_length) if content_length and content_length.isdigit() else len(response.content)

    return {
        'storage_path': relative_path.replace(os.sep, '/'),
        'mime_type': response.headers.get('Content-Type'),
        'file_size': file_size,
    }


def upsert_notice_source(cursor, notice_type, notice_id, source_url, source_title):
    """원문 URL upsert"""
    cursor.execute(
        '''
        INSERT INTO notice_sources (
            notice_type,
            notice_id,
            source_url,
            source_title
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(notice_type, notice_id)
        DO UPDATE SET
            source_url = excluded.source_url,
            source_title = excluded.source_title,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (notice_type, notice_id, source_url, source_title)
    )


def upsert_notice_attachment(cursor, notice_type, notice_id, attachment):
    """첨부파일 메타 upsert"""
    cursor.execute(
        '''
        INSERT INTO notice_attachments (
            notice_type,
            notice_id,
            source_attach_no,
            original_filename,
            download_url,
            storage_path,
            mime_type,
            file_size,
            display_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(notice_type, notice_id, source_attach_no)
        DO UPDATE SET
            original_filename = excluded.original_filename,
            download_url = excluded.download_url,
            storage_path = excluded.storage_path,
            mime_type = excluded.mime_type,
            file_size = excluded.file_size,
            display_order = excluded.display_order,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (
            notice_type,
            notice_id,
            attachment['source_attach_no'],
            attachment['original_filename'],
            attachment['download_url'],
            attachment['storage_path'],
            attachment['mime_type'],
            attachment['file_size'],
            attachment['display_order'],
        )
    )


def save_notice_attachments(cursor, notice_type, article_no, attachments):
    """첨부파일 저장 및 메타데이터 기록"""
    for attachment in attachments:
        try:
            file_info = download_attachment(notice_type, article_no, attachment)
            attachment_record = {
                **attachment,
                **file_info,
            }
            upsert_notice_attachment(cursor, notice_type, article_no, attachment_record)
            print(f"📎 첨부 저장 완료: {attachment['original_filename']}")
        except Exception as e:
            upsert_notice_attachment(cursor, notice_type, article_no, {**attachment, 'storage_path':'', 'mime_type':None, 'file_size':None})
            print(f"첨부 다운로드 실패, 원문 링크 보존 ({attachment['original_filename']}): {e}")


def find_exact_duplicate(conn, detail):
    # Poster images can contain different requirements even when their surrounding text is identical.
    if detail.get('has_images'): return None
    candidates=conn.execute('SELECT id,notice_type FROM notices WHERE title=? AND full_text=?',
                            (detail['title'],detail['full_text'])).fetchall()
    incoming_files=sorted(a['original_filename'] for a in detail['attachments'])
    for candidate in candidates:
        stored_files=sorted(row[0] for row in conn.execute('SELECT original_filename FROM notice_attachments WHERE notice_id=? AND notice_type=?',
                                                         (candidate['id'],candidate['notice_type'])))
        if incoming_files==stored_files:return candidate
    return None


def save_to_db(notices, table_name='scholarships', notice_type='scholarship', board=None, max_new=None, download_files=True):
    """DB에 저장 (중복 체크)"""
    if table_name not in ('jobs', 'scholarships'):
        raise ValueError('Unknown notice table')
    if not notices:
        print("저장할 공지사항이 없습니다.")
        return 0

    host = os.getenv('CLOVA_STUDIO_HOST')
    api_key = os.getenv('CLOVA_STUDIO_API_KEY')
    request_id = os.getenv('CLOVA_STUDIO_REQUEST_ID')

    completion_executor = CompletionExecutor(
        host=host,
        api_key=api_key,
        request_id=request_id
    )
    conn = get_db_connection()
    if board and not board['enabled']:
        with conn: register_sources(conn, [board])
    cursor = conn.cursor()

    latest_id = get_latest_article_no(table_name)
    print(f"📊 DB 최신 ID: {latest_id}")

    new_count = 0
    errors = 0

    for notice in notices:
        article_no = notice['article_no']

        if max_new is not None and new_count >= max_new: break
        if board:
            origin = find_origin(conn, board, article_no)
            if origin:
                with conn: save_origin(conn, board, notice, origin['notice_id'], origin['notice_type'])
                continue
        if not board or board.get('legacy_ids'):
            existing = conn.execute('SELECT id,notice_type FROM notices WHERE id=?', (article_no,)).fetchone() if board else None
            if existing:
                with conn: save_origin(conn, board, notice, existing['id'], existing['notice_type'])
                continue
            if not board and cursor.execute(f'SELECT 1 FROM {table_name} WHERE id=?', (article_no,)).fetchone():
                continue

        print(f"새 공지 [{board['id'] if board else notice_type}:{article_no}]: {notice['title']}")
        try:
            detail = notice.get('detail') or get_notice_detail(notice['url'])
            full_text = detail['full_text']
            title = detail['title']
            if not full_text.strip(): raise ValueError('Empty notice body; retry next run')
            full_text_filtered = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', full_text)
            if board:
                duplicate = find_exact_duplicate(conn, detail)
                if duplicate:
                    with conn: save_origin(conn, board, notice, duplicate['id'], duplicate['notice_type'])
                    continue
            result = completion_executor.execute(title + '\n' + full_text_filtered)

            target_audience = result.get('target_audience') or "공지사항 참조"
            if isinstance(target_audience, list):
                target_audience = '\n'.join(f"- {item}" for item in target_audience)

            organizer = result.get('organizer') or "미지정"
            deadline = result.get('schedule', {}).get('deadline') or "미정"
            selection_date = result.get('schedule', {}).get('selection_date')

            benefits = result.get('benefits') or "공지사항 참조"
            if isinstance(benefits, list):
                benefits = '\n'.join(f"- {item}" for item in benefits)

            category = result.get('category') or "기타"
            fields = classification_fields(title, full_text, target_audience, benefits, category, result)

            # Allocate IDs under the writer lock when importing several boards concurrently.
            conn.execute('BEGIN IMMEDIATE')
            if board:
                existing = find_origin(conn, board, article_no)
                if not existing and board.get('legacy_ids'):
                    existing = conn.execute('SELECT id AS notice_id,notice_type FROM notices WHERE id=?', (article_no,)).fetchone()
                duplicate = find_exact_duplicate(conn, detail) if not existing else None
                if existing or duplicate:
                    notice_id = existing['notice_id'] if existing else duplicate['id']
                    kind = existing['notice_type'] if existing else duplicate['notice_type']
                    save_origin(conn, board, notice, notice_id, kind)
                    conn.commit()
                    continue
            stored_id = article_no if not board or board.get('legacy_ids') else next_notice_id(conn)
            cursor.execute(
                f'''
                INSERT INTO {table_name}
                (id, target_audience, organizer, deadline, selection_date, benefit, category, title, full_text,
                 main_category, subcategory, eligibility_conditions, classification_status, classification_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    stored_id,
                    target_audience,
                    organizer,
                    deadline,
                    selection_date,
                    benefits,
                    category,
                    title,
                    full_text,
                    fields['main_category'], fields['subcategory'], fields['eligibility_conditions'],
                    fields['classification_status'], fields['classification_reason']
                )
            )

            save_profile(conn, stored_id, extract_profile(title, full_text, target_audience, fields['main_category'], fields['subcategory']))

            upsert_notice_source(
                cursor,
                notice_type,
                stored_id,
                detail['source_url'],
                title
            )
            if board: save_origin(conn, board, notice, stored_id, notice_type)
            if download_files:
                save_notice_attachments(cursor, notice_type, stored_id, detail['attachments'])
            else:
                for attachment in detail['attachments']:
                    upsert_notice_attachment(cursor, notice_type, stored_id, {**attachment, 'storage_path':'', 'mime_type':None, 'file_size':None})
            conn.commit()

            new_count += 1
            print(f"✅ 저장 완료: {article_no}")

        except Exception as error:
            conn.rollback()
            errors += 1
            print(f"저장 실패 ({article_no}), 다음 배치에서 재시도: {error}")

    conn.commit()
    conn.close()

    print(f"\n저장 {new_count}개, 실패 {errors}개")
    if errors: raise RuntimeError(f"{errors} notice(s) failed; successful notices were committed")
    return new_count


def main():
    parser = argparse.ArgumentParser(description='성균관대 본교·단과대·학과 공지 수집')
    parser.add_argument('--source', action='append', help='수집할 출처 ID. 생략하면 활성 출처 전체')
    parser.add_argument('--pages', type=int, help='출처별 목록 페이지 수 (기본: 설정값)')
    parser.add_argument('--max-new', type=int, help='출처별 신규 저장 상한')
    parser.add_argument('--dry-run', action='store_true', help='목록만 확인; DB 저장·LLM 호출 없음')
    parser.add_argument('--no-download', action='store_true', help='첨부 링크만 저장')
    parser.add_argument('--list-sources', action='store_true')
    args = parser.parse_args()
    boards = load_sources()
    if args.list_sources:
        for board in boards: print(f"{board['id']}\t{board['name']}\t{board['url']}")
        return
    if args.pages is not None and not 1 <= args.pages <= 100: parser.error('--pages: 1~100')
    if args.max_new is not None and args.max_new < 1: parser.error('--max-new: 1 이상')
    if args.source and set(args.source) - {b['id'] for b in boards}: parser.error('등록되지 않은 출처 ID')
    failures = []
    for board in boards:
        if (args.source and board['id'] not in args.source) or (not args.source and not board['enabled']): continue
        try:
            notices = crawl_notices(board['url'], board['name'], args.pages or board['pages'])
            if args.dry_run:
                for notice in notices: print(f"[{notice['article_no']}] {notice['title']} {notice['url']}")
            else:
                save_to_db(notices, table_name=board['table'], notice_type='scholarship' if board['table']=='scholarships' else 'job',
                           board=board, max_new=args.max_new, download_files=not args.no_download)
        except Exception as error:
            failures.append(board['id'])
            print(f"출처 수집 실패 [{board['id']}]: {error}")
        time.sleep(0.5)
    if failures: raise SystemExit(f"수집 실패 출처 (나머지는 저장됨): {', '.join(failures)}")


if __name__ == '__main__':
    main()
