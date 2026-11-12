"""Discover SKKU notice boards from official directories and verify real list/detail parsing."""
import argparse
import concurrent.futures
import hashlib
import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from crawler import REQUEST_HEADERS, parse_notice_list, parse_notice_detail
from sources import ROOT, load_sources

DIRECTORIES = [
    'https://www.skku.edu/skku/edu/education.do',
    'https://www.skku.edu/skku/edu/graduateSchool/graduate_school_2023.do',
    'https://www.skku.edu/skku/edu/graduateSchool/graduate_school02.do',
    'https://www.skku.edu/skku/edu/graduateSchool/graduate_school03.do',
]
EXTRA_SEEDS = [
    'https://ase.skku.edu/ase/notice.do',
    'https://sas.skku.edu/sas/notice.do',
    'https://cculture.skku.edu/cculture/index.do',
]
BOARD_WORDS = re.compile(r'공지사항|공지$|공지[ ·(/-]|취업정보|채용정보|장학공지|^Notice', re.I)
CACHE = ROOT / 'work/source-discovery'


def official_url(href, base=''):
    try:
        parsed = urlparse(urljoin(base, href))
        port = parsed.port
    except ValueError:return None
    if parsed.scheme not in ('http', 'https') or not parsed.hostname: return None
    if not any(parsed.hostname.endswith('.' + domain) or parsed.hostname == domain for domain in ('skku.edu','skku.ac.kr')): return None
    if port not in (None,80,443): return None
    path = re.sub(r';[^/]*', '', parsed.path or '/')
    if re.fullmatch(r'/board/notice/\d+/?',path):return None
    if re.search(r'\.(?:pdf|hwp|hwpx|docx?|xlsx?|pptx?|zip|jpg|png|gif|css|js)$', path, re.I): return None
    query = {k:v for k,v in parse_qs(parsed.query).items() if k not in ('article.offset','articleLimit','page','mode','PHPSESSID','boardId','link')}
    if any(k in query for k in ('articleNo','itemId','wr_id','attachNo','fileId','idx','bltn_seq','num')): return None
    return urlunparse(('https', parsed.hostname, path, '', urlencode(query,doseq=True), ''))


def board_key(url):
    parsed=urlparse(official_url(url) or url)
    # SKKU's shared CMS serves the same site path under multiple subdomain aliases.
    return (parsed.path.rstrip('/'),parsed.query) if parsed.path.endswith('.do') else (parsed.hostname,parsed.path.rstrip('/'),parsed.query)


def fetch(url):
    CACHE.mkdir(exist_ok=True,parents=True)
    key=hashlib.sha256(url.encode()).hexdigest()
    file=CACHE / f'{key}.json'
    if file.is_file() and time.time()-file.stat().st_mtime < 86400: return json.loads(file.read_text())
    error=None
    for attempt in range(2):
        try:
            response=requests.get(url,headers=REQUEST_HEADERS,timeout=(6,15))
            response.raise_for_status(); response.encoding='utf-8'
            result={'url':response.url,'html':response.text}
            file.write_text(json.dumps(result,ensure_ascii=False))
            return result
        except requests.RequestException as exc:
            error=exc
            if attempt==0: time.sleep(.5)
    raise error


def directory_sites(html, url):
    soup=BeautifulSoup(html,'html.parser');sites={}
    for link in soup.select('a[href]'):
        if not link.select_one('img[alt="홈페이지"]'): continue
        target=official_url(link['href'],url)
        if target: sites[target]={'url':target,'found_on':url}
    return list(sites.values())


def inspect_site(site):
    page=fetch(site['url']);soup=BeautifulSoup(page['html'],'html.parser')
    candidates={};follow={}
    for a in soup.select('a[href]'):
        target=official_url(a['href'],page['url'])
        if not target: continue
        label=a.get_text(' ',strip=True)
        parsed=urlparse(target)
        if parsed.hostname in ('www.skku.edu','www.skku.ac.kr'): continue
        if (BOARD_WORDS.search(label) or re.search(r'(?:^|/|_)notice(?:[._/]|$)',parsed.path,re.I)) and not re.search(r'faq|qna|search|login|faculty',parsed.path,re.I):
            candidates[board_key(target)]={'url':target,'label':label,'found_on':site['url']}
        if re.search(r'연계전공|융합전공|협동과정',label) and not re.search(r'교과|이수|신청|포기|안내|모집|공지|자료|졸업',label):
            follow[target]={'url':target,'found_on':site['url']}
        elif re.search(r'학과|학부|대학|대학원',label) and urlparse(page['url']).hostname!=parsed.hostname and parsed.hostname not in ('www.skku.edu','www.skku.ac.kr') and len(label)<35:
            follow[target]={'url':target,'found_on':site['url']}
    if BOARD_WORDS.search(soup.title.get_text(' ',strip=True) if soup.title else '') or re.search(r'/notice[^/]*\.do',urlparse(page['url']).path):
        candidates[board_key(page['url'])]={'url':official_url(page['url']),'label':'공지','found_on':site['found_on']}
    return list(candidates.values()),list(follow.values())


