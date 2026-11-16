"""Source-preserving, previewed and atomic local catalogue imports."""
from datetime import datetime
import json
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4
from pydantic import Field, StrictInt, model_validator
from commercepilot.domain import Command
from commercepilot.services import Conflict, Missing, digest, now


class SourceOption(Command):
    name: str = Field(min_length=1,max_length=100)
    values: list[str] = Field(max_length=500)


class SourceProduct(Command):
    source_id: str = Field(min_length=1,max_length=200)
    source_url: str = Field(max_length=2000)
    store_name: str = Field(min_length=1,max_length=200)
    store_id: str = Field(pattern=r'^[0-9]+$')
    product_id: str = Field(pattern=r'^[0-9]+$')
    location_id: str = Field(pattern=r'^[0-9]*$')
    title: str = Field(min_length=1,max_length=200,pattern=r'\S')
    sku: str = Field(min_length=1,max_length=100,pattern=r'\S')
    source_sku: str | None
    sku_generated: bool
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    price_min_minor: StrictInt = Field(ge=0,le=10**15)
    price_max_minor: StrictInt = Field(ge=0,le=10**15)
    price_minor: StrictInt | None = Field(ge=0,le=10**15)
    description: str = Field(max_length=100000)
    image_urls: list[str] = Field(max_length=200)
    options: list[SourceOption] = Field(max_length=50)
    declared_variant_count: StrictInt = Field(ge=0,le=1000000)
    variant_detail_status: Literal['option_lists_only_no_variant_level_prices_or_stock']
    in_stock_snapshot: bool | None
    observed_at: datetime
    original_prices: dict[str,Any]

    @model_validator(mode='after')
    def consistency(self):
        if self.observed_at.tzinfo is None:raise ValueError('Aware source observation time required')
        if self.source_id!=f'{self.store_id}:{self.location_id}:{self.product_id}':raise ValueError('Source identity mismatch')
        if self.price_max_minor<self.price_min_minor:raise ValueError('Invalid price range')
        expected=self.price_min_minor if self.price_min_minor==self.price_max_minor else None
        if self.price_minor!=expected:raise ValueError('Exact price must be unknown for a range')
        for url in [self.source_url,*self.image_urls]:
            parts=urlsplit(url)
            if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:raise ValueError('Public HTTPS source links required')
        if self.sku_generated:
            if self.source_sku or self.sku!=f'BUMPA-{self.store_id}-{self.product_id}':raise ValueError('Generated SKU must be labelled and source-derived')
        elif self.sku!=self.source_sku:raise ValueError('Merchant SKU must match source')
        return self


class ScrapedCatalogue(Command):
    source_system: Literal['bumpa_storefront']
    source_origin: str = Field(max_length=2000)
    observed_at: datetime
    discovered_urls: StrictInt = Field(ge=1,le=1000)
    products: list[SourceProduct] = Field(min_length=1,max_length=1000)
    errors: list[dict[str,str]] = Field(max_length=1000)
    limitations: list[str] = Field(max_length=20)

    @model_validator(mode='after')
    def scope(self):
        origin=urlsplit(self.source_origin)
        if origin.scheme!='https' or not origin.hostname or origin.username or origin.password or origin.path not in {'','/'} or origin.query or origin.fragment:raise ValueError('Public HTTPS origin required')
        if self.observed_at.tzinfo is None:raise ValueError('Aware observation timestamp required')
        if len(self.products)+len(self.errors)!=self.discovered_urls:raise ValueError('Discovery totals do not reconcile')
        identities=[p.source_id for p in self.products]
        if len(set(identities))!=len(identities):raise ValueError('Repeated source product identity')
        for p in self.products:
            if urlsplit(p.source_url).netloc!=origin.netloc:raise ValueError('Product URL is outside the source origin')
        return self


def source_hash(product):
    # Re-reading identical facts at a new time is not a new product.
    return digest(json.dumps(product.model_dump(mode='json',exclude={'observed_at'}),sort_keys=True))


