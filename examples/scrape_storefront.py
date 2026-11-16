"""Scrape explicitly authorized, discovered public product URLs to a local preview."""
import argparse
import json
from pathlib import Path
from commercepilot.storefront import scrape

parser=argparse.ArgumentParser()
parser.add_argument('--origin',required=True)
parser.add_argument('--urls',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
result=scrape(args.origin,json.loads(Path(args.urls).read_text()),args.output)
print(json.dumps({'discovered':result['discovered_urls'],'products':len(result['products']),'errors':len(result['errors']),'generated_skus':sum(p['sku_generated'] for p in result['products']),'price_ranges':sum(p['price_minor'] is None for p in result['products'])}))
