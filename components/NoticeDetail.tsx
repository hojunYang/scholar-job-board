import NormalizedConditions from './NormalizedConditions';
import Link from 'next/link';
import type { Job, EligibilityConditions as Conditions } from '@/types';
import AppShell from './AppShell';
import Icon from './Icon';
import AttachmentList from './AttachmentList';
import { categoryStyles, deadlineInfo, shortText } from '@/lib/notice-ui';

export default function NoticeDetail({ notice, sourceId }: { notice: Job; sourceId?: string }) {
  const category = notice.main_category || undefined;
  const meta = categoryStyles[category || ''] || { label: '미분류', icon: 'file', tone: 'gray' };
  const deadline = deadlineInfo(notice.deadline, Date.now(), notice.title, notice.classification_status);
  let conditions: Partial<Conditions> = {};
  try { conditions = JSON.parse(notice.eligibility_conditions || '{}') || {}; } catch { /* Old notices may lack extracted conditions. */ }
  const evidence = Array.isArray(conditions.evidence) ? conditions.evidence.filter(item => typeof item === 'string') : [];
  const sourceUrl = notice.sourceUrl && /^https?:\/\//i.test(notice.sourceUrl) ? notice.sourceUrl : null;
  const source = notice.origins?.some(origin=>origin.boardId===sourceId) ? sourceId : undefined;
  const back = `/notices?${new URLSearchParams({...(category ? {category} : {}), ...(source ? {source} : {})})}`;
  return (
    <AppShell source={source} category={category} subcategory={notice.subcategory || undefined}>
      <Link href={back} className="back-link"><Icon name="arrow" size={16} style={{ transform: 'rotate(180deg)' }}/>목록으로</Link>
      <div className="detail-heading"><div className="detail-labels"><span className={`category-badge tone-${meta.tone}`}><Icon name={meta.icon} size={15}/>{meta.label}</span><span>{notice.subcategory}</span><span className={`deadline-badge deadline-${deadline.state}`}>{deadline.label}</span></div><h1>{notice.title}</h1>{!!notice.origins?.length && <div className="detail-origins">{notice.origins.filter(origin=>/^https?:\/\//i.test(origin.url)).map(origin=><a key={origin.boardId} href={origin.url} target="_blank" rel="noreferrer">{origin.name}{origin.publishedAt?` · ${origin.publishedAt}`:''}</a>)}</div>}<p><Icon name="building" size={16}/>{notice.organizer}</p></div>
      <div className="detail-grid">
        <div className="detail-main">
          <section className="detail-panel eligibility-panel"><div className="panel-title"><span className="panel-icon"><Icon name="graduation" size={21}/></span><div><h2>지원 대상과 조건</h2></div></div><p className="audience-summary">{shortText(notice.target_audience, '원문 참조')}</p><NormalizedConditions value={notice.normalizedEligibility} category={category} subcategory={notice.subcategory || undefined}/>{evidence.length ? <details className="conditions-disclosure"><summary>상세 조건 {evidence.length}개<Icon name="chevron" size={15}/></summary><ul>{evidence.map((line, index) => <li key={index}>{line}</li>)}</ul><p className="helper-text">원문 조건. 제외·우대 사항 및 AND/OR 관계 확인 필요.</p></details> : <p className="helper-text">상세 조건: 원문 참조</p>}</section>
          <section className="detail-panel"><div className="panel-title"><span className="panel-icon warm"><Icon name="sparkles" size={21}/></span><div><h2>혜택과 지원 내용</h2></div></div><p className="benefit-copy">{shortText(notice.benefit, '원문 참조')}</p></section>
          <section className="detail-panel"><div className="panel-title"><span className="panel-icon cool"><Icon name="file" size={21}/></span><div><h2>본문</h2></div></div><div className="original-text">{notice.full_text || '본문 없음. 원문 참조.'}</div></section>
          <section className="detail-panel"><div className="simple-panel-title"><h2>첨부파일 <span>{notice.attachments?.length || 0}</span></h2><span>원본 파일</span></div><AttachmentList attachments={notice.attachments}/></section>
        </div>
        <aside className="detail-aside"><div className="deadline-panel"><h2>일정</h2><span className={`deadline-badge deadline-${deadline.state}`}>{deadline.label}</span><dl><div><dt>접수 마감</dt><dd>{notice.deadline}</dd></div>{notice.selection_date && <div><dt>선발·발표</dt><dd>{notice.selection_date}</dd></div>}<div><dt>주관 기관</dt><dd>{notice.organizer}</dd></div></dl>{sourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer" className="solid-button">원문 보기<Icon name="external" size={16}/></a> : <div className="source-unavailable">원문 링크 없음</div>}<p>최종 일정·신청 방법은 원문 참조.</p></div></aside>
      </div>
    </AppShell>
  );
}
