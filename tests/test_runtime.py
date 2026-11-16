import os
import pytest
from fastapi.testclient import TestClient
from commercepilot.gateway import webhook_app
from commercepilot.secrets import save_secrets, read_secrets, load_environment
from commercepilot.whatsapp import WhatsApp
from test_whatsapp import wa_setup, onboard, post, payload
from test_delivery import Sender, draft


def test_gateway_exposes_no_private_surface(wa_setup):
    app, client, headers, merchant, binding, clock = wa_setup
    public = TestClient(webhook_app(app.state.whatsapp))
    for route in ['/', '/docs', '/openapi.json', '/v1/me', '/v1/products', '/assets/dashboard.js']:
        assert public.get(route, headers=headers).status_code == 404
    assert public.get('/health').status_code == 200
    assert public.get('/webhooks/whatsapp', params={'hub.mode':'subscribe','hub.verify_token':'fixture-verification-token','hub.challenge':'check'}).text == 'check'
    assert post(public, payload()).json()['accepted'] == 1
    assert public.post('/webhooks/whatsapp',content=b'{}').status_code == 401


def test_automatic_reply_drain_obeys_policy_and_does_not_replay(wa_setup):
    app, c, h, merchant, binding, clock = wa_setup
    sender = Sender()
    sender.phone_number_id = '222'
    draft(wa_setup, sender)
    result = app.state.delivery.process_one()
    assert result['state'] == 'accepted'
    assert app.state.delivery.process_one() is None
    assert len(sender.calls) == 1
    post(c,payload(mid='second'))
    app.state.whatsapp.process_one()
    c.put('/v1/policy',headers=h,json={'enabled':False,'actions':[],'expires_at':'2099-01-01T00:00:00Z'})
    assert app.state.delivery.process_one() is None
    assert len(sender.calls) == 1


def test_reports_render_unknowns_and_exact_large_money():
    reply = WhatsApp.render_reply({'result':{'message':'Report', 'report':{'currency':'NGN','net_sales_minor':99999999999999999,'gross_profit_minor':None,'operating_profit_minor':None,'missing':['cogs']}}})
    assert 'NGN 999,999,999,999,999.99' in reply
    assert 'Gross profit: Unknown' in reply
    assert 'Missing: cogs' in reply


@pytest.mark.skipif(os.name != 'nt',reason='Windows user-scoped DPAPI')
def test_windows_secrets_are_encrypted_and_env_overrides(tmp_path,monkeypatch):
    path=tmp_path/'secrets.dpapi'
    save_secrets(path,{'WHATSAPP_APP_SECRET':'fixture-private-value'})
    assert b'fixture-private-value' not in path.read_bytes()
    assert read_secrets(path)['WHATSAPP_APP_SECRET']=='fixture-private-value'
    monkeypatch.setenv('WHATSAPP_APP_SECRET','environment-value')
    load_environment(path)
    assert os.environ['WHATSAPP_APP_SECRET']=='environment-value'
    with pytest.raises(ValueError):
        save_secrets(path,{'NOT_PERMITTED':'value'})
    damaged=tmp_path/'damaged.dpapi'
    damaged.write_bytes(b'corrupt')
    with pytest.raises(RuntimeError):
        read_secrets(damaged)
