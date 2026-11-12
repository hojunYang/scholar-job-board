# Scholar Job Board

> 성균관대 본교 전체 공지와 단과대·학과 공지를 수집하고 분류하는 대시보드

Next.js 15 + TypeScript + SQLite + Tailwind CSS

## Installation

```bash
npm install
```

## Usage

```bash
# Development
npm run dev

# Production
npm run build
npm start

# Crawler (Python)
cd scripts
pip install -r requirements.txt
python crawler.py
```

## Project Structure

```
scholar-job-board/
├── app/                    # Next.js App Router
│   ├── page.tsx           # 메인 대시보드
│   ├── jobs/              # 채용 공고 페이지
│   └── scholarships/      # 장학금 페이지
├── components/            # React 컴포넌트
├── lib/                   # DB 연결 및 쿼리
├── types/                 # TypeScript 타입
├── data/                  # SQLite 데이터베이스
└── scripts/               # Python 크롤러
    ├── crawler.py        # 공지사항 크롤러
    ├── llm.py            # LLM 파싱
    └── run_crawler.sh    # 배치 실행 스크립트
```

## 공지 분류 및 대상 조건

13개 대분류·세부분류와 지원 조건 JSON을 저장합니다. 기존 DB에 적용하려면 `python3 scripts/migrate_notices.py`를 실행하세요. 실행 전 자동 백업을 만듭니다. 전체 공지는 `/notices`에서 조회합니다.

컬럼 정의, 자동분류 한계, SQL 예제와 검증 방법은 [공지 분류 스키마](docs/notice-classification.md)를 참고하세요.

## License

MIT