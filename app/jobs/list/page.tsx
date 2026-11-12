import { redirect } from 'next/navigation';
export default async function JobsList({ searchParams }: { searchParams: Promise<{ filter?: string }> }) {
  const { filter } = await searchParams;
  redirect(`/notices?${new URLSearchParams({ category: '취업·인턴·현장실습', status: filter === 'closing-soon' ? 'closing-soon' : 'open' })}`);
}
