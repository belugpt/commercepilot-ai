from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from commercepilot.api import create_app
from commercepilot.domain import Action
from commercepilot.planners import CommandPlanner
from test_agent import PROFILE


@pytest.fixture
def workspace(tmp_path):
    app = create_app(str(tmp_path/'business.db'), planner=CommandPlanner())
    c = TestClient(app)
    merchant, key = app.state.services.provision('Ada')
    h = {'Authorization':f'Bearer {key}'}
    c.put('/v1/policy',headers=h,json={'enabled':True,'actions':[a.value for a in Action],'expires_at':'2099-01-01T00:00:00Z'})
    conv=c.post('/v1/conversations',headers=h).json()['id']
    import json
    c.post(f'/v1/conversations/{conv}/messages',headers={**h,'Idempotency-Key':'profile'},json={'message':'/profile '+json.dumps(PROFILE)})
    return c, app.state.services, h, merchant, conv


def order(**updates):
    value={'source_system':'fixture','source_id':'order-1','revision':1,'occurred_at':'2026-11-16T10:00:00+01:00','currency':'NGN','verification_status':'merchant_reported','evidence_reference':'invoice-1','status':'open','payment_status':'paid','channel':'whatsapp','lines':[{'sku':'D1','title':'Dress','quantity':2,'unit_price_minor':50000,'cogs_minor':None}],'discounts_minor':5000,'refunds_minor':1000,'cash_collected_minor':95000}
    value.update(updates)
    return value


def report(c,h,day='2026-11-16',currency='NGN'):
    response=c.get('/v1/reports/daily',headers=h,params={'day':day,'currency':currency})
    assert response.status_code==200
    return response.json()


def test_exact_ledger_unknowns_and_explicit_coverage(workspace):
    c,s,h,m,_=workspace
    assert c.post('/v1/orders/ingest',headers=h,json=order()).status_code==200
    r=report(c,h)
    assert r['gross_sales_minor']==100000 and r['net_sales_minor']==95000
    assert r['refunds_minor']==1000 and r['cash_after_refunds_minor']==94000
    assert r['cogs_minor'] is None and r['operating_profit_minor'] is None
    data=order(revision=2,lines=[{'sku':'D1','title':'Dress','quantity':2,'unit_price_minor':50000,'cogs_minor':30000}])
    c.post('/v1/orders/ingest',headers=h,json=data)
    assert report(c,h)['gross_profit_minor']==64000
    assert report(c,h)['operating_profit_minor'] is None
    c.put('/v1/reports/expense-coverage',headers=h,json={'day':'2026-11-16','currency':'NGN','complete':True})
    assert report(c,h)['expenses_minor']==0
    assert report(c,h)['operating_profit_minor']==64000


def test_duplicate_conflict_and_out_of_order_revisions_preserve_history(workspace):
    c,s,h,m,_=workspace
    first=c.post('/v1/orders/ingest',headers=h,json=order()).json()
    repeat=c.post('/v1/orders/ingest',headers=h,json=order()).json()
    assert repeat['duplicate'] and repeat['id']==first['id']
    assert c.post('/v1/orders/ingest',headers=h,json=order(discounts_minor=2000)).status_code==409
    assert len(c.get('/v1/data-quality',headers=h).json())==1
    c.post('/v1/orders/ingest',headers=h,json=order(revision=3,status='cancelled'))
    c.post('/v1/orders/ingest',headers=h,json=order(revision=2))
    assert len(c.get('/v1/orders',headers=h).json())==1
    assert report(c,h)['cancelled_orders']==1
    assert report(c,h)['net_sales_minor']==0
    assert report(c,h)['cash_after_refunds_minor']==94000
    with s.db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM order_events WHERE merchant_id=?',(m,)).fetchone()[0]==3


def test_currencies_timezone_period_and_empty_history(workspace):
    c,s,h,_,_=workspace
    assert report(c,h)['net_sales_minor'] is None
    c.post('/v1/orders/ingest',headers=h,json=order(occurred_at='2026-11-15T23:30:00Z'))
    c.post('/v1/orders/ingest',headers=h,json=order(source_id='usd',currency='USD'))
    c.post('/v1/orders/ingest',headers=h,json=order(source_id='next-day',occurred_at='2026-11-16T23:00:00Z'))
    assert report(c,h)['orders']==1
    assert report(c,h,currency='USD')['orders']==1
    assert report(c,h,day='2026-11-17')['orders']==1
    assert report(c,h,day='2026-11-15')['orders']==0


