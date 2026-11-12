export interface NoticeAttachment {
  id: number;
  originalFilename: string;
  mimeType: string | null;
  fileSize: number | null;
  downloadPath: string;
}

export interface EligibilityConditions {
  applicant_type: string[];
  education: string[];
  enrollment: string[];
  grade: string[];
  major: string[];
  gpa: string[];
  income: string[];
  residence: string[];
  restrictions: string[];
  preferences: string[];
  evidence: string[];
  status: 'extracted' | 'not_stated';
}

interface NoticeMetadata {
  sourceLabels?: string | null;
  origins?: {boardId: string; name: string; url: string; publishedAt: string | null}[];
  eligibilityMatch?: 'matched' | 'unknown' | null;
  normalizedEligibility?: Record<string, unknown>;
  main_category: string | null;
  subcategory: string | null;
  eligibility_conditions: string | null;
  classification_status: 'pending' | 'auto' | 'reviewed' | 'needs_review';
  classification_reason: string | null;
  notice_type?: 'job' | 'scholarship';
  sourceUrl?: string | null;
  attachmentCount?: number;
  attachments?: NoticeAttachment[];
}

// 채용 공고 인터페이스
export interface Job extends NoticeMetadata {
  id: number;
  target_audience: string;
  organizer: string;
  deadline: string;
  selection_date: string | null;
  benefit: string;
  category: string;
  title: string;
  full_text: string;
  created_at?: string;
  updated_at?: string;
}

// 장학금 인터페이스
export interface Scholarship extends NoticeMetadata {
  id: number;
  target_audience: string;
  organizer: string;
  deadline: string;
  selection_date: string | null;
  benefit: string;
  category: string;
  title: string;
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
