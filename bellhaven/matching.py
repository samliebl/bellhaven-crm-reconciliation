from difflib import SequenceMatcher
import json
import os
from .core import billing_values, digest, location_fields, normalize, now, requires_chow, street_key

def identity_score(location, account):
    fields = location_fields(account)
    same_city = normalize(fields['city']) == normalize(location['city'])
    same_state = normalize(fields['state']) == normalize(location['state'])
    same_zip = str(fields['zip'])[:5] == location['zip'][:5]
    same_street = bool(fields['street']) and street_key(fields['street']) == street_key(location['street'])
    similarity = SequenceMatcher(None, normalize(account.get('name')), normalize(location['name'])).ratio()
    reasons = []
    if same_street and same_city and same_state and same_zip:
        return 100, ['Street, city, state, and ZIP agree after address normalization']
    if same_street and same_city and same_state:
        return 94, ['Street, city, and state agree; ZIP differs or is absent']
    if similarity == 1 and same_city and same_state:
        return 88, ['Exact facility name and city/state; address needs reviewer verification']
    if same_city and same_state and similarity >= .75:
        return 70 + round(similarity * 10), ['Similar name in the same city/state; identity is uncertain']
    if same_street and (same_zip or same_city):
        return 75, ['Street agrees with locality, but other identity fields conflict']
    return 0, reasons

def find_parent(accounts):
    configured = os.environ.get('CRM_PARENT_ID')
    if configured:
        candidates = [a for a in accounts if str(a['id']) == configured]
    else:
        candidates = [a for a in accounts if normalize(a.get('name')) == 'bellhaven senior living' and not a.get('parent_id')]
        if not candidates:
            candidates = [a for a in accounts if not a.get('parent_id') and normalize(a.get('name')) in ('bellhaven', 'bellhaven senior living parent', 'bellhaven senior living corporate')]
    if len(candidates) != 1:
        raise ValueError('Cannot uniquely identify Bellhaven parent. Set CRM_PARENT_ID after reviewing the CRM snapshot.')
    return candidates[0]

def canonical_payload(location, account=None):
    # The live account schema is inspected before any approvals. Environment
    # overrides support CRM copies using different address/care property names.
    field_map = json.loads(os.environ.get('CRM_FIELD_MAP', '{}'))
    payload = {'name': location['name']}
    for key in ('street', 'city', 'state', 'zip', 'care_offerings'):
        target = field_map.get(key, key)
        if account is not None and key == 'street' and target not in account:
            target = 'address' if isinstance(account.get('address'), str) else target
        if account is not None and key == 'zip' and target not in account and 'postal_code' in account:
            target = 'postal_code'
        value = location[key]
        if key == 'care_offerings' and account is not None and isinstance(account.get(target), str):
            value = '; '.join(value)
        payload[target] = value
    if account is not None and isinstance(account.get('address'), dict):
        payload.pop(field_map.get('street', 'street'), None)
        for key in ('city', 'state', 'zip'):
            payload.pop(field_map.get(key, key), None)
        old = account['address']
        payload['address'] = {**old, 'street' if 'street' in old else 'line1':location['street'], 'city':location['city'], 'state':location['state'], 'postal_code' if 'postal_code' in old else 'zip':location['zip']}
    return payload

def note_with(account, text):
    old = str(account.get('note') or '').strip()
    return old if text in old else (old + '\n' + text).strip()

def patch_action(account, payload, guard_parent=False):
    return {'method':'PATCH', 'account_id':str(account['id']), 'payload':payload, 'before':account, 'guard_parent':guard_parent}

def changes(account, payload):
    return {k:v for k,v in payload.items() if account.get(k) != v and not (k == 'care_offerings' and isinstance(account.get(k), list) and sorted(account[k]) == sorted(v))}