def test_expense_provenance_corrections_and_unknown_cash(workspace):
    c,s,h,_,_=workspace
    c.post('/v1/orders/ingest',headers=h,json=order(cash_collected_minor=None))
    expense={k:v for k,v in order().items() if k in {'source_system','source_id','revision','occurred_at','currency','verification_status','evidence_reference'}}
    expense.update(source_id='boxes',amount_minor=12345,category='packaging',note='supplier')
    first=c.post('/v1/financial-records',headers=h,json=expense).json()
    assert first['record']['occurred_at'].endswith('+01:00')
    assert c.post('/v1/financial-records',headers=h,json=expense).json()['duplicate']
    assert c.post('/v1/financial-records',headers=h,json={**expense,'amount_minor':5}).status_code==409
    c.post('/v1/financial-records',headers=h,json={**expense,'revision':2,'amount_minor':13000})
    r=report(c,h)
    assert r['reported_expenses_minor']==13000
    assert r['expenses_minor'] is None and r['cash_after_refunds_minor'] is None
    assert len(r['source_ids'])==2


def test_cross_tenant_records_plans_uploads_and_quality(workspace):
    c,s,h,_,_=workspace
    c.post('/v1/orders/ingest',headers=h,json=order())
    plan=c.post('/v1/plans',headers=h,json={'title':'November','currency':'NGN','starts_on':'2026-11-01','ends_on':'2026-11-30','revenue_target_minor':500000,'expense_budget_minor':100000,'assumptions':'draft'}).json()
    media=c.post('/v1/media',headers={**h,'Content-Type':'application/pdf'},content=b'%PDF-1.4\nfixture').json()
    _,key=s.provision('Other')
    other={'Authorization':f'Bearer {key}'}
    assert c.get('/v1/orders',headers=other).json()==[]
    assert c.get(f"/v1/plans/{plan['id']}",headers=other).status_code==404
    assert c.post(f"/v1/plans/{plan['id']}/approve",headers=other,json={'payload_hash':plan['payload_hash']}).status_code==404
    assert c.get(f"/v1/media/{media['id']}",headers=other).status_code==404
    assert c.get('/v1/data-quality',headers=other).json()==[]


def test_plan_approval_binds_exact_immutable_payload(workspace):
    c,s,h,m,_=workspace
    data={'title':'November','currency':'NGN','starts_on':'2026-11-01','ends_on':'2026-11-30','revenue_target_minor':500000,'expense_budget_minor':100000,'assumptions':'draft'}
    plan=c.post('/v1/plans',headers=h,json=data).json()
    assert plan['state']=='draft'
    assert c.post(f"/v1/plans/{plan['id']}/approve",headers=h,json={'payload_hash':'0'*64}).status_code==409
    assert c.post(f"/v1/plans/{plan['id']}/approve",headers=h,json={'payload_hash':plan['payload_hash']}).json()['state']=='approved'
    c.post(f"/v1/plans/{plan['id']}/approve",headers=h,json={'payload_hash':plan['payload_hash']})
    with s.db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM audit WHERE event='plan.approved' AND merchant_id=?",(m,)).fetchone()[0]==1


def test_quarantine_type_size_dedup_and_safe_download(workspace):
    c,s,h,_,_=workspace
    headers={**h,'Content-Type':'application/pdf'}
    assert c.post('/v1/media',headers=headers,content=b'<script>bad</script>').status_code==422
    assert c.post('/v1/media',headers={**h,'Content-Type':'text/html'},content=b'<html>').status_code==415
    assert c.post('/v1/media',headers=headers,content=b'%PDF-'+b'x'*8_000_000).status_code==413
    media=c.post('/v1/media',headers=headers,content=b'%PDF-1.4 fixture').json()
    assert c.post('/v1/media',headers=headers,content=b'%PDF-1.4 fixture').json()['id']==media['id']
    response=c.get('/v1/media/'+media['id'],headers=h)
    assert response.headers['content-type']=='application/octet-stream'
    assert response.headers['x-content-type-options']=='nosniff'
    assert media['state']=='quarantined'


def test_dashboard_no_auth_bypass_and_agent_daily_report(workspace):
    import json
    c,s,h,_,conv=workspace
    page=c.get('/')
    assert page.status_code==200 and 'CommercePilot' in page.text
    assert "script-src 'self'" in page.headers['content-security-policy']
    assert c.get('/assets/dashboard.js').status_code==200
    assert c.get('/assets/unknown').status_code==404
    assert c.get('/v1/me').status_code==401
    c.post('/v1/orders/ingest',headers=h,json=order())
    response=c.post(f'/v1/conversations/{conv}/messages',headers={**h,'Idempotency-Key':'sales'},json={'message':'/sales '+json.dumps({'day':'2026-11-16','currency':'NGN'})})
    assert response.json()['state']=='completed'
    assert response.json()['result']['report']['net_sales_minor']==95000


def test_malformed_financial_records_and_naive_timestamps_rejected(workspace):
    c,s,h,_,_=workspace
    for data in [order(discounts_minor=200000),order(occurred_at='2026-11-16T10:00:00'),order(lines=[]),order(merchant_id='foreign')]:
        assert c.post('/v1/orders/ingest',headers=h,json=data).status_code==422
