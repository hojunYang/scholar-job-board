"""Additive, transactional schema migration shared by backfill and crawler."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('jobs', 'scholarships')
COLUMNS = {
    'main_category': 'TEXT',
    'subcategory': 'TEXT',
    'eligibility_conditions': "TEXT CHECK (eligibility_conditions IS NULL OR (json_valid(eligibility_conditions) AND json_type(eligibility_conditions) = 'object'))",
    'classification_status': "TEXT NOT NULL DEFAULT 'pending' CHECK (classification_status IN ('pending', 'auto', 'reviewed', 'needs_review'))",
    'classification_reason': 'TEXT',
}


def ensure_notice_schema(conn):
    taxonomy = json.loads((ROOT / 'data/notice-taxonomy.json').read_text())
    conn.execute('CREATE TABLE IF NOT EXISTS notice_categories (main_category TEXT NOT NULL, subcategory TEXT NOT NULL, PRIMARY KEY (main_category, subcategory))')
    conn.executemany('INSERT OR IGNORE INTO notice_categories VALUES (?, ?)',
                     [(main, sub) for main, subs in taxonomy.items() for sub in subs])
    for table in TABLES:
        conn.execute(f'''CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY, target_audience TEXT NOT NULL, organizer TEXT NOT NULL,
            deadline TEXT NOT NULL, selection_date TEXT, benefit TEXT NOT NULL,
            category TEXT NOT NULL, title TEXT NOT NULL, full_text TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        names = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
        for name, declaration in COLUMNS.items():
            if name not in names:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {declaration}')
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_classification ON {table}(main_category, subcategory)')
        for action in ('INSERT', 'UPDATE OF main_category, subcategory'):
            suffix = 'insert' if action == 'INSERT' else 'update'
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS validate_{table}_category_{suffix}
                BEFORE {action} ON {table}
                WHEN NOT ((NEW.main_category IS NULL AND NEW.subcategory IS NULL) OR
                    EXISTS (SELECT 1 FROM notice_categories WHERE main_category = NEW.main_category AND subcategory = NEW.subcategory))
                BEGIN SELECT RAISE(ABORT, 'Invalid notice category pair'); END''')

    view=conn.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='notices'").fetchone()
    if view and 'source_rank = 1 AND' not in view[0]:
        conn.execute('DROP VIEW notices')
    conn.execute((ROOT / 'data/notices-view.sql').read_text())
    conn.execute((ROOT / 'data/eligibility-schema.sql').read_text())
    for statement in (ROOT / 'data/notice-sources-schema.sql').read_text().split(';'):
        if statement.strip(): conn.execute(statement)
