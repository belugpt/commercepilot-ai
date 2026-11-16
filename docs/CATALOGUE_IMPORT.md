# Authorized public storefront catalogue import

Version 0.6 adds an owner-operated import for explicitly authorized public Bumpa storefront pages. It does not use a merchant API key, sign in, change Bumpa records or provide ongoing synchronization. The user must supply the source site and authorize reading it. Review its robots rules and applicable site conditions before collection. The validated live site allowed all crawlers.

## Collect a preview

Discover the public product links through the storefront's visible catalogue, including every pagination page. Save those observed HTTPS links as a JSON array. Do not invent private product/API endpoints. Then run:

```powershell
python examples/scrape_storefront.py --origin https://store.example --urls product-urls.json --output .local/imports/store
```

The collector checks robots.txt, limits reads to the explicit origin's `/products/` URLs, rejects cross-origin redirects, limits page sizes, runs two reads at a time, and performs at most one retry per failed page. It parses public Next.js page data and product JSON-LD without executing scripts. Other Bumpa themes may use different schemas; unsupported pages produce review errors. Retain failures and reconcile the discovered URL count before claiming a complete import.

The preview preserves source IDs/URLs, observation timestamp, product names, plain descriptions, HTTPS image links, observed price ranges, original source price fields, option names/values, declared variant counts and an availability snapshot. It does not infer individual variant combinations, variant prices, stock quantities, cost prices or unpublished products. Image links are preserved; image binaries are not downloaded. Source HTML and the private preview stay in the selected local output folder, outside the public repository.

Money is parsed with Decimal using an explicit currency scale. Effective sale-price fields take precedence when present; the advertised minimum is checked against product JSON-LD. Conflicting prices fail review. A parent with different minimum/maximum prices has `price_minor: null`, with its actual range in the attached `catalogue` metadata. This is a resource-read contract addition: clients must not convert a missing exact parent price to zero. Manual product creation still requires an exact integer price.

If the source publishes no SKU, generate the clearly labelled internal identifier `BUMPA-<store-id>-<product-id>`. Keep `source_sku: null` and `sku_generated: true`; never present this identifier as the merchant's original SKU. Distinct source products with the same title remain distinct records.

## Preview and commit

Authenticated owners submit the preview JSON to `POST /v1/catalogue/imports`. The response includes an immutable payload hash and per-product create/unchanged/conflict classifications. `GET /v1/catalogue/imports/{id}` retrieves it. Commit that exact hash through `POST /v1/catalogue/imports/{id}/commit` with `{"payload_hash":"..."}`. These are explicit manual owner operations; models cannot invoke the import or authorize it.

Migration 007 adds tenant-constrained source mappings and import batches. Commit is atomic. Any unresolved read error, duplicate SKU, existing SKU collision or changed source blocks the batch with no partial product creation. Repeated source facts are deduplicated even when observation time changes; conflicting updates require a separate review workflow. Repeating a committed batch does not create duplicates. A product import changes catalogue data only, never orders, sales or expenses.

Read imported details through the existing product API or `/v1/me`. The catalogue dashboard displays price ranges and a “View imported details” control for descriptions, options and source/image links. Factual captions preserve price ranges and label prices as storefront snapshots. WhatsApp `/products` retrieves up to 100 products and displays the first 20 with an explicit truncation note; the dashboard shows up to 200 records.

## Validation

The initial authorized import collected 50 public product records across three storefront pages with no read failures. It preserved 380 image links and 12 price ranges, labelled all 50 missing source SKUs with generated internal IDs, and retained option lists plus source-declared variation counts. Individual variation prices/stock were not fetched. All 50 effective minimum prices matched public product JSON-LD. Browser verification confirmed the actual records, a price range, option lists and source/image links after commit. The full 88-test suite passed before applying the import.
