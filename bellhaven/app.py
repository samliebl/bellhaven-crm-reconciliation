import html
import json
import secrets
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .core import CRM, ROOT, database
from .execution import decide, execute

CSS = '''
:root{--ink:#183b35;--muted:#667a75;--paper:#f4f7f3;--border:#d7e0d8;--green:#205d4c;--gold:#b08127}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif}
header{background:#173f35;color:white;padding:24px 5vw}header a{color:white;text-decoration:none}header p{margin:3px 0 0;color:#c0d6cc}
main{max-width:1200px;margin:auto;padding:30px 24px 80px}h1,h2,h3{line-height:1.2}h1{font:32px Georgia,serif}h2{font-size:20px}
a{color:var(--green)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}.stat,.panel{background:white;border:1px solid var(--border);border-radius:12px;padding:22px}
.stat b{font-size:32px;display:block}.stat span,.muted{color:var(--muted)}.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}
.badge{display:inline-block;border-radius:20px;background:#e5ede7;padding:4px 12px;font-size:12px;font-weight:650}.warning{background:#fff4d8;border:1px solid #e5c779;padding:18px;border-radius:10px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;border-bottom:1px solid var(--border);padding:12px 10px;vertical-align:top}th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.table-wrap{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eff3ee;padding:16px;border-radius:8px;font-size:12px}code{overflow-wrap:anywhere}input{padding:10px;border:1px solid var(--border);border-radius:7px;font:inherit;max-width:100%}
button,.button{display:inline-block;border:0;padding:12px 20px;border-radius:8px;font:600 14px system-ui;cursor:pointer;text-decoration:none;background:var(--green);color:white}.secondary{background:#e8eee8;color:var(--ink)}button:disabled{opacity:.4;cursor:not-allowed}
.actions{display:flex;align-items:end;gap:14px;flex-wrap:wrap;margin:20px 0}.actions label{display:block}.eyebrow{letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-size:12px}.error{color:#8f2e27;background:#fff0ec;padding:16px;border-radius:8px}
@media(max-width:760px){.cols{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}main{padding:20px 14px}td,th{padding:9px 6px}}
'''

def esc(value):
    return html.escape(str(value if value is not None else ''))

def pretty(value):
    return '<pre>' + esc(json.dumps(value,indent=2)) + '</pre>'

def page(title,body):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · Bellhaven Review</title><style>{CSS}</style></head><body><header><a href="/"><strong>Bellhaven / CRM Review</strong></a><p>Website evidence → reviewed decisions → verified CRM changes</p></header><main>{body}</main></body></html>'

def index(conn):
    rows = conn.execute('SELECT * FROM proposals ORDER BY CASE state WHEN \'pending\' THEN 0 WHEN \'failed\' THEN 1 ELSE 2 END,id').fetchall()
    run = conn.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 1').fetchone()
    snapshot = json.loads(run['snapshot']) if run else (json.loads((ROOT/'data'/'locations.json').read_text()) if (ROOT/'data'/'locations.json').exists() else {})
    counts = {state:sum(r['state']==state for r in rows) for state in ('pending','applied','rejected','failed')}
    body = '<div class="eyebrow">Reconciliation workspace</div><h1>Make every account count.</h1><p class="muted">Review the evidence and the exact change. Only an approval can write to the CRM.</p>'
    body += '<div class="stats">' + ''.join(f'<div class="stat"><b>{value}</b><span>{label}</span></div>' for label,value in [('Website facilities',len(snapshot.get('locations',[]))),('Awaiting review',counts['pending']),('Applied & verified',counts['applied']),('Rejected',counts['rejected'])]) + '</div>'
    if not run:
        body += '<div class="warning">Website evidence is available. Run the pipeline with a candidate token to generate CRM proposals.</div>'
    body += '<div class="panel"><h2>Proposed changes & decision history</h2><div class="table-wrap"><table><thead><tr><th>Facility / account</th><th>Finding</th><th>Decision</th><th></th></tr></thead><tbody>'
    for row in rows:
        body += f'<tr><td><strong>{esc(row["title"])}</strong><br><span class="muted">Proposal {row["id"]}</span></td><td>{esc(row["kind"].replace("_"," "))}</td><td><span class="badge">{esc(row["state"])}</span></td><td><a href="/proposal/{row["id"]}">Review evidence →</a></td></tr>'
    body += '</tbody></table></div></div>'
    if run:
        matches = conn.execute('SELECT * FROM matches WHERE run_id=?',(run['id'],)).fetchall()
        body += '<div class="panel" style="margin-top:20px"><h2>Complete website coverage</h2><p class="muted">Includes matches that need no changes. Latest run: '+esc(run['at'])+'</p><div class="table-wrap"><table><tr><th>Website location</th><th>CRM account</th><th>Classification</th></tr>'
        for match in matches:
            loc=json.loads(match['location'])
            body+=f'<tr><td>{esc(loc["name"])}</td><td><code>{esc(match["account_id"] or "New account proposed")}</code></td><td>{esc(match["classification"].replace("_"," "))}</td></tr>'
        body += '</table></div></div>'
    return page('Queue',body)

