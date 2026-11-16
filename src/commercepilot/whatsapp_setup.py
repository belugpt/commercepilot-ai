"""Explicit operator-only account subscription and callback renewal."""
import json
import os
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def subscribe(waba,callback=None,transport=None):
    if not re.fullmatch(r'[0-9]{1,100}',waba):
        raise ValueError('numeric WABA ID required')
    version=os.environ.get('WHATSAPP_GRAPH_VERSION','')
    token=os.environ.get('WHATSAPP_ACCESS_TOKEN')
    verify=os.environ.get('WHATSAPP_VERIFY_TOKEN')
    if not re.fullmatch(r'v[0-9]+\.0',version) or not token:
        raise ValueError('explicit provider version and access token required')
    data={}
    if callback:
        url=urlsplit(callback)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment or len(callback)>200 or not verify:
            raise ValueError('HTTPS callback without embedded credentials and a configured verify token required')
        data={'override_callback_uri':callback,'verify_token':verify}
    def request(payload):
        req=Request(f'https://graph.facebook.com/{version}/{waba}/subscribed_apps',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=30) as response:
            return json.loads(response.read(100000))
    try:
        result=(transport or request)(data)
    except HTTPError as exc:
        try:
            error=json.loads(exc.read(100000)).get('error',{})
            code=error.get('code')
            text=str(error.get('message','')).lower()
            reason='credential_expired_or_invalid' if any(x in text for x in ['session','access token','expired']) else 'callback_verification_failed' if 'callback' in text else 'provider_rejected'
            suffix=f'HTTP {exc.code}, code {code if isinstance(code,int) else "unknown"}, {reason}'
        except Exception:
            suffix=f'HTTP {exc.code}, provider_rejected'
        raise RuntimeError('Meta subscription failed: '+suffix+'. Provider details omitted.') from None
    except Exception:
        raise RuntimeError('Meta subscription failed; check account permissions, token expiry and callback availability. Provider details omitted.') from None
    if result.get('success') is not True:
        raise RuntimeError('Meta did not confirm the subscription')
    return {'subscribed':True,'callback':callback or 'app_default','verification':'Meta accepted subscription; send a real message to validate delivery'}
