import { notFound } from 'next/navigation';
import { getScholarshipById } from '@/lib/queries';
import NoticeDetail from '@/components/NoticeDetail';
export const dynamic = 'force-dynamic';
export default async function ScholarshipDetailPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{source?: string}> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const notice = getScholarshipById(Number(id));
  if (!notice) notFound();
  const { source } = await searchParams;
  return <NoticeDetail notice={notice} sourceId={source}/>;
}
