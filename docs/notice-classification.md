# 공지 분류 스키마 및 마이그레이션

2026-11-12 적용. 기존 SQLite `data/scholar.db`의 jobs 1,133행, scholarships 491행을 보존하며 1,624행을 오프라인 규칙으로 재분류했다. 중복 ID를 합친 notices 뷰는 1,416개다. 원래 테이블의 모든 기존 컬럼과 출처·첨부 메타데이터는 백업과 해시로 대조해 보존을 확인했다.

## 추가 컬럼

jobs와 scholarships 양쪽에 동일한 컬럼을 추가한다.

| 컬럼 | 형식 | 의미 |
|---|---|---|
| main_category | TEXT, nullable | 13개 대분류. 근거 부족한 신규 공지는 NULL 가능 |
| subcategory | TEXT, nullable | 대분류에 속하는 세부분류 |
| eligibility_conditions | TEXT(JSON object), nullable | 대상·지원조건을 항목별 원문 문장으로 보존 |
| classification_status | TEXT | pending / auto / reviewed / needs_review |
| classification_reason | TEXT | 분류 근거 또는 검토 사유 |

기존 category와 target_audience는 원래 값을 유지한다. main_category/subcategory는 새 분류용이고 기존 category는 과거 라벨이다. notice_categories에는 허용 분류 쌍을 저장하며 INSERT/UPDATE 트리거가 잘못된 조합을 거부한다. JSON 문법·객체 여부와 검토 상태도 DB에서 검증한다. 분류 정의는 data/notice-taxonomy.json 한 곳에서 Python과 TypeScript가 함께 읽는다. 세부분류는 총 77개다.

## 대상·조건 JSON

```json
{
  "applicant_type": ["본교 대학원 재학생(휴학생·수료생 불가)"],
  "education": ["본교 대학원 재학생(휴학생·수료생 불가)"],
  "enrollment": ["본교 대학원 재학생(휴학생·수료생 불가)"],
  "grade": [],
  "major": [],
  "gpa": ["직전 학기 평점 3.5 이상"],
  "income": ["소득 4구간 이하"],
  "residence": [],
  "restrictions": ["본교 대학원 재학생(휴학생·수료생 불가)", "직전 학기 평점 3.5 이상", "소득 4구간 이하"],
  "preferences": [],
  "evidence": ["본교 대학원 재학생(휴학생·수료생 불가)", "직전 학기 평점 3.5 이상", "소득 4구간 이하"],
  "status": "extracted"
}
```

예시는 저장 형식을 설명한다. enrollment는 허용 재학상태의 열거가 아니라 조건 원문이다. ‘휴학생 불가’를 ‘휴학생 가능’으로 바꾸지 않으며 OR/AND·예외·제외 조건을 문장 그대로 보존한다. 배열의 중복 문장은 제거하지만 서로 다른 조건을 임의로 결합하지 않는다. evidence는 기존 대상 요약과 본문의 자격·대상·우대사항 구간에서 가져온 문장이다. 구조화 항목은 해당 문장을 키워드로 나눈 것이므로 기계적인 지원 가능/불가 판정에 바로 사용하지 않는다. 조건이 없으면 배열을 비우고 status=not_stated로 저장한다.

SQL 예시:

```sql
SELECT id, main_category, subcategory, target_audience,
       json_extract(eligibility_conditions, '$.gpa') AS gpa_conditions,
       json_extract(eligibility_conditions, '$.income') AS income_conditions
FROM notices
WHERE main_category = '장학·학비지원';

SELECT id, title, classification_reason
FROM notices WHERE classification_status = 'needs_review';
```

## 통합 조회와 기존 링크

notices는 두 테이블을 합쳐 같은 ID 중 한 행을 고르는 읽기 전용 뷰다. 본문 유무, 수정시각, 본문 길이, 원본 타입 순으로 대표 행을 선택한다. notice_type은 job/scholarship이며 기존 상세 경로를 유지한다. 원본·출처·첨부를 삭제하거나 물리적으로 병합하지 않았다. 제목만 같은 다른 ID는 별도 공지로 유지한다.

대시보드의 장학/채용 목록·통계는 테이블명이 아닌 새 대분류로 조회한다. /notices에서 13개 대분류와 세부분류를 조회하며 12개씩 페이지를 나눈다. 상세 페이지에는 대상 조건 문장을 표시한다.

## 재실행과 신규 수집

```bash
python3 scripts/migrate_notices.py
# 별도 파일을 처리하려면
python3 scripts/migrate_notices.py --db /absolute/path/to/scholar.db
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm run build
```

