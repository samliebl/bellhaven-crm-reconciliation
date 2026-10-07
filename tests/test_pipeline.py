import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bellhaven.core import CRM, database, parse_location, requires_chow, scrape, street_key
from bellhaven.execution import decide, execute
from bellhaven.matching import find_parent, identity_score, reconcile

LOC={'name':'Bellhaven of Example','street':'10 North Main Street','city':'Example','state':'OH','zip':'43000','care_offerings':['Assisted Living'],'source_url':'https://example.test/communities/example'}
PARENT={'id':'parent','account_id':'parent','name':'Bellhaven Senior Living (Parent Account)','parent_id':''}

def account(account_id='a', **values):
    return {'id':account_id,'account_id':account_id,'name':LOC['name'],'parent_id':'parent','billing_street':'10 N Main St','billing_city':'Example','billing_state':'OH','billing_zip':'43000','care_type':'Assisted Living','status':'Active','lifetime_revenue':0,'outstanding_ar':0,'chow_current_account':'','duplicate_of_account':'','note':'',**values}

class FakeCRM:
    normalize_account=staticmethod(CRM.normalize_account)
    def __init__(self,accounts):
        self.accounts={a['id']:copy.deepcopy(a) for a in accounts}
        self.writes=[]; self.timeout_create=False; self.timeout_patch=False
    def list_accounts(self): return copy.deepcopy(list(self.accounts.values()))
    def get(self,identifier): return copy.deepcopy(self.accounts[identifier])
    def call(self,path,method='GET',payload=None):
        self.writes.append((method,path,copy.deepcopy(payload)))
        if method=='POST':
            identifier='new'+str(len(self.accounts))
            result=account(identifier,**payload)
            self.accounts[identifier]=result
            if self.timeout_create:
                self.timeout_create=False; raise TimeoutError('simulated lost response')
            return copy.deepcopy(result)
        identifier=path.split('/')[-1]
        self.accounts[identifier].update(payload)
        if self.timeout_patch:
            self.timeout_patch=False; raise TimeoutError('simulated lost response')
        return self.get(identifier)

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.conn=database(Path(self.tmp.name)/'review.db'); self.lock=Path(self.tmp.name)/'lock'
    def tearDown(self): self.conn.close(); self.tmp.cleanup()
    def generate(self,accounts,locations=None):
        snapshot={'locations':locations if locations is not None else [LOC], 'pages':['https://example.test/communities'], 'directory_count':len(locations if locations is not None else [LOC]),'fetched_at':'2026-10-07'}
        return reconcile(self.conn,snapshot,accounts,PARENT)
    def proposal(self): return self.conn.execute('SELECT * FROM proposals ORDER BY id DESC LIMIT 1').fetchone()
    def test_address_normalization(self):
        self.assertEqual(street_key('4850 Northwest Sylvania Avenue'),street_key('4850 NW Sylvania Ave'))
        self.assertEqual(street_key('3313 Wilmington Pk'),street_key('3313 Wilmington Pike'))
    def test_parent_detection(self): self.assertEqual(find_parent([PARENT])['id'],'parent')
    def test_billing_truth_table(self):
        for revenue,ar,expected in [(0,0,False),(100,0,False),(0,20,False),(100,20,True)]:
            self.assertEqual(requires_chow(account(lifetime_revenue=revenue,outstanding_ar=ar)),expected)
        bad=account(); del bad['outstanding_ar']
        with self.assertRaises(ValueError): requires_chow(bad)
    def test_no_false_same_name_match(self):
        self.assertEqual(identity_score(LOC,account(billing_city='Elsewhere',billing_state='CO'))[0],0)
    def test_confident_match_no_changes(self):
        self.generate([PARENT,account()]); self.assertIsNone(self.proposal())
    def test_reparent_rechecks_billing(self):
        old=account(parent_id='other',lifetime_revenue=100,outstanding_ar=0)
        self.generate([PARENT,old]); crm=FakeCRM([PARENT,old]); crm.accounts['a']['outstanding_ar']=50
        with self.assertRaises(RuntimeError): decide(self.conn,self.proposal()['id'],'approve','Test reviewer',crm,self.lock)
        self.assertEqual(crm.writes,[])
    def test_chow_preserves_old_except_pointer(self):
        old=account(parent_id='other',lifetime_revenue=100,outstanding_ar=50)
        self.generate([PARENT,old]); crm=FakeCRM([PARENT,old]); decide(self.conn,self.proposal()['id'],'approve','Test reviewer',crm,self.lock)
        self.assertEqual([w[0] for w in crm.writes],['POST','PATCH'])
        current=crm.get('a'); successor=current.pop('chow_current_account'); expected=copy.deepcopy(old); expected.pop('chow_current_account')
        self.assertEqual(current,expected); self.assertEqual(crm.get(successor)['parent_id'],'parent')
        self.generate(crm.list_accounts()); self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],1)
    def test_rejected_not_reproposed(self):
        old=account(name='Old name'); self.generate([PARENT,old]); decide(self.conn,self.proposal()['id'],'reject','Test reviewer')
        self.generate([PARENT,old]); self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],1)
    def test_applied_fix_not_reproposed(self):
        old=account(name='Old name'); self.generate([PARENT,old]); crm=FakeCRM([PARENT,old]); decide(self.conn,self.proposal()['id'],'approve','Test reviewer',crm,self.lock)
        self.generate(crm.list_accounts()); self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],1)
    def test_writes_require_approval(self):
        old=account(name='Old name'); self.generate([PARENT,old]); crm=FakeCRM([PARENT,old])
        with self.assertRaises(ValueError): execute(self.conn,self.proposal()['id'],crm,self.lock)
        self.assertEqual(crm.writes,[])
    def test_duplicate_link_and_inactive(self):
        self.generate([PARENT,account('a'),account('b')]); crm=FakeCRM([PARENT,account('a'),account('b')]); decide(self.conn,self.proposal()['id'],'approve','Test reviewer',crm,self.lock)
        losers=[a for a in crm.list_accounts() if a.get('duplicate_of_account')]
        self.assertEqual(len(losers),1); self.assertEqual(losers[0]['status'],'Inactive')
    def test_duplicate_survivor_prefers_website_phone(self):
        loc={**LOC,'phone':'(555) 123-4567'}
        a=account('a',phone='5551234567'); b=account('b',phone='5550000000')
        self.generate([PARENT,a,b],[loc]); action=json.loads(self.proposal()['plan'])[0]
        self.assertEqual(action['account_id'],'b'); self.assertEqual(action['payload']['duplicate_of_account'],'a')
    def test_absent_needs_review_preserves_parent(self):
        old=account(); self.generate([PARENT,old],[]); crm=FakeCRM([PARENT,old]); decide(self.conn,self.proposal()['id'],'approve','Test reviewer',crm,self.lock)
        self.assertEqual(crm.get('a')['status'],'Needs Review'); self.assertEqual(crm.get('a')['parent_id'],'parent')
    def test_create_lost_response_recovers_without_second_post(self):
        self.generate([PARENT]); crm=FakeCRM([PARENT]); crm.timeout_create=True; identifier=self.proposal()['id']
        with self.assertRaises(TimeoutError): decide(self.conn,identifier,'approve','Test reviewer',crm,self.lock)
        self.generate(crm.list_accounts())
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],1)
        execute(self.conn,identifier,crm,self.lock)
        self.assertEqual(len([w for w in crm.writes if w[0]=='POST']),1)
        self.assertEqual(self.proposal()['state'],'applied')
    def test_patch_lost_response_recovers_without_second_patch(self):
        old=account(name='Old name'); self.generate([PARENT,old]); crm=FakeCRM([PARENT,old]); crm.timeout_patch=True; identifier=self.proposal()['id']
        with self.assertRaises(TimeoutError): decide(self.conn,identifier,'approve','Test reviewer',crm,self.lock)
        execute(self.conn,identifier,crm,self.lock); self.assertEqual(len(crm.writes),1)
    def test_unknown_create_outcome_is_not_retried(self):
        self.generate([PARENT]); identifier=self.proposal()['id']; self.conn.execute("UPDATE proposals SET state='failed',reviewer='Reviewer',decided_at='today' WHERE id=?",(identifier,)); self.conn.execute("INSERT INTO operations VALUES(?,0,'started','{}')",(identifier,)); self.conn.commit(); crm=FakeCRM([PARENT])
        with self.assertRaisesRegex(RuntimeError,'uncertain'): execute(self.conn,identifier,crm,self.lock)
        self.assertEqual(crm.writes,[])
    def test_remote_match_appeared_blocks_create(self):
        self.generate([PARENT]); crm=FakeCRM([PARENT,account()])
        with self.assertRaisesRegex(RuntimeError,'appeared'): decide(self.conn,self.proposal()['id'],'approve','Reviewer',crm,self.lock)
        self.assertEqual(crm.writes,[])
    def test_stale_fields_block_write(self):
        old=account(name='Old name'); self.generate([PARENT,old]); crm=FakeCRM([PARENT,old]); crm.accounts['a']['name']='Changed by another person'
        with self.assertRaises(RuntimeError): decide(self.conn,self.proposal()['id'],'approve','Reviewer',crm,self.lock)
        self.assertEqual(crm.writes,[])
    def test_two_website_facilities_same_address_require_investigation(self):
        self.generate([PARENT,account()],[LOC,{**LOC,'name':'Other campus service','source_url':'https://example.test/communities/other'}])
        self.assertTrue(all(not json.loads(r['plan']) for r in self.conn.execute('SELECT plan FROM proposals')))
    def test_detail_parser_multiple_care_offerings(self):
        source='<h1>Example</h1><dl><dt>Address</dt><dd>10 Main St<br>Example, OH 43000</dd><dt>Care Offerings</dt><dd><span class="badge">Assisted Living</span><span class="badge">Memory Support</span></dd></dl>'
        result=parse_location(source,'https://example.test/communities/example')
        self.assertEqual(result['care_offerings'],['Assisted Living','Memory Support']); self.assertEqual(result['city'],'Example')
    def test_crawl_includes_homepage_only_location(self):
        base='https://example.test'
        detail='<h1>Example</h1><dl><dt>Address</dt><dd>10 Main St<br>Example, OH 43000</dd><dt>Care Offerings</dt><dd>Assisted Living</dd></dl>'
        pages={base+'/':'We serve 2 communities. <a href="/communities/hidden">New facility</a>',base+'/about':'About',base+'/communities':'1 communities listed <a href="/communities/listed">Listed</a>',base+'/communities/hidden':detail,base+'/communities/listed':detail.replace('10 Main','11 Main')}
        with patch('bellhaven.core.request',side_effect=lambda url:pages[url]):
            result=scrape(base,self.tmp.name)
        self.assertEqual(len(result['locations']),2); self.assertEqual(result['directory_count'],1)
    def test_incomplete_crawl_does_not_publish_location_list(self):
        base='https://example.test'
        target=Path(self.tmp.name)/'locations.json'; target.write_text('previous complete snapshot')
        pages={base+'/':'Home',base+'/about':'About',base+'/communities':'2 communities listed <a href="/communities/one">One</a>',base+'/communities/one':'<h1>Example</h1><dl><dt>Address</dt><dd>10 Main St<br>Example, OH 43000</dd><dt>Care Offerings</dt><dd>Assisted Living</dd></dl>'}
        with patch('bellhaven.core.request',side_effect=lambda url:pages[url]):
            with self.assertRaisesRegex(ValueError,'Incomplete directory'): scrape(base,self.tmp.name)
        self.assertEqual(target.read_text(),'previous complete snapshot')

if __name__=='__main__': unittest.main()
