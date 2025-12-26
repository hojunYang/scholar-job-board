# Scholar Job Board

> 성균관대 장학금/채용 공고를 자동으로 크롤링하고 관리하는 대시보드

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

## License

MIT