import Link from 'next/link';
import type { Job } from '@/types';

interface JobListProps {
  jobs: Job[];
}

export default function JobList({ jobs }: JobListProps) {
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
    <div className="list-container">
      {jobs.map((job) => (
        <Link key={job.id} href={`/jobs/${job.id}`} className="card">
          <div className="card-header">
            <div className="card-title-section">
              <div className="flex flex-wrap items-center gap-2">
                <span className="badge badge-category">{job.category}</span>
                {job.attachmentCount ? (
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                    첨부 {job.attachmentCount}개
                  </span>
                ) : null}
              </div>
              <h3 className="card-organizer">{job.title}</h3>
            </div>
          </div>
          
          <div className="card-content">
            <div className="info-row">
              <span className="info-label">대상</span>
              <p className="info-text">{job.target_audience}</p>
            </div>
            <div className="info-row">
              <span className="info-label">혜택</span>
              <p className="info-text">{job.benefit}</p>
            </div>
          </div>

          <div className="card-footer">
            <div className="footer-item">
              <span className="footer-icon">📅</span>
              <span className="footer-label">마감</span>
              <span className="footer-value">{formatDeadline(job.deadline)}</span>
            </div>
            {job.selection_date && (
              <div className="footer-item">
                <span className="footer-icon">📢</span>
                <span className="footer-label">발표</span>
                <span className="footer-value">{job.selection_date}</span>
              </div>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
