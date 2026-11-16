# Data collection and financial integrity

Version 0.2 collects merchant-reported expenses through authenticated conversation messages. Each record preserves integer minor-unit amount, explicit currency, category, timezone-aware source timestamp, normalized UTC timestamp, recording timestamp, source system/type, conversation run evidence, verification state, unknown confidence and unreconciled status. Original message and validated arguments remain linked through the run. There is no claim of external verification.

Duplicate delivery with the same message idempotency key produces one effect. Detecting the same receipt described in different messages, conflicts across providers, OCR, source correction history and expense approval/reconciliation are future milestones. Do not treat current records as a complete accounting ledger.

Reports currently calculate explicitly supplied aggregates deterministically. Net sales deduct discounts; refunds remain separate, cash is never inferred and unknown COGS/expenses leave profit unknown. The response labels inputs unverified. It does not silently combine expenses across currencies or derive authoritative business profitability from partial records.

Production ingestion must preserve source identifiers, original values, actors, confidence/evidence and adjustment history; enforce tenant/provider/source uniqueness; reconcile imported orders, payments, cancellations/refunds and provider totals; define currency scales, merchant-timezone reporting periods and explicit FX policy. Forecasts wait for sufficiently validated history and baseline backtesting.
