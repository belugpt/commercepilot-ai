"""Read authorized public Bumpa storefront pages without account/API access."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

USER_AGENT='CommercePilotCatalogueImporter/0.6'
MAX_PAGE_BYTES=2_000_000


class NextData(HTMLParser):
    def __init__(self):
        super().__init__(); self.take=False; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('id')=='__NEXT_DATA__': self.take=True
    def handle_data(self,data):
        if self.take:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='script':self.take=False


class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.hidden+=1
        if tag in {'p','br','li','div'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style'} and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


class StructuredOffers(HTMLParser):
    def __init__(self):super().__init__();self.take=False;self.parts=[];self.offers=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('type')=='application/ld+json':self.take=True;self.parts=[]
    def handle_data(self,data):
        if self.take:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.take:
            value=json.loads(''.join(self.parts))
            if isinstance(value,dict) and value.get('@type')=='Product' and isinstance(value.get('offers'),dict):self.offers.append(value['offers'])
            self.take=False


def plain(value):
    parser=PlainText();parser.feed(value or '')
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())


def page_data(html):
    parser=NextData();parser.feed(html)
    if not parser.parts:raise ValueError('Public page has no supported Bumpa product data')
    return json.loads(''.join(parser.parts),parse_float=str)['props']['pageProps']


def minor(value,currency):
    if value is None:return None
    if currency not in {'NGN','USD','GBP','EUR','KES','GHS'}:raise ValueError('Unsupported currency scale; review required')
    amount=Decimal(str(value))*100
    if not amount.is_finite() or amount<0 or amount!=amount.to_integral_value() or amount>10**15:
        raise ValueError('Invalid money precision or range')
    return int(amount)


def normalize(html,url,observed_at):
    source=page_data(html)
    store=source['storeData']; currency=store['currency']
    if isinstance(currency,dict):currency=currency['currency']
    product_id=str(source['id']); store_id=str(store['id'])
    if not re.fullmatch(r'[0-9]+',product_id) or not re.fullmatch(r'[0-9]+',store_id):raise ValueError('Invalid source IDs')
    if not urlsplit(url).path.rstrip('/').endswith('/'+product_id):raise ValueError('Product page ID does not match requested URL')
    location=str(source.get('location') or '')
    low=minor(source.get('min_selling_price'),currency)
    high=minor(source.get('max_selling_price'),currency)
    base=minor(source.get('price'),currency)
    # Some storefront pages expose discount prices while has_discount is false.
    # Preserve originals and cross-check the effective minimum against JSON-LD.
    discount_low=minor(source.get('min_discount_price'),currency)
    discount_high=minor(source.get('max_discount_price'),currency)
    sale=minor(source.get('sales'),currency)
    if (discount_low is not None and discount_high is not None) or source.get('has_discount'):
        low=discount_low if discount_low is not None else sale
        high=discount_high if discount_high is not None else sale
    else:
        low=low if low is not None else base
        high=high if high is not None else base
    if low is None or high is None or high<low:raise ValueError('Advertised price could not be resolved; review required')
    structured=StructuredOffers();structured.feed(html)
    advertised=[o['price'] for o in structured.offers if o.get('price') is not None]
    if advertised and any(minor(price,currency)!=low for price in advertised):
        raise ValueError('Structured advertised price conflicts with extracted price; review required')
    image_url=source.get('image_url')
    images=[image_url] if image_url else []
    for image in source.get('images') or []:
        path=image.get('path') if isinstance(image,dict) else image
        if path and image_url:images.append(urljoin(image_url,path))
    images=list(dict.fromkeys(u for u in images if urlsplit(u).scheme=='https'))
    options=[{'name':str(o['name']),'values':[str(v) for v in o['values']]} for o in source.get('options') or []]
    source_sku=source.get('sku')
    return {'source_id':f'{store_id}:{location}:{product_id}','source_url':url,'store_name':store['name'],'store_id':store_id,'product_id':product_id,'location_id':location,
            'title':source['title'],'sku':str(source_sku).strip() if source_sku and str(source_sku).strip() else f'BUMPA-{store_id}-{product_id}',
            'source_sku':str(source_sku).strip() if source_sku and str(source_sku).strip() else None,'sku_generated':not bool(source_sku and str(source_sku).strip()),'currency':currency,
            'price_min_minor':low,'price_max_minor':high,'price_minor':low if low==high else None,
            'description':plain(source.get('details') or source.get('description')),'image_urls':images,'options':options,
            'declared_variant_count':source.get('variation_count',0),'variant_detail_status':'option_lists_only_no_variant_level_prices_or_stock',
            'in_stock_snapshot':source.get('in_stock'),'observed_at':observed_at,
            'original_prices':{**{k:source.get(k) for k in ['price','sales','min_selling_price','max_selling_price','min_discount_price','max_discount_price','has_discount']},'structured_offer_prices':advertised}}


class SameOriginRedirect(HTTPRedirectHandler):
    def __init__(self,origin):self.origin=origin
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl).netloc!=urlsplit(self.origin).netloc or urlsplit(newurl).scheme!='https':
            raise ValueError('Cross-origin redirect requires explicit review')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def scrape(origin,urls,output):
    origin=origin.rstrip('/')
    origin_parts=urlsplit(origin)
    if origin_parts.scheme!='https' or not origin_parts.hostname or origin_parts.username or origin_parts.password or origin_parts.path or origin_parts.query or origin_parts.fragment:
        raise ValueError('Explicit public HTTPS storefront origin required')
    opener=build_opener(SameOriginRedirect(origin))
    def fetch(url):
        with opener.open(Request(url,headers={'User-Agent':USER_AGENT}),timeout=25) as response:
            data=response.read(MAX_PAGE_BYTES+1)
        if len(data)>MAX_PAGE_BYTES:raise ValueError('Page capacity exceeded')
        return data.decode('utf-8')
    robots=RobotFileParser();robots.parse(fetch(origin+'/robots.txt').splitlines())
    urls=list(dict.fromkeys(urls))
    if not urls or len(urls)>1000:raise ValueError('Provide 1 to 1000 discovered product URLs')
    for url in urls:
        parts=urlsplit(url)
        if parts.scheme!='https' or parts.netloc!=urlsplit(origin).netloc or not parts.path.startswith('/products/') or parts.username or parts.password:
            raise ValueError('Only discovered product URLs on the explicit storefront are accepted')
        if not robots.can_fetch(USER_AGENT,url):raise ValueError('Storefront crawling rules prohibit a product page')
    directory=Path(output);directory.mkdir(parents=True,exist_ok=True)
    observed=datetime.now(timezone.utc).isoformat()
    def collect(url):
        # Bounded public-page reads, two at a time. No scripts are executed.
        for attempt in range(2):
            try:
                html=fetch(url)
                item=normalize(html,url,observed)
                (directory/f"product-{item['product_id']}.html").write_text(html,encoding='utf-8')
                time.sleep(.2)
                return item,None
            except Exception:
                if attempt==0:time.sleep(1)
        return None,{'source_url':url,'reason':'public_product_read_or_validation_failed'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(collect,urls))
    products=[p for p,error in results if p]
    errors=[error for p,error in results if error]
    stores={p['store_id'] for p in products}
    if len(stores)>1:raise ValueError('Multiple stores discovered; review before importing')
    result={'source_system':'bumpa_storefront','source_origin':origin,'observed_at':observed,'discovered_urls':len(urls),'products':products,'errors':errors,
            'limitations':['Public storefront snapshot; unpublished products are unavailable.','Option lists and declared variation counts do not prove individual variant price or stock.','Generated SKUs are internal source-based identifiers, not claimed merchant SKUs.']}
    (directory/'catalogue-preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
