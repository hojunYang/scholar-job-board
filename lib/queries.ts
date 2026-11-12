import { profileSql, type Profile } from './eligibility';
import { getDb } from './db';
import type { Job, NoticeAttachment, Scholarship, Stats } from '@/types';

type NoticeTable = 'jobs' | 'scholarships';
type NoticeType = 'job' | 'scholarship';

interface NoticeAttachmentRow {
  downloadPath: string;
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
      file_size AS fileSize,
      download_url AS downloadPath
    FROM notice_attachments
    WHERE notice_type = ?
      AND notice_id = ?
    ORDER BY display_order ASC, id ASC
  `).all(noticeType, noticeId) as NoticeAttachmentRow[];

  return rows.filter(row => /^https?:\/\//i.test(row.downloadPath));
}

export interface NoticeFilters {
  source?: string;
  profile?: Profile;
  mainCategory?: string;
  subcategory?: string;
  status?: 'open' | 'closing-soon' | 'closed';
  query?: string;
  audience?: string;
  review?: boolean;
  sort?: 'latest' | 'deadline';
  limit?: number;
  offset?: number;
}

const deadlineSql = `datetime(CASE WHEN length(notice.deadline) = 10 THEN notice.deadline || ' 23:59:59' ELSE notice.deadline END,
  CASE WHEN length(notice.deadline) > 10 AND (substr(notice.deadline, -1) = 'Z' OR substr(notice.deadline, -6, 1) IN ('+', '-')) THEN '+9 hours' ELSE '+0 hours' END)`;
const rollingSql = `(notice.deadline LIKE '%상시%' OR notice.deadline LIKE '%수시%' OR notice.deadline LIKE '%채용시%' OR notice.deadline LIKE '%채용 시%' OR notice.deadline LIKE '%선발시%' OR notice.deadline LIKE '%선발 시%' OR notice.deadline LIKE '%충원시%' OR notice.deadline LIKE '%충원 시%')`;
const closedSql = `(${deadlineSql} < datetime('now', '+9 hours') OR notice.title LIKE '%[마감]%' OR notice.title LIKE '%채용완료%' OR notice.title LIKE '%모집완료%' OR notice.classification_status IN ('needs_review', 'pending'))`;

function noticeWhere(filters: NoticeFilters) {
  const eligibility = profileSql(filters.profile);
  const clauses: string[] = eligibility.sql ? [eligibility.sql] : [];
  const params: (string | number)[] = [...eligibility.params];
  for (const [column, value] of [['main_category', filters.mainCategory], ['subcategory', filters.subcategory]]) {
    if (value) { clauses.push(`notice.${column} = ?`); params.push(value); }
  }
  if (filters.source) {
    clauses.push('EXISTS (SELECT 1 FROM notice_origins origin WHERE origin.notice_id = notice.id AND origin.board_id = ?)');
    params.push(filters.source);
  }
  // instr treats user-entered percent and underscore as literal search characters.
  if (filters.query) {
    clauses.push("instr(lower(notice.title || ' ' || notice.organizer || ' ' || notice.full_text || ' ' || notice.target_audience), lower(?)) > 0");
    params.push(filters.query.slice(0, 300));
  }
  if (filters.audience) {
    clauses.push("instr(lower(notice.target_audience || ' ' || COALESCE(notice.eligibility_conditions, '')), lower(?)) > 0");
    params.push(filters.audience.slice(0, 100));
  }
  if (filters.review) clauses.push("notice.classification_status IN ('needs_review', 'pending')");
  clauses.push(filters.status === 'closed' ? closedSql : `COALESCE(${closedSql}, 0) = 0`);
  if (filters.status === 'open') clauses.push(`(${deadlineSql} >= datetime('now', '+9 hours') OR ${rollingSql})`);
  if (filters.status === 'closing-soon') clauses.push(`${deadlineSql} >= datetime('now', '+9 hours') AND ${deadlineSql} <= datetime('now', '+9 hours', '+7 days')`);
  return { sql: clauses.length ? 'WHERE ' + clauses.join(' AND ') : '', params };
}

export function getNotices(filters: NoticeFilters = {}): Job[] {
  const { sql, params } = noticeWhere(filters);
  const order = filters.sort === 'deadline' || filters.status === 'closing-soon'
    ? `(${deadlineSql} IS NULL) ASC, ${deadlineSql} ASC, notice.id DESC`
    : 'notice.created_at DESC, notice.id DESC';
  const limit = filters.limit === undefined ? -1 : Math.min(200, Math.max(1, Math.trunc(filters.limit)));
  const offset = Math.max(0, Math.trunc(filters.offset || 0));
  return getDb().prepare(`SELECT notice.*, (SELECT group_concat(name, ' · ') FROM (SELECT DISTINCT board.name FROM notice_origins origin JOIN notice_boards board ON board.id=origin.board_id WHERE origin.notice_id=notice.id)) AS sourceLabels, ${profileSql(filters.profile).matchSql} AS eligibilityMatch, (SELECT COUNT(*) FROM notice_attachments a
    WHERE a.notice_type = notice.notice_type AND a.notice_id = notice.id) AS attachmentCount
    FROM notices notice LEFT JOIN notice_eligibility eligibility ON eligibility.notice_id = notice.id ${sql} ORDER BY ${order} LIMIT ? OFFSET ?`).all(...params, limit, offset) as Job[];
}

export function getNoticeCount(filters: NoticeFilters = {}): number {
  const { sql, params } = noticeWhere(filters);
  return (getDb().prepare(`SELECT COUNT(*) AS count FROM notices notice LEFT JOIN notice_eligibility eligibility ON eligibility.notice_id = notice.id ${sql}`).get(...params) as { count: number }).count;
}

export function getNoticeBoards(): { id: string; name: string }[] {
  return getDb().prepare(`SELECT id,name FROM notice_boards ORDER BY university,COALESCE(college, ''),COALESCE(department, ''),name`).all() as { id: string; name: string }[];
}

export function getBoardStats(filters: NoticeFilters = {}) {
  const latest = getDb().prepare('SELECT MAX(created_at) AS latest FROM notices').get() as { latest: string | null };
  return { total: getNoticeCount(filters), open: getNoticeCount({ ...filters, status: 'open' }), soon: getNoticeCount({ ...filters, status: 'closing-soon' }),
    latest: latest.latest };
}

export function getCategoryCounts(filters: NoticeFilters = {}): { main_category: string | null; count: number }[] {
  const { sql, params } = noticeWhere(filters);
  return getDb().prepare(`SELECT main_category, COUNT(*) AS count FROM notices notice LEFT JOIN notice_eligibility eligibility ON eligibility.notice_id = notice.id ${sql} GROUP BY main_category`).all(...params) as { main_category: string | null; count: number }[];
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

  notice.origins = db.prepare('SELECT board.id AS boardId, board.name, origin.source_url AS url, origin.published_at AS publishedAt FROM notice_origins origin JOIN notice_boards board ON board.id=origin.board_id WHERE origin.notice_id=? ORDER BY board.name').all(id) as NonNullable<T['origins']>;
  notice.normalizedEligibility = db.prepare('SELECT * FROM notice_eligibility WHERE notice_id = ?').get(id) as Record<string, unknown> | undefined;
  notice.attachments = getNoticeAttachments(noticeType, id);
  return notice;
}

// Classification drives lists; notice_type still identifies the original detail route.
export function getAllJobs(): Job[] {
  return getNotices({ mainCategory: '취업·인턴·현장실습', limit: 10 });
}
export function getOpenJobs(): Job[] {
  return getNotices({ mainCategory: '취업·인턴·현장실습', status: 'open' });
}
export function getClosingSoonJobs(): Job[] {
  return getNotices({ mainCategory: '취업·인턴·현장실습', status: 'closing-soon' });
}
export function getJobById(id: number): Job | null {
  return getNoticeById<Job>('jobs', 'job', id);
}
export function getAllScholarships(): Scholarship[] {
  return getNotices({ mainCategory: '장학·학비지원', limit: 10 });
}
export function getOpenScholarships(): Scholarship[] {
  return getNotices({ mainCategory: '장학·학비지원', status: 'open' });
}
export function getClosingSoonScholarships(): Scholarship[] {
  return getNotices({ mainCategory: '장학·학비지원', status: 'closing-soon' });
}
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
    "SELECT COUNT(*) as count FROM notices WHERE main_category = '취업·인턴·현장실습' AND datetime(deadline) > datetime('now')"
  ).get() as { count: number }).count;

  // 마감 직전 채용 공고 (D-7: 현재부터 7일 이내 마감)
  const closingSoonJobs = (db.prepare(
    "SELECT COUNT(*) as count FROM notices WHERE main_category = '취업·인턴·현장실습' AND datetime(deadline) > datetime('now') AND datetime(deadline) <= datetime('now', '+7 days')"
  ).get() as { count: number }).count;

  // 마감 전 전체 장학금
  const openScholarships = (db.prepare(
    "SELECT COUNT(*) as count FROM notices WHERE main_category = '장학·학비지원' AND datetime(deadline) > datetime('now')"
  ).get() as { count: number }).count;

  // 마감 직전 장학금 (D-7)
  const closingSoonScholarships = (db.prepare(
    "SELECT COUNT(*) as count FROM notices WHERE main_category = '장학·학비지원' AND datetime(deadline) > datetime('now') AND datetime(deadline) <= datetime('now', '+7 days')"
  ).get() as { count: number }).count;

  return {
    openJobs,
    closingSoonJobs,
    openScholarships,
    closingSoonScholarships,
  };
}
