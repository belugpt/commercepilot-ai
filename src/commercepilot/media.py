"""Bounded, authenticated WhatsApp attachment retrieval into quarantine only."""
import base64
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4
from commercepilot.domain import Action, PolicyInput
from commercepilot.policy import authorize
from commercepilot.services import Conflict, digest, now

LIMIT=8_000_000
MIMES={'application/pdf','image/png','image/jpeg','audio/ogg','audio/mpeg','audio/mp4','audio/aac','audio/amr','video/mp4','video/3gpp'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('media redirects are not allowed')


class MetaMedia:
    def __init__(self, token, version, phone_id, transport=None):
        if not re.fullmatch(r'v[0-9]+\.0',version) or not re.fullmatch(r'[0-9]{1,100}',phone_id):
            raise ValueError('explicit provider version and phone ID required')
        self._token,self.version,self.phone_id=token,version,phone_id
        self.transport=transport or self.request

    def request(self,url,limit):
        request=Request(url,headers={'Authorization':'Bearer '+self._token})
        with build_opener(NoRedirect()).open(request,timeout=20) as response:
            data=response.read(limit+1)
        if len(data)>limit:
            raise ValueError('media capacity exceeded')
        return data

    def fetch(self,phone_id,attachment):
        if phone_id!=self.phone_id or not re.fullmatch(r'[0-9]{1,100}',attachment.id):
            raise ValueError('media is outside configured account')
        metadata=json.loads(self.transport(f'https://graph.facebook.com/{self.version}/{attachment.id}?phone_number_id={phone_id}',100000))
        mime=metadata.get('mime_type','').split(';')[0].lower()
        size=int(metadata.get('file_size',0))
        if metadata.get('id')!=attachment.id or metadata.get('messaging_product')!='whatsapp' or mime not in MIMES or not 0<size<=LIMIT:
            raise ValueError('unsupported provider media metadata')
        url=metadata.get('url','')
        parts=urlsplit(url)
        if parts.scheme!='https' or parts.hostname!='lookaside.fbsbx.com' or parts.username or parts.password or parts.port not in {None,443}:
            raise ValueError('provider media host is not allowed')
        data=self.transport(url,LIMIT)
        fingerprint=hashlib.sha256(data).digest()
        expected={fingerprint.hex(),base64.b64encode(fingerprint).decode()}
        if len(data)!=size or metadata.get('sha256') not in expected or (attachment.sha256 and attachment.sha256 not in expected):
            raise ValueError('provider media integrity failed')
        if attachment.mime_type and attachment.mime_type.split(';')[0].lower()!=mime:
            raise ValueError('provider media type conflict')
        return mime,data,fingerprint.hex()


def configured_media():
    if os.getenv('WHATSAPP_MEDIA_ENABLED','false').lower()!='true':
        return None
    values=[os.getenv(k) for k in ['WHATSAPP_ACCESS_TOKEN','WHATSAPP_GRAPH_VERSION','WHATSAPP_PHONE_NUMBER_ID']]
    if not all(values):
        raise ValueError('WhatsApp media requires explicit account credentials')
    return MetaMedia(*values)


def capture(whatsapp,item,message):
    """Authorize before retrieval, recheck before commit, and deduplicate recovery."""
    agent,services=whatsapp.agent,whatsapp.services
    merchant,conversation,key=item['merchant_id'],item['conversation_id'],'whatsapp:'+item['id']
    body=item['body']
    def permitted(c):
        policy=c.execute('SELECT body FROM policies WHERE merchant_id=?',(merchant,)).fetchone()
        reason=authorize(Action.MEDIA,PolicyInput.model_validate_json(policy['body']) if policy else None)
        profile=c.execute('SELECT body FROM business_profiles WHERE merchant_id=?',(merchant,)).fetchone()
        return not reason and profile and 'content' in json.loads(profile['body'])['capabilities'] and whatsapp._guard(c,item)
    with whatsapp.db.connect() as c:
        previous=c.execute('SELECT id,payload_hash FROM agent_runs WHERE merchant_id=? AND conversation_id=? AND idempotency_key=?',(merchant,conversation,key)).fetchone()
        if previous:
            if previous['payload_hash']!=digest(body):
                raise Conflict('attachment request conflicts')
            return agent.get_run(merchant,previous['id'])
        allowed=permitted(c)
    attachment=getattr(message,message.type)
    mime,data,fingerprint=whatsapp.media_loader.fetch(item['phone_number_id'],attachment) if allowed else (None,None,None)
    run_id=str(uuid4())
    with whatsapp.db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if not allowed or not permitted(c):
            state,result='blocked',{'message':'Attachment capture requires an active media.capture grant, content capability and enabled channel. No file was stored.'}
        else:
            previous=c.execute('SELECT id FROM media_uploads WHERE merchant_id=? AND content_hash=?',(merchant,fingerprint)).fetchone()
            media_id=previous['id'] if previous else str(uuid4())
            if not previous:
                c.execute("INSERT INTO media_uploads VALUES(?,?,?,?,?,?,'quarantined',?)",(media_id,merchant,fingerprint,mime,len(data),data,now()))
            c.execute('INSERT OR IGNORE INTO media_sources VALUES(?,?,?,?,?)',(merchant,item['id'],media_id,attachment.id,now()))
            services.audit(c,merchant,'media.quarantined',media_id)
            state,result='completed',{'message':'Attachment stored in quarantine. No transcription, OCR or financial extraction was performed. Supply confirmed details as text to create a product or expense.','media':{'id':media_id,'mime_type':mime,'bytes':len(data),'state':'quarantined'}}
        c.execute("INSERT INTO agent_runs VALUES(?,?,?,?,?,?,'media_capture',NULL,NULL,?)",(run_id,merchant,conversation,key,digest(body),state,now()))
        c.execute("INSERT INTO messages(merchant_id,conversation_id,run_id,role,body,created_at) VALUES(?,?,?,'user',?,?)",(merchant,conversation,run_id,'WhatsApp attachment '+attachment.id,now()))
        agent.persist_completion(c,merchant,conversation,run_id,state,result)
    return agent.get_run(merchant,run_id)
