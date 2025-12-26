import Link from 'next/link';
import JobList from '@/components/JobList';
import { getOpenJobs, getClosingSoonJobs } from '@/lib/queries';

// 동적 렌더링 강제
export const dynamic = 'force-dynamic';

interface PageProps {
  searchParams: Promise<{ filter?: string }>;
}

export default async function JobsListPage({ searchParams }: PageProps) {
  const { filter } = await searchParams;
  
  let jobs;
  let title;
  let description;

  if (filter === 'closing-soon') {
    jobs = getClosingSoonJobs();
    title = '마감 직전 채용 공고 (D-7)';
    description = '7일 이내 마감되는 채용 공고입니다.';
  } else {
    jobs = getOpenJobs();
    title = '마감 전 채용 공고';
    description = '현재 지원 가능한 모든 채용 공고입니다.';
  }

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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Link href="/" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-6">
          ← 대시보드로 돌아가기
        </Link>

        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">{title}</h1>
          <p className="text-gray-600">{description}</p>
          <p className="text-sm text-gray-500 mt-2">총 {jobs.length}개의 공고</p>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          {jobs.length > 0 ? (
            <JobList jobs={jobs} />
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500 text-lg">해당하는 채용 공고가 없습니다.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

