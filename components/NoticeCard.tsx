import Link from 'next/link';
import type { Job } from '@/types';
import Icon from './Icon';
import { categoryStyles, deadlineInfo, noticeHref, shortText } from '@/lib/notice-ui';

export default function NoticeCard({ notice, source }: { notice: Job; source?: string }) {
  const meta = categoryStyles[notice.main_category || ''] || { label: '미분류', icon: 'file', tone: 'gray' };
  const deadline = deadlineInfo(notice.deadline, Date.now(), notice.title, notice.classification_status);
  return (
    <Link href={noticeHref(notice) + (source ? `?${new URLSearchParams({source})}` : '')} className="opportunity-card">
      <div className="card-topline"><span className={`category-badge tone-${meta.tone}`}><Icon name={meta.icon} size={14}/>{meta.label}</span><span className={`deadline-badge deadline-${deadline.state}`}>{deadline.state === 'soon' && <span className="small-dot"/>}{deadline.label}</span></div>
      {notice.eligibilityMatch && <p className={`match-label ${notice.eligibilityMatch}`}>{notice.eligibilityMatch==='matched'?'선택 조건 일치':'선택 조건 중 미확인 항목 있음'}</p>}
      {notice.sourceLabels && <p className="notice-source-label">{notice.sourceLabels}</p>}
      <div className="card-kicker">{notice.subcategory || '미분류'}<span>·</span><span className="organizer-clip">{notice.organizer}</span></div>
      <h3>{notice.title.replace(/^[✨✅]\s*/, '')}</h3>
      <div className="card-facts"><div><Icon name="graduation" size={16}/><p>{shortText(notice.target_audience, '원문 참조')}</p></div><div><Icon name="sparkles" size={16}/><p>{shortText(notice.benefit, '원문 참조')}</p></div></div>
      <div className="opportunity-footer"><span><Icon name="calendar" size={14}/>{deadline.state === 'unknown' ? '마감일 미정' : deadline.state === 'rolling' ? '선발·접수 조건 참조' : deadline.date ? `${deadline.date} 마감` : '마감'}</span><span className="card-trailing">{notice.attachmentCount ? <span className="attachment-count"><Icon name="paperclip" size={13}/>{notice.attachmentCount}</span> : null}<span className="card-open"><Icon name="diagonal" size={17}/></span></span></div>
    </Link>
  );
}
