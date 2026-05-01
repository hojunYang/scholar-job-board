import { getDb } from './db';
import type { Job, NoticeAttachment, Scholarship, Stats } from '@/types';

type NoticeTable = 'jobs' | 'scholarships';
type NoticeType = 'job' | 'scholarship';

interface NoticeAttachmentRow {
  id: number;
  originalFilename: string;
  mimeType: string | null;
  fileSize: number | null;
}

interface StoredNoticeAttachment {
  id: number;
  originalFilename: string;
  mimeType: string | null;
  storagePath: string;
}

function buildListQuery(tableName: NoticeTable, noticeType: NoticeType, whereClause: string, orderBy: string) {
  return `
    SELECT
      notice.*,
      COALESCE(attachment_counts.attachment_count, 0) AS attachmentCount
    FROM ${tableName} AS notice
    LEFT JOIN (
      SELECT notice_id, COUNT(*) AS attachment_count
      FROM notice_attachments
      WHERE notice_type = '${noticeType}'
      GROUP BY notice_id
    ) AS attachment_counts
      ON attachment_counts.notice_id = notice.id
    ${whereClause}
    ${orderBy}
  `;
}

function buildDetailQuery(tableName: NoticeTable, noticeType: NoticeType) {
  return `
    SELECT
      notice.*,
      source.source_url AS sourceUrl,
      COALESCE(attachment_counts.attachment_count, 0) AS attachmentCount
    FROM ${tableName} AS notice
    LEFT JOIN notice_sources AS source
      ON source.notice_type = '${noticeType}'
      AND source.notice_id = notice.id
    LEFT JOIN (
      SELECT notice_id, COUNT(*) AS attachment_count
      FROM notice_attachments
      WHERE notice_type = '${noticeType}'
      GROUP BY notice_id
    ) AS attachment_counts
      ON attachment_counts.notice_id = notice.id
    WHERE notice.id = ?
  `;
}

function getNoticeAttachments(noticeType: NoticeType, noticeId: number): NoticeAttachment[] {
  const db = getDb();
  const rows = db.prepare(`
    SELECT
      id,
      original_filename AS originalFilename,
      mime_type AS mimeType,
      file_size AS fileSize
    FROM notice_attachments
    WHERE notice_type = ?
      AND notice_id = ?
    ORDER BY display_order ASC, id ASC
  `).all(noticeType, noticeId) as NoticeAttachmentRow[];

  return rows.map((row) => ({
    ...row,
    downloadPath: `/api/attachments/${row.id}?download=1`,
  }));
}

function getNoticeList<T extends Job | Scholarship>(
  tableName: NoticeTable,
  noticeType: NoticeType,
  whereClause: string,
  orderBy: string
): T[] {
  const db = getDb();
  return db.prepare(buildListQuery(tableName, noticeType, whereClause, orderBy)).all() as T[];
}

function getNoticeById<T extends Job | Scholarship>(
  tableName: NoticeTable,
  noticeType: NoticeType,
  id: number
): T | null {
  const db = getDb();
  const notice = db.prepare(buildDetailQuery(tableName, noticeType)).get(id) as T | undefined;

  if (!notice) {
    return null;
  }

  notice.attachments = getNoticeAttachments(noticeType, id);
  return notice;
}

// 채용 공고 리스트 조회
export function getAllJobs(): Job[] {
  return getNoticeList<Job>('jobs', 'job', '', 'ORDER BY notice.created_at DESC LIMIT 10');
}

// 마감 전 채용 공고 조회
export function getOpenJobs(): Job[] {
  return getNoticeList<Job>(
    'jobs',
    'job',
    "WHERE datetime(notice.deadline) > datetime('now')",
    'ORDER BY notice.deadline ASC'
  );
}

// 마감 직전 채용 공고 조회 (D-7)
export function getClosingSoonJobs(): Job[] {
  return getNoticeList<Job>(
    'jobs',
    'job',
    "WHERE datetime(notice.deadline) > datetime('now') AND datetime(notice.deadline) <= datetime('now', '+7 days')",
    'ORDER BY notice.deadline ASC'
  );
}

// 채용 공고 상세 조회
export function getJobById(id: number): Job | null {
  return getNoticeById<Job>('jobs', 'job', id);
}

// 장학금 리스트 조회
export function getAllScholarships(): Scholarship[] {
  return getNoticeList<Scholarship>('scholarships', 'scholarship', '', 'ORDER BY notice.created_at DESC LIMIT 10');
}

// 마감 전 장학금 조회
export function getOpenScholarships(): Scholarship[] {
  return getNoticeList<Scholarship>(
    'scholarships',
    'scholarship',
    "WHERE datetime(notice.deadline) > datetime('now')",
    'ORDER BY notice.deadline ASC'
  );
}

// 마감 직전 장학금 조회 (D-7)
export function getClosingSoonScholarships(): Scholarship[] {
  return getNoticeList<Scholarship>(
    'scholarships',
    'scholarship',
    "WHERE datetime(notice.deadline) > datetime('now') AND datetime(notice.deadline) <= datetime('now', '+7 days')",
    'ORDER BY notice.deadline ASC'
  );
}

// 장학금 상세 조회
export function getScholarshipById(id: number): Scholarship | null {
  return getNoticeById<Scholarship>('scholarships', 'scholarship', id);
}

export function getNoticeAttachmentById(id: number): StoredNoticeAttachment | null {
  const db = getDb();
  const attachment = db.prepare(`
    SELECT
      id,
      original_filename AS originalFilename,
      mime_type AS mimeType,
      storage_path AS storagePath
    FROM notice_attachments
    WHERE id = ?
  `).get(id) as StoredNoticeAttachment | undefined;

  return attachment || null;
}

// 통계 데이터 조회
export function getStats(): Stats {
  const db = getDb();

  // 마감 전 전체 채용 공고 (deadline이 현재보다 미래)
  const openJobs = (db.prepare(
    "SELECT COUNT(*) as count FROM jobs WHERE datetime(deadline) > datetime('now')"
  ).get() as { count: number }).count;

  // 마감 직전 채용 공고 (D-7: 현재부터 7일 이내 마감)
  const closingSoonJobs = (db.prepare(
    "SELECT COUNT(*) as count FROM jobs WHERE datetime(deadline) > datetime('now') AND datetime(deadline) <= datetime('now', '+7 days')"
  ).get() as { count: number }).count;

  // 마감 전 전체 장학금
  const openScholarships = (db.prepare(
    "SELECT COUNT(*) as count FROM scholarships WHERE datetime(deadline) > datetime('now')"
  ).get() as { count: number }).count;

  // 마감 직전 장학금 (D-7)
  const closingSoonScholarships = (db.prepare(
    "SELECT COUNT(*) as count FROM scholarships WHERE datetime(deadline) > datetime('now') AND datetime(deadline) <= datetime('now', '+7 days')"
  ).get() as { count: number }).count;

  return {
    openJobs,
    closingSoonJobs,
    openScholarships,
    closingSoonScholarships,
  };
}
