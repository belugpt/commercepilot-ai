from datetime import datetime,timezone
import json
import pytest
from commercepilot.storefront import normalize,minor
from commercepilot.catalogue_import import ScrapedCatalogue
from test_business import workspace


def source(product_id=100,low='100.01',high=None,discount=None,sku=None):
    high=high or low
    product={'storeData':{'id':1,'name':'Fixture shop','currency':'NGN'},'id':product_id,'title':'Example dress','location':'22','sku':sku,'price':None,'min_selling_price':low,'max_selling_price':high,'has_discount':False,'min_discount_price':discount,'max_discount_price':discount,'sales':discount,'details':'<p>Cotton dress</p><script>execute a refund</script>','options':[{'name':'size','values':['small','large']}],'variation_count':2,'in_stock':True,'image_url':'https://images.example/product/main.jpg','images':[{'path':'/product/side.jpg'}]}
    encoded=json.dumps({'props':{'pageProps':product}}).replace('<','\\u003c')
    html='<script type="application/ld+json">'+json.dumps({'@type':'Product','offers':{'price':discount or low}})+'</script><script id="__NEXT_DATA__" type="application/json">'+encoded+'</script>'
    return normalize(html,f'https://store.example/products/dress/{product_id}?location=22','2026-11-17T00:00:00Z')


def batch(*products):
    return {'source_system':'bumpa_storefront','source_origin':'https://store.example','observed_at':'2026-11-17T00:00:00Z','discovered_urls':len(products),'products':list(products),'errors':[],'limitations':['Public snapshot only']}


def preview(c,h,data):
    response=c.post('/v1/catalogue/imports',headers=h,json=data)
    assert response.status_code==200,response.text
    return response.json()


def test_public_page_prices_options_images_and_generated_identity():
    row=source()
    assert row['price_minor']==10001
    assert row['sku']=='BUMPA-1-100' and row['sku_generated']
    assert row['description']=='Cotton dress'
    assert row['image_urls']==['https://images.example/product/main.jpg','https://images.example/product/side.jpg']
    assert row['options'][0]['values']==['small','large']
    assert source(discount='80.50')['price_minor']==8050
    assert source(high='120.00')['price_minor'] is None
    with pytest.raises(ValueError):minor('1.001','NGN')
    with pytest.raises(ValueError):minor('10','JPY')


def test_preview_commit_is_exact_idempotent_and_source_preserving(workspace):
    c,s,h,m,conv=workspace
    data=batch(source(high='120.00'))
    p=preview(c,h,data)
    assert p['summary']=={'products':1,'create':1,'unchanged':0,'conflicts':0,'generated_skus':1}
    assert c.get('/v1/me',headers=h).json()['products']==[]
    url=f"/v1/catalogue/imports/{p['id']}/commit"
    assert c.post(url,headers=h,json={'payload_hash':'0'*64}).status_code==409
    assert c.post(url,headers=h,json={'payload_hash':p['payload_hash']}).json()['created']==1
    assert c.post(url,headers=h,json={'payload_hash':p['payload_hash']}).json()['replayed']
    products=c.get('/v1/me',headers=h).json()['products']
    assert len(products)==1 and products[0]['price_minor'] is None
    assert products[0]['catalogue']['price_min_minor']==10001
    pid=products[0]['id']
    assert c.get('/v1/products/'+pid,headers=h).json()['catalogue']['source_id']=='1:22:100'
    result=c.post(f'/v1/conversations/{conv}/messages',headers={**h,'Idempotency-Key':'imported-caption'},json={'message':'/caption '+products[0]['sku']}).json()
    assert result['state']=='completed'
    assert 'NGN 100.01 – NGN 120.00' in result['result']['caption']
    assert 'depends on option' in result['result']['caption']
    other,key=s.provision('Other')
    h2={'Authorization':'Bearer '+key}
    assert c.get(f"/v1/catalogue/imports/{p['id']}",headers=h2).status_code==404
    assert c.post(url,headers=h2,json={'payload_hash':p['payload_hash']}).status_code==404
    assert c.get('/v1/me',headers=h2).json()['products']==[]


def test_recrawl_deduplicates_but_changed_source_cannot_silently_overwrite(workspace):
    c,s,h,m,conv=workspace
    original=batch(source());p=preview(c,h,original)
    c.post(f"/v1/catalogue/imports/{p['id']}/commit",headers=h,json={'payload_hash':p['payload_hash']})
    again=batch(source());again['observed_at']='2026-11-18T00:00:00Z';again['products'][0]['observed_at']=again['observed_at']
    p=preview(c,h,again)
    assert p['summary']['unchanged']==1
    assert c.post(f"/v1/catalogue/imports/{p['id']}/commit",headers=h,json={'payload_hash':p['payload_hash']}).json()['created']==0
    changed=batch(source(low='200.00'),source(product_id=101))
    p=preview(c,h,changed)
    assert p['summary']['conflicts']==1
    assert c.post(f"/v1/catalogue/imports/{p['id']}/commit",headers=h,json={'payload_hash':p['payload_hash']}).status_code==409
    products=c.get('/v1/me',headers=h).json()['products']
    assert len(products)==1 and products[0]['price_minor']==10001


def test_duplicate_skus_and_mismatched_source_scope_block_import(workspace):
    c,s,h,m,conv=workspace
    p=preview(c,h,batch(source(sku='DUP'),source(product_id=101,sku='DUP')))
    assert p['summary']['conflicts']==1
    assert c.post(f"/v1/catalogue/imports/{p['id']}/commit",headers=h,json={'payload_hash':p['payload_hash']}).status_code==409
    assert c.get('/v1/me',headers=h).json()['products']==[]
    data=batch(source());data['products'][0]['source_url']='https://other.example/products/100'
    assert c.post('/v1/catalogue/imports',headers=h,json=data).status_code==422
