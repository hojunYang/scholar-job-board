import type { CSSProperties } from 'react';

const paths: Record<string, React.ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
  book: <><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Z"/><path d="M12 5v15"/></>,
  briefcase: <><rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4h8v3M3 12c5 3 13 3 18 0M12 12v4"/></>,
  flask: <><path d="M9 3h6M10 3v7l-6 9a1.5 1.5 0 0 0 1 2h14a1.5 1.5 0 0 0 1-2l-6-9V3M7 15h10"/><path d="m10 17 1 1"/></>,
  activity: <><path d="M3 12h4l3-8 4 16 3-8h4"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  graduation: <><path d="m2 8 10-5 10 5-10 5L2 8Zm4 3v6c4 3 8 3 12 0v-6M22 8v8"/></>,
  award: <><circle cx="12" cy="9" r="6"/><path d="m8 14-1 8 5-3 5 3-1-8"/></>,
  sparkles: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4M18 4h4"/></>,
  heart: <path d="M20.5 5.5a5 5 0 0 0-7 0L12 7l-1.5-1.5a5 5 0 0 0-7 7L12 21l8.5-8.5a5 5 0 0 0 0-7Z"/>,
  globe: <><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h3M14 14h3M7 17h3"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
  file: <><path d="M14 3H5v18h14V8l-5-5Z"/><path d="M14 3v5h5M8 12h8M8 16h5"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
  diagonal: <path d="M5 19 19 5M5 5h14v14"/>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  filter: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="currentColor"/><circle cx="15" cy="17" r="2" fill="currentColor"/></>,
  external: <><path d="M14 3h7v7m0-7L11 13M10 3H3v18h18v-7"/></>,
  paperclip: <path d="m8 14 7-7a3 3 0 0 1 4 4l-9 9a5 5 0 0 1-7-7l10-10"/>,
  building: <><path d="M4 21V5l8-2 8 2v16M2 21h20M9 21v-5h6v5M8 7h1m6 0h1M8 11h1m6 0h1"/></>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
};
export default function Icon({ name, size = 20, style }: { name: string; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>{paths[name] || paths.file}</svg>;
}
