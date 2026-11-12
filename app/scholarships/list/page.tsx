import { redirect } from 'next/navigation';
export default async function ScholarshipsList({ searchParams }: { searchParams: Promise<{ filter?: string }> }) {
  const { filter } = await searchParams;
  redirect(`/notices?${new URLSearchParams({ category: '장학·학비지원', status: filter === 'closing-soon' ? 'closing-soon' : 'open' })}`);
}
