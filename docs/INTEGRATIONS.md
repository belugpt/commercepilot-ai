# Integration evidence — 2026-11-16

No provider accounts or credentials exist yet. No live provider requests or writes have been tested.

## Bumpa

User-provided https://www.bumpa.io/ identifies a public-beta v1 API, links https://docs.bumpa.io/, and shows base https://api.getbumpa.com/api/commerce/v1 with X-Api-Key authentication and public/secret key scopes. The landing page has product/order examples. The API reference loads as an unreadable client-rendered page in the research tool, so detailed schemas and write permissions are not verified. Treat landing-page capability summaries as leads for contract validation, not a completed adapter.

MCP is marked testing/early access, with read tools and upcoming write tools. Do not assume REST and MCP expose identical operations. Next: obtain an account, official reference/OpenAPI export, scoped keys, sandbox policy, rate limits, pagination schemas, webhook signature/replay rules, products/orders coverage and commercial terms. No invented write endpoints or scraping fallback.

## Other providers

- Shopify: https://shopify.dev/docs/api/admin-graphql/latest retrieved; latest listed 2026-10. Pin supported version and verify OAuth, least-privilege product/order scopes, pagination, query costs, HMAC webhooks and reconciliation with a development store.
- Instagram: https://developers.facebook.com/documentation/instagram-platform/content-publishing retrieved. Professional accounts and login-specific permission sets apply; media must be accessible to Meta. Validate chosen login, review/access, media formats/limits, container state and independent post reads.
- Facebook Pages: official Graph API validation, app review, permissions and read-back remain pending.
- WhatsApp: current official webhook overview was retrieved in 0.3 and confirms account/phone/message envelope and business-scoped sender IDs. Signed intake, operator-attested sender bindings, durable worker and draft replies are implemented and locally tested. Live business account/phone registration, media, templates/windows, opt-in and delivery states remain unverified. See WHATSAPP.md for official sources and test limitations.
- AI provider: choose account/model and implement strict planner output after tool and data boundaries are established. No model dependency is hardwired into domain logic.
