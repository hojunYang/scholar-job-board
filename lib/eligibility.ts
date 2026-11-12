import configuration from '@/data/profile-filters.json';

export const options: Record<string, [string, string][]> = {
  studyLevel: [['undergraduate','학부'],['masters','석사과정'],['doctoral','박사과정']],
  studentYear: Array.from({length:6},(_,i)=>[String(i+1),`${i+1}학년`]),
  enrollment: [['enrolled','재학'],['on_leave','휴학'],['completed','수료'],['research_registered','연구등록'],['expected_graduate','졸업예정'],['graduated','졸업']],
  incomeTier: [...Array.from({length:11},(_,i)=>[String(i),`${i}구간`] as [string,string]),['basic','기초생활수급'],['near_poor','차상위']],
  degreeLevel: [['high_school','고졸'],['associate','전문학사'],['bachelor','학사'],['master','석사'],['doctorate','박사']],
  graduationStatus: [['graduated','졸업 / 학위 취득'],['expected','졸업예정']],
  workAvailability: [['full_time','전일제 가능'],['part_time','시간제만 가능']],
  applicantType: [['individual','개인'],['team','팀'],['organization','기업·단체']],
};
export const labels: Record<string,string> = {studyLevel:'과정',studentYear:'현재 학년',enrollment:'학적',incomeTier:'학자금 지원구간',degreeLevel:'보유 학위',graduationStatus:'졸업 상태',experienceYears:'경력 (년)',gpa:'평점',age:'만 나이',workAvailability:'근무 가능 시간',applicantType:'신청 형태'};
export type Profile = Record<string,string>;
export function profileFields(category?: string, subcategory?: string): string[] {
  let fields = [...((configuration as Record<string,string[]>)[category || ''] || [])];
  if (category === '취업·인턴·현장실습' && /현장실습|인턴/.test(subcategory || '')) fields = ['studyLevel','studentYear','enrollment','graduationStatus','workAvailability'];
  if (category === '근로·알바·학생조교' && /국가근로/.test(subcategory || '')) fields.push('incomeTier');
  return fields;
}
export function parseProfile(params: Record<string,string|undefined>, category?: string, subcategory?: string): Profile {
  const result: Profile = {};
  for (const field of profileFields(category,subcategory)) {
    const value = params[field];
    if (!value) continue;
    if (options[field]?.some(([key])=>key===value)) result[field]=value;
    else if (['experienceYears','age','gpa'].includes(field) && /^\d+(\.\d+)?$/.test(value) && Number(value)<= (field==='gpa'?4.5:120)) result[field]=value;
  }
  if (result.studyLevel && result.studyLevel !== 'undergraduate') delete result.studentYear;
  if (result.studentYear && !result.studyLevel) result.studyLevel='undergraduate';
  if (result.gpa) { result.gpaScale=params.gpaScale==='4.3'?'4.3':'4.5'; if(Number(result.gpa)>Number(result.gpaScale)) delete result.gpa; }
  if(Object.keys(result).length && params.includeUnknown==='1') result.includeUnknown='1';
  return result;
}
export function profileSql(profile: Profile = {}) {
  const columns: Record<string,string> = {studyLevel:'study_levels',studentYear:'student_years',enrollment:'enrollment_statuses',incomeTier:'income_tiers',degreeLevel:'degree_levels',graduationStatus:'graduation_statuses',applicantType:'applicant_types'};
  const clauses: string[] = [], unknowns: string[] = [];
  const params: (string|number)[] = [];
  for(const [field,value] of Object.entries(profile)) {
    if(!labels[field]) continue;
    const state=`json_extract(eligibility.field_states, '$.${field}')`;
    let matches: string, unknown=`COALESCE(${state}, 'unknown') IN ('unknown','ambiguous')`;
    const bound: (string|number)[]=[];
    if(columns[field]) {matches=`EXISTS (SELECT 1 FROM json_each(eligibility.${columns[field]}) WHERE value = ?)`;bound.push(field==='studentYear'?Number(value):value);}
    else if(field==='gpa') {
      const path=`'$."${profile.gpaScale || '4.5'}"'`;
      matches=`json_extract(eligibility.gpa_minima, ${path}) <= ?`;bound.push(Number(value));
      unknown=`(${unknown} OR (${state} <> 'any' AND json_extract(eligibility.gpa_minima, ${path}) IS NULL))`;
    } else if(field==='experienceYears' || field==='age') {
      const prefix=field==='age'?'age':'experience';
      matches=`(eligibility.${prefix}_min IS NULL OR eligibility.${prefix}_min <= ?) AND (eligibility.${prefix}_max IS NULL OR eligibility.${prefix}_max >= ?)`;bound.push(Number(value),Number(value));
      if(field==='experienceYears') {matches+=` AND (COALESCE(eligibility.experience_required,0) = 0 OR ? > 0)`;bound.push(Number(value));}
    } else { matches=`(? = 'full_time' OR eligibility.requires_full_time = 0)`;bound.push(value); }
    clauses.push(`(${state} = 'any' OR (${state} = 'known' AND (${matches}))${profile.includeUnknown==='1'?` OR ${unknown}`:''})`);
    unknowns.push(unknown);params.push(...bound);
  }
  return { sql: clauses.join(' AND '), params, matchSql: clauses.length ? `CASE WHEN ${unknowns.join(' OR ')} THEN 'unknown' ELSE 'matched' END` : 'NULL' };
}
