import { parseProfile, type Profile } from '@/lib/eligibility';
import Link from 'next/link';
import type { ReactNode } from 'react';
import Header from './Header';
import Icon from './Icon';
import { categoryStyles } from '@/lib/notice-ui';
import { getBoardStats, getCategoryCounts } from '@/lib/queries';
import taxonomy from '@/data/notice-taxonomy.json';

export default function AppShell({ children, category, subcategory, status, query, audience, sort, source, profile = {} }: {
  source?: string; profile?: Profile; children: ReactNode; category?: string; subcategory?: string; status?: string;
  query?: string; audience?: string; sort?: string;
}) {
  const counts = getCategoryCounts({ source, status: ['open','closing-soon','closed'].includes(status || '') ? status as 'open'|'closing-soon'|'closed' : undefined, query, audience });
  const stats = getBoardStats({source});
  const categories: Record<string, string[]> = taxonomy;
  const total = counts.reduce((sum, row) => sum + row.count, 0);
  function categoryHref(main?: string, sub?: string) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...parseProfile(profile, main, sub), category: main, subcategory: sub, status, source,
      q: query, audience, sort })) if (value) params.set(key, value);
    return `/notices?${params}`;
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">본문으로 바로가기</a>
      <div className="app-body">
        <Header source={source} query={query} latest={stats.latest}/>
        <div className="upper-menu">
          <nav className="upper-scope-nav" aria-label="탐색 메뉴">
            <Link href={source?`/notices?${new URLSearchParams({source})}`:"/notices"} className={!status ? 'upper-scope selected' : 'upper-scope'}><Icon name="grid" size={15}/>전체 공지 <small>{stats.total.toLocaleString()}</small></Link>
            <Link href={`/notices?${new URLSearchParams({...source?{source}:{},status:"closing-soon"})}`} className={status === 'closing-soon' ? 'upper-scope selected' : 'upper-scope'}><Icon name="clock" size={15}/>마감 임박</Link>
          </nav>
          <nav className="upper-category-nav" aria-label={status === 'closed' ? '공지 대분류 · 마감' : '공지 대분류'}>
            <Link href={categoryHref()} className={!category ? 'upper-category selected' : 'upper-category'} aria-current={!category ? 'page' : undefined}>전체 <small>{total.toLocaleString()}</small></Link>
            {Object.entries(categoryStyles).map(([main, meta]) => <Link key={main} href={categoryHref(main)} className={category === main ? 'upper-category selected' : 'upper-category'} aria-current={category === main ? 'page' : undefined}>
              {meta.label}<small>{counts.find(row => row.main_category === main)?.count || 0}</small>
            </Link>)}
          </nav>
          {category && categories[category] && <nav className="upper-subcategory-nav" aria-label="공지 세부분류">
            <Link href={categoryHref(category)} className={!subcategory ? 'upper-subcategory selected' : 'upper-subcategory'} aria-current={!subcategory ? 'page' : undefined}>전체 세부분류</Link>
            {categories[category].map(sub => <Link key={sub} href={categoryHref(category, sub)} className={subcategory === sub ? 'upper-subcategory selected' : 'upper-subcategory'} aria-current={subcategory === sub ? 'page' : undefined}>{sub}</Link>)}
          </nav>}
        </div>
        <main id="main-content" className="workspace">{children}</main>
        <footer className="page-footer">성균관대학교 공지</footer>
      </div>
    </div>
  );
}