def detail(conn,proposal_id,csrf,message=''):
    row=conn.execute('SELECT * FROM proposals WHERE id=?',(proposal_id,)).fetchone()
    if not row:
        return None
    evidence,actions=json.loads(row['evidence']),json.loads(row['plan'])
    loc=evidence.get('website')
    body=f'<a href="/">← All proposals</a><div class="eyebrow" style="margin-top:20px">Proposal {proposal_id} / {esc(row["kind"].replace("_"," "))}</div><h1>{esc(row["title"])}</h1><span class="badge">{esc(row["state"])}</span>'
    if message:
        body+='<p class="error">'+esc(message)+'</p>'
    if row['error']:
        body+='<p class="error">'+esc(row['error'])+'</p>'
    if row['kind']=='chow_required':
        body+='<div class="warning" style="margin-top:20px"><strong>Billing protection: preserve the old account.</strong><br>Revenue history and outstanding AR are both positive. Create the correct-parent successor, then set only the old account’s CHOW pointer. Do not change its parent, financial values, name, status, or other business fields.</div>'
    if row['kind']=='no_longer_listed':
        body+='<div class="warning" style="margin-top:20px">Website absence is evidence for investigation. This proposal marks Needs Review and explains the absence. It preserves ownership and billing; it does not claim the facility closed.</div>'
    body+='<div class="cols"><section class="panel"><h2>Website evidence</h2>'
    if loc:
        body+=f'<strong>{esc(loc["name"])}</strong><p>{esc(loc["street"])}<br>{esc(loc["city"])}, {esc(loc["state"])} {esc(loc["zip"])}</p><p>{esc(" · ".join(loc["care_offerings"]))}</p><a href="{esc(loc["source_url"])}" target="_blank" rel="noopener">Open source page ↗</a><p class="muted">Collected {esc(evidence.get("fetched_at"))}</p>'
    else:
        body+=f'<p>Absent from the complete crawl of {evidence.get("website_count")} facilities.</p><p class="muted">Collected {esc(evidence.get("fetched_at"))}</p><details><summary>Pages checked</summary>{pretty(evidence.get("pages",[]))}</details>'
    body+='</section><section class="panel"><h2>CRM evidence</h2>'
    candidates=evidence.get('candidates',[])
    if not candidates:
        body+=pretty(evidence['account']) if evidence.get('account') else '<p>No candidate met the identity threshold in the complete CRM snapshot.</p>'
    for candidate in candidates:
        account=candidate['account']
        body+=f'<h3>{esc(account["name"])}</h3><p class="muted">Evidence score {candidate["score"]}/100 · {esc(account["id"])}</p><p>{esc("; ".join(candidate["reasons"]))}</p>{pretty(account)}'
    body+='</section></div><section class="panel"><h2>Exact approved operations</h2>'
    if not actions:
        body+='<p>Investigation is required before an executable change can be proposed.</p>'
    for i,action in enumerate(actions,1):
        body+=f'<h3>{i}. {"Create a new account" if action["method"]=="POST" else "Update account "+esc(action["account_id"])}</h3><div class="table-wrap"><table><tr><th>Field</th><th>Before</th><th>After</th></tr>'
        for key,value in action['payload'].items():
            before=action.get('before',{}).get(key,'— new account —')
            if value=='$created_id': value='ID returned by the approved create above'
            body+=f'<tr><td><code>{esc(key)}</code></td><td>{esc(before)}</td><td><strong>{esc(value)}</strong></td></tr>'
        body+='</table></div>'
    body+='</section>'
    if row['state']=='pending':
        body+=f'<form action="/proposal/{proposal_id}/decision" method="post"><input type="hidden" name="csrf" value="{csrf}"><div class="actions"><div><label for="reviewer">Reviewer name</label><input id="reviewer" name="reviewer" required placeholder="Your name"></div><button name="decision" value="approve" {"disabled" if not actions else ""}>Approve and apply</button><button class="secondary" name="decision" value="reject">Reject change</button></div></form><p class="muted">Approval is recorded before execution. Current CRM values and billing facts are checked again, and every operation is read back to verify it.</p>'
    else:
        body+=f'<p>Decision recorded for <strong>{esc(row["reviewer"])}</strong> at {esc(row["decided_at"])}.</p>'
        if row['state'] in ('failed','approved','applying'):
            body+=f'<form action="/proposal/{proposal_id}/retry" method="post"><input type="hidden" name="csrf" value="{csrf}"><button>Resume approved change safely</button></form>'
        if row['result']:
            body+='<details><summary>Verified CRM results</summary>'+pretty(json.loads(row['result']))+'</details>'
    body+='<details style="margin-top:24px"><summary>Full evidence and decision fingerprint</summary><code>'+esc(row['fingerprint'])+'</code>'+pretty(evidence)+'</details>'
    return page(row['title'],body)

