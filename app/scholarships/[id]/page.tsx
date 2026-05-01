import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getScholarshipById } from '@/lib/queries';
import AttachmentList from '@/components/AttachmentList';

// 동적 렌더링 강제
export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ScholarshipDetailPage({ params }: PageProps) {
  const { id } = await params;
  const scholarship = getScholarshipById(Number(id));

  if (!scholarship) {
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
            <div className="flex flex-wrap items-center gap-2">
              <span className="badge badge-category">{scholarship.category}</span>
              {scholarship.attachmentCount ? (
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                  첨부 {scholarship.attachmentCount}개
                </span>
              ) : null}
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mt-4">{scholarship.title}</h1>
            <p className="mt-2 text-sm text-gray-500">주관: {scholarship.organizer}</p>
            {scholarship.sourceUrl && (
              <a
                href={scholarship.sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
              >
                원문 공지 보기
              </a>
            )}
          </div>

          <div className="grid grid-cols-1 gap-6 mb-8 p-6 bg-gray-50 rounded-lg md:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">주관</h3>
              <p className="text-gray-900">{scholarship.organizer}</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">대상</h3>
              <p className="text-gray-900">{scholarship.target_audience}</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">혜택</h3>
              <p className="text-gray-900">{scholarship.benefit}</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500 mb-2">마감일</h3>
              <p className="text-gray-900">{formatDeadline(scholarship.deadline)}</p>
            </div>
            {scholarship.selection_date && (
              <div>
                <h3 className="text-sm font-semibold text-gray-500 mb-2">발표일</h3>
                <p className="text-gray-900">{scholarship.selection_date}</p>
              </div>
            )}
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">첨부파일</h2>
            <AttachmentList attachments={scholarship.attachments} />
          </div>

          <div className="prose max-w-none">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">상세 내용</h2>
            <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
              {scholarship.full_text}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
