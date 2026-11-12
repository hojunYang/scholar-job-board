"""Backfill queryable eligibility values without changing original notices or classification."""
import argparse
import collections
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from notice_schema import ROOT, ensure_notice_schema
from eligibility import extract_profile, save_profile, FIELDS


def migrate(path):
    path = Path(path).resolve()
    if not path.is_file(): raise FileNotFoundError(path)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    backup = path.parent / 'backups' / f'{path.stem}.before-profile.{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.db'
    backup.parent.mkdir(exist_ok=True)
    try:
        with sqlite3.connect(backup) as destination:
            conn.backup(destination)
        coverage = collections.defaultdict(collections.Counter)
        with conn:
            ensure_notice_schema(conn)
            rows = conn.execute('SELECT * FROM notices').fetchall()
            for row in rows:
                profile = extract_profile(row['title'], row['full_text'], row['target_audience'], row['main_category'], row['subcategory'])
                save_profile(conn, row['id'], profile)
                for field in FIELDS:
                    coverage[row['main_category']][f"{field}:{profile['field_states'][field]}"] += 1
            assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert conn.execute('SELECT COUNT(*) FROM notice_eligibility').fetchone()[0] >= len(rows)
        report = dict(database=str(path), backup=str(backup), notices=len(rows), coverage=coverage)
        backup.with_suffix('.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        return report
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/scholar.db')
    print(json.dumps(migrate(parser.parse_args().db), ensure_ascii=False, indent=2))
