"""Import the current verified sample from every discovered board, reusing cached source HTML."""
import argparse
import concurrent.futures
import json
from pathlib import Path

from crawler import save_to_db
from discover_sources import board_key
from sources import ROOT, load_sources


def ingest(report_path, workers=2):
    report=json.loads(Path(report_path).read_text())
    configured={board_key(b['url']):b for b in load_sources()}
    results=[]
    def process(item):
        board=configured[board_key(item['url'])]
        count=save_to_db([item['sample']],board['table'],'scholarship' if board['table']=='scholarships' else 'job',
                         board=board,download_files=False)
        return {'source':board['id'],'saved':count}
    verified=[b for b in report['boards'] if b['status']=='verified' and board_key(b['url']) in configured]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(process,board):board for board in verified}
        for future in concurrent.futures.as_completed(futures):
            board=futures[future]
            try:result=future.result()
            except Exception as error:result={'source':configured[board_key(board['url'])]['id'],'error':str(error)}
            results.append(result)
            print('Sample result:',json.dumps(result,ensure_ascii=False),flush=True)
            (ROOT/'work/source-ingest-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'work/source-discovery-report.json')
    parser.add_argument('--workers',type=int,choices=range(1,5),default=2)
    args=parser.parse_args()
    results=ingest(args.report,args.workers)
    failures=[r for r in results if 'error' in r]
    print(f'Checked {len(results)} boards; saved {sum(r.get("saved",0) for r in results)}; failed {len(failures)}')
    if failures:raise SystemExit(1)
