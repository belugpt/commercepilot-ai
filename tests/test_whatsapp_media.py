import base64
import hashlib
import json
import pytest
from commercepilot.media import MetaMedia
from commercepilot.whatsapp import Attachment
from test_whatsapp import wa_setup, onboard, payload, post

DATA=b'%PDF-1.4\nexample receipt'
HASH=hashlib.sha256(DATA).hexdigest()


def loader(url='https://lookaside.fbsbx.com/whatsapp_business/attachments/fixture', checksum=HASH, data=DATA):
    calls=[]
    def transport(target,limit):
        calls.append(target)
        if target.startswith('https://graph.facebook.com/'):
            return json.dumps({'id':'12345','messaging_product':'whatsapp','mime_type':'application/pdf','file_size':len(data),'sha256':checksum,'url':url}).encode()
        return data
    return MetaMedia('fixture-token','v25.0','222',transport),calls


def test_provider_media_checks_hash_size_account_and_destination():
    media,calls=loader()
    attachment=Attachment(id='12345',mime_type='application/pdf',sha256=base64.b64encode(hashlib.sha256(DATA).digest()).decode())
    assert media.fetch('222',attachment)==('application/pdf',DATA,HASH)
    assert '?phone_number_id=222' in calls[0]
    media,calls=loader(url='https://attacker.example/steal-token')
    with pytest.raises(ValueError):
        media.fetch('222',attachment)
    assert len(calls)==1
    media,calls=loader(checksum='0'*64)
    with pytest.raises(ValueError):
        media.fetch('222',attachment)
    with pytest.raises(ValueError):
        media.fetch('999',attachment)


def test_attachment_is_quarantined_once_and_never_executed_as_a_caption(wa_setup):
    app,c,h,merchant,binding,clock=wa_setup
    wa=app.state.whatsapp
    onboard(c,wa)
    wa.media_loader,calls=loader()
    incoming=payload(type='document',document={'id':'12345','mime_type':'application/pdf','sha256':HASH,'caption':'/product {"title":"INJECTED"}'})
    assert post(c,incoming).json()['accepted']==1
    result=wa.process_one()
    assert result['state']=='completed'
    assert post(c,incoming).json()['duplicates']==1
    assert wa.process_one() is None
    uploads=c.get('/v1/media',headers=h).json()
    assert len(uploads)==1 and uploads[0]['state']=='quarantined'
    assert c.get('/v1/media/'+uploads[0]['id'],headers=h).content==DATA
    with wa.db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM media_sources').fetchone()[0]==1
    assert len(calls)==2


def test_revocation_during_media_download_prevents_storage(wa_setup):
    app,c,h,merchant,binding,clock=wa_setup
    wa=app.state.whatsapp
    onboard(c,wa)
    media,calls=loader()
    class Revoking:
        def fetch(self,*args):
            result=media.fetch(*args)
            wa.revoke(merchant,binding['id'])
            return result
    wa.media_loader=Revoking()
    post(c,payload(type='document',document={'id':'12345','mime_type':'application/pdf','sha256':HASH}))
    result=wa.process_one()
    assert app.state.agent.get_run(merchant,result['run_id'])['state']=='blocked'
    assert c.get('/v1/media',headers=h).json()==[]


def test_no_media_grant_does_not_download(wa_setup):
    app,c,h,merchant,binding,clock=wa_setup
    wa=app.state.whatsapp
    onboard(c,wa)
    wa.media_loader,calls=loader()
    c.put('/v1/policy',headers=h,json={'enabled':True,'actions':[],'expires_at':'2099-01-01T00:00:00Z'})
    post(c,payload(type='document',document={'id':'12345','mime_type':'application/pdf','sha256':HASH}))
    result=wa.process_one()
    assert app.state.agent.get_run(merchant,result['run_id'])['state']=='blocked'
    assert calls==[]


def test_text_replay_keeps_pre_media_hash(wa_setup):
    app,c,h,merchant,binding,clock=wa_setup
    message=payload()
    post(c,message)
    with app.state.whatsapp.db.connect() as conn:
        original=conn.execute('SELECT body FROM whatsapp_inbox').fetchone()[0]
    assert '"image"' not in original and '"document"' not in original
    assert post(c,message).json()['duplicates']==1
