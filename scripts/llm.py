import requests
import json
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

system_prompt = """
# Role
너는 대학생을 위한 '취업 및 장학 정보 정형 데이터 추출기(Data Extractor)'이다. 
사용자가 입력한 공지사항 텍스트를 분석하여, 아래 정의된 JSON 스키마에 맞춰 정보를 추출하라.

# Extraction Rules (Strict)
1. 모든 출력은 반드시 **JSON** 형식이어야 한다.
2. 텍스트에 명시되지 않은 정보는 무리하게 추론하지 말고 `null`로 표기하라.
3. **대상(target_audience)** 필드는 가장 중요하므로, 아래 기준을 엄격히 따르라.
   - 학년, 전공, 최소 학점, 소득 분위, 생계관련 제한, 모집인원, 거주지 제한 상세히 포함할 것.
   - "누구나", "제한 없음"인 경우 명시할 것.
   - 정보가 흩어져 있어도 종합하여 작성할 것.

# Output Schema (JSON Keys)
1. **organizer**: (String) 주최 기관, 기업명, 또는 재단명.
2. **schedule**: (Object)
    - `deadline`: (String) 마감일 (YYYY-MM-DD 형식 권장, 시간 포함 가능) 꼭 단일 날짜로 표기할 것.
    - `selection_date`: (String) 선발 또는 발표 날짜. 없으면 null.
3. **target_audience**: (String) **[중요]** 지원 자격 요건 상세 요약 (개조식).
4. **benefits**: (String) 장학금 액수, 인턴 급여, 또는 활동 혜택.
5. **category**: (String) 예시: 다음 중 하나 선택 ['교내장학', '교외장학', '채용/인턴', '대외활동', '기타'].

# Example Output
{
  "organizer": "한국장학재단",
  "schedule": {
    "deadline": "2024-05-31 18:00",
    "selection_date": "2024-06-15"
  },
  "target_audience": "- 소프트웨어학과 재학생\n- 직전 학기 학점 3.5 이상\n- 소득분위 8구간 이하\n 00명 채용",
  "benefits": "등록금 전액 및 생활비 200만원",
  "category": "교외장학"
}
"""

class CompletionExecutor:
    def __init__(self, host, api_key, request_id):
        self._host = host
        self._api_key = api_key
        self._request_id = request_id

    def execute(self, send_message):
        headers = {
            'Authorization': self._api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
            'Content-Type': 'application/json; charset=utf-8'
        }

        completion_request = {
            "messages": [{"role":"system","content":[{"type":"text","text":system_prompt}]}, {"role":"user","content":[{"type":"text","text":send_message}]}],
            "temperature": 0.5,
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 512,
            "repetitionPenalty": 1.1,
            "stop": [],
            "includeAiFilters": True,
            "tools": [],
            "tool_choice": "auto",
        }

        response = requests.post(self._host + '/v3/chat-completions/HCX-DASH-002',
                         headers=headers, json=completion_request)
        
        result = response.json()
        content = result['result']['message']['content']
        
        # ```json ... ``` 에서 JSON 부분만 추출
        return self._extract_json(content)
    
    def _extract_json(self, text):
        """응답 텍스트에서 JSON 부분만 추출"""
        if '```json' in text:
            start = text.find('```json') + 7
            end = text.find('```', start)
            json_str = text[start:end].strip()
        else:
            json_str = text.strip()
        
        return json.loads(json_str)


if __name__ == '__main__':
    # 환경 변수에서 API 키 로드
    host = os.getenv('CLOVA_STUDIO_HOST')
    api_key = os.getenv('CLOVA_STUDIO_API_KEY')
    request_id = os.getenv('CLOVA_STUDIO_REQUEST_ID')
    
    if not all([host, api_key, request_id]):
        print("❌ .env 파일에 API 설정이 없습니다.")
        print("CLOVA_STUDIO_HOST, CLOVA_STUDIO_API_KEY, CLOVA_STUDIO_REQUEST_ID를 설정하세요.")
        exit(1)
    
    completion_executor = CompletionExecutor(
        host=host,
        api_key=api_key,
        request_id=request_id
    )


    send_message =  """안녕하세요, 학생지원팀입니다.
사단법인 위드다문화에서는 다문화가족 학생이 대한민국의 우수한 인재로 성장할 수 있도록 지속적으로 장학지원을 진행하고 있습니다. 이에 따라 2025년 12월 23일(화)부터 2026년 1월 16일(금)까지 장학생을 모집하오니, 많은 학생들의 지원 바랍니다.

1. 신청자격 : 다문화가족지원법 상 다문화가족에 해당하는 학생 (세부자격 당사 장학규정 참조)
2. 지급금액 : 등록금성 장학금(대학생 1,000,000원 이내/ 대학원생 1,500,000원 이내)
3. 제출서류 : 당사 장학규정 참고 (홈페이지〉게시판〉공지사항〉2026년 상반기 위드다문화 장학생선발 참조)
4. 서류제출처 : 이메일 접수(supervision@damunwha.or.kr)
5. 서류제출기한 : 2026년 1월 16일(금) 까지 (서류도착기준)

*붙임
1. 사단법인 위드다문화 장학규정 1부
2. 장학금 지원신청서 1부
3. 개인정보수집 이용동의서 1부

자세한 사항은 첨부파일 참고 바랍니다."""
    
    result = completion_executor.execute(send_message)
    
    if result:
        print("\n✅ 추출된 JSON:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n❌ JSON 추출 실패")
