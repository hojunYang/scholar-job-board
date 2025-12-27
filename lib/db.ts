import Database from 'better-sqlite3';
import path from 'path';

// DB 파일 경로
const dbPath = path.join(process.cwd(), 'data', 'scholar.db');

// DB 인스턴스 생성
let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    initializeDatabase();
  }
  return db;
}

// 데이터베이스 초기화 (테이블 생성)
function initializeDatabase() {
  const db = getDb();
  
  // 채용 공고 테이블
  db.exec(`
    CREATE TABLE IF NOT EXISTS jobs (
      id INTEGER PRIMARY KEY,
      target_audience TEXT NOT NULL,
      organizer TEXT NOT NULL,
      deadline TEXT NOT NULL,
      selection_date TEXT,
      benefit TEXT NOT NULL,
      category TEXT NOT NULL,
      title TEXT NOT NULL,
      full_text TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // 장학금 테이블
  db.exec(`
    CREATE TABLE IF NOT EXISTS scholarships (
      id INTEGER PRIMARY KEY,
      target_audience TEXT NOT NULL,
      organizer TEXT NOT NULL,
      deadline TEXT NOT NULL,
      selection_date TEXT,
      benefit TEXT NOT NULL,
      category TEXT NOT NULL,
      title TEXT NOT NULL,
      full_text TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);
}

// DB 연결 종료
export function closeDb() {
  if (db) {
    db.close();
    db = null;
  }
}