def verify_board(candidate):
    page=fetch(candidate['url']);rows=parse_notice_list(page['html'],page['url'])
    if not rows: return {**candidate,'status':'empty','notices':0}
    # A current ordinary notice is more useful for initial ingestion than an old pinned one.
    ordered=sorted(rows,key=lambda r:(r.get('published_at') or '',str(r['article_no'])),reverse=True)
    errors=[];samples=[]
    for row in ordered[:3]:
        try:
            detail_page=fetch(row['url'])
            detail=parse_notice_detail(detail_page['html'],detail_page['url'])
            if not detail['title']: raise ValueError('Empty notice title')
            samples.append({**row,'detail':detail})
            break
        except Exception as error: errors.append(str(error))
    if not samples: raise ValueError('; '.join(errors))
    soup=BeautifulSoup(page['html'],'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    owner=re.sub(r'^성균관대학교\s*','',title.split('|')[-1].strip()).strip()
    if not owner or re.search(r'게시판|찾을 수|접근|Error|LOGIN|로그인',owner,re.I): raise ValueError(f'Invalid board owner: {title}')
    headings=[n.get_text(' ',strip=True) for n in soup.select('.page-title-txt')]
    label=' '.join(headings) if headings else candidate['label']
    label=re.sub(r'공지사항|게시판목록|trending_flat', '', label).strip(' -:')
    if not label or re.fullmatch(r'(?:read more|notice|공지|커뮤니티)',label,re.I): label='공지'
    if len(label)>45:label='공지'
    slug=re.sub(r'[^a-z0-9]+','-',urlparse(candidate['url']).path.lower()).strip('-')
    if not slug: slug=urlparse(candidate['url']).hostname.split('.')[0]+'-notice'
    config=dict(id=slug,university='성균관대학교',college=owner if owner.endswith(('대학','대학원')) else None,
                department=None if owner.endswith(('대학','대학원')) else owner,name=f'{owner} · {label}',
                url=candidate['url'],table='jobs',legacy_ids=False,enabled=True,pages=2)
    return {**candidate,'status':'verified','notices':len(rows),'config':config,'sample':samples[0]}


def discover(workers=6,max_sites=250):
    sites={};failures=[]
    for url in DIRECTORIES:
        try:
            page=fetch(url)
            for site in directory_sites(page['html'],page['url']):sites[site['url']]=site
        except Exception as error: failures.append({'url':url,'phase':'directory','error':str(error)})
    for board in load_sources():sites[board['url']]={'url':board['url'],'found_on':'existing configuration'}
    for url in EXTRA_SEEDS:sites[url]={'url':url,'found_on':'user / official search'}
    seen=set();candidates={}
    for depth in range(3):
        batch=[s for url,s in sites.items() if url not in seen][:max_sites-len(seen)]
        if not batch:break
        print(f'Discovering round {depth+1}: {len(batch)} sites',flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(inspect_site,site):site for site in batch}
            for future in concurrent.futures.as_completed(futures):
                site=futures[future];seen.add(site['url'])
                try:
                    boards,following=future.result()
                    for board in boards:candidates.setdefault(board_key(board['url']),board)
                    for next_site in following:sites.setdefault(next_site['url'],next_site)
                except Exception as error:failures.append({**site,'phase':'site','error':str(error)})
        print(f'Inspected {len(seen)} sites, found {len(candidates)} candidate boards',flush=True)
    verified=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(verify_board,b):b for b in candidates.values()}
        for future in concurrent.futures.as_completed(futures):
            board=futures[future]
            try:
                result=future.result();verified.append(result)
                print(f"{result['status']}: {result.get('config',{}).get('name',board['url'])}",flush=True)
            except Exception as error:failures.append({**board,'phase':'board','error':str(error)})
    return {'directories':DIRECTORIES,'sites_checked':len(seen),'candidates':len(candidates),
            'boards':sorted(verified,key=lambda r:r['url']),'failures':failures}


def consolidate_sources(sources):
    by_key={}
    for source in sources:
        board=dict(source)
        board['url']=official_url(board['url']) or board['url']
        key=board_key(board['url'])
        if key in by_key:
            canonical=by_key[key]
            canonical['replaces']=list(dict.fromkeys(canonical.get('replaces',[])+[board['id']]+board.get('replaces',[])))
        else:by_key[key]=board
    return list(by_key.values())


def apply_report(report):
    path=ROOT/'data/notice-sources.json';existing=load_sources()
    keys={board_key(b['url']) for b in existing};ids={b['id'] for b in existing}
    for result in report['boards']:
        if result['status']!='verified':continue
        board=result['config'];key=board_key(board['url'])
        if key in keys:continue
        if board['id'] in ids:board['id']+='-'+hashlib.sha256(board['url'].encode()).hexdigest()[:8]
        existing.append(board);keys.add(key);ids.add(board['id'])
    existing=consolidate_sources(existing)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(existing,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)
    load_sources()
    return len(existing)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=6,choices=range(1,9))
    parser.add_argument('--max-sites',type=int,default=250)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    report=discover(args.workers,args.max_sites)
    destination=ROOT/'work/source-discovery-report.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if args.apply:print('Configured boards:',apply_report(report))
    print('Report:',destination,'verified:',sum(b['status']=='verified' for b in report['boards']),'failed:',len(report['failures']))
