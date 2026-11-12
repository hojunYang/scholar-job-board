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

### 1. **본교·단과대·학과 수집**
- 본교는 `notice01.do` 전체 공지에서 모든 공지 성격을 수집합니다.
- 단과대·학과 게시판은 `data/notice-sources.json`에서 관리합니다.
- 원래 장학/채용 테이블은 보존하며 화면 분류는 `main_category`를 사용합니다.

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

1. 설정된 출처의 목록을 페이지별로 수집합니다(기본 2페이지).
2. 일반 글과 고정 공지를 함께 추출하고 출처 내 중복을 제거합니다.
3. 출처별 원문 ID를 확인하고, 본교는 기존 양쪽 테이블의 같은 ID도 재사용합니다.
4. 새로운 글의 상세 본문과 첨부 링크를 추출합니다.
5. LLM 분류와 대상 조건 추출을 거쳐 원자적으로 저장합니다.
6. 실패한 글은 다음 실행에서 다시 시도합니다.

## 주의사항

- 실제 HTML 구조에 맞게 CSS 선택자를 조정해야 할 수 있습니다.
- 너무 자주 실행하면 서버에 부담을 줄 수 있으니 주의하세요.
- 크롤링 전에 해당 사이트의 robots.txt를 확인하세요.


## 분류 스키마와 기존 공지 재분류

```bash
# 프로젝트 루트에서 실행
python3 scripts/migrate_notices.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

백업 후 기존 행에 대분류·세부분류·대상 조건 JSON을 채웁니다. 신규 크롤링도 같은 컬럼에 저장합니다. 자세한 항목과 검토 필요 공지는 [스키마 설명](../docs/notice-classification.md)을 참고하세요.

## 배치 LLM 프롬프트

- `scripts/prompts/notice_extraction.txt`: 대분류 판단 기준, 역할 구분, 대상·자격·근거 추출 규칙.
- `data/notice-taxonomy.json`: 허용 대분류·세부분류. LLM이 13개 대분류 중 하나를 선택한 뒤, 선택된 대분류의 세부분류만 별도 요청합니다. 일반적으로 공지당 2회 호출합니다.
- 대분류·JSON이 잘못되거나 대분류가 규칙과 다르면 참고 후보를 제공하고 한 번 교정 요청합니다(최대 3회 호출). 세부분류 요청 실패·잘못된 조합은 규칙 분류로 보완하고 검토 대상으로 저장합니다.
- 유효한 LLM 분류를 사용하되 교정 후에도 확실한 규칙 분류와 다르면 규칙 분류를 유지하고 LLM 후보·근거와 함께 검토 필요로 표시합니다.
- 대상 조건은 원문에 있는 문장으로 저장합니다. 원문에 없는 LLM 대상 요약은 조건의 근거로 쓰지 않습니다. 분류 인용 근거도 실제 제목·본문과 대조합니다.
- 배치는 MAX(id)보다 작다는 이유로 공지를 건너뛰지 않고 실제 ID 존재 여부를 검사합니다. 이전 LLM 실패로 비어 있는 ID도 다시 처리할 수 있습니다.
- `bash scripts/run_crawler.sh`는 현재 체크아웃의 크롤러·프롬프트를 사용하고 `scripts/logs/`에 기록합니다. 별도 cron/launchd 설정은 변경하지 않습니다.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
bash -n scripts/run_crawler.sh
```

### 분류별 지원 조건

`notice_eligibility`는 원문 조건과 별도로 조회 가능한 학년 배열, 소득구간 배열, 학위 배열, 경력·나이 범위, 만점별 평점을 저장합니다. `field_states`의 `known`/`any`/`unknown`/`ambiguous`로 명시 조건·제한 없음·미확인·복합 조건을 구분합니다. 근거 문장은 `evidence`, 단순 비교할 수 없는 제약은 `caveats`에 보존합니다.

기존 DB 재처리: `python3 scripts/migrate_eligibility.py --db data/scholar.db`. 실행 전 SQLite 백업을 만들고 원본 공지는 변경하지 않습니다. 새 공지는 크롤러 저장 시 동일 추출기를 거칩니다. LLM 대상 요약에는 분류별 필수 조건과 제외·우대·AND/OR를 보존하도록 지시합니다. 소득 %와 지원구간, 다른 만점의 성적은 임의 환산하지 않습니다.

화면별 필터 구성은 `data/profile-filters.json`과 `lib/eligibility.ts`에서 관리합니다. 현장실습·인턴은 학생 조건, 국가근로는 소득 조건을 추가합니다. 선택 조건은 AND로 비교하고 미확인·복합 조건은 기본 제외하며, ‘미확인 조건 포함’ 선택 시 표시합니다. 전공·자격증·학기·잔여학기 등은 원문 확인이 필요하며, 필터 일치는 전체 지원 자격 충족을 의미하지 않습니다.

### 본교·단과대·학과 공지 수집

