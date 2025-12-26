import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getJobById } from '@/lib/queries';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function JobDetailPage({ params }: PageProps) {
  const { id } = await params;
  const job = getJobById(Number(id));

  if (!job) {
    notFound();
  }

  const formatDeadline = (deadline: string) => {
    try {
      const date = new Date(deadline);
      
      // Invalid Date 체크
      if (isNaN(date.getTime())) {
        return deadline; // 원본 문자열 그대로 반환
      }
      
      return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return deadline; // 원본 문자열 그대로 반환
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="header">
        <div className="header-container">
          <div className="header-content">
            <Link href="/" className="header-logo">
              <div className="header-logo-icon">🎓</div>
              <div className="header-logo-text">
                <h1>성균관대 장학금, 채용/모집 대시보드</h1>
              </div>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Link href="/" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-6">
          ← 목록으로 돌아가기
        </Link>

        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="mb-6">
            <span className="badge badge-category">{job.category}</span>
            <h1 className="text-3xl font-bold text-gray-900 mt-4">{job.organizer}</h1>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 p-6 bg-gray-50 rounded-lg">
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">대상</h3>
              <p className="text-gray-900">{job.target_audience}</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">혜택</h3>
              <p className="text-gray-900">{job.benefit}</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">마감일</h3>
              <p className="text-gray-900">{formatDeadline(job.deadline)}</p>
            </div>
            {job.selection_date && (
              <div>
                <h3 className="text-sm font-semibold text-gray-500 mb-2">발표일</h3>
                <p className="text-gray-900">{job.selection_date}</p>
              </div>
            )}
          </div>

          <div className="prose max-w-none">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">상세 내용</h2>
            <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
              {job.full_text}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

