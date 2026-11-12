import Link from 'next/link';
import Icon from './Icon';

export default function Header({ query = '', latest, source }: { source?: string; query?: string; latest?: string | null }) {
  const collected = latest ? new Date(latest.replace(' ', 'T') + 'Z').toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric' }) : null;
  return (
    <header className="topbar">
      <Link href="/" className="mobile-brand" aria-label="campus 홈"><span className="brand-symbol" aria-hidden="true"><i/><i/><i/><i/></span><span>campus<span className="brand-dot">·</span></span></Link>
      <form action="/notices" className="global-search" role="search">
        {source && <input type="hidden" name="source" value={source}/>}
        <Icon name="search" size={17} />
        <input name="q" aria-label="전체 공지 검색" placeholder="공지 검색" defaultValue={query} maxLength={300} key={query} />
        <button type="submit" aria-label="검색"><Icon name="arrow" size={16} /></button>
      </form>
      <div className="collection-date"><span className="status-dot" />{collected ? `${collected} 수집 기준` : '캠퍼스 공지 모음'}</div>
      <span className="school-avatar" aria-label="성균관대학교">S</span>
    </header>
  );
}
