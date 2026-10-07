import argparse
import json
import os
from collections import Counter
from .core import CRM, ROOT, database, load_env, now, process_lock, scrape
from .matching import find_parent, reconcile

def run(cached=False):
    load_env()
    with process_lock():
        snapshot=json.loads((ROOT/'data'/'locations.json').read_text()) if cached else scrape(os.environ.get('WEBSITE_BASE_URL','https://analyst-assessment-production.up.railway.app'))
        crm=CRM(); accounts=crm.list_accounts(); parent=find_parent(accounts)
        (ROOT/'data'/'crm-latest.json').write_text(json.dumps(accounts,indent=2))
        before=ROOT/'data'/'crm-before.json'
        if not before.exists(): before.write_text(json.dumps(accounts,indent=2))
        conn=database()
        try:
            prior=conn.execute('SELECT COUNT(*) FROM proposals').fetchone()[0]
            rid=reconcile(conn,snapshot,accounts,parent)
            new=conn.execute('SELECT COUNT(*) FROM proposals').fetchone()[0]-prior
            counts=dict(Counter(r['classification'] for r in conn.execute('SELECT classification FROM matches WHERE run_id=?',(rid,))))
            print(json.dumps({'run_id':rid,'website_count':len(snapshot['locations']),'crm_count':len(accounts),'new_proposals':new,'classifications':counts,'writes':0},indent=2))
        finally: conn.close()

def export():
    conn=database()
    try:
        output={'exported_at':now(),'runs':[dict(r) for r in conn.execute('SELECT id,at,parent_id FROM runs')], 'proposals':[]}
        for row in conn.execute('SELECT * FROM proposals ORDER BY id'):
            item=dict(row)
            for key in ('plan','evidence','result'):
                item[key]=json.loads(item[key]) if item[key] else None
            item['operations']=[dict(r) for r in conn.execute('SELECT * FROM operations WHERE proposal_id=? ORDER BY step',(row['id'],))]
            output['proposals'].append(item)
        path=ROOT/'data'/'audit.json'; path.write_text(json.dumps(output,indent=2)); print(path)
    finally: conn.close()

def main():
    parser=argparse.ArgumentParser(description='Bellhaven pipeline: generates proposals, never auto-approves')
    sub=parser.add_subparsers(dest='command',required=True)
    scan=sub.add_parser('run'); scan.add_argument('--cached-website',action='store_true')
    sub.add_parser('scrape')
    web=sub.add_parser('serve'); web.add_argument('--port',type=int,default=8765)
    sub.add_parser('export')
    args=parser.parse_args(); load_env()
    if args.command=='run': run(args.cached_website)
    elif args.command=='scrape':
        result=scrape(os.environ.get('WEBSITE_BASE_URL','https://analyst-assessment-production.up.railway.app')); print(f"Collected {len(result['locations'])} facilities")
    elif args.command=='serve':
        from .app import serve
        serve(args.port)
    else: export()

if __name__=='__main__': main()
