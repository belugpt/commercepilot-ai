import pytest
from commercepilot.whatsapp_setup import subscribe


def test_callback_rotation_uses_exact_explicit_endpoint(monkeypatch):
    monkeypatch.setenv('WHATSAPP_ACCESS_TOKEN','fixture')
    monkeypatch.setenv('WHATSAPP_VERIFY_TOKEN','fixture-verify')
    monkeypatch.setenv('WHATSAPP_GRAPH_VERSION','v25.0')
    seen=[]
    def transport(data):
        seen.append(data)
        return {'success':True}
    result=subscribe('111','https://example.com/webhooks/whatsapp',transport)
    assert result['subscribed'] is True
    assert seen==[{'override_callback_uri':'https://example.com/webhooks/whatsapp','verify_token':'fixture-verify'}]
    for url in ['http://example.com/webhook','https://secret@example.com/webhook']:
        with pytest.raises(ValueError):
            subscribe('111',url,transport)
    assert len(seen)==1


def test_setup_never_exposes_provider_errors(monkeypatch):
    monkeypatch.setenv('WHATSAPP_ACCESS_TOKEN','fixture')
    monkeypatch.setenv('WHATSAPP_GRAPH_VERSION','v25.0')
    def broken(data):
        raise ValueError('private provider response with credentials')
    with pytest.raises(RuntimeError) as error:
        subscribe('111',transport=broken)
    assert 'private provider response' not in str(error.value)


def test_expired_token_reports_safe_code_without_secret_body(monkeypatch):
    import io
    from urllib.error import HTTPError
    monkeypatch.setenv('WHATSAPP_ACCESS_TOKEN','fixture')
    monkeypatch.setenv('WHATSAPP_GRAPH_VERSION','v25.0')
    def expired(data):
        raise HTTPError('https://graph.facebook.com',401,'Unauthorized',{},io.BytesIO(b'{"error":{"code":190,"message":"Expired access token PRIVATE-VALUE"}}'))
    with pytest.raises(RuntimeError) as error:
        subscribe('111',transport=expired)
    assert 'code 190' in str(error.value)
    assert 'credential_expired_or_invalid' in str(error.value)
    assert 'PRIVATE-VALUE' not in str(error.value)