마이그레이션은 SQLite backup API로 WAL을 포함한 일관된 스냅샷을 data/backups/에 먼저 저장하고 트랜잭션 안에서 스키마·데이터를 갱신한다. 백업 옆에 실행 보고서 JSON도 저장한다. pending 행만 채우므로 재실행해도 자동·수동 분류를 덮어쓰지 않는다. 원래 updated_at은 공지 수정시각이므로 마이그레이션으로 바꾸지 않는다.

크롤러와 Next.js DB 초기화 모두 추가 스키마를 생성할 수 있다. 기존 데이터의 재분류는 위 마이그레이션 명령으로 실행한다. 신규 수집은 먼저 13개 대분류를 판단한 뒤 해당 대분류의 세부분류만 별도 LLM 요청으로 선택한다. 프롬프트는 scripts/prompts/notice_extraction.txt에 있다. 잘못된 대분류·JSON이나 대분류가 규칙과 다르면 참고 후보를 제공해 한 번 교정 요청한다. 세부분류 요청이 실패하거나 허용하지 않은 조합이면 규칙으로 보완하고 검토 필요로 표시한다. 교정 후에도 확실한 규칙 분류와 LLM 판단이 충돌하면 규칙 분류를 유지하고 LLM 후보·근거를 기록한다.

LLM 분류 인용과 대상 요약을 원문과 대조한다. 대상 조건은 기존 원문 추출을 사용하고, 원문에 없는 LLM 요약을 조건 근거로 쓰지 않는다. 공지의 지시문은 분류 데이터로만 취급한다. 기존 크롤러의 충돌 표시는 첨부·출처 기능을 보존하는 버전으로 정리했다. 배치 실행 파일은 현재 체크아웃을 사용하며 별도 스케줄러 설정은 바꾸지 않았다.

## 이번 적용 결과

아래는 규칙 기반 자동분류 건수이며 전수 수동 검수 결과가 아니다.

| 대분류 | ID 기준 공지 수 |
|---|---:|
| 취업·인턴·현장실습 | 371 |
| 장학·학비지원 | 252 |
| 근로·알바·학생조교 | 153 |
| 교육·역량개발 | 131 |
| 봉사·멘토링·서포터즈 | 122 |
| 실험·설문·인터뷰 참여 | 98 |
| 행사·강연·문화 | 59 |
| 공모전·경진대회 | 51 |
| 생활·복지·시설 | 50 |
| 국제교류·해외연수 | 49 |
| 연구경험·학술지원 | 34 |
| 창업·사업화 | 25 |
| 학사·행정 | 21 |

미분류 대/세분류는 0개다. 본문이 없는 7개 공지(ID 134500, 135978, 137247, 137657, 140948, 135234, 138212)는 제목으로 잠정 분류해 needs_review로 표시했다. 대상 조건 근거를 찾을 수 없는 15개는 not_stated다. 같은 ID의 두 테이블 간 대/세분류 불일치는 0개다. 조건 원문은 각 행의 기존 정보를 따로 보존한다.

기존 원문·첨부를 외부에서 다시 수집하지 않았다. 날짜 파싱, 접수 상태 판정, 재공고 관계 연결은 이번 변경에 포함하지 않았다. 기존 로컬에서 삭제된 첨부 다운로드 API도 복원하지 않았다.

검증: 분류·조건·마이그레이션 단위 테스트, LLM/HTTP를 모의한 신규 크롤러 저장 확인, TypeScript 검사, Next.js 프로덕션 빌드, HTTP 200 응답과 실제 상세 링크·필터 조회 확인.


## 배치 프롬프트 실호출 확인 (2026-11-12)

대분류와 세부분류 요청을 분리한 뒤 기존 공지 6개 표본에서 LLM 대분류 6개가 예상값과 일치했다. 세부분류 기준을 보강한 최종 재확인 3개에서는 다음과 같이 반환했다. 이는 소수 표본 점검이며 전체 분류 정확도를 보장하는 통계는 아니다.

| 공지 ID | LLM 대분류 | LLM 세부분류 |
|---|---|---|
| 133659 | 근로·알바·학생조교 | 교내근로 |
| 134485 | 국제교류·해외연수 | 해외 집중교육 |
| 139664 | 행사·강연·문화 | 사업·진학 설명회 |

최종 3개 중 2개는 분류명은 맞았지만 인용 근거가 원문과 완전히 일치하지 않아 검토 필요로 처리했다. 실호출 점검은 기존 DB를 읽기만 했으며 응답을 운영 DB에 덮어쓰지 않았다. 전체 운영 배치 및 외부 스케줄러 설정은 실행·변경하지 않았다.


UI 기본 목록·카테고리·건수에서는 마감된 공지를 제외한다. 마감 탭(status=closed)에서만 마감 공지 목록과 건수를 조회하며, 카테고리 이동 시 마감 필터를 유지한다. 마감일 미정·상시 공지는 기본 목록에 포함한다. DB 원본은 삭제하지 않는다.
