import json
from .core import now, process_lock, requires_chow
from .matching import identity_score

def equals_payload(account, payload):
    return all(account.get(k) == v for k,v in payload.items())

def resolved(action, created_id):
    payload = dict(action['payload'])
    for key,value in payload.items():
        if value == '$created_id':
            if not created_id:
                raise RuntimeError('The successor account id has not been recorded')
            payload[key] = created_id
    return payload

def check_precondition(action, current):
    before = action['before']
    keys = set(action['payload']) | {'parent_id'}
    if action.get('guard_parent'):
        keys |= {'lifetime_revenue','outstanding_ar'}
    if 'chow_current_account' in action['payload']:
        keys |= set(before) - {'updated_at','modified_at'}
    changed = [k for k in keys if current.get(k) != before.get(k)]
    if changed:
        raise RuntimeError('CRM changed since review: ' + ', '.join(sorted(changed)) + '. Re-run and review updated evidence.')
    if 'parent_id' in action['payload'] and action['payload']['parent_id'] != current.get('parent_id'):
        if requires_chow(current):
            raise RuntimeError('Billing SOP blocks direct re-parenting: revenue history and outstanding AR')
    if 'chow_current_account' in action['payload'] and not requires_chow(current):
        raise RuntimeError('Billing facts changed: this CHOW plan needs a fresh review')

def execute(conn, proposal_id, crm, lock_path=None):
    with process_lock(lock_path):
        row = conn.execute('SELECT * FROM proposals WHERE id=?',(proposal_id,)).fetchone()
        if not row or row['state'] not in ('approved','applying','failed') or not row['reviewer'] or not row['decided_at']:
            raise ValueError('A recorded approval is required before CRM writes')
        actions = json.loads(row['plan'])
        if not actions:
            raise ValueError('This item requires investigation; there is no executable change to approve')
        conn.execute("UPDATE proposals SET state='applying',error=NULL WHERE id=?",(proposal_id,))
        conn.commit()
        created_id, outcomes = None, []
        try:
            # Validate all existing accounts before the first mutation.
            for step,action in enumerate(actions):
                operation = conn.execute('SELECT * FROM operations WHERE proposal_id=? AND step=?',(proposal_id,step)).fetchone()
                if action['method'] == 'POST':
                    if operation and operation['state'] == 'done':
                        created_id = json.loads(operation['result'])['id']
                    continue
                if operation and operation['state'] == 'done':
                    continue
                current = crm.get(action['account_id'])
                payload = resolved(action,created_id) if created_id or '$created_id' not in action['payload'].values() else None
                if operation and payload and equals_payload(current,payload):
                    continue
                check_precondition(action,current)
            for step,action in enumerate(actions):
                operation = conn.execute('SELECT * FROM operations WHERE proposal_id=? AND step=?',(proposal_id,step)).fetchone()
                if operation and operation['state'] == 'done':
                    result = json.loads(operation['result'])
                    if action['method'] == 'POST':
                        created_id = result['id']
                    outcomes.append(result)
                    continue
                payload = resolved(action,created_id)
                if action['method'] == 'POST':
                    marker = 'Reconciliation operation: ' + row['fingerprint']
                    live_accounts = crm.list_accounts()
                    existing = [a for a in live_accounts if marker in str(a.get('note') or '')]
                    if len(existing) > 1:
                        raise RuntimeError('Multiple accounts carry this operation marker; manual investigation required')
                    if existing:
                        result = existing[0]
                        if not equals_payload(result,payload):
                            raise RuntimeError('Recovered create differs from the approved payload')
                    elif operation:
                        raise RuntimeError('Previous create outcome is uncertain. No automatic POST retry; inspect CRM before recovery.')
                    else:
                        location = json.loads(row['evidence']).get('website')
                        if location:
                            conflicts = [a for a in live_accounts if identity_score(location,a)[0] >= 88 and str(a['id']) != action.get('chow_old_id') and not a.get('duplicate_of_account') and not a.get('chow_current_account')]
                            if conflicts:
                                raise RuntimeError('A matching account appeared since review; refresh evidence instead of creating another')
                        # Commit before transmission, so a timeout cannot cause a
                        # repeated create on the next run or approval retry.
                        conn.execute('INSERT INTO operations VALUES(?,?,?,?)',(proposal_id,step,'started','{}'))
                        conn.commit()
                        response = crm.call('accounts','POST',payload)
                        result = response.get('account',response) if isinstance(response,dict) else response
                        if isinstance(result,dict):
                            result = crm.normalize_account(result)
                        if not isinstance(result,dict) or not result.get('id'):
                            raise RuntimeError('Create returned no account id; outcome is uncertain')
                        result = crm.get(result['id'])
                    created_id = result['id']
                    if not equals_payload(result,payload):
                        raise RuntimeError('Created account failed read-back verification')
                else:
                    current = crm.get(action['account_id'])
                    if not (operation and equals_payload(current,payload)):
                        check_precondition(action,current)
                        conn.execute('INSERT OR REPLACE INTO operations VALUES(?,?,?,?)',(proposal_id,step,'started','{}'))
                        conn.commit()
                        crm.call('accounts/' + action['account_id'],'PATCH',payload)
                    result = crm.get(action['account_id'])
                    if not equals_payload(result,payload):
                        raise RuntimeError('Updated account failed read-back verification')
                    if 'chow_current_account' in payload:
                        before = action['before']
                        changed = [k for k,v in before.items() if k not in ('chow_current_account','updated_at','modified_at') and result.get(k) != v]
                        if changed:
                            raise RuntimeError('Old CHOW account was unexpectedly modified: ' + ', '.join(changed))
                conn.execute('INSERT OR REPLACE INTO operations VALUES(?,?,?,?)',(proposal_id,step,'done',json.dumps(result)))
                conn.commit()
                outcomes.append(result)
            conn.execute("UPDATE proposals SET state='applied',result=?,error=NULL WHERE id=?",(json.dumps(outcomes),proposal_id))
            conn.commit()
            return outcomes
        except Exception as exc:
            conn.execute("UPDATE proposals SET state='failed',error=? WHERE id=?",(str(exc),proposal_id))
            conn.commit()
            raise

def decide(conn, proposal_id, decision, reviewer, crm=None, lock_path=None, reason=''):
    if decision not in ('approve','reject') or not reviewer.strip():
        raise ValueError('Provide a valid decision and reviewer')
    row = conn.execute('SELECT * FROM proposals WHERE id=?',(proposal_id,)).fetchone()
    if not row or row['state'] != 'pending':
        raise ValueError('Only pending proposals can receive a new decision')
    if decision == 'approve' and not json.loads(row['plan']):
        raise ValueError('Investigate ambiguous identity/billing data before proposing a concrete change')
    state = 'approved' if decision == 'approve' else 'rejected'
    changed = conn.execute("UPDATE proposals SET state=?,reviewer=?,decided_at=?,decision_reason=? WHERE id=? AND state='pending'",(state,reviewer.strip(),now(),reason.strip(),proposal_id)).rowcount
    conn.commit()
    if changed != 1:
        raise RuntimeError('This proposal was already decided')
    if decision == 'approve':
        return execute(conn,proposal_id,crm,lock_path)
