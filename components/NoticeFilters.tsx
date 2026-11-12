'use client';

import { useRouter } from 'next/navigation';
import { useTransition, useState } from 'react';
import { labels, options, profileFields, type Profile } from '@/lib/eligibility';

export default function NoticeFilters({ category = '', subcategory = '', query = '', audience = '', sort = 'latest', status = '', profile = {}, source = '', boards = [] }: {
  source?: string; boards?: {id:string;name:string}[]; category?: string; subcategory?: string; query?: string; audience?: string; sort?: string; status?: string; profile?: Profile;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [study, setStudy] = useState(profile.studyLevel || '');
  const fields = profileFields(category,subcategory);
  function navigate(form: HTMLFormElement) {
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form)) if (typeof value === 'string' && value.trim()) params.set(key, value.trim());
    if(params.get('studyLevel') && params.get('studyLevel')!=='undergraduate') params.delete('studentYear');
    startTransition(() => router.push(`/notices?${params}`, { scroll: false }));
  }
  return (
    <form key={JSON.stringify({category,subcategory,profile,sort,status,query,source})} className={`profile-filters ${pending ? 'is-pending' : ''}`} aria-busy={pending} onSubmit={event => { event.preventDefault(); navigate(event.currentTarget); }}>
      {Object.entries({q:query,status,category,subcategory,audience}).map(([name,value])=>value&&<input key={name} type="hidden" name={name} value={value}/>)}
      <label className="source-filter">출처<select name="source" defaultValue={source} onChange={event=>navigate(event.currentTarget.form!)}><option value="">전체 출처</option>{boards.map(board=><option key={board.id} value={board.id}>{board.name}</option>)}</select></label>
      {fields.length ? <>
        <div className="profile-filter-title">내 조건</div>
        <div className="profile-fields">{fields.map(field => field==='studentYear' && study && study!=='undergraduate' ? null : <label key={field}>{labels[field]}
          {options[field] ? <select name={field} defaultValue={profile[field] || ''} onChange={field==='studyLevel'?event=>setStudy(event.target.value):undefined}><option value="">선택 안 함</option>{options[field].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select> : <input name={field} type="number" min="0" max={field==='gpa'?4.5:120} step={field==='age'?'1':'0.1'} defaultValue={profile[field]} placeholder="입력 안 함"/>}
          {field==='gpa' && <select name="gpaScale" aria-label="평점 만점" defaultValue={profile.gpaScale || '4.5'}><option value="4.5">4.5 만점</option><option value="4.3">4.3 만점</option></select>}
        </label>)}</div>
        <div className="profile-actions"><label><input type="checkbox" name="includeUnknown" value="1" defaultChecked={profile.includeUnknown==='1'}/>미확인 조건 포함</label><button type="submit" className="solid-button" disabled={pending}>조건 적용</button></div>
        <p className="helper-text">선택한 조건만 비교합니다. 전공·학기·자격증 등 나머지 요건은 원문을 확인하세요.</p>
      </> : <p className="helper-text">분류를 선택하면 해당 공지의 대상 조건을 설정할 수 있습니다.</p>}
      <label className="profile-sort">정렬 <select name="sort" defaultValue={sort}><option value="latest">최근 수집순</option><option value="deadline">마감일순</option></select></label>
      {!fields.length && <button type="submit">적용</button>}
      <span className="sr-only" role="status">{pending ? '공지 불러오는 중' : ''}</span>
    </form>
  );
}
