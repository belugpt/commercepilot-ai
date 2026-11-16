from datetime import date, timedelta
from test_business import workspace, order


def test_forecast_refuses_to_invent_unobserved_days(workspace):
    c,s,h,m,conv=workspace
    result=c.post('/v1/forecasts',headers=h,json={'ends_on':'2026-11-16','currency':'NGN'}).json()
    assert result['state']=='insufficient_history'
    assert len(result['missing_days'])==28
    assert 'daily' not in result


def test_statistical_forecast_backtests_and_preserves_provenance(workspace):
    c,s,h,m,conv=workspace
    first=date(2026,10,20)
    for i in range(28):
        day=first+timedelta(days=i)
        data=order(source_id=f'day-{i}',occurred_at=day.isoformat()+'T12:00:00+01:00',lines=[{'sku':'D1','title':'Dress','quantity':1,'unit_price_minor':10000+(i%7)*1000,'cogs_minor':5000}],discounts_minor=0,refunds_minor=0)
        assert c.post('/v1/orders/ingest',headers=h,json=data).status_code==200
    result=c.post('/v1/forecasts',headers=h,json={'ends_on':'2026-11-16','currency':'NGN'}).json()
    assert result['state']=='estimated' and result['method']=='weekly_naive'
    assert result['backtest']['scores']['weekly_naive']['wape']==0
    assert result['daily'][0]['day']=='2026-11-17'
    assert result['daily'][0]['base_minor']==10000
    assert len(result['source_ids'])==28
    other,key=s.provision('Other')
    assert c.post('/v1/forecasts',headers={'Authorization':'Bearer '+key},json={'ends_on':'2026-11-16','currency':'NGN'}).status_code==422


def test_plan_variance_keeps_unknown_expenses(workspace):
    c,s,h,m,conv=workspace
    c.post('/v1/orders/ingest',headers=h,json=order())
    plan=c.post('/v1/plans',headers=h,json={'title':'Daily target','currency':'NGN','starts_on':'2026-11-16','ends_on':'2026-11-16','revenue_target_minor':100000,'expense_budget_minor':5000,'assumptions':'Recorded orders only'}).json()
    result=c.get(f"/v1/plans/{plan['id']}/variance",headers=h).json()
    assert result['revenue_variance_minor']==-5000
    assert result['expense_variance_minor'] is None
    c.put('/v1/reports/expense-coverage',headers=h,json={'day':'2026-11-16','currency':'NGN','complete':True})
    assert c.get(f"/v1/plans/{plan['id']}/variance",headers=h).json()['expense_variance_minor']==-5000
    other,key=s.provision('Other')
    assert c.get(f"/v1/plans/{plan['id']}/variance",headers={'Authorization':'Bearer '+key}).status_code==404
