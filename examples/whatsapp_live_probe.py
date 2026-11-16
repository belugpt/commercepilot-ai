"""Explicit operator test for a configured Meta test phone; never run automatically."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from commercepilot.delivery import MetaTextSender
from commercepilot.secrets import load_environment


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--send-hello-world',metavar='VERIFIED_RECIPIENT_DIGITS')
    args=parser.parse_args()
    load_environment(os.getenv('COMMERCEPILOT_SECRET_FILE','.local/secrets.dpapi'))
    token=os.environ['WHATSAPP_ACCESS_TOKEN']
    phone=os.environ['WHATSAPP_PHONE_NUMBER_ID']
    version=os.environ['WHATSAPP_GRAPH_VERSION']
    sender=MetaTextSender(token,version,phone)
    request=Request(f'https://graph.facebook.com/{version}/{phone}?fields=id,display_phone_number,verified_name',headers={'Authorization':'Bearer '+token})
    try:
        with urlopen(request,timeout=20) as response:
            record=json.loads(response.read(100000))
        if record.get('id')!=phone:
            raise ValueError('Configured phone did not match provider response')
        print('PASS: provider authenticated the configured phone ID.')
    except Exception:
        raise SystemExit('Provider phone validation failed. Check credentials, scopes and expiry; secret response omitted.') from None
    if not args.send_hello_world:
        return
    recipient=args.send_hello_world
    if not re.fullmatch(r'[0-9]{5,20}',recipient):
        parser.error('recipient must contain country-code digits')
    # A named, explicit test operation, independent of merchant reply automation.
    # Claim before submission: reruns cannot duplicate an ambiguous network send.
    target=Path('.local/live-hello-world.json')
    target.parent.mkdir(exist_ok=True,parents=True)
    try:
        with target.open('x',encoding='utf-8') as f:
            json.dump({'state':'submitting','phone_id':phone},f)
    except FileExistsError:
        raise SystemExit('A test submission already exists. Inspect its outcome before starting another test.') from None
    try:
        response=sender.transport(phone,{'messaging_product':'whatsapp','to':recipient,'type':'template','template':{'name':'hello_world','language':{'code':'en_US'}}})
        result={'state':'accepted','provider_message_id':response['messages'][0]['id'],'phone_id':phone,'delivery':'not_yet_verified'}
        target.write_text(json.dumps(result),encoding='utf-8')
        print('PASS: Meta accepted the Hello World test template. Receipt confirmation is still required.')
    except Exception:
        target.write_text(json.dumps({'state':'uncertain_or_rejected','phone_id':phone}),encoding='utf-8')
        raise SystemExit('Test submission needs review; no automatic retry and no provider secrets printed.') from None


if __name__=='__main__':
    main()