def serve(port=8765):
    csrf=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def respond(self,body,status=200,content_type='text/html; charset=utf-8'):
            data=body.encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(data)
        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
        def do_GET(self):
            if not self.allowed(): return self.respond('Invalid host',403)
            conn=database()
            try:
                path=urllib.parse.urlparse(self.path).path
                if path=='/': return self.respond(index(conn))
                if path=='/api/state':
                    rows=[dict(r) for r in conn.execute('SELECT id,title,kind,state,reviewer,decided_at,error FROM proposals ORDER BY id')]
                    return self.respond(json.dumps(rows),content_type='application/json')
                if path.startswith('/proposal/') and path.rsplit('/',1)[1].isdigit():
                    body=detail(conn,int(path.rsplit('/',1)[1]),csrf)
                    return self.respond(body or 'Not found',200 if body else 404)
                self.respond('Not found',404)
            finally:
                conn.close()
        def do_POST(self):
            if not self.allowed(): return self.respond('Invalid host',403)
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                return self.respond('Invalid origin',403)
            length=int(self.headers.get('Content-Length','0'))
            if length > 4096: return self.respond('Request too large',413)
            form=urllib.parse.parse_qs(self.rfile.read(length).decode())
            if not secrets.compare_digest(form.get('csrf',[''])[0],csrf):
                return self.respond('Invalid approval session',403)
            parts=urllib.parse.urlparse(self.path).path.strip('/').split('/')
            if len(parts)!=3 or parts[0]!='proposal' or not parts[1].isdigit() or parts[2] not in ('decision','retry'):
                return self.respond('Not found',404)
            proposal_id=int(parts[1]); conn=database()
            try:
                if parts[2]=='decision':
                    decision=form.get('decision',[''])[0]
                    decide(conn,proposal_id,decision,form.get('reviewer',[''])[0],CRM() if decision=='approve' else None)
                else:
                    execute(conn,proposal_id,CRM())
                self.send_response(303); self.send_header('Location',f'/proposal/{proposal_id}'); self.end_headers()
            except Exception as exc:
                self.respond(detail(conn,proposal_id,csrf,str(exc)) or esc(exc),409)
            finally:
                conn.close()
    print(f'Review app: http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
