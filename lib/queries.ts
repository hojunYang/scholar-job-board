import { getDb } from './db';
import type { Job, Scholarship, Stats } from '@/types';

// 채용 공고 리스트 조회
export function getAllJobs(): Job[] {
  const db = getDb();
  const jobs = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC').all() as Job[];
  return jobs;
}

// 마감 전 채용 공고 조회
export function getOpenJobs(): Job[] {
  const db = getDb();
  const jobs = db.prepare(
    "SELECT * FROM jobs WHERE datetime(deadline) > datetime('now') ORDER BY deadline ASC"
  ).all() as Job[];
  return jobs;
}

// 마감 직전 채용 공고 조회 (D-7)
export function getClosingSoonJobs(): Job[] {
  const db = getDb();
  const jobs = db.prepare(
    "SELECT * FROM jobs WHERE datetime(deadline) > datetime('now') AND datetime(deadline) <= datetime('now', '+7 days') ORDER BY deadline ASC"
  ).all() as Job[];
  return jobs;
}

// 채용 공고 상세 조회
export function getJobById(id: number): Job | null {
  const db = getDb();
  const job = db.prepare('SELECT * FROM jobs WHERE id = ?').get(id) as Job | undefined;
  return job || null;
}

// 장학금 리스트 조회
export function getAllScholarships(): Scholarship[] {
  const db = getDb();
  const scholarships = db.prepare('SELECT * FROM scholarships ORDER BY created_at DESC').all() as Scholarship[];
  return scholarships;
}

// 마감 전 장학금 조회
export function getOpenScholarships(): Scholarship[] {
  const db = getDb();
  const scholarships = db.prepare(
    "SELECT * FROM scholarships WHERE datetime(deadline) > datetime('now') ORDER BY deadline ASC"
  ).all() as Scholarship[];
  return scholarships;
}

// 마감 직전 장학금 조회 (D-7)
export function getClosingSoonScholarships(): Scholarship[] {
  const db = getDb();
  const scholarships = db.prepare(
    "SELECT * FROM scholarships WHERE datetime(deadline) > datetime('now') AND datetime(deadline) <= datetime('now', '+7 days') ORDER BY deadline ASC"
  ).all() as Scholarship[];
  return scholarships;
}

// 장학금 상세 조회
export function getScholarshipById(id: number): Scholarship | null {
  const db = getDb();
  const scholarship = db.prepare('SELECT * FROM scholarships WHERE id = ?').get(id) as Scholarship | undefined;
  return scholarship || null;
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
