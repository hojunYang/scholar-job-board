import { notFound } from 'next/navigation';
import { getJobById } from '@/lib/queries';
import NoticeDetail from '@/components/NoticeDetail';
export const dynamic = 'force-dynamic';
export default async function JobDetailPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{source?: string}> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const notice = getJobById(Number(id));
  if (!notice) notFound();
  const { source } = await searchParams;
  return <NoticeDetail notice={notice} sourceId={source}/>;
}
