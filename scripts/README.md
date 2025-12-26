# 크롤러 사용 방법

## 설치

```bash
cd scripts
pip install -r requirements.txt
```

## 환경 설정

`.env` 파일을 생성하고 Clova Studio API 키를 설정하세요:

```bash
# .env 파일
CLOVA_STUDIO_HOST=https://clovastudio.stream.ntruss.com
CLOVA_STUDIO_API_KEY=Bearer your_api_key_here
CLOVA_STUDIO_REQUEST_ID=your_request_id_here
```

## 실행

```bash
python crawler.py
```

## 기능

### 1. **이중 크롤링**
- **장학금/모집**: https://www.skku.edu/skku/campus/skk_comm/notice06.do → `scholarships` 테이블
- **채용/취업**: https://www.skku.edu/skku/campus/skk_comm/notice07.do → `jobs` 테이블

### 2. **자동 처리**
- articleNo(ID) 기반 중복 체크
- 새로운 공지만 처리
- 상세 페이지에서 full_text 자동 추출
- LLM으로 구조화된 데이터 추출 (대상, 혜택, 마감일 등)

### 3. **DB 저장**
- SQLite DB에 자동 저장
- 리스트 데이터 자동 문자열 변환
- 제어 문자 자동 제거

## 처리 순서

1. 두 개의 공지사항 페이지 크롤링 (notice06, notice07)
2. 각 페이지에서 최대 10개의 링크 추출
3. articleNo 파싱
4. DB의 최신 ID와 비교
5. 새로운 공지만 상세 페이지 방문
6. LLM으로 데이터 구조화
7. DB에 저장 (사용자 확인 후)

## 주의사항

- 실제 HTML 구조에 맞게 CSS 선택자를 조정해야 할 수 있습니다.
- 너무 자주 실행하면 서버에 부담을 줄 수 있으니 주의하세요.
- 크롤링 전에 해당 사이트의 robots.txt를 확인하세요.

