export const categoryStyles: Record<string, { label: string; icon: string; tone: string }> = {
  '장학·학비지원': { label: '장학·학비지원', icon: 'book', tone: 'green' },
  '근로·알바·학생조교': { label: '근로·알바·조교', icon: 'clock', tone: 'orange' },
  '취업·인턴·현장실습': { label: '취업·인턴·현장실습', icon: 'briefcase', tone: 'blue' },
  '연구경험·학술지원': { label: '연구경험·학술지원', icon: 'flask', tone: 'purple' },
  '실험·설문·인터뷰 참여': { label: '실험·설문 참여', icon: 'activity', tone: 'pink' },
  '교육·역량개발': { label: '교육·역량개발', icon: 'graduation', tone: 'blue' },
  '공모전·경진대회': { label: '공모전·경진대회', icon: 'award', tone: 'orange' },
  '창업·사업화': { label: '창업·사업화', icon: 'sparkles', tone: 'green' },
  '봉사·멘토링·서포터즈': { label: '봉사·멘토링·서포터즈', icon: 'heart', tone: 'pink' },
  '국제교류·해외연수': { label: '국제교류·해외연수', icon: 'globe', tone: 'purple' },
  '행사·강연·문화': { label: '행사·강연·문화', icon: 'calendar', tone: 'orange' },
  '생활·복지·시설': { label: '생활·복지·시설', icon: 'sun', tone: 'green' },
  '학사·행정': { label: '학사·행정', icon: 'file', tone: 'gray' },
};

export function noticeHref(notice: { id: number; notice_type?: string }) {
  return `/${notice.notice_type === 'scholarship' ? 'scholarships' : 'jobs'}/${notice.id}`;
}

export function deadlineInfo(value: string, now = Date.now(), title = '', classificationStatus = '') {
  if (['needs_review', 'pending'].includes(classificationStatus)) return { label: '마감', state: 'closed', date: '' };
  if (/\[마감\]|채용완료|모집완료/.test(title)) return { label: '마감', state: 'closed', date: value };
  if (/상시|수시|채용\s*시|선발\s*시|충원\s*시/.test(value)) return { label: '상시 모집', state: 'rolling', date: value };
  if (!/^\d{4}-\d{2}-\d{2}(?:$|[ T])/.test(value)) return { label: '미정', state: 'unknown', date: value };
  let iso = value.replace(' ', 'T');
  if (iso.length === 10) iso += 'T23:59:59+09:00';
  else if (!/(Z|[+-]\d{2}:\d{2})$/.test(iso)) iso += '+09:00';
  const timestamp = Date.parse(iso);
  if (!Number.isFinite(timestamp)) return { label: '미정', state: 'unknown', date: value };
  const dateInSeoul = (time: number) => new Date(time + 9 * 3600000).toISOString().slice(0, 10);
  const days = Math.round((Date.parse(dateInSeoul(timestamp)) - Date.parse(dateInSeoul(now))) / 86400000);
  const date = new Date(timestamp).toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' });
  if (timestamp < now) return { label: '마감', state: 'closed', date };
  return { label: days === 0 ? '오늘 마감' : `D-${days}`, state: days <= 7 ? 'soon' : 'open', date };
}

export function shortText(value: string, fallback = '원문 참조') {
  return !value || ['공지사항 참조', '미정', '미제공', '해당 없음'].includes(value.trim()) ? fallback : value.replace(/\s+/g, ' ').replace(/^[-•]\s*/, '');
}
