"""Offline classification; keep source facts and mark uncertain decisions for review."""
import json
import re
import unicodedata
from pathlib import Path

TAXONOMY = json.loads((Path(__file__).resolve().parents[1] / 'data/notice-taxonomy.json').read_text())

UNKNOWN = {'', '미정', '미제공', '미지정', '공지사항 참조', '해당 없음', '정보 없음'}


def text(value):
    if isinstance(value, list):
        return '\n'.join(text(item) for item in value)
    return '' if value is None else str(value).strip()


def classify(title, full_text='', target_audience='', benefit='', legacy_category=''):
    title = unicodedata.normalize('NFKC', title)
    title = re.sub(r'\[(?:채용/모집|채용|모집|마감)\]', '', title)
    body = unicodedata.normalize('NFKC', full_text)
    context = title + '\n' + target_audience + '\n' + benefit + '\n' + body

    def has(pattern, value=title):
        return re.search(pattern, value, re.I) is not None

    def result(main, sub, reason, status='auto'):
        assert sub in TAXONOMY[main]
        if not body.strip():
            status = 'needs_review'
            reason += '; 본문 없음'
        return dict(main_category=main, subcategory=sub,
                    classification_status=status, classification_reason=reason)

    def pick(main, sub, reason):
        return result(main, sub, reason)

    if has(r'학군사관|ROTC|전문연구요원|공무원|수습직원|공정선거지원단'):
        return pick('취업·인턴·현장실습', '공직·군 진출', '공직·군·전문연구요원')
    if has(r'기관모집'):
        return pick('근로·알바·학생조교', '국가근로', '기관 대상 근로사업 참여 모집; 학생 일자리 아님')
    if has(r'BA-DIVE|Global Summer Program|U-STEP|Royal Society|국비유학생|Yenching Academy'):
        return pick('국제교류·해외연수', '해외탐방·연구연수', '해외 파견·유학·연구교류')
    if has(r'생활지도조교'):
        return pick('근로·알바·학생조교', '생활지도조교', '기숙사 생활지도 업무')
    if has(r'행정\s*조교'):
        if has(r'월\s*[\d,]+원|월\s*급|전일제|4대\s*보험|학사\s*학위\s*이상|대학\s*졸업', context):
            return pick('취업·인턴·현장실습', '대학 직원 채용', '행정조교: 학위·전일제·월급 등 고용조건')
        return result('근로·알바·학생조교', '교내근로', '행정조교: 학생근로/직원 고용조건 확인 필요', 'needs_review')
    if has(r'근로|아르바이트|시험관리원|촬영staff|스탭\s*모집|사회자\s*모집|진행자\s*모집|운영\s*조교|운영보조\s*조교|진행\s*조교|공개과정.*조교|포스터.*부착'):
        sub = '국가근로' if has(r'국가근로') else '단기·행사·시험 근로' if has(r'아르바이트|단기|시험관리원|staff|스탭|사회자|진행자|포스터') else '교내근로'
        return pick('근로·알바·학생조교', sub, '학생 근로·업무 수행 모집')
    if has(r'이론/실습TA|교과지원\s*TA|(?:조교.*TA|TA.*모집)|Lab Assistant|과목\s*조교'):
        return pick('근로·알바·학생조교', '수업지원 조교', '수업 지원 TA/조교')
    if has(r'Learning tips|Teaching Tips|원고.*(?:작성|집필).*모집'):
        return pick('근로·알바·학생조교', '원고·콘텐츠 제작', '원고·학습자료 제작 업무')
    if has(r'연구조교|연구\s*조교|연구보조원|RA\s*모집|RA\('):
        return pick('근로·알바·학생조교', '학생 연구보조', '학생 연구 보조 업무')
    if has(r'박사\s*후|Post.?doc'):
        return pick('취업·인턴·현장실습', '박사후연구원', '박사후 연구직 고용')
    if has(r'(?:교수|교원|강사).*(?:채용|초빙|공개전형|임용)|(?:채용|초빙).*(?:교수|교원)|강의배정|Distinguished Faculty'):
        return pick('취업·인턴·현장실습', '교원·전문연구직', '교원·강사 채용/임용')
    if has(r'직원|자체계약직|Project Manager|행정원|행정인력|행정\s*직|행정지원|행정\s*연구원|연구행정|연구비\s*관리|행정실무자|랩매니저|연구과제지원\s*연구원|연구보조인력|전임연구인력'):
        return pick('취업·인턴·현장실습', '대학 직원 채용', '직원·연구행정 고용')
    if has(r'지도교수 모집'):
        return pick('연구경험·학술지원', '학생 연구프로젝트', '프로젝트 지도교수 모집; 교원 고용 공고 아님')
    if has(r'연구 참여원'):
        return pick('근로·알바·학생조교', '단기·행사·시험 근로', '토론회 연구활동·행사 지원 업무')
    if has(r'송파채움교실.*강사'):
        return pick('근로·알바·학생조교', '수업지원 조교', '학생·학위소지자 대상 시간제 유급 강의')
    if has(r'학부연구생|학부생.*연구.*인턴|학부.*인턴.*연구|연구.*학부생|NEXGEM Internship'):
        return pick('연구경험·학술지원', '학부연구생·연구실 인턴', '학부 연구실 참여')
    if has(r'실험|연구참여자|연구 참여자|연구대상자|재활.*참여자|신체 도식|통증 예측과 뇌 반응|뇌영상 데이터|기억과제') and not has(r'실험실창업|설계실무|실험 보조'):
        sub = '재활·건강 연구' if has(r'재활|발목|요통|통증') else '뇌영상·인지 실험' if has(r'MRI|뇌|인지|기억|지각|신체 도식') else '온라인·행동·언어 실험'
        return pick('실험·설문·인터뷰 참여', sub, '연구 대상자 모집')
    if has(r'설문|예비조사|본조사|인터뷰이|FGI|이중언어자.*번역'):
        sub = '인터뷰·사용성 평가' if has(r'인터뷰|FGI') else '설문·조사'
        if has(r'이중언어자.*번역'):
            return pick('근로·알바·학생조교', '원고·콘텐츠 제작', '척도 번역·검토 작업에 대한 보수')
        return pick('실험·설문·인터뷰 참여', sub, '조사·인터뷰 참여')
    if has(r'현장실습|현장\s*실습'):
        return pick('취업·인턴·현장실습', '학점인정 현장실습', '현장실습 참여')
    if has(r'교환장학생|교환학생|CAMPUS Asia|일본파견|중국파견'):
        return pick('국제교류·해외연수', '교환·파견', '교환·파견이 주목적')
    if has(r'해외봉사|KOICA.*봉사|월드프렌즈|아프리카중남미') and not has(r'설명회'):
        return pick('국제교류·해외연수', '해외봉사', '해외 파견 봉사')
    if has(r'글로벌 버디|SG MAPLE|프렌즈 프로그램|RISE HANS|국제공동수업.*봉사'):
        return pick('국제교류·해외연수', '국내 버디·국제교류', '국내 국제교류 활동')
    if has(r'해외교육|해외 교육|CMU|Carnegie Mellon|파견 교육생|AICOSS.*(?:독일|UNLV|UTAS)|한미대학생연수|WEST'):
        return pick('국제교류·해외연수', '해외 집중교육', '해외 교육·연수')
    if has(r'해외연수|해외 연수|해외탐방|해외융합|방일단|파견대표단|파란사다리|경기청년 사다리|한미첨단분야 청년교류|중봉뇌과학펠로우|St. Gallen|한미학생회의|S-Global Challenger|청년발전행동|YCAFE|해외 취창업|청소년교류'):
        return pick('국제교류·해외연수', '해외탐방·연구연수', '국제교류·해외 탐방/연구연수')
    if has(r'YEHS.*신입회원'):
        return pick('봉사·멘토링·서포터즈', '학생단체·교내 언론', '공학 학생 네트워크 회원 모집')
    if has(r'설명회|특강|강연|세미나|심포지엄|컨퍼런스|콘퍼런스|Conference|포럼|박람회|EXPO|축제|ESKARA|페스티벌|Convergence Capabilities|잡 콘서트|스마트라이프위크|대학원 한마당|이벤트|커피와 츄러스|북토크|토크 콘서트') and not has(r'공모전|경진대회|자원봉사|서포터즈|봉사단|멘토단|연구팀|공모전.*진행자'):
        sub = '직무·채용 설명회' if has(r'직무.*설명회|채용설명회|채용 설명회') else '사업·진학 설명회' if has(r'설명회') else '포럼·박람회' if has(r'포럼|박람회|EXPO|컨퍼런스|콘퍼런스|Conference') else '참여 이벤트' if has(r'이벤트|커피와 츄러스|북토크') else '축제·문화' if has(r'축제|ESKARA|페스티벌|공연') else '학술강연·세미나'
        return pick('행사·강연·문화', sub, '행사 참석·안내')
    if has(r'공모전|경진대회|해커톤|경연대회|투자 대회|구름톤|모의 IMO|Global Livinglab|문학상|아이디어 공모|아이디어.*프로젝트|Challenge|챌린지|대학가요제|자원봉사대회|모두의 아이디어'):
        sub = '창업 경진대회' if has(r'창업|Pioneers') else '창작·문예·영상' if has(r'문학|사진|영상|문예|가요') else '아이디어·정책' if has(r'아이디어|정책|논문 공모|우수사례') else '기술·해커톤'
        return pick('공모전·경진대회', sub, '심사·경쟁·수상형 모집')
    if has(r'CES.*참가기업'):
        return pick('창업·사업화', '사업화·기술이전', '기업 해외 전시·시장 진출 지원')
    if has(r'창업|텍스코어|TeX.Corps|사업화|기술이전|BRIDGE|지식재산권'):
        sub = '창업동아리' if has(r'동아리|CREW') else '보육·입주기업' if has(r'입주|보육|레지던시|성창재') else '사업화·기술이전' if has(r'사업화|기술이전|기술개발과제|자문') else '창업 멘토링' if has(r'멘토링') else '예비창업·탐색'
        return pick('창업·사업화', sub, '창업·사업화 활동/지원')
    if has(r'장학|장학생|등록금.*지원|등록금.*반값|학자금') and not has(r'근로|홍보대사|멘토링|멘토|학사.*입사|기관모집'):
        sub = '학자금대출·이자지원' if has(r'대출|이자') else '산학·채용연계 장학' if has(r'산학|채용|연구장학생|Track|트랙') else '국가장학' if has(r'국가장학|한국장학재단|주거안정장학|푸른등대') else '생활비 장학' if has(r'생활비') else '성적·연구우수 장학' if has(r'우수|연구우수') else '등록금 장학' if has(r'등록금') else '재단·지자체 장학' if legacy_category=='교외장학' or has(r'재단|장학회|장학재단') else '장학생 선발'
        return pick('장학·학비지원', sub, '장학·학비 지원')
    if has(r'기숙사|입주자|입주생|입사생|주거|새빛호스텔|연합생활관|고촌학사'):
        return pick('생활·복지·시설', '기숙사·주거', '주거·입사 지원')
    if has(r'상담|마인드힐링|Mental Care|정서지원') and not has(r'멘토|지원단|서포터즈'):
        return pick('생활·복지·시설', '심리상담', '상담·심리 지원')
    if has(r'피트니스|체력증진센터|운동장|시설.*이용'):
        return pick('생활·복지·시설', '시설 이용', '교내 시설 이용')
    if has(r'셔틀버스|교통|마을버스'):
        return pick('생활·복지·시설', '교통', '교통·이동 지원')
    if has(r'금연|웰니스|Wellness|Movement|MOVEMENT|야구.*재능 기부|농구.*재능 기부|메디케어'):
        return pick('생활·복지·시설', '건강·체육', '건강·체육 프로그램 이용')
    if has(r'기본소득|장려금|청년문화패스|청년 주거|자립준비청년|인생설계학교'):
        return pick('생활·복지·시설', '청년정책·생활지원', '공공 청년·생활 지원')
    if has(r'장학사업.*기관|기관모집'):
        return result('근로·알바·학생조교', '국가근로', '기관 대상 근로사업 참여 모집; 학생 일자리 아님', 'needs_review')
    if has(r'수습기자|신문사|방송국|뉴미디어부|학생단체'):
        return pick('봉사·멘토링·서포터즈', '학생단체·교내 언론', '교내 학생 언론·단체')
    if has(r'멘티|취업탐색 멘토링|글로벌 멘토링|크로스 멘토|현직자|토스뱅크 개발자|선배.*멘토링|교수멘토링|로드맵'):
        return pick('교육·역량개발', '학습·진로 멘토링', '멘티의 학습·진로 개발')
    if has(r'멘토|멘토링|서울런|드림클래스|랜선나눔|랜선야학'):
        return pick('봉사·멘토링·서포터즈', '교육 멘토', '교육 멘토 역할 모집')
    if has(r'서포터즈|기자단|홍보대사|테크 컴패니언즈|청년기획단|도민주주단|제작팀|디깅단'):
        return pick('봉사·멘토링·서포터즈', '홍보·기자단', '홍보·콘텐츠·대학생 활동')
    if has(r'봉사|재능기부|방과후|돌봄교실|바자|두드림단|배워서 남 주는'):
        sub = '행사 자원봉사' if has(r'행사|마라톤|축제|페스티벌|기념식|한마당') else '의료·복지·환경봉사'
        return pick('봉사·멘토링·서포터즈', sub, '봉사 활동')
    if has(r'학위수여|학위증서|학위복|수업연한단축|졸업|수료|이수포기|논문대체'):
        return pick('학사·행정', '졸업·학위', '졸업·학위 절차')
    if has(r'학생증|증명서'):
        return pick('학사·행정', '학생증·증명', '학생증·증명 발급')
    if has(r'등록금.*납부|선택경비|등록.*납부'):
        return pick('학사·행정', '등록·납부', '등록·납부 절차')
    if has(r'출석|평가 제도|교차수강'):
        return pick('학사·행정', '수강·출석·평가', '수업 운영·제도')
    if has(r'예비군'):
        return pick('학사·행정', '예비군', '예비군 일정')
    if has(r'안전조치|통제구역|연휴.*안내'):
        return pick('학사·행정', '안전·운영 안내', '안전·운영 공지')
    if has(r'학군사관|ROTC|전문연구요원|공무원|수습직원|공정선거지원단'):
        return pick('취업·인턴·현장실습', '공직·군 진출', '공직·군·전문연구요원')
    if has(r'연구학점'):
        return pick('연구경험·학술지원', '연구학점', '연구학점 참여')
    if has(r'Qualcomm Innovation Fellowship'):
        return pick('장학·학비지원', '성적·연구우수 장학', '논문 심사 기반 연구 장학금')
    if has(r'청년밥상'):
        return pick('장학·학비지원', '생활비 장학', '저소득 대학생 식비 장학금')
    if has(r'논문 모집|논문.*투고|연구발표|학술.*발표|포스터 발표'):
        return pick('연구경험·학술지원', '논문 투고·학술발표', '논문·연구성과 발표')
    if has(r'클라우드.*사용자|연구 모임|학술.*지원|기술개발과제|기술혁신자문'):
        return pick('연구경험·학술지원', '연구 인프라 지원', '연구자원·과제 지원')
    if has(r'연구팀|연구과제|캡스톤|산학프로젝트|성장경로'):
        return pick('연구경험·학술지원', '학생 연구프로젝트', '학생 프로젝트·연구 참여')
    if has(r'기업 현장체험|NVIDIA-SeoulTech'):
        return pick('교육·역량개발', '기술·직무교육', '기업 견학·기술 실무 체험')
    if has(r'마이크로디그리|수강|교과목|복수전공|융합트랙|이수증|강좌|강의 안내'):
        return pick('교육·역량개발', '교과·마이크로디그리', '교과·이수과정 신청')
    if has(r'자격증|AICE|AI-901|국제인증'):
        return pick('교육·역량개발', '자격증', '자격·인증 교육')
    if has(r'고시|스터디|언론사준비반|변리사반|실원'):
        return pick('교육·역량개발', '고시·스터디', '시험 준비·스터디')
    if has(r'부트캠프|bootcamp'):
        return pick('교육·역량개발', '부트캠프', '집중 교육')
    if has(r'교육|워크숍|워크샵|아카데미|Academy|단기연수|전문가 과정|철학캠프|요리학교|통계 실습|수강생|교육생|School|썸머스쿨|Summer School|PharmXplore|SAY'):
        return pick('교육·역량개발', '기술·직무교육', '교육·워크숍 참여')
    if has(r'프로젝트|Project|비교과|비교가 프로그램|SPRINT|라이프클럽|인성함양|시민의식|창조스쿨|Student Fellow|성균공부방|리빙랩|Living Lab|커뮤니티|공감 프로그램|자기이해|HUSS-POP'):
        return pick('교육·역량개발', '비교과·팀프로젝트', '비교과·체험 프로젝트')
    if has(r'인턴|일경험|일자리 참여자|POS-TEP'):
        return pick('취업·인턴·현장실습', '인턴·일경험', '직무 경험 모집')
    if has(r'근로장학생|근로학생', body[:700]):
        return pick('근로·알바·학생조교', '교내근로', '본문에 명시된 학생 근로 모집')
    if has(r'채용|연구원 모집|연구원\(보\)|엔지니어|담당자.*모집'):
        return pick('취업·인턴·현장실습', '기업·공공기관 채용', '고용·채용 모집')
    if has(r'교내장학|교외장학', legacy_category) and has(r'장학', body[:1200]):
        return result('장학·학비지원', '장학생 선발', '기존 장학 라벨·본문의 장학 표현; 확인 필요', 'needs_review')
    return dict(main_category=None, subcategory=None, classification_status='needs_review',
                classification_reason='제목·본문으로 분류 확정 불가')


CONDITION_PATTERNS = {
    'applicant_type': r'기관|기업|교원|교직원|학생|대학|팀|성인|누구나|제한\s*없',
    'education': r'학부|대학원|석사|박사|학사|학위|전문학사|대학.*졸업',
    'enrollment': r'재학|휴학|수료|재적|졸업예정|졸업생|연구등록',
    'grade': r'[1-6１-６].*학년|학기|학년',
    'major': r'전공|학과|학부|계열|이공|인문',
    'gpa': r'평점|성적|GPA|학점.*이상|백분위',
    'income': r'소득|구간|분위|수급|차상위|중위소득|생계',
    'residence': r'거주|주민등록|주소|출신|지역|전입|국적|시민권',
    'restrictions': r'불가|제외|제한|미만|중복|결격|금지|이하|이상|필수|반드시|가능|자격|조건',
    'preferences': r'우대|우선|권장',
}


def extract_eligibility(target_audience, full_text=''):
    """Store verbatim clauses, including exclusions; never infer allowed status from keywords."""
    target = text(target_audience)
    evidence = []
    if target not in UNKNOWN:
        evidence.append(target)
    # Keep the eligibility section only; do not turn benefits or schedules into conditions.
    lines = full_text.splitlines()
    active = False
    for line in lines:
        stripped = line.strip()
        if re.search(r'(?:지원|신청|참여|응모)\s*(?:자격|대상|조건)|자격\s*요건|모집\s*대상|우대\s*사항', stripped):
            active = True
        elif active and re.match(r'^(?:[0-9]+[.)]|[가-하][.)]|[□■▶])\s*', stripped) and re.search(r'기간|일정|방법|서류|처우|혜택|급여|문의|선발|인원|업무|시간|내용|지원금', stripped):
            active = False
        if active and stripped and len(stripped) <= 1000:
            evidence.append(stripped)
    clauses = list(dict.fromkeys(part.strip(' \t-•⦁') for item in evidence for part in item.splitlines() if part.strip(' \t-•⦁')))
    result = {key: [s for s in clauses if re.search(pattern, s, re.I)] for key, pattern in CONDITION_PATTERNS.items()}
    result['evidence'] = clauses
    result['status'] = 'extracted' if clauses else 'not_stated'
    return result


def grounded_clauses(value, source):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError('원문 근거는 비어 있지 않은 문자열 배열이어야 함')
    normalize = lambda s: re.sub(r'\s+', '', unicodedata.normalize('NFKC', s))
    normalized_source = normalize(source)
    if any(normalize(item) not in normalized_source for item in value):
        raise ValueError('LLM 근거 문구가 원문에 없음')
    return list(dict.fromkeys(value))


def classification_fields(title, full_text, target_audience, benefit, legacy_category, llm_result=None):
    rule = classify(title, full_text, target_audience, benefit, legacy_category)
    decision = dict(rule)
    conditions = extract_eligibility(target_audience, full_text)
    if llm_result is not None:
        main, sub = llm_result.get('main_category'), llm_result.get('subcategory')
        issues = []
        source = title + '\n' + full_text
        grounded_target = []
        for clause in text(target_audience).splitlines():
            if not clause.strip():
                continue
            try:
                grounded_target.extend(grounded_clauses([clause], source))
            except ValueError:
                pass
        conditions = extract_eligibility('\n'.join(grounded_target), full_text)
        if isinstance(main, str) and main in TAXONOMY and isinstance(sub, str) and sub in TAXONOMY[main]:
            decision = dict(main_category=main, subcategory=sub, classification_status='auto',
                            classification_reason='LLM 분류')
            if rule['main_category'] and (main, sub) != (rule['main_category'], rule['subcategory']):
                issues.append(f"규칙과 불일치: {rule['main_category']}/{rule['subcategory']}")
                if rule['classification_status'] == 'auto':
                    decision['main_category'] = rule['main_category']
                    decision['subcategory'] = rule['subcategory']
                    decision['classification_reason'] = f'규칙 분류 유지; LLM 후보: {main}/{sub}'
            reason = llm_result.get('classification_reason')
            if isinstance(reason, str) and reason.strip():
                decision['classification_reason'] += ': ' + reason.strip()
            else:
                issues.append('LLM 분류 이유 누락')
            try:
                evidence = grounded_clauses(llm_result.get('classification_evidence'), source)
                if not evidence:
                    raise ValueError('LLM 분류 근거 누락')
                decision['classification_reason'] += '; 원문 근거: ' + ' / '.join(evidence)
            except ValueError as error:
                issues.append(str(error))
        else:
            issues.append('LLM 분류 조합 누락/오류; 규칙 분류 사용')
        try:
            raw = llm_result.get('eligibility_conditions')
            if raw is None:
                raw = {key: conditions[key] for key in (*CONDITION_PATTERNS, 'evidence')}
            if not isinstance(raw, dict):
                raise ValueError('LLM 대상 조건 형식 오류; 원문 추출 사용')
            fields = {key: grounded_clauses(raw.get(key), source) for key in (*CONDITION_PATTERNS, 'evidence')}
            evidence = list(dict.fromkeys(item for values in fields.values() for item in values))
            if evidence or not conditions['evidence']:
                for key in (*CONDITION_PATTERNS, 'evidence'):
                    fields[key] = list(dict.fromkeys(conditions[key] + fields[key]))
                fields['evidence'] = list(dict.fromkeys(fields['evidence'] + evidence))
                fields['status'] = 'extracted' if fields['evidence'] else 'not_stated'
                conditions = fields
            else:
                issues.append('LLM 대상 조건 비어 있음; 원문 추출 사용')
        except ValueError as error:
            issues.append(str(error))
        if llm_result.get('needs_review') is not False:
            issues.append('LLM 검토 필요 또는 검토 상태 누락')
        if not full_text.strip():
            issues.append('본문 없음')
        if issues:
            decision['classification_status'] = 'needs_review'
            decision['classification_reason'] += '; ' + '; '.join(issues)
    decision['eligibility_conditions'] = json.dumps(conditions, ensure_ascii=False)
    return decision
