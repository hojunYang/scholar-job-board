import Database from 'better-sqlite3';
import path from 'path';
import { readFileSync } from 'fs';
import taxonomy from '@/data/notice-taxonomy.json';

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

  db.exec(`
    CREATE TABLE IF NOT EXISTS notice_sources (
      notice_type TEXT NOT NULL,
      notice_id INTEGER NOT NULL,
      source_url TEXT NOT NULL,
      source_title TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (notice_type, notice_id)
    )
  `);

  db.exec(`
    CREATE TABLE IF NOT EXISTS notice_attachments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      notice_type TEXT NOT NULL,
      notice_id INTEGER NOT NULL,
      source_attach_no INTEGER NOT NULL,
      original_filename TEXT NOT NULL,
      download_url TEXT NOT NULL,
      storage_path TEXT NOT NULL,
      mime_type TEXT,
      file_size INTEGER,
      display_order INTEGER NOT NULL DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      UNIQUE (notice_type, notice_id, source_attach_no)
    )
  `);

  db.transaction(() => {
    db.exec(`CREATE TABLE IF NOT EXISTS notice_categories (
      main_category TEXT NOT NULL, subcategory TEXT NOT NULL,
      PRIMARY KEY (main_category, subcategory)
    )`);
    const addCategory = db.prepare('INSERT OR IGNORE INTO notice_categories VALUES (?, ?)');
    for (const [main, subs] of Object.entries(taxonomy)) {
      for (const sub of subs) addCategory.run(main, sub);
    }
    const columns: Record<string, string> = {
      main_category: 'TEXT',
      subcategory: 'TEXT',
      eligibility_conditions: "TEXT CHECK (eligibility_conditions IS NULL OR (json_valid(eligibility_conditions) AND json_type(eligibility_conditions) = 'object'))",
      classification_status: "TEXT NOT NULL DEFAULT 'pending' CHECK (classification_status IN ('pending', 'auto', 'reviewed', 'needs_review'))",
      classification_reason: 'TEXT',
    };
    for (const table of ['jobs', 'scholarships']) {
      const existing = new Set((db.prepare(`PRAGMA table_info(${table})`).all() as { name: string }[]).map(row => row.name));
      for (const [column, declaration] of Object.entries(columns)) {
        if (!existing.has(column)) db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${declaration}`);
      }
      db.exec(`CREATE INDEX IF NOT EXISTS idx_${table}_classification ON ${table}(main_category, subcategory)`);
      for (const [suffix, action] of [['insert', 'INSERT'], ['update', 'UPDATE OF main_category, subcategory']]) {
        db.exec(`CREATE TRIGGER IF NOT EXISTS validate_${table}_category_${suffix}
          BEFORE ${action} ON ${table}
          WHEN NOT ((NEW.main_category IS NULL AND NEW.subcategory IS NULL) OR
            EXISTS (SELECT 1 FROM notice_categories WHERE main_category = NEW.main_category AND subcategory = NEW.subcategory))
          BEGIN SELECT RAISE(ABORT, 'Invalid notice category pair'); END`);
      }
    }
    const noticeView = db.prepare("SELECT sql FROM sqlite_master WHERE type='view' AND name='notices'").get() as {sql:string} | undefined;
    if (noticeView && !noticeView.sql.includes('source_rank = 1 AND')) db.exec('DROP VIEW notices');
    db.exec(readFileSync(path.join(process.cwd(), 'data', 'notices-view.sql'), 'utf8'));
    db.exec(readFileSync(path.join(process.cwd(), 'data', 'eligibility-schema.sql'), 'utf8'));
    db.exec(readFileSync(path.join(process.cwd(), 'data', 'notice-sources-schema.sql'), 'utf8'));
    const addBoard = db.prepare('INSERT INTO notice_boards (id, university, college, department, name, url) VALUES (@id,@university,@college,@department,@name,@url) ON CONFLICT(id) DO UPDATE SET university=excluded.university,college=excluded.college,department=excluded.department,name=excluded.name,url=excluded.url');
    const boards = JSON.parse(readFileSync(path.join(process.cwd(), 'data', 'notice-sources.json'), 'utf8'));
    for (const board of boards) {
      addBoard.run({id:board.id,university:board.university,college:board.college,department:board.department,name:board.name,url:board.url});
      if (board.legacy_ids) for (const table of board.legacy_tables || [board.table]) {
        if (!['jobs','scholarships'].includes(table)) throw new Error('Invalid legacy source table');
        const kind = table === 'scholarships' ? 'scholarship' : 'job';
        db.prepare(`INSERT OR IGNORE INTO notice_origins (board_id, article_no, notice_id, notice_type, source_url) SELECT ?, id, id, ?, COALESCE((SELECT source_url FROM notice_sources s WHERE s.notice_id=n.id AND s.notice_type=?), ? || '?mode=view&articleNo=' || id) FROM ${table} n WHERE id < 1000000000`).run(board.id,kind,kind,board.url);
      }
      for (const replaced of board.replaces || []) {
        if (replaced === board.id) throw new Error('Cannot replace the active source');
        db.prepare('INSERT OR IGNORE INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url,published_at) SELECT ?,article_no,notice_id,notice_type,source_url,published_at FROM notice_origins WHERE board_id=?').run(board.id,replaced);
        db.prepare('DELETE FROM notice_origins WHERE board_id=?').run(replaced);
        db.prepare('DELETE FROM notice_boards WHERE id=?').run(replaced);
      }
    }
  })();
}

// DB 연결 종료
export function closeDb() {
  if (db) {
    db.close();
    db = null;
  }
}