기본 배치는 `data/notice-sources.json`의 활성 출처를 전부 수집합니다. 본교 전체 공지(`notice01.do`)와 공식 대학·학과·연계전공·융합전공·협동과정·대학원 게시판을 수집합니다. 전체 등록 목록과 검증 범위는 [수집 출처 목록](../docs/notice-source-coverage.md)을 참고하세요. 본교는 학사·입학·취업·채용/모집·장학·행사/세미나·일반을 구분하지 않고 전체 목록을 수집합니다. 예전 본교 장학/채용 출처는 전체 출처로 통합하며 원본 공지와 상세 URL은 보존합니다. 출처는 공지 성격의 대분류와 별개이며, 학과 게시판에 올라온 장학 공지도 장학 필터에서 찾을 수 있습니다.

```bash
python3 scripts/crawler.py --list-sources
# 목록 확인만: DB 변경, 첨부 다운로드, LLM 호출 없음
python3 scripts/crawler.py --source cse-undergraduate --pages 1 --dry-run
# 등록한 전체 활성 출처: 출처별 기본 2페이지, 고정 공지도 빠짐없이 포함
bash scripts/run_crawler.sh
# 특정 게시판 수집, 첨부는 원문 다운로드 링크만 저장
bash scripts/run_crawler.sh --source cse-undergraduate --pages 2 --no-download
# 초기 확인용: 출처별 신규 저장 2개로 제한
python3 scripts/crawler.py --source sw-undergraduate --max-new 2 --no-download
```

다른 단과대·학과는 같은 설정 파일에 고유 `id`, `university`, `college`, `department`, 표시용 `name`, 게시판 `url`, `table: "jobs"`, `legacy_ids: false`, `enabled: true`, `pages: 2`를 추가합니다. `table`은 기존 저장 테이블/상세 URL 호환용이며 실제 화면 분류는 LLM 결과의 `main_category`를 따릅니다. 같은 SKKU CMS의 `articleNo` 및 공과대학 `viewBoardId`/`itemId` 형식을 지원합니다. 다른 학교의 다른 HTML 구조는 파서 추가가 필요합니다. 게시판 URL 등록이 학교 전체 게시판 자동 탐색을 의미하지는 않습니다.

`notice_boards`에 대학·단과대·학과·게시판을, `notice_origins`에 출처별 원문 글 ID·URL·게시일과 내부 공지 ID를 저장합니다. 기존 상세 주소와 본문은 보존하며 신규 학과 공지는 1,000,000,001부터 별도 내부 ID를 사용해 글 번호 충돌을 방지합니다. 이미지가 없고 제목·본문·첨부파일명이 정확히 같은 교차 게시는 카드 한 장으로 합치고 원문 출처를 모두 유지합니다. 유사한 제목만으로 서로 다른 글을 합치지는 않습니다.

하나의 공지 저장이 실패하면 해당 공지의 본문·분류·대상 조건·출처를 함께 롤백하고 다음 실행에서 다시 시도합니다. 다른 글·다른 출처 수집은 계속하며 실패가 남으면 배치는 0이 아닌 종료 코드를 반환합니다. 기존 공지의 수정·삭제 추적, 이미지 OCR, 전체 과거 글 소급 수집은 수행하지 않습니다. 수집 간격에 비해 신규 공지가 많다면 출처의 `pages`를 늘려야 합니다. cron/launchd 주기 자체는 변경하지 않습니다.

### 공식 안내에서 게시판 추가 발견

```bash
# 공식 대학·대학원 안내와 등록 출처의 실제 링크를 따라가서 목록 및 본문 검증 후 등록
python3 scripts/discover_sources.py --apply
# 발견 단계에서 실제로 확인한 최신 글 1개씩을 저장해 출처별 처리 경로를 검증
python3 scripts/ingest_discovered.py --workers 2
# 이후 평소 배치는 등록된 출처의 최신 2페이지를 모두 확인
bash scripts/run_crawler.sh --no-download
```

발견 단계는 성대 공식 도메인의 실제 링크만 따라가며 CMS의 다른 호스트 별칭과 동일 게시판의 카테고리 탭은 합칩니다. 게시판 등록 전 실제 목록과 공지 본문을 읽고, 로그인 페이지·오류 응답·지원하지 않는 형식은 등록하지 않습니다. 결과와 제외 사유는 `work/source-discovery-report.json`, 초기 저장 결과는 `work/source-ingest-report.json`에 기록합니다. 발견 단계의 공개 HTML 캐시는 24시간 유효하며 평소 크롤러는 매 실행 원문을 새로 조회합니다.

SKKU CMS의 목록/썸네일 형식 외에 GnuBoard(`bo_table`/`wr_id`), 기존 PHP 게시판(`tbl`/`num`), 에너지과학과의 `/board/notice/{id}` 형식을 지원합니다. 발견 자체는 LLM을 호출하지 않습니다. 초기 저장과 평소 배치의 LLM 호출은 제공자의 남은 요청·토큰 한도 및 갱신 시각을 확인해 기다리고, 429 응답도 갱신 후 재시도합니다. 여러 출처를 함께 처리해도 공지 ID 할당과 중복 검사를 SQLite 쓰기 잠금 안에서 수행합니다.
