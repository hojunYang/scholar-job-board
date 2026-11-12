import { labels, options, profileFields } from '@/lib/eligibility';

export default function NormalizedConditions({value, category, subcategory}: {value?: Record<string,unknown>; category?: string; subcategory?: string}) {
  if(!value) return null;
  const parse = (key:string) => {try{return JSON.parse(String(value[key] || 'null'));}catch{return null;}};
  const states = parse('field_states') || {};
  const columns: Record<string,string> = {studyLevel:'study_levels',studentYear:'student_years',enrollment:'enrollment_statuses',incomeTier:'income_tiers',degreeLevel:'degree_levels',graduationStatus:'graduation_statuses',applicantType:'applicant_types'};
  const rows = profileFields(category,subcategory).flatMap(field=>{
    if(states[field]!=='known' && states[field]!=='any') return [];
    let text: string;
    if(states[field]==='any') text='제한 없음';
    else if(columns[field]) text=(parse(columns[field]) || []).map((v:string|number)=>options[field]?.find(([key])=>key===String(v))?.[1] || String(v)).join(' · ');
    else if(field==='gpa') text=Object.entries(parse('gpa_minima') || {}).map(([scale,min])=>`${min} / ${scale} 이상`).join(' · ');
    else if(field==='workAvailability') text=value.requires_full_time?'전일제 가능':'시간제 가능';
    else {const prefix=field==='age'?'age':'experience';text=[value[`${prefix}_min`]!=null?`${value[`${prefix}_min`]} 이상`:'',value[`${prefix}_max`]!=null?`${value[`${prefix}_max`]} 이하`:''].filter(Boolean).join(' · ');}
    return text?[`${labels[field]}: ${text}`]:[];
  });
  return <><div className="condition-tags">{rows.map(row=><span key={row}>{row}</span>)}</div>{!rows.length&&<p className="helper-text">비교 가능한 조건 미확인</p>}</>;
}
