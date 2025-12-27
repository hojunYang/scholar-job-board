import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import os
import re
from llm import CompletionExecutor
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 경로
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'scholar.db')

def get_db_connection():
    """데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_latest_article_no(table_name):
    """DB에서 가장 최신 articleNo 가져오기"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # id가 articleNo라고 가정
    cursor.execute(f'SELECT MAX(id) as max_id FROM {table_name}')
    result = cursor.fetchone()
    conn.close()
    
    return result['max_id'] if result['max_id'] else 0

def crawl_notices(url, notice_type="장학금"):
    """성균관대 공지사항 크롤링"""
    print(f"🔍 크롤링 시작 ({notice_type}): {url}")
    
    try:
        # GET 요청
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 10개의 dl 태그 찾기
        content_wraps = soup.find_all('dl', class_='board-list-content-wrap', limit=10)
        
        if not content_wraps:
            print("❌ board-list-content-wrap을 찾을 수 없습니다.")
            return []
        
        print(f"📋 {len(content_wraps)}개의 공지사항 항목을 찾았습니다.")
        
        # 각 dl에서 a 태그 찾기
        links = []
        for wrap in content_wraps:
            a_tag = wrap.find('a', href=True)
            if a_tag:
                links.append(a_tag)
        
        notices = []
        seen_ids = set()  # 중복 체크용
        
        for link in links:
            href = link.get('href', '')
            
            # articleNo 추출
            if 'articleNo=' in href:
                article_no = href.split('articleNo=')[1].split('&')[0]
                article_no = int(article_no)
                
                # 중복 체크
                if article_no in seen_ids:
                    print(f"⚠️  크롤링 중복 발견: {article_no}")
                    continue
                
                seen_ids.add(article_no)
                
                # 제목 추출
                title = link.get_text(strip=True)
                
                notices.append({
                    'article_no': article_no,
                    'title': title,
                    'url': f"https://www.skku.edu/skku/campus/skk_comm/notice06.do?mode=view&articleNo={article_no}"
                })
        
        print(f"✅ {len(notices)}개의 공지사항을 찾았습니다.")
        return notices
        
    except Exception as e:
        print(f"❌ 크롤링 오류: {e}")
        return []

def get_notice_detail(article_no):
    """공지사항 상세 내용 가져오기"""
    url = f"https://www.skku.edu/skku/campus/skk_comm/notice06.do?mode=view&articleNo={article_no}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상세 내용 추출 (실제 HTML 구조에 맞게 수정 필요)
        content_div = soup.find('pre')
        title = soup.find('em', class_='ellipsis').get_text(strip=True)

        if content_div and title:
            content = content_div.get_text(strip=True)
            return content, title
        else:
            return "상세 내용을 찾을 수 없습니다."
            
    except Exception as e:
        print(f"❌ 상세 내용 가져오기 오류 (articleNo={article_no}): {e}")
        return ""

def save_to_db(notices, table_name='scholarships'):
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
    
    # 현재 DB의 최신 articleNo
    latest_id = get_latest_article_no(table_name)
    print(f"📊 DB 최신 ID: {latest_id}")
    
    new_count = 0
    
    for notice in notices:
        article_no = notice['article_no']
        
        # 이미 있는지 확인
        if article_no <= latest_id:
            print(f"⏭️  건너뛰기 (기존 데이터): {article_no} - {notice['title']}")
            continue
        
        
        print(f"🆕 새 공지: {article_no} - {notice['title']}")
        
        # 상세 내용 가져오기
        full_text, title = get_notice_detail(article_no)
        
        # 제어 문자 제거 (JSON 파싱 에러 방지)
        full_text_filtered = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', full_text)
        
        # DB에 삽입
        try:
            result = completion_executor.execute(full_text_filtered)
            
            # 필수 필드 기본값 처리
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
            
            cursor.execute(f'''
                INSERT INTO {table_name} 
                (id, target_audience, organizer, deadline, selection_date, benefit, category, title, full_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article_no,
                target_audience,
                organizer,
                deadline,
                selection_date,
                benefits,
                category,
                title,
                full_text
            ))
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
    
    # 1. 장학금 공지 크롤링 (notice06)
    print("\n" + "=" * 60)
    print("📚 장학금/모집 공지 크롤링")
    print("=" * 60)
    scholarship_url = "https://www.skku.edu/skku/campus/skk_comm/notice06.do"
    scholarship_notices = crawl_notices(scholarship_url, "장학금/모집")
    
    # 2. 채용 공고 크롤링 (notice07)
    print("\n" + "=" * 60)
    print("💼 채용/취업 공고 크롤링")
    print("=" * 60)
    job_url = "https://www.skku.edu/skku/campus/skk_comm/notice07.do"
    job_notices = crawl_notices(job_url, "채용/취업")
    
    # 결과 출력
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
        # DB에 자동 저장
        if scholarship_notices:
            print("\n💾 장학금 데이터 저장 중...")
            save_to_db(scholarship_notices, table_name='scholarships')
        
        if job_notices:
            print("\n💾 채용 공고 데이터 저장 중...")
            save_to_db(job_notices, table_name='jobs')
    else:
        print("⚠️  크롤링된 공지사항이 없습니다.")
    
    print("\n" + "=" * 60)
    print("✅ 크롤러 종료")
    print("=" * 60)

if __name__ == "__main__":
    main()
