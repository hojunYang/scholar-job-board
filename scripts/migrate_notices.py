"""Back up SQLite, add classification columns and classify existing notices offline."""
import argparse
import collections
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from classification import classification_fields
from notice_schema import ROOT, TABLES, ensure_notice_schema


def migrate(db_path):
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f'{db_path.stem}.before-classification.{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.db'
    try:
        with sqlite3.connect(backup) as dest:
            conn.backup(dest)
        with conn:
            ensure_notice_schema(conn)
            rows = [(table, dict(row)) for table in TABLES for row in conn.execute(f'SELECT * FROM {table}')]
            grouped = collections.defaultdict(list)
            for table, row in rows:
                grouped[row['id']].append((table, row))
            changed = 0
            for notice_id, entries in grouped.items():
                # Pick complete source content consistently, retaining each row's original fields.
                source = max((row for _, row in entries), key=lambda r: (bool(r['full_text'].strip()), r['updated_at'] or '', len(r['full_text'])))
                fields = classification_fields(source['title'], source['full_text'], source['target_audience'], source['benefit'], source['category'])
                for table, row in entries:
                    if row['classification_status'] != 'pending':
                        continue  # Reruns preserve previously classified and manually reviewed rows.
                    eligibility = classification_fields(row['title'], row['full_text'], row['target_audience'], row['benefit'], row['category'])['eligibility_conditions']
                    conn.execute(f'''UPDATE {table} SET main_category=?, subcategory=?, eligibility_conditions=?,
                        classification_status=?, classification_reason=? WHERE id=?''',
                        (fields['main_category'], fields['subcategory'], eligibility,
                         fields['classification_status'], fields['classification_reason'], notice_id))
                    changed += 1
            assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert len(rows) == sum(conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in TABLES)
        counts = conn.execute('SELECT main_category, subcategory, COUNT(*) FROM notices GROUP BY main_category, subcategory ORDER BY main_category, subcategory').fetchall()
        review = [dict(row) for row in conn.execute("SELECT id, title, classification_reason AS reason FROM notices WHERE classification_status = 'needs_review'")]
        report = dict(database=str(db_path), backup=str(backup), stored_rows=len(rows), unique_notices=len(grouped),
                      updated_rows=changed, categories=[dict(main_category=m, subcategory=s, count=n) for m, s, n in counts],
                      needs_review=review)
        report_path = backup.with_suffix('.report.json')
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        return report
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/scholar.db')
    args = parser.parse_args()
    print(json.dumps(migrate(args.db), ensure_ascii=False, indent=2))