def reconcile(conn, snapshot, accounts, parent):
    parent_id = str(parent['id'])
    cursor = conn.execute('INSERT INTO runs(at,snapshot,parent_id) VALUES(?,?,?)', (now(), json.dumps(snapshot), parent_id))
    run_id = cursor.lastrowid
    used, reserved, proposed = set(), set(), []
    active = [a for a in accounts if str(a['id']) != parent_id and not a.get('duplicate_of_account') and not a.get('chow_current_account')]
    address_counts = {}
    for loc in snapshot['locations']:
        key = (street_key(loc['street']), normalize(loc['city']), normalize(loc['state']))
        address_counts[key] = address_counts.get(key, 0) + 1

    def add(title, kind, actions, evidence, location=None):
        semantic = {'kind':kind, 'location':location.get('source_url') if location else None,
                    'actions':[{k:v for k,v in a.items() if k not in ('before', 'guard_parent')} for a in actions]}
        fingerprint = digest(semantic)
        conn.execute('INSERT OR IGNORE INTO proposals(fingerprint,run_id,title,kind,plan,evidence) VALUES(?,?,?,?,?,?)', (fingerprint,run_id,title,kind,json.dumps(actions),json.dumps(evidence)))
        proposed.append(fingerprint)

    for loc in snapshot['locations']:
        candidates = sorted([(score, str(a['id']), a, reasons) for a in active for score,reasons in [identity_score(loc,a)] if score >= 70], key=lambda x:(-x[0],x[1]))
        evidence = {'website':loc, 'fetched_at':snapshot['fetched_at'], 'candidates':[{'score':s,'account':a,'reasons':r} for s,_,a,r in candidates], 'parent':parent}
        if not candidates:
            payload = {**canonical_payload(loc), 'parent_id':parent['id'], 'status':'Active', 'note':f"Created after website reconciliation: {loc['source_url']}"}
            add(loc['name'], 'missing_account', [{'method':'POST','payload':payload,'source_url':loc['source_url']}], evidence, loc)
            conn.execute('INSERT INTO matches VALUES(?,?,?,?,?)',(run_id,json.dumps(loc),None,'missing_account',json.dumps(evidence)))
            continue
        best_score = candidates[0][0]
        address_key = (street_key(loc['street']), normalize(loc['city']), normalize(loc['state']))
        strong = [c for c in candidates if c[0] >= 94]
        ambiguous = best_score < 88 or address_counts[address_key] > 1 or any(c[1] in used for c in strong or candidates[:1])
        # Duplicate claims require precise address identity and sufficiently
        # similar names; same-address businesses are otherwise left for review.
        if len(strong) > 1 and any(SequenceMatcher(None,normalize(c[2].get('name')),normalize(loc['name'])).ratio() < .55 for c in strong):
            ambiguous = True
        if not strong and len(candidates) > 1 and candidates[0][0]-candidates[1][0] < 8:
            ambiguous = True
        if ambiguous:
            reserved.update(c[1] for c in candidates)
            add(loc['name'], 'ambiguous_match', [], evidence, loc)
            conn.execute('INSERT INTO matches VALUES(?,?,?,?,?)',(run_id,json.dumps(loc),None,'ambiguous_match',json.dumps(evidence)))
            continue
        group = strong or candidates[:1]
        # Prefer an existing CHOW target and then a billing-bearing survivor;
        # avoid inactivating a debtor merely to retain a zero-revenue duplicate.
        chow_targets = {str(a.get('chow_current_account')) for a in accounts if a.get('chow_current_account')}
        def survivor_rank(candidate):
            a = candidate[2]
            try:
                revenue,ar = billing_values(a)
            except ValueError:
                revenue=ar=0
            return (candidate[1] in chow_targets, ar > 0, revenue > 0, str(a.get('parent_id')) == parent_id, normalize(a.get('name'))==normalize(loc['name']), a.get('status')=='Active', candidate[0], candidate[1])
        winner = max(group, key=survivor_rank)[2]
        used.update(c[1] for c in group)
        payload = canonical_payload(loc, winner)
        payload['status'] = 'Active'
        actions, kind = [], 'confident_match'
        moving = str(winner.get('parent_id') or '') != parent_id
        if moving:
            try:
                chow = requires_chow(winner)
            except ValueError as exc:
                evidence['blocked_reason'] = str(exc)
                add(loc['name'], 'billing_data_missing', [], evidence, loc)
                conn.execute('INSERT INTO matches VALUES(?,?,?,?,?)',(run_id,json.dumps(loc),str(winner['id']),'billing_data_missing',json.dumps(evidence)))
                continue
            evidence['billing_rule'] = {'lifetime_revenue':winner['lifetime_revenue'],'outstanding_ar':winner['outstanding_ar'],'requires_chow':chow}
            if chow:
                # The old account receives ONLY the CHOW pointer, after create.
                new_payload = {**canonical_payload(loc), 'parent_id':parent['id'], 'status':'Active', 'note':f"CHOW successor of account {winner['id']}; source: {loc['source_url']}"}
                actions = [{'method':'POST','payload':new_payload,'source_url':loc['source_url'],'chow_old_id':str(winner['id'])},patch_action(winner,{'chow_current_account':'$created_id'},True)]
                kind = 'chow_required'
            else:
                payload['parent_id'] = parent['id']
                actions = [patch_action(winner, changes(winner,payload),True)]
                kind = 'wrong_parent'
        else:
            delta = changes(winner,payload)
            if delta:
                actions = [patch_action(winner,delta)]
                kind = 'needs_fix'
        for candidate in group:
            loser = candidate[2]
            if loser['id'] == winner['id']:
                continue
            text = f"Duplicate of account {winner['id']} based on website name/address: {loc['source_url']}. Retained for audit; no merge or deletion."
            losing_payload = {'status':'Inactive','duplicate_of_account':'$created_id' if kind == 'chow_required' else winner['id'],'note':note_with(loser,text)}
            actions.append(patch_action(loser,losing_payload))
        if len(group) > 1:
            evidence['duplicate_survivor'] = winner['id']
            if kind == 'confident_match':
                kind = 'duplicate_accounts'
        if actions:
            add(loc['name'],kind,actions,evidence,loc)
        conn.execute('INSERT INTO matches VALUES(?,?,?,?,?)',(run_id,json.dumps(loc),str(winner['id']),kind,json.dumps(evidence)))

    for account in accounts:
        account_id = str(account['id'])
        if account_id in used or account_id in reserved or str(account.get('parent_id')) != parent_id:
            continue
        if account.get('duplicate_of_account') or account.get('chow_current_account'):
            continue
        text = 'Not found in the complete Bellhaven website crawl. Ownership/closure is unconfirmed; retain parent and billing data pending investigation.'
        delta = changes(account, {'status':'Needs Review','note':note_with(account,text)})
        if delta:
            add(account.get('name', account_id), 'no_longer_listed', [patch_action(account,delta)], {'account':account,'website_count':len(snapshot['locations']),'directory_count':snapshot['directory_count'],'pages':snapshot['pages'],'fetched_at':snapshot['fetched_at']})
    conn.commit()
    return run_id
