"""Normalize explicit eligibility into comparable values, preserving unknown/ambiguous states."""
import json
import re
import unicodedata

FIELDS = ('studyLevel', 'studentYear', 'enrollment', 'incomeTier', 'degreeLevel',
          'graduationStatus', 'experienceYears', 'gpa', 'age', 'workAvailability', 'applicantType')
DEGREES = ['high_school', 'associate', 'bachelor', 'master', 'doctorate']
STUDIES = ['undergraduate', 'masters', 'doctoral']
STATUSES = {
    'enrolled': r'재학생|재학중|재학|재적생|재적',
    'on_leave': r'휴학예정자|휴학생|휴학자|휴학',
    'completed': r'수료생|수료자|수료',
    'research_registered': r'연구등록생|연구등록',
    'expected_graduate': r'졸업\s*예정자|졸업\s*예정생|졸업\s*예정',
    'graduated': r'졸업생|졸업자',
}
NEGATIVE = r'(?:지원|참여|선발|활동|수혜)?\s*(?:불가|제외|금지|불가능|미선발|不可|不許)'


def normalize(value):
    value = unicodedata.normalize('NFKC', value or '')
    value = re.sub(r'재\s*[/·ㆍ]\s*휴학', '재학·휴학', value)
    return value.replace('석/박사', '석사·박사').replace('석·박사', '석사·박사')


def contexts(value):
    """Parenthesized exclusions must not negate the preceding eligible group."""
    result = re.findall(r'\(([^()]*)\)', value)
    result.append(re.sub(r'\([^()]*\)', '', value))
    return result


def preferred(text, end):
    tail = text[end:end + 70]
    return bool(re.match(r'\s*(?:학위|졸업|소지자|취득자|보유자|전공자|이상|과정|자|인\s*자|관련|분야|경력|의|를|을|\s)*\s*우대', tail))


def denied(text, end, terms):
    tail = text[end:]
    connector = r'(?:\s|[,/·ㆍ]|및|또는|과|와|은|는|도|의\s*경우)'
    chain = rf'(?:{connector}|{terms})*'
    return bool(re.match(chain + NEGATIVE, tail))


def enum_mentions(value, definitions):
    terms = '|'.join(f'(?:{pattern})' for pattern in definitions.values())
    positive, negative = set(), set()
    for context in contexts(value):
        for key, pattern in definitions.items():
            for match in re.finditer(pattern, context):
                if preferred(context, match.end()):
                    continue
                (negative if denied(context, match.end(), terms) else positive).add(key)
    return positive - negative, negative


def eligibility_source(target, full_text):
    # This data already exists in the DB; supplement it with the original eligibility sections.
    from classification import extract_eligibility
    original = extract_eligibility('', full_text)['evidence']
    meaningful = [line for line in original if len(line) > 10 and not re.fullmatch(r'[\d. )가-하]*[지원신청참여모집자격대상요건우대사항 ]+', line)]
    clauses = original if meaningful else extract_eligibility(target, '')['evidence']
    mandatory = []
    in_preferences = False
    for line in clauses:
        if re.search(r'^(?:[○□■▶]|[0-9]+[.)])?\s*(?:지원내용|지원내역|지원금액|선발절차|지원서\s*접수|제출서류|접수기간|접수방법)', line):
            break
        if re.search(r'우대\s*사항', line) and len(line) < 30:
            in_preferences = True
        elif re.search(r'^(?:\d+[.)]|[가-하][.)]|[□■▶]).*(?:자격|대상|조건)', line):
            in_preferences = False
        if not in_preferences:
            mandatory.append(line)
    return normalize('\n'.join(mandatory)), clauses


def extract_profile(title, full_text='', target_audience='', main_category='', subcategory=''):
    source, clauses = eligibility_source(target_audience, full_text)
    if full_text and target_audience:
        for pattern in (r'소득|분위|구간|수급|차상위', r'평점|GPA', r'전일제|풀타임|시간제'):
            if not re.search(pattern, source):
                supplements = [line for line in normalize(target_audience).splitlines() if re.search(pattern, line)]
                source += '\n' + '\n'.join(supplements)
    states = dict.fromkeys(FIELDS, 'unknown')
    evidence = {field: [] for field in FIELDS}
    result = {key: None for key in ('study_levels', 'student_years', 'enrollment_statuses', 'income_tiers',
                                  'degree_levels', 'graduation_statuses', 'experience_min', 'experience_max',
                                  'experience_required', 'gpa_minima', 'age_min', 'age_max',
                                  'requires_full_time', 'applicant_types')}
    caveats = []

    def set_field(field, state, **values):
        states[field] = state
        result.update(values)

    def cite(field, pattern):
        evidence[field] = list(dict.fromkeys(line for line in clauses if re.search(pattern, normalize(line), re.I)))

    study_patterns = {'undergraduate': r'학부생|학부\s*재학생|학부|학사과정|학사\s*과정|대학생(?!활)|대학교?\s*재학생',
                      'masters': r'석사(?:과정)?|대학원생|대학원\s*재학생|대학원\s*과정',
                      'doctoral': r'박사(?:과정)?|대학원생|대학원\s*재학생|대학원\s*과정'}
    # Degree holders in a recruitment notice are not currently enrolled students.
    study_source = re.sub(r'(?:전문)?학사\s*(?:학위|이상|졸업)|(?:석사|박사)\s*(?:학위\s*)?(?:소지자|취득자|졸업자|이상)|(?:석사|박사)\s*학위', '', source)
    study, denied_study = enum_mentions(study_source, study_patterns)
    if '대학(원)' in source or '대학 및 대학원' in source or '대학/대학원' in source:
        study.update(STUDIES)
    study = sorted(study)
    if study:
        set_field('studyLevel', 'known', study_levels=study)
    cite('studyLevel', r'학부|대학생|학사과정|석사|박사|대학원')

    years, excluded_years = set(), set()
    year_pattern = r'(?<![0-9])([1-6](?:\s*(?:[~∼〜\-–,·ㆍ/]|및|또는|과|와)\s*[1-6])*)\s*학년(?!도)'
    for match in re.finditer(year_pattern, source):
        tail = source[match.end():match.end() + 70]
        if re.search(r'성적증명|성적.*\($', source[max(0,match.start()-20):match.start()]): continue
        if re.match(r'\s*(?:전체\s*)?(?:평균|성적|평점|취득|이수)', tail):
            continue  # Previous-year grades are not a current-year admission restriction.
        digits = [int(n) for n in re.findall(r'[1-6]', match.group(1))]
        if re.search(r'[~∼〜\-–]', match.group(1)):
            allowed = set(range(min(digits), max(digits) + 1))
        else:
            allowed = set(digits)
        if re.match(r'\s*이상', tail): allowed = set(range(min(allowed), 7))
        if re.match(r'\s*이하', tail): allowed = set(range(1, max(allowed) + 1))
        # A semester-specific exclusion does not exclude that whole academic year.
        negative = not re.match(r'\s*[12]\s*학기', tail) and bool(re.match(r'\s*(?:및\s*휴학생|재학생|학생|은|는|의\s*경우|지원|참여|선발|\s)*' + NEGATIVE, tail))
        (excluded_years if negative else years).update(allowed)
    if re.search(r'신입생|새내기', source) and not years:
        years.add(1)
    years -= excluded_years
    if years:
        set_field('studentYear', 'known', student_years=sorted(years))
        if states['studyLevel'] == 'unknown':
            set_field('studyLevel', 'known', study_levels=['undergraduate'])
    if re.search(r'학년\s*무관|학년\s*제한\s*없|모든\s*학년|전\s*학년\s*(?:대상|가능)', source):
        set_field('studentYear', 'any', student_years=list(range(1, 7)))
    if re.search(r'[56]\s*년제', source) and years:
        states['studentYear'] = 'ambiguous'
        caveats.append('학제별 학년 조건이 달라 원문 확인 필요')
    if re.search(r'학년|학기|등록학기|잔여학기', source):
        caveats.append('학년 외 학기·등록·잔여학기 요건은 원문 확인')
    if states['studentYear'] == 'unknown' and 'undergraduate' in study and re.search(r'학부생|학부\s*재학생|학사\s*과정', source):
        if re.search(r'학기|등록학기|잔여학기', source):
            states['studentYear'] = 'ambiguous'
        else:
            set_field('studentYear', 'any', student_years=list(range(1, 7)))
    if re.search(r'학년.{0,12}(?:진급|재학)\s*예정|[1-6]\s*-\s*[12].{0,15}학년', source):
        states['studentYear'] = 'ambiguous'
        caveats.append('진급 시점 또는 학년·학기 표기 확인 필요')
    cite('studentYear', r'학년|학기|신입생|새내기')

    allowed_status, denied_status = enum_mentions(source, STATUSES)
    if allowed_status or denied_status:
        if not allowed_status:
            allowed_status = set(STATUSES) - denied_status
        set_field('enrollment', 'known', enrollment_statuses=sorted(allowed_status))
    cite('enrollment', r'재학|휴학|수료|졸업|재적|연구등록')

    incomes = set()
    income_context = '\n'.join(line for line in source.splitlines() if re.search(r'소득|분위|지원\s*구간|수급|차상위', line))
    income_pattern = r'(?:(?:학자금\s*)?(?:지원\s*)?(?:소득\s*)?(?:지원\s*)?구간\s*|소득\s*분위\s*)?([0-9]|10)(?:\s*[~∼\-–]\s*([0-9]|10))?\s*(?:구간|분위)\s*(?:\([^()]*\)\s*)?(이하|이내|이상|초과|미만)?'
    for match in re.finditer(income_pattern, income_context):
        low, high = int(match.group(1)), int(match.group(2) or match.group(1))
        operator = match.group(3)
        if match.group(2): values = set(range(low, high + 1))
        elif operator in ('이하', '이내'): values = set(range(0, high + 1))
        elif operator == '미만': values = set(range(0, high))
        elif operator == '이상': values = set(range(low, 11))
        elif operator == '초과': values = set(range(low + 1, 11))
        else: values = {low}
        if values and values <= set(range(11)): incomes.update(str(n) for n in values)
    if re.search(r'기초\s*생활\s*수급|기초\s*수급', income_context): incomes.add('basic')
    if re.search(r'차상위', income_context): incomes.add('near_poor')
    if incomes:
        set_field('incomeTier', 'known', income_tiers=sorted(incomes))
    if re.search(r'(?:소득|구간|분위)\s*(?:제한\s*없|무관)', source):
        set_field('incomeTier', 'any', income_tiers=[])
    if income_context and re.search(r'또는|조건\s*중\s*하나|아래\s*조건\s*중\s*하나|하나를\s*충족', source):
        states['incomeTier'] = 'ambiguous'
        caveats.append('소득 외 대체 지원자격이 있어 소득 단독 판정 보류')
    if re.search(r'중위소득|건강보험료', source) and not incomes:
        states['incomeTier'] = 'ambiguous'
        caveats.append('중위소득 비율·보험료를 학자금 구간으로 임의 환산하지 않음')
    cite('incomeTier', r'소득|분위|구간|수급|차상위|건강보험료')

    degree_matches = []
    degree_patterns = {'high_school': r'고졸|고등학교\s*졸업', 'associate': r'전문학사|전문대(?:학)?\s*(?:이상\s*)?졸업',
                       'bachelor': r'(?<!전문)학사\s*(?!과정)(?:학위|이상|졸업|취득|소지)|4년제\s*(?:정규\s*)?대학(?:교)?\s*졸업|대학(?:교)?\s*졸업\s*\(?4년',
                       'master': r'석사\s*(?:학위|이상|졸업|취득|소지)', 'doctorate': r'박사\s*(?:학위|이상|졸업|취득|소지)'}
    for name, pattern in degree_patterns.items():
        for context in contexts(source):
          for match in re.finditer(pattern, context):
            if preferred(context, match.end()) or denied(context, match.end(), '|'.join(degree_patterns.values()) + '|' + STATUSES['expected_graduate']):
                continue
            if name == 'bachelor' and re.match(r'\s*과정', context[match.end():]): continue
            degree_matches.append(DEGREES.index(name))
    if degree_matches:
        minimum = min(degree_matches)
        set_field('degreeLevel', 'known', degree_levels=DEGREES[minimum:])
    if re.search(r'학력\s*무관|학위\s*무관|학력\s*제한\s*없', source):
        set_field('degreeLevel', 'any', degree_levels=DEGREES)
    if re.search(r'(?:학사|석사|박사)\s*(?:학위\s*)?수료', source):
        states['degreeLevel'] = 'ambiguous'
        caveats.append('학위 취득과 과정 수료 요건 구분 필요')
    if len(set(degree_matches)) > 1 and re.search(r'분야에\s*한정|분야별|직무별|부문별', source):
        states['degreeLevel'] = 'ambiguous'
        caveats.append('직무·분야별 학력 요건이 다름')
    cite('degreeLevel', r'학사|석사|박사|고졸|전문대|대학.*졸업|학력')

    expected, denied_expected = enum_mentions(source, {'expected': STATUSES['expected_graduate']})
    if 'expected' in denied_expected:
        set_field('graduationStatus', 'known', graduation_statuses=['graduated'])
    elif 'expected' in expected:
        set_field('graduationStatus', 'known', graduation_statuses=['graduated', 'expected'])
    elif degree_matches and re.search(r'취득자|소지자|보유자|졸업자|졸업\s*학력', source):
        # Whether upcoming graduates qualify is unstated, rather than automatically allowed.
        set_field('graduationStatus', 'ambiguous', graduation_statuses=['graduated'])
    cite('graduationStatus', r'졸업|소지자|취득자')

    career_values = []
    for match in re.finditer(r'(?:경력|경험)\s*(?:합계\s*)?(\d+(?:\.\d+)?)\s*(?:~\s*(\d+(?:\.\d+)?))?\s*년\s*(이상|이하|미만|이내)?', source):
        if preferred(source, match.end()): continue
        low, high = float(match.group(1)), float(match.group(2)) if match.group(2) else None
        if match.group(3) in ('이하', '이내', '미만') and high is None:
            low, high = 0, low
        career_values.append((low, high))
    if career_values:
        set_field('experienceYears', 'known', experience_min=max(n[0] for n in career_values),
                  experience_max=min((n[1] for n in career_values if n[1] is not None), default=None), experience_required=1)
    elif re.search(r'경력\s*무관|신입\s*[/·,]\s*경력|신입.*지원\s*가능|신입', source):
        set_field('experienceYears', 'any', experience_min=0, experience_required=0)
    elif re.search(r'(?:경력|경험).{0,18}우대|우대사항.{0,25}(?:경력|경험)', source):
        set_field('experienceYears', 'any', experience_min=0, experience_required=0)
    elif re.search(r'경력자|유경험자|경력\s*보유', source):
        set_field('experienceYears', 'known', experience_min=0, experience_required=1)
    cite('experienceYears', r'경력|경험|신입')

    gpa = {}
    for line in source.splitlines():
        if not re.search(r'성적|평점|학점|GPA', line, re.I): continue
        for match in re.finditer(r'([0-4]\.\d+)\s*/\s*(4\.[35])', line):
            score, scale = float(match.group(1)), match.group(2)
            if 0 <= score <= float(scale): gpa[scale] = max(gpa.get(scale, 0), score)
        for match in re.finditer(r'(4\.[35])\s*(?:만점\s*)?(?:기준|만점)[^\n]{0,12}?([0-4]\.\d+)\s*이상', line):
            scale, score = match.group(1), float(match.group(2))
            if score <= float(scale): gpa[scale] = max(gpa.get(scale, 0), score)
        for match in re.finditer(r'(?:평점(?:평균)?|평균\s*평점|학점)\s*([0-4]\.\d+)\s*이상.{0,20}?(4\.[35])\s*만점', line):
            score, scale = float(match.group(1)), match.group(2)
            if score <= float(scale): gpa[scale] = max(gpa.get(scale, 0), score)
    if gpa: set_field('gpa', 'known', gpa_minima=gpa)
    elif re.search(r'(?:평점|GPA|성적).{0,25}\d\.\d|평점\s*평균|성적.*[AB][+0^]', source, re.I):
        states['gpa'] = 'ambiguous'
        caveats.append('성적 만점 기준 또는 평가 방식 확인 필요')
    if gpa and re.search(r'또는\s*(?:학과\s*)?석차|직전.*전체|직전.*평균\s*평점|직전.*전\s*학기', source):
        states['gpa'] = 'ambiguous'
        caveats.append('성적의 대체·직전·누적 요건을 한 점수로 단순화하지 않음')
    cite('gpa', r'성적|평점|GPA|학점')

    age_matches = list(re.finditer(r'(?:만\s*)?(\d{1,2})\s*(?:~\s*(\d{1,2}))?\s*세\s*(이상|이하|미만|초과)?', source))
    if age_matches:
        lows, highs = [], []
        for match in age_matches:
            n, upper, op = int(match.group(1)), match.group(2), match.group(3)
            if upper: lows.append(n); highs.append(int(upper))
            elif op == '이상': lows.append(n)
            elif op == '초과': lows.append(n + 1)
            elif op == '이하': highs.append(n)
            elif op == '미만': highs.append(n - 1)
            else: lows.append(n); highs.append(n)
        low, high = max(lows, default=0), min(highs, default=None)
        if high is None or low <= high: set_field('age', 'known', age_min=low, age_max=high)
        else: states['age'] = 'ambiguous'
    cite('age', r'세|출생|나이|연령')

    work_source = normalize(target_audience)
    if re.search(r'전일제|풀타임|전일\s*근무', work_source):
        if re.search(r'(?:전일제|풀타임|전일\s*근무).{0,12}우대', work_source):
            set_field('workAvailability', 'any', requires_full_time=0)
        else: set_field('workAvailability', 'known', requires_full_time=1)
    elif re.search(r'파트타임|시간제|주\s*1[45](?:\.5)?\s*시간\s*(?:이하|이내)', work_source):
        set_field('workAvailability', 'known', requires_full_time=0)
    cite('workAvailability', r'전일|풀타임|파트타임|시간제|근무시간|근로시간')

    types = set()
    if re.search(r'기업|기관|사업자|법인', source) and re.search(r'기업|기관|입주|사업화', title): types.add('organization')
    if re.search(r'팀\s*(?:구성|단위|대표|신청)|구성된\s*팀|참가팀|개?팀|동아리', source): types.add('team')
    if re.search(r'개인|누구나|학생|성인|학위|졸업|재학', source) and not types: types.add('individual')
    if re.search(r'개인\s*(?:또는|및|/).*팀|개인.*팀.*모두', source): types.update(('individual', 'team'))
    if types: set_field('applicantType', 'known', applicant_types=sorted(types))
    cite('applicantType', r'개인|팀|기관|기업|동아리|학생|성인')

    if re.search(r'누구나|제한\s*없음|제한\s*없|자격\s*무관', source) and not re.search(r'전공\s*(?:제한|무관)|학위\s*무관|학년\s*무관', source):
        # Broad participation does not override an explicit numeric or exclusion condition.
        for field in ('studyLevel', 'studentYear', 'enrollment', 'age'):
            if states[field] == 'unknown': states[field] = 'any'
    result.update(field_states=states, evidence=evidence, caveats=list(dict.fromkeys(caveats)), version=1)
    return result


JSON_COLUMNS = ('study_levels', 'student_years', 'enrollment_statuses', 'income_tiers', 'degree_levels',
                'graduation_statuses', 'gpa_minima', 'applicant_types', 'field_states', 'evidence', 'caveats')


def save_profile(conn, notice_id, profile):
    columns = list(profile)
    values = [json.dumps(profile[key], ensure_ascii=False) if key in JSON_COLUMNS and profile[key] is not None else profile[key] for key in columns]
    conn.execute(f'''INSERT INTO notice_eligibility (notice_id, {','.join(columns)})
        VALUES ({','.join('?' for _ in range(len(columns) + 1))})
        ON CONFLICT(notice_id) DO UPDATE SET {','.join(f'{key}=excluded.{key}' for key in columns)}, updated_at=CURRENT_TIMESTAMP''',
                 [notice_id, *values])
