import json
import os
import re
import sqlite3
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from llm import CompletionExecutor

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_support_tables(conn)
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
    article_no = parse_qs(parsed.query).get('articleNo', [None])[0]

    if not article_no:
        return None

    try:
        return int(article_no)
    except ValueError:
        return None


def extract_attach_no(download_url):
    """다운로드 URL에서 attachNo 추출"""
    parsed = urlparse(download_url)
    attach_no = parse_qs(parsed.query).get('attachNo', [None])[0]

    if not attach_no:
        return None

    try:
        return int(attach_no)
    except ValueError:
        return None


def crawl_notices(url, notice_type="장학금"):
    """성균관대 공지사항 크롤링"""
    print(f"🔍 크롤링 시작 ({notice_type}): {url}")

    try:
        response = requests.get(url, headers=REQUEST_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        content_wraps = soup.find_all('dl', class_='board-list-content-wrap', limit=10)

        if not content_wraps:
            print("❌ board-list-content-wrap을 찾을 수 없습니다.")
            return []

        print(f"📋 {len(content_wraps)}개의 공지사항 항목을 찾았습니다.")

        notices = []
        seen_ids = set()

        for wrap in content_wraps:
            link = wrap.find('a', href=True)
            if not link:
                continue

            href = link.get('href', '')
            article_no = extract_article_no(href)
            if article_no is None:
                continue

            if article_no in seen_ids:
                print(f"⚠️  크롤링 중복 발견: {article_no}")
                continue

            seen_ids.add(article_no)
            detail_url = urljoin(response.url, href)
            title = link.get_text(' ', strip=True)

            notices.append({
                'article_no': article_no,
                'title': title,
                'url': detail_url,
            })

        print(f"✅ {len(notices)}개의 공지사항을 찾았습니다.")
        return notices

    except Exception as e:
        print(f"❌ 크롤링 오류: {e}")
        return []


def parse_notice_attachments(soup, base_url):
    """공지사항 첨부파일 메타데이터 추출"""
    attachments = []

    for index, link in enumerate(soup.select('ul.filedown_list a[href]'), start=1):
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


def get_notice_detail(source_url):
    """공지사항 상세 내용과 첨부 메타데이터 가져오기"""
    try:
        response = requests.get(source_url, headers=REQUEST_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        content_node = soup.find('pre')
        if not content_node:
            content_node = soup.find('div', class_='fr-view')

        title_node = soup.find('em', class_='ellipsis')
        attachments = parse_notice_attachments(soup, response.url)

        if content_node:
            if content_node.name == 'pre':
                content = content_node.get_text(strip=True)
            else:
                content = content_node.get_text('\n', strip=True)
        else:
            content = "상세 내용을 찾을 수 없습니다."

        title = title_node.get_text(strip=True) if title_node else source_url

        return {
            'full_text': content,
            'title': title,
            'attachments': attachments,
            'source_url': source_url,
        }

    except Exception as e:
        print(f"❌ 상세 내용 가져오기 오류 ({source_url}): {e}")
        return {
            'full_text': "",
            'title': source_url,
            'attachments': [],
            'source_url': source_url,
        }


def sanitize_filename(filename):
    """파일 시스템에 안전한 파일명으로 변환"""
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', filename)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized or 'attachment'


def download_attachment(notice_type, article_no, attachment):
    """첨부파일 다운로드 후 저장 경로 반환"""
    response = requests.get(attachment['download_url'], headers=REQUEST_HEADERS)
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
            print(f"⚠️  첨부 저장 실패 ({attachment['original_filename']}): {e}")


def save_to_db(notices, table_name='scholarships', notice_type='scholarship'):
    """DB에 저장 (중복 체크)"""
    if not notices:
        print("저장할 공지사항이 없습니다.")
        return

    host = os.getenv('CLOVA_STUDIO_HOST')
    api_key = os.getenv('CLOVA_STUDIO_API_KEY')
    request_id = os.getenv('CLOVA_STUDIO_REQUEST_ID')

    completion_executor = CompletionExecutor(
        host=host,
        api_key=api_key,
        request_id=request_id
    )
    conn = get_db_connection()
    cursor = conn.cursor()

    latest_id = get_latest_article_no(table_name)
    print(f"📊 DB 최신 ID: {latest_id}")

    new_count = 0

    for notice in notices:
        article_no = notice['article_no']

        if article_no <= latest_id:
            print(f"⏭️  건너뛰기 (기존 데이터): {article_no} - {notice['title']}")
            continue

        print(f"🆕 새 공지: {article_no} - {notice['title']}")
        detail = get_notice_detail(notice['url'])
        full_text = detail['full_text']
        title = detail['title']

        full_text_filtered = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', full_text)

        try:
            result = completion_executor.execute(full_text_filtered)

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

            cursor.execute(
                f'''
                INSERT INTO {table_name}
                (id, target_audience, organizer, deadline, selection_date, benefit, category, title, full_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    article_no,
                    target_audience,
                    organizer,
                    deadline,
                    selection_date,
                    benefits,
                    category,
                    title,
                    full_text
                )
            )

            upsert_notice_source(
                cursor,
                notice_type,
                article_no,
                detail['source_url'],
                title
            )
            save_notice_attachments(cursor, notice_type, article_no, detail['attachments'])

            new_count += 1
            print(f"✅ 저장 완료: {article_no}")

        except sqlite3.IntegrityError as e:
            print(f"⚠️  IntegrityError (articleNo={article_no}): {e}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 오류 (articleNo={article_no}): {e}")
            print(f"응답 내용: {full_text[:200]}...")
        except KeyError as e:
            print(f"❌ LLM 응답 키 누락 (articleNo={article_no}): {e}")
            print(f"응답: {result}")
        except Exception as e:
            print(f"❌ 저장 오류 (articleNo={article_no}): {e}")
            print(f"타입: {type(e).__name__}")

    conn.commit()
    conn.close()

    print(f"\n📥 총 {new_count}개의 새로운 공지사항이 저장되었습니다.")


def main():
    """메인 함수"""
    print("=" * 60)
    print("🎓 성균관대 공지사항 크롤러")
    print("=" * 60)

    print("\n" + "=" * 60)
    print("📚 장학금/모집 공지 크롤링")
    print("=" * 60)
    scholarship_url = "https://www.skku.edu/skku/campus/skk_comm/notice06.do"
    scholarship_notices = crawl_notices(scholarship_url, "장학금/모집")

    print("\n" + "=" * 60)
    print("💼 채용/취업 공고 크롤링")
    print("=" * 60)
    job_url = "https://www.skku.edu/skku/campus/skk_comm/notice05.do"
    job_notices = crawl_notices(job_url, "채용/취업")

    total_count = 0

    if scholarship_notices:
        print("\n📋 장학금/모집 크롤링 결과:")
        for i, notice in enumerate(scholarship_notices, 1):
            print(f"{i}. [{notice['article_no']}] {notice['title']}")
        total_count += len(scholarship_notices)

    if job_notices:
        print("\n📋 채용/취업 크롤링 결과:")
        for i, notice in enumerate(job_notices, 1):
            print(f"{i}. [{notice['article_no']}] {notice['title']}")
        total_count += len(job_notices)

    if total_count > 0:
        if scholarship_notices:
            print("\n💾 장학금 데이터 저장 중...")
            save_to_db(scholarship_notices, table_name='scholarships', notice_type='scholarship')

        if job_notices:
            print("\n💾 채용 공고 데이터 저장 중...")
            save_to_db(job_notices, table_name='jobs', notice_type='job')
    else:
        print("⚠️  크롤링된 공지사항이 없습니다.")

    print("\n" + "=" * 60)
    print("✅ 크롤러 종료")
    print("=" * 60)


if __name__ == "__main__":
    main()