class CatalogueImport:
    def __init__(self,services):self.services,self.db=services,services.db

    def classify(self,c,merchant,product):
        source=c.execute('SELECT product_id,payload_hash FROM catalogue_sources WHERE merchant_id=? AND source_system=? AND source_id=?',(merchant,'bumpa_storefront',product.source_id)).fetchone()
        if source:
            return 'unchanged' if source['payload_hash']==source_hash(product) else 'source_changed_requires_review'
        existing=c.execute('SELECT id FROM products WHERE merchant_id=? AND sku=?',(merchant,product.sku)).fetchone()
        return 'sku_conflict' if existing else 'create'

    def prepare(self,merchant,data):
        body=data.model_dump_json();fingerprint=digest(body)
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT id FROM catalogue_imports WHERE merchant_id=? AND payload_hash=?',(merchant,fingerprint)).fetchone()
            if old:return self.inspect(merchant,old['id'],connection=c)
            batch_id=str(uuid4())
            c.execute("INSERT INTO catalogue_imports VALUES(?,?,?,?,?,'preview',?,NULL)",(batch_id,merchant,fingerprint,data.source_origin,body,now()))
            self.services.audit(c,merchant,'catalogue.import_prepared',batch_id)
            return self.inspect(merchant,batch_id,connection=c)

    def inspect(self,merchant,batch_id,connection=None):
        if connection is None:
            with self.db.connect() as c:return self.inspect(merchant,batch_id,connection=c)
        row=connection.execute('SELECT * FROM catalogue_imports WHERE merchant_id=? AND id=?',(merchant,batch_id)).fetchone()
        if not row:raise Missing('Catalogue import not found')
        data=ScrapedCatalogue.model_validate_json(row['body'])
        seen=set();items=[]
        for p in data.products:
            state=self.classify(connection,merchant,p)
            if p.sku in seen:state='duplicate_sku_in_batch'
            seen.add(p.sku)
            items.append({'title':p.title,'sku':p.sku,'source_id':p.source_id,'state':state,'currency':p.currency,'price_min_minor':p.price_min_minor,'price_max_minor':p.price_max_minor,'images':len(p.image_urls),'sku_generated':p.sku_generated,'declared_variant_count':p.declared_variant_count})
        return {'id':batch_id,'state':row['state'],'payload_hash':row['payload_hash'],'source_origin':data.source_origin,'products':items,'errors':data.errors,'limitations':data.limitations,
                'summary':{'products':len(items),'create':sum(p['state']=='create' for p in items),'unchanged':sum(p['state']=='unchanged' for p in items),'conflicts':sum(p['state'] not in {'create','unchanged'} for p in items),'generated_skus':sum(p['sku_generated'] for p in items)}}

    def commit(self,merchant,batch_id,payload_hash):
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM catalogue_imports WHERE merchant_id=? AND id=?',(merchant,batch_id)).fetchone()
            if not row:raise Missing('Catalogue import not found')
            if row['payload_hash']!=payload_hash:raise Conflict('Import does not match the previewed payload')
            if row['state']=='committed':return {'id':batch_id,'state':'committed','replayed':True,'created':0}
            preview=self.inspect(merchant,batch_id,connection=c)
            if preview['errors'] or preview['summary']['conflicts']:raise Conflict('Resolve import errors or conflicts before committing; nothing changed')
            data=ScrapedCatalogue.model_validate_json(row['body']);created=0
            for p in data.products:
                if self.classify(c,merchant,p)=='unchanged':continue
                product_id=str(uuid4())
                core={'title':p.title,'sku':p.sku,'price_minor':p.price_minor,'currency':p.currency}
                c.execute('INSERT INTO products VALUES(?,?,?,?)',(product_id,merchant,p.sku,json.dumps(core)))
                c.execute('INSERT INTO catalogue_sources VALUES(?,?,?,?,?,?,?)',(merchant,data.source_system,p.source_id,product_id,source_hash(p),p.model_dump_json(),now()))
                self.services.audit(c,merchant,'product.imported',product_id);created+=1
            c.execute("UPDATE catalogue_imports SET state='committed',committed_at=? WHERE merchant_id=? AND id=?",(now(),merchant,batch_id))
            self.services.audit(c,merchant,'catalogue.import_committed',batch_id)
            return {'id':batch_id,'state':'committed','created':created,'unchanged':preview['summary']['unchanged'],'replayed':False}
