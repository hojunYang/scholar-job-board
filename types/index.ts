// 채용 공고 인터페이스
export interface Job {
  id: number;
  target_audience: string;
  organizer: string;
  deadline: string;
  selection_date: string | null;
  benefit: string;
  category: string;
  full_text: string;
  created_at?: string;
  updated_at?: string;
}

// 장학금 인터페이스
export interface Scholarship {
  id: number;
  target_audience: string;
  organizer: string;
  deadline: string;
  selection_date: string | null;
  benefit: string;
  category: string;
  full_text: string;
  created_at?: string;
  updated_at?: string;
}

// 통계 카드 Props
export interface StatsCardProps {
  title: string;
  value: string;
  change: string;
  isPositive: boolean;
  icon: string;
  href?: string;
}

// 통계 데이터
export interface Stats {
  // 채용 공고
  openJobs: number;           // 마감 전 전체 채용 공고
  closingSoonJobs: number;    // 마감 직전(D-7) 채용 공고
  
  // 장학금
  openScholarships: number;        // 마감 전 전체 장학금
  closingSoonScholarships: number; // 마감 직전(D-7) 장학금
}

