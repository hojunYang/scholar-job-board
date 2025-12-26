import Link from 'next/link';
import type { Scholarship } from '@/types';

interface ScholarshipListProps {
  scholarships: Scholarship[];
}

export default function ScholarshipList({ scholarships }: ScholarshipListProps) {
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
      {scholarships.map((scholarship) => (
        <Link key={scholarship.id} href={`/scholarships/${scholarship.id}`} className="card">
          <div className="card-header">
            <div className="card-title-section">
              <span className="badge badge-category">{scholarship.category}</span>
              <h3 className="card-organizer">{scholarship.target_audience}</h3>
            </div>
          </div>
          
          <div className="card-content">
            <div className="info-row">
              <span className="info-label">주관기관</span>
              <p className="info-text">{scholarship.organizer}</p>
            </div>
            
            <div className="info-row">
              <span className="info-label">혜택</span>
              <p className="info-text">{scholarship.benefit}</p>
            </div>
          </div>

          <div className="card-footer">
            <div className="footer-item">
              <span className="footer-icon">📅</span>
              <span className="footer-label">마감</span>
              <span className="footer-value">{formatDeadline(scholarship.deadline)}</span>
            </div>
            {scholarship.selection_date && (
              <div className="footer-item">
                <span className="footer-icon">📢</span>
                <span className="footer-label">발표</span>
                <span className="footer-value">{scholarship.selection_date}</span>
              </div>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
