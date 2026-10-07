"""Read-only end-state verification independent of proposal execution."""
import json
from collections import Counter
from .core import ROOT, normalize, now, street_key

def verify(conn, accounts, before, snapshot):
    current={str(a['id']):a for a in accounts}
    original={str(a['id']):a for a in before}
    parent=conn.execute('SELECT parent_id FROM runs ORDER BY id DESC LIMIT 1').fetchone()['parent_id']
    checks,exceptions,coverage = [],[],[]
    def check(label, passed):
        checks.append({'check':label,'passed':bool(passed)})
    check('Every original account remains present',set(original)<=set(current))
    check('Original lifetime revenue and outstanding AR are unchanged',all(i in current and all(a.get(k)==current[i].get(k) for k in ('lifetime_revenue','outstanding_ar')) for i,a in original.items()))
    rows=conn.execute('SELECT * FROM proposals ORDER BY id').fetchall()
    allowed,posts,chows={},0,[]
    for row in rows:
        actions=json.loads(row['plan'])
        if row['state']=='applied':
            created=None
            for step,action in enumerate(actions):
                operation=conn.execute('SELECT * FROM operations WHERE proposal_id=? AND step=?',(row['id'],step)).fetchone()
                check(f'Proposal {row["id"]} step {step+1} has a completed journal record',operation and operation['state']=='done')
                if not operation: continue
                result=json.loads(operation['result'])
                if action['method']=='POST':
                    created=result['id']; posts+=1; target=current.get(str(created),{})
                else:
                    target=current.get(action['account_id'],{})
                    allowed.setdefault(action['account_id'],set()).update(action['payload'])
                    if 'parent_id' in action['payload']: allowed[action['account_id']].add('parent_name')
                expected={k:created if v=='$created_id' else v for k,v in action['payload'].items()}
                check(f'Proposal {row["id"]} step {step+1} matches the live CRM',all(target.get(k)==v for k,v in expected.items()))
                if 'chow_current_account' in action['payload']:
                    old=action['before']
                    check(f'CHOW old account {action["account_id"]} preserved except pointer and server timestamp',all(target.get(k)==v for k,v in old.items() if k not in ('chow_current_account','updated_at','modified_at')))
                    chows.append({'old_account':action['account_id'],'current_account':created,'old_parent':old['parent_id'],'old_fields_preserved':True})
        elif row['state']=='rejected':
            for action in actions:
                if action['method']=='PATCH':
                    check(f'Rejected proposal {row["id"]} left its proposed fields untouched',all(current[action['account_id']].get(k)==action['before'].get(k) for k in action['payload']))
            exceptions.append({'proposal_id':row['id'],'title':row['title'],'reason':row['reviewer']})
    check('Only approved creates added accounts',len(current)-len(original)==posts)
    check('No unapproved business-field edits',all(not ({k for k,v in a.items() if k not in ('updated_at','modified_at') and current.get(i,{}).get(k)!=v} - allowed.get(i,set())) for i,a in original.items()))
    for loc in snapshot['locations']:
        candidates=[a for a in accounts if str(a.get('parent_id'))==parent and a.get('status')=='Active' and not a.get('duplicate_of_account') and normalize(a.get('name'))==normalize(loc['name']) and normalize(a.get('billing_city'))==normalize(loc['city']) and normalize(a.get('billing_state'))==normalize(loc['state'])]
        check(f'One current Active Bellhaven account: {loc["name"]}',len(candidates)==1)
        if len(candidates)==1:
            a=candidates[0]
            coverage.append({**loc,'crm_account_id':a['id'],'billing_street':a['billing_street'],'billing_address_differs':street_key(a['billing_street'])!=street_key(loc['street'])})
    states=dict(Counter(r['state'] for r in rows))
    check('No pending, approved, applying, or failed proposals',not any(states.get(s) for s in ('pending','approved','applying','failed')))
    report={'verified_at':now(),'passed':all(c['passed'] for c in checks),'website_facilities':len(snapshot['locations']),'crm_before':len(before),'crm_after':len(accounts),'new_accounts':posts,'decision_counts':states,'chow_accounts':chows,'reviewed_exceptions':exceptions,'coverage':coverage,'checks':checks}
    return report
