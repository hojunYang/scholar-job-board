import Link from 'next/link';
export default function NotFound() {
  return <main className="standalone-state"><h1>공지를 찾을 수 없습니다.</h1><Link href="/notices" className="solid-button">전체 공지</Link></main>;
}
