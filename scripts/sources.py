"""Configured boards and source-specific article identities; internal IDs stay globally unique."""
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_sources(path=None):
    sources = json.loads(Path(path or ROOT / 'data/notice-sources.json').read_text())
    ids, urls = set(), set()
    for board in sources:
        if board['id'] in ids or board['url'] in urls:
            raise ValueError('Duplicate source id or URL')
        ids.add(board['id']); urls.add(board['url'])
        if urlparse(board['url']).scheme != 'https' or board['table'] not in ('jobs', 'scholarships'):
            raise ValueError('Invalid source URL or table')
        if any(table not in ('jobs','scholarships') for table in board.get('legacy_tables', [])):
            raise ValueError('Invalid legacy table')
        if not isinstance(board.get('pages'), int) or not 1 <= board['pages'] <= 100:
            raise ValueError('Source pages must be between 1 and 100')
    return sources


def register_sources(conn, sources):
    for board in sources:
        conn.execute('''INSERT INTO notice_boards (id,university,college,department,name,url)
            VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET university=excluded.university,
            college=excluded.college,department=excluded.department,name=excluded.name,url=excluded.url''',
            tuple(board.get(k) for k in ('id','university','college','department','name','url')))
        if board.get('legacy_ids'):
            for table in board.get('legacy_tables', [board['table']]):
                kind = 'job' if table == 'jobs' else 'scholarship'
                conn.execute(f'''INSERT OR IGNORE INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url)
                    SELECT ?,id,id,?,COALESCE((SELECT source_url FROM notice_sources s WHERE s.notice_id=n.id AND s.notice_type=?), ? || '?mode=view&articleNo=' || id)
                    FROM {table} n WHERE id < 1000000000''', (board['id'], kind, kind, board['url']))
        for replaced in board.get('replaces', []):
            if replaced == board['id']: raise ValueError('Cannot replace the active source')
            conn.execute('''INSERT OR IGNORE INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url,published_at)
                SELECT ?,article_no,notice_id,notice_type,source_url,published_at FROM notice_origins WHERE board_id=?''', (board['id'],replaced))
            conn.execute('DELETE FROM notice_origins WHERE board_id=?', (replaced,))
            conn.execute('DELETE FROM notice_boards WHERE id=?', (replaced,))


def find_origin(conn, board, article_no):
    return conn.execute('SELECT notice_id,notice_type FROM notice_origins WHERE board_id=? AND article_no=?',
                        (board['id'], article_no)).fetchone()


def save_origin(conn, board, notice, notice_id, notice_type):
    conn.execute('''INSERT INTO notice_origins (board_id,article_no,notice_id,notice_type,source_url,published_at)
        VALUES (?,?,?,?,?,?) ON CONFLICT(board_id,article_no) DO UPDATE SET source_url=excluded.source_url,
        published_at=excluded.published_at''',
        (board['id'], notice['article_no'], notice_id, notice_type, notice['url'], notice.get('published_at')))


def next_notice_id(conn):
    # Reserve a separate internal range; upstream article numbers are not global identifiers.
    return max(1000000000, conn.execute('SELECT MAX(id) FROM (SELECT id FROM jobs UNION ALL SELECT id FROM scholarships)').fetchone()[0] or 0) + 1
