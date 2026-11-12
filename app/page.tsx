import { parseProfile } from '@/lib/eligibility';
import Link from 'next/link';
import { redirect } from 'next/navigation';
import AppShell from '@/components/AppShell';
import Icon from '@/components/Icon';
import NoticeFilters from '@/components/NoticeFilters';
import NoticeCard from '@/components/NoticeCard';
import { getBoardStats, getNotices, getNoticeCount, getNoticeBoards, type NoticeFilters as Filters } from '@/lib/queries';
import { categoryStyles } from '@/lib/notice-ui';
import taxonomy from '@/data/notice-taxonomy.json';

export const dynamic = 'force-dynamic';
type Params = Record<string, string | undefined> & { category?: string; subcategory?: string; page?: string; q?: string; audience?: string; status?: string; review?: string; sort?: string };

export default async function OpportunityBoard({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  if (params.review === '1') {
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) if (value && key !== 'review' && key !== 'page') next.set(key, value);
    next.set('status', 'closed');
    redirect(`/notices?${next}`);
  }
  const categories: Record<string, string[]> = taxonomy;
  const category = params.category && Object.hasOwn(categories, params.category) ? params.category : undefined;
  const subcategory = category && params.subcategory && categories[category].includes(params.subcategory) ? params.subcategory : undefined;
  const status = ['open', 'closing-soon', 'closed'].includes(params.status || '') ? params.status as Filters['status'] : undefined;
  const query = params.q?.trim().slice(0, 300) || undefined;
  const audience = params.audience?.trim().slice(0, 100) || undefined;
  const boards = getNoticeBoards();
  const source = boards.some(board=>board.id===params.source) ? params.source : undefined;
  const sort = params.sort === 'deadline' ? 'deadline' : 'latest';
  const profile = parseProfile(params, category, subcategory);
  const filters: Filters = { mainCategory: category, subcategory, status, query, audience, sort, profile, source };
  const count = getNoticeCount(filters);
  const pages = Math.max(1, Math.ceil(count / 12));
  const page = Math.min(pages, Math.max(1, Number.parseInt(params.page || '1', 10) || 1));
  const notices = getNotices({ ...filters, limit: 12, offset: (page - 1) * 12 });
  const stats = getBoardStats({source});
  const showingClosed = status === 'closed';
  const summaryCount = showingClosed ? getNoticeCount({ source, status: 'closed' }) : stats.total;
  function href(updates: Record<string, string | undefined>) {
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...profile, source, category, subcategory, q: query, audience, status, sort, ...updates })) if (value) next.set(key, value);
    return `/notices?${next}`;
  }
  const chips = [{ label: '전체', value: undefined }, { label: '마감 전', value: 'open' }, { label: 'D-7', value: 'closing-soon' }, { label: '마감', value: 'closed' }];
  return (
    <AppShell source={source} profile={profile} category={category} subcategory={subcategory} status={status} query={query} audience={audience} sort={sort}>
      <section className="overview-strip" aria-label="공지 현황">
        <Link href={`/notices?${new URLSearchParams({...source?{source}:{},...showingClosed?{status:'closed'}:{}})}`}><span className="metric-icon"><Icon name="grid"/></span><div><span>{showingClosed ? '마감 공지' : '전체 공지'}</span><strong>{summaryCount.toLocaleString()}<small>개</small></strong></div><span className="metric-context"></span></Link>
        <Link href={`/notices?${new URLSearchParams({...source?{source}:{},status:'open'})}`}><span className="metric-icon metric-green"><Icon name="sparkles"/></span><div><span>마감 전</span><strong>{stats.open.toLocaleString()}<small>개</small></strong></div><span className="metric-context">상시 공지 포함</span></Link>
        <Link href={`/notices?${new URLSearchParams({...source?{source}:{},status:'closing-soon'})}`}><span className="metric-icon metric-orange"><Icon name="clock"/></span><div><span>7일 이내 마감</span><strong>{stats.soon.toLocaleString()}<small>개</small></strong></div><span className="metric-context"></span></Link>
      </section>
      <section className="discovery-section" aria-label="공지 탐색">
        <div className="section-title"><div><h1>{category ? categoryStyles[category].label : query ? `'${query}' 검색 결과` : showingClosed ? '마감 공지' : '전체 공지'}<span>{count.toLocaleString()}</span></h1></div>{(category || query || audience || source) && <Link href="/notices" className="reset-link">필터 초기화 <Icon name="close" size={14}/></Link>}</div>
        <div className="browse-tabs" aria-label="접수 일정 필터">{chips.map(chip => <Link key={chip.label} href={href({ status: chip.value, page: undefined })} className={status === chip.value ? 'browse-tab active' : 'browse-tab'} aria-current={status === chip.value ? 'page' : undefined}>{chip.value === 'closing-soon' && <span className="small-dot"/>}{chip.label}</Link>)}</div>
        <NoticeFilters source={source} boards={boards} key={JSON.stringify({category,subcategory,profile,source})} profile={profile} category={category} subcategory={subcategory} query={query} audience={audience} sort={sort} status={status}/>
        {audience && <p className="filter-explanation">대상·조건에 ‘{audience}’ 포함</p>}
        <div className="results-caption"><span>{count ? <><strong>{(page - 1) * 12 + 1}–{Math.min(page * 12, count)}</strong> / {count.toLocaleString()}개 공지</> : '검색 결과 없음'}</span><span>저장된 일정 기준</span></div>
        {notices.length ? <div className="opportunity-grid">{notices.map(notice => <NoticeCard source={source} key={notice.id} notice={notice}/>)}</div> : <div className="empty-state"><span><Icon name="search" size={30}/></span><h3>검색 결과가 없습니다.</h3><p>검색어나 조건을 변경하세요.</p><Link className="solid-button" href="/notices">전체 공지 <Icon name="arrow" size={17}/></Link></div>}
        {pages > 1 && <nav className="pagination" aria-label="공지 페이지">{page > 1 ? <Link href={href({ page: String(page - 1) })} className="page-direction">← 이전</Link> : <span className="page-direction disabled">← 이전</span>}<div>{Array.from({ length: Math.min(5, pages) }, (_, index) => Math.max(1, Math.min(page - 2, pages - 4)) + index).map(index => <Link key={index} href={href({ page: String(index) })} aria-current={page === index ? 'page' : undefined} className={page === index ? 'page-number active' : 'page-number'}>{index}</Link>)}{pages > 5 && <span className="page-total">/ {pages}</span>}</div>{page < pages ? <Link href={href({ page: String(page + 1) })} className="page-direction">다음 →</Link> : <span className="page-direction disabled">다음 →</span>}</nav>}
      </section>
    </AppShell>
  );
}
