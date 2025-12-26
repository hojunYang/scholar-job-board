import StatsCard from "@/components/StatsCard";
import JobList from "@/components/JobList";
import ScholarshipList from "@/components/ScholarshipList";
import Header from "@/components/Header";
import { getAllJobs, getAllScholarships, getStats } from "@/lib/queries";

export default function Dashboard() {
  // DB에서 데이터 가져오기
  const jobs = getAllJobs();
  const scholarships = getAllScholarships();
  const stats = getStats();

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 통계 카드 섹션 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatsCard
            title="마감 전 장학금"
            value={stats.openScholarships.toString()}
            change=""
            isPositive={true}
            icon="💰"
            href="/scholarships/list?filter=open"
          />
          <StatsCard
            title="마감 직전 장학금 (D-7)"
            value={stats.closingSoonScholarships.toString()}
            change=""
            isPositive={false}
            icon="⚡"
            href="/scholarships/list?filter=closing-soon"
          />
          <StatsCard
            title="마감 전 채용 공고"
            value={stats.openJobs.toString()}
            change=""
            isPositive={true}
            icon="📊"
            href="/jobs/list?filter=open"
          />
          <StatsCard
            title="마감 직전 채용 공고 (D-7)"
            value={stats.closingSoonJobs.toString()}
            change=""
            isPositive={false}
            icon="⏰"
            href="/jobs/list?filter=closing-soon"
          />
        </div>

        {/* 채용 공고 및 장학금 리스트 */}
        <div className="flex flex-col gap-6 md:flex-row">
          <div className="flex-1 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">최근 장학금 공고</h2>
            <ScholarshipList scholarships={scholarships} />
          </div>
          <div className="flex-1 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">최근 채용 공고</h2>
            <JobList jobs={jobs} />
          </div>
        </div>
      </main>
    </div>
  );
}

