CREATE TABLE IF NOT EXISTS notice_boards (
  id TEXT PRIMARY KEY,
  university TEXT NOT NULL,
  college TEXT,
  department TEXT,
  name TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS notice_origins (
  board_id TEXT NOT NULL REFERENCES notice_boards(id),
  article_no TEXT NOT NULL,
  notice_id INTEGER NOT NULL,
  notice_type TEXT NOT NULL CHECK (notice_type IN ('job', 'scholarship')),
  source_url TEXT NOT NULL,
  published_at TEXT,
  PRIMARY KEY (board_id, article_no)
);
CREATE INDEX IF NOT EXISTS idx_notice_origins_notice ON notice_origins(notice_id, notice_type);
