# CommercePilot AI --- Master Product Specification

**Status:** Final consolidated product specification\
**Product category:** WhatsApp-first autonomous commerce operations and
business intelligence platform\
**Initial market:** Nigeria, with an architecture designed for
international expansion\
**Primary interface:** WhatsApp\
**Working product name:** CommercePilot AI

------------------------------------------------------------------------

## 1. Executive summary

CommercePilot AI is a WhatsApp-first autonomous commerce operating
agent. It helps merchants create and manage products, generate and
publish content, synchronise commerce channels, monitor orders and
sales, understand business economics, plan operations and forecast
business performance.

The product is intended to serve merchants across the spectrum:
individual social sellers, small businesses, growing e-commerce
operators and established multi-store retailers. It uses a common
multi-tenant platform with configurable merchant profiles, capabilities,
integrations and permissions.

The agent is autonomous within merchant-approved boundaries. It should
execute routine, authorised and reversible tasks without repeatedly
asking for confirmation. It must escalate high-impact, sensitive,
destructive or out-of-policy actions.

Business economics data is collected using a hybrid model: automatically
from connected systems where possible, and conversationally through
WhatsApp, voice notes, images, receipts, invoices and other documents
where integrations do not provide sufficient information.

**Product promise:** Your business operations, intelligence and planning
assistant --- accessible through WhatsApp.

## 2. Product decisions --- authoritative

These decisions supersede conflicting assumptions in earlier drafts.

  -----------------------------------------------------------------------
  Decision                Final choice            Product consequence
  ----------------------- ----------------------- -----------------------
  Target audience         All merchant segments   One configurable
                                                  platform for solo
                                                  sellers through
                                                  established retailers

  Autonomy                Autonomous              Agent plans, executes
                                                  and verifies authorised
                                                  workflows independently

  Business economics data Hybrid                  Integrations plus
                                                  WhatsApp, voice,
                                                  document and manual
                                                  collection
  -----------------------------------------------------------------------

### 2.1 Target audience

Support: - Individual and social-commerce sellers. - Small businesses
and independent retailers. - Growing e-commerce businesses. -
Established retailers and multi-store businesses.

Do not build separate products or codebases for each segment. Use
merchant profiles, configurable modules, capability flags, permissions
and integration adapters. Merchants should be able to begin with minimal
infrastructure and progressively adopt more advanced functionality.

### 2.2 Autonomy

The agent must do more than respond to questions. It must be able to
receive a request or event, understand context, plan a workflow, check
policies, execute tools, verify outcomes and record results.

Routine, reversible and pre-authorised actions should be autonomous.
High-impact financial actions, destructive operations, sensitive account
changes and actions outside configured limits require explicit approval.

### 2.3 Hybrid economics data

Collect data automatically from connected commerce, payment,
advertising, logistics and accounting systems where supported. Collect
missing data through WhatsApp text, voice, images, receipts, invoices,
supplier documents and merchant confirmation.

Every important financial record must preserve source, timestamp,
verification status and confidence. Missing information must remain
unknown, not be silently treated as zero.

------------------------------------------------------------------------

## 3. Product vision and principles

### Vision

Make business operations, commerce execution and useful business
intelligence accessible to merchants through a familiar conversational
interface.

### Product principles

1.  **Conversation first:** merchants should be able to use natural
    language, voice notes and media.
2.  **Execution over conversation:** the product must complete and
    verify tasks, not merely suggest steps.
3.  **Autonomy with boundaries:** execute within explicit permissions,
    thresholds and policies.
4.  **Financial integrity:** authoritative financial outputs come from
    validated records and deterministic calculations.
5.  **Progressive sophistication:** merchants can start simply and adopt
    more capabilities as they grow.
6.  **Platform independence:** core business records must not be trapped
    inside one commerce provider.
7.  **Explainability:** recommendations should show relevant facts,
    assumptions, uncertainty and missing data.
8.  **Merchant control:** merchants can inspect activity, change
    permissions and intervene.
9.  **Reliability:** idempotency, retries, reconciliation and exception
    handling are core requirements.
10. **Privacy and security:** tenant isolation and least-privilege
    access apply throughout.

## 4. Core user experience

WhatsApp is the primary interface for: - Text commands and questions. -
Voice notes and transcription. - Product images and videos. - Receipts,
invoices and other documents. - Notifications, reports and exception
handling. - Conversational data collection and onboarding.

A complementary web dashboard should provide: - Business overview and
KPIs. - Product and channel management. - Publishing calendar and
content history. - Sales and financial reports. - Expense and cost
records. - Budgets, plans and forecasts. - Staff access, permissions and
autonomy settings. - Task history, exceptions and audit trail.

The dashboard complements WhatsApp; it must not become a prerequisite
for routine workflows.

## 5. Merchant onboarding and capability profiles

Onboarding should be conversational and progressive, not a long
mandatory questionnaire.

Capture and maintain: - Business name, sector and description. -
Business model and product/service categories. - Sales channels and
connected platforms. - Currency, locale, timezone and reporting
preferences. - Product, order, inventory and fulfilment practices. -
Cost and expense practices. - Business goals and reporting priorities. -
Staff, roles and access requirements. - Autonomy permissions and
thresholds.

Use a `merchant_capabilities` model to enable features according to the
merchant's needs and connected systems. The agent should discover
capabilities and ask only for missing information needed for a requested
task. Confirmed details should be reused rather than repeatedly
requested.

## 6. Functional modules

### 6.1 WhatsApp interface

-   Receive and process text, voice, images, videos and documents.
-   Maintain conversation context and task state.
-   Identify intent and entities.
-   Ask concise clarifying questions when essential.
-   Send progress, completion, failure and exception notifications.
-   Support supported WhatsApp message templates and platform
    constraints.

### 6.2 Product catalogue management

-   Create products from text, images and documents.
-   Extract product attributes and suggest missing fields.
-   Generate titles, descriptions, categories and tags.
-   Manage variants, SKUs, prices, media and availability.
-   Map canonical products to channel-specific listings.
-   Detect conflicts between channel records.
-   Require policy checks for bulk or high-impact changes.

### 6.3 Content generation

-   Generate platform-appropriate captions, descriptions and hashtags.
-   Adapt tone and format to merchant preferences.
-   Reuse approved brand voice and product facts.
-   Avoid inventing product claims, materials, discounts or
    availability.
-   Support content variations and scheduling.

### 6.4 Social publishing

Initial targets: - Facebook Pages. - Instagram professional accounts,
subject to applicable Meta permissions and publishing requirements.

Capabilities: - Prepare and schedule posts. - Publish text and supported
media formats. - Check platform-specific requirements before
submission. - Track scheduled, submitted, published, failed and
uncertain states. - Verify publication using returned platform
identifiers or subsequent reads where possible. - Retry transient
failures safely without duplicate posts.

### 6.5 Commerce integrations and synchronisation

Initial targets: - Shopify. - Bumpa, conditional on verified API access
and documented capabilities.

Build provider adapters rather than embedding provider-specific logic
throughout the application. Validate authentication, scopes, rate
limits, webhooks, pagination, API versions, commercial requirements and
supported objects before committing to functionality.

Do not fabricate Bumpa endpoints or capabilities. If official API access
is unavailable or insufficient, clearly mark the integration as blocked
or limited. Do not substitute scraping or browser automation without
explicit approval and a compliance review.

### 6.6 Sales intelligence

Collect and report: - Gross sales. - Discounts. - Net sales. - Orders by
status. - Paid, pending and cancelled orders. - Refunds and returns. -
Cash collected, where verifiable. - Average order value. - Units sold. -
Top products. - Sales by channel. - Trends against comparable periods.

Clearly distinguish revenue, cash collected, profit and bank balance. Do
not infer one from another.

### 6.7 Business economics

Support: - Product purchase or production costs. - Cost of goods sold
(COGS). - Packaging and delivery costs. - Payment processing fees. -
Advertising and marketing expenses. - Rent, utilities, payroll and other
operating expenses. - Cost allocation to products, orders, channels and
periods. - Gross profit and gross margin. - Contribution margin. -
Operating profit and operating margin. - Break-even analysis. - Unit
economics. - Cash-flow visibility.

Use deterministic calculation services and validated source records. Do
not present net profit as authoritative if material cost or expense
categories are missing. Clearly label estimates and assumptions.

### 6.8 Business planning

Support: - Revenue and profit targets. - Monthly and quarterly
budgets. - Expense limits. - Inventory and purchasing plans. - Marketing
plans. - Staffing and operational plans. - Milestones and KPIs. -
Actual-versus-plan variance analysis.

Plans should be versioned, attributable and subject to merchant approval
when they create commitments or materially change business rules.

### 6.9 Forecasting and scenarios

Forecast: - Revenue. - Product demand. - Inventory requirements. -
Expenses. - Cash flow. - Profitability.

Provide base, optimistic and downside scenarios where data supports
them. Display assumptions, date ranges, confidence/uncertainty and
limitations. Compare forecasts with actual results using appropriate
measures, such as WAPE where suitable, and compare against a simple
baseline.

An LLM must not be the sole forecasting or calculation engine. Use
appropriate statistical or forecasting methods and evaluate them against
historical data.

### 6.10 Business advisory

The agent may identify: - Unusual changes in sales or refunds. -
Products with deteriorating margins. - Stock-out or overstock risks. -
Budget overruns. - Cash-flow pressure. - Opportunities to improve
product or channel performance.

Recommendations must cite the underlying data, state assumptions and
distinguish facts from hypotheses. The agent should not make unsupported
guarantees.

## 7. Autonomy and permission architecture

Implement a dedicated policy engine separate from the LLM.

### 7.1 Execution lifecycle

1.  Receive request, event or scheduled trigger.
2.  Resolve merchant, identity, context and relevant records.
3.  Build a structured task plan.
4.  Classify actions and risk.
5.  Check scopes, permissions, thresholds and policy version.
6.  Execute through an authorised tool or integration.
7.  Verify the result independently.
8.  Persist task, evidence, audit and outcome.
9.  Notify the merchant when appropriate.
10. Escalate failures, ambiguity or out-of-policy actions.

### 7.2 Default action policy

  -----------------------------------------------------------------------
  Action                              Default treatment
  ----------------------------------- -----------------------------------
  Generate product descriptions and   Autonomous
  captions                            

  Prepare routine reports             Autonomous

  Categorise expenses with confidence Autonomous, uncertain items flagged
  scoring                             

  Publish within an approved schedule Autonomous
  and rules                           

  Sync product data within agreed     Autonomous
  rules                               

  Change price beyond configured      Approval required
  threshold                           

  Delete products or orders           Explicit approval

  Issue refunds or make payments      Explicit approval

  Change budgets or commit            Approval required
  expenditure                         

  Change account security or access   Explicit approval
  -----------------------------------------------------------------------

Merchant settings may impose stricter rules. They must not override
platform policies or applicable law.

### 7.3 Safety and reliability controls

-   Least-privilege integration scopes.
-   Explicit action permissions and expiry.
-   Material-change invalidation of prior approvals.
-   Idempotency keys for external mutations.
-   Retries with backoff and dead-letter handling.
-   Independent post-action verification.
-   Human-readable audit history.
-   Exception queue for uncertain or failed tasks.
-   Kill switch and revocation of permissions.
-   Rate and spend limits where relevant.

## 8. Hybrid data collection and data quality

### 8.1 Collection sources

  -----------------------------------------------------------------------
  Data                                Preferred source
  ----------------------------------- -----------------------------------
  Orders and sales                    Commerce API/webhooks

  Product and inventory records       Commerce API

  Payment fees and settlement         Payment integration or merchant
                                      input

  COGS and product costs              Product records, invoices or
                                      merchant input

  Advertising costs                   Ad platform integration or receipts

  Rent, utilities and payroll         Accounting integration, documents
                                      or merchant input

  Delivery and packaging              Logistics integration, supplier
                                      records or merchant input

  Targets and planning assumptions    WhatsApp conversation

  Forecast assumptions                Historical records plus merchant
                                      confirmation
  -----------------------------------------------------------------------

### 8.2 Provenance fields

Every financial record should include, as applicable: - `source_type` -
`source_system` - `source_record_id` - `merchant_id` - `occurred_at` -
`recorded_at` - `currency` - `amount` - `verification_status` -
`confidence_score` - `created_by` - `updated_by` -
`evidence_reference` - `reconciliation_status`

### 8.3 Data integrity

-   Preserve original source values and normalized values.
-   Do not overwrite source records silently.
-   Detect duplicates and conflicting records.
-   Keep unknown, zero and not-applicable distinct.
-   Track corrections and adjustment history.
-   Reconcile imported totals against provider totals where possible.
-   Support multi-currency records without silently mixing currencies.
-   Define accounting period and timezone handling explicitly.

## 9. System architecture

Use a modular, API-first, multi-tenant architecture.

### 9.1 Logical services

1.  Merchant and tenant service.
2.  Merchant capability and business profile service.
3.  WhatsApp channel adapter.
4.  Commerce and social integration adapters.
5.  Product catalogue service.
6.  Content and publishing service.
7.  AI orchestration and task planner.
8.  Autonomy policy and permission service.
9.  Data ingestion and normalization service.
10. Financial records and calculation service.
11. Planning and forecasting service.
12. Reporting and notification service.
13. Audit, observability and exception service.
14. Web dashboard and public/internal API.

### 9.2 Architecture rules

-   Separate AI reasoning from deterministic business logic.
-   Separate integration execution from policy enforcement.
-   Use asynchronous jobs for long-running workflows.
-   Use webhooks where supported and scheduled reconciliation as a
    fallback.
-   Design all external mutations for idempotency.
-   Use provider adapters and canonical internal models.
-   Enforce tenant isolation at every data access boundary.
-   Store credentials in a secure secrets facility; encrypt tokens at
    rest.
-   Never ask users to send passwords through WhatsApp.
-   Version APIs, policies, prompts and financial calculations.

### 9.3 Suggested technology stack

Treat these as recommendations, not instructions to replace an existing
working stack: - Backend: Python and FastAPI. - Frontend: Next.js and
React. - Database: PostgreSQL. - Queue/cache: Redis with Celery or an
equivalent worker system. - Object storage: S3-compatible storage. - AI:
model API with structured tool calling and schema validation. -
WhatsApp: official WhatsApp Business Platform / Cloud API. - Commerce:
Shopify Admin GraphQL API. - Social: Meta Graph API. - Deployment:
Docker and an appropriate cloud platform.

Codex must inspect the repository before selecting or changing
technologies.

## 10. Core data model

Retain existing relevant entities and add or adapt the following.

### Identity and configuration

-   users
-   merchants
-   merchant_members
-   business_profiles
-   merchant_capabilities
-   roles
-   permissions
-   connected_accounts
-   oauth_credentials
-   autonomy_policies
-   action_permissions

### Commerce

-   products
-   product_variants
-   product_media
-   channel_product_mappings
-   inventory_items
-   inventory_movements
-   orders
-   order_items
-   payments
-   refunds
-   returns

### Content and execution

-   posts
-   post_media
-   publishing_schedules
-   publishing_results
-   conversations
-   messages
-   tasks
-   task_steps
-   execution_runs
-   approvals
-   exception_queue
-   audit_logs

### Economics and planning

-   financial_records
-   expenses
-   cost_records
-   cost_allocations
-   receipts
-   data_sources
-   data_quality_issues
-   budgets
-   business_plans
-   targets
-   KPIs
-   business_assumptions
-   forecasts
-   forecast_versions
-   forecast_actuals
-   reports
-   notifications

Define relationships, constraints, indexes, currency handling, tenant
scoping, soft-delete rules and retention policies in the database
design.

## 11. Integrations and external dependencies

### WhatsApp

Use the official WhatsApp Business Platform. Validate webhook
signatures, message types, media retrieval, template requirements, rate
limits, delivery states and opt-in requirements.

### Shopify

Use the official Admin GraphQL API and current supported API version.
Validate scopes, pagination, webhooks, rate limits and object coverage.

Documentation: https://shopify.dev/docs/api/admin-graphql

### Bumpa

Validate official API availability, access requirements, authentication,
supported product/order objects, webhooks, rate limits, commercial terms
and sandbox/testing options.

Documentation: https://developer.getbumpa.com/

Bumpa functionality is conditional on actual access and verified
capabilities. Do not represent a planned or mocked connector as
production-ready.

### Meta

Validate current requirements for Facebook Pages and Instagram
professional account publishing, permissions, app review and media
constraints.

Documentation: - https://developers.facebook.com/docs/graph-api/ -
https://developers.facebook.com/docs/instagram-platform/content-publishing/

## 12. Security, privacy and compliance

-   Enforce tenant isolation and role-based access control.
-   Encrypt credentials and sensitive data at rest and in transit.
-   Apply least-privilege OAuth scopes.
-   Validate webhook signatures and incoming payloads.
-   Protect against prompt injection in messages, documents and
    retrieved content.
-   Treat uploaded content and platform data as untrusted input.
-   Keep secrets out of prompts, logs and user-visible responses.
-   Maintain auditable records of sensitive actions.
-   Support permission revocation and account disconnection.
-   Define retention, deletion, export and incident-response procedures.
-   Assess applicable Nigerian data protection obligations and other
    jurisdictions before expansion.
-   Do not claim legal compliance without a documented assessment.

## 13. MVP definition

### Included

-   WhatsApp onboarding and merchant profile.
-   Merchant capability configuration.
-   Product creation from text and media.
-   Product catalogue management.
-   AI descriptions and social captions.
-   Facebook Page and Instagram professional publishing where approved.
-   Shopify integration.
-   Bumpa integration only if official access and capabilities are
    verified.
-   Scheduling and autonomous publishing within merchant-approved rules.
-   Execution verification, retries and task history.
-   Sales/order ingestion.
-   Daily sales report.
-   Basic product/channel performance.
-   Conversational expense and cost collection.
-   Basic financial data provenance and missing-data indicators.
-   Basic web dashboard and autonomy settings.

### Excluded from initial MVP

-   Payment processing and custody of funds.
-   Autonomous refunds or payments.
-   Full accounting or ERP.
-   Payroll processing.
-   Advanced inventory optimization.
-   Advertising campaign management.
-   Automatic price optimization.
-   Complex multi-entity consolidation.
-   Full forecasting before sufficient validated history exists.

## 14. Roadmap

The following is a proposed sequence. Re-estimate after repository
inspection, integration validation and team-capacity assessment.

  -------------------------------------------------------------------------
  Phase                           Target Deliverables      Exit condition
  ---------------- --------------------- ----------------- ----------------
  0\. Foundation              Weeks 1--3 Repo assessment,  Verified scope
  and validation                         architecture,     and
                                         data model, API   implementation
                                         validation,       plan
                                         security and test 
                                         foundation        

  1\. Autonomous              Weeks 4--9 WhatsApp          Reliable product
  commerce                               onboarding,       management and
                                         products,         publishing
                                         content,          
                                         publishing,       
                                         Shopify and       
                                         conditional       
                                         Bumpa, autonomy   
                                         policies          

  2\. Sales                 Weeks 10--13 Order ingestion,  Traceable,
  intelligence                           reconciliation,   reconciled sales
                                         daily reports,    reporting
                                         sales trends and  
                                         alerts            

  3\. Business              Weeks 14--19 Hybrid expense    Explainable
  economics                              collection,       profitability
                                         receipts, COGS,   with
                                         margins,          missing-data
                                         operating costs   controls
                                         and cash-flow     
                                         visibility        

  4\. Planning and          Weeks 20--25 Targets, budgets, Plans can be
  management                             plans, KPIs and   created and
                                         variance analysis monitored

  5\. Forecasting           Weeks 26--33 Demand, revenue,  Forecasts
  and decision                           inventory,        evaluated
  intelligence                           cash-flow and     against
                                         profit forecasts, baselines and
                                         scenarios and     actuals
                                         advisory          

  6\. Expansion         After validation Multi-store,      Multi-segment
                                         advanced          scale without
                                         integrations,     platform
                                         industry          fragmentation
                                         configurations    
                                         and enterprise    
                                         controls          
  -------------------------------------------------------------------------

## 15. MVP acceptance criteria

1.  A merchant can onboard through WhatsApp and establish a valid
    business profile.
2.  Merchant data is isolated from all other tenants.
3.  Products can be created and updated through supported conversational
    workflows.
4.  The agent generates content grounded in product facts.
5.  Publishing occurs only through supported official APIs and
    configured permissions.
6.  The system verifies publishing outcomes and does not claim success
    based only on an LLM response.
7.  Retries do not create duplicate external mutations.
8.  Sales and orders are ingested with source identifiers and
    timestamps.
9.  Reports distinguish gross sales, discounts, net sales, refunds and
    cash collected.
10. Duplicate and conflicting records are detected or surfaced.
11. Merchants can submit expenses and costs through WhatsApp.
12. Financial calculations are deterministic and traceable.
13. Unknown costs are not silently treated as zero.
14. Routine actions execute within the autonomy policy.
15. Sensitive or out-of-policy actions are escalated.
16. Merchants can inspect task history and revoke permissions.
17. Failed tasks enter a recoverable exception workflow.

## 16. Testing strategy

Create unit, integration, contract, security, end-to-end and operational
tests.

Important scenarios: - New merchant onboarding and tenant isolation. -
Text, voice, image and document ingestion. - Product creation with
missing attributes. - Duplicate product and order events. - Platform API
timeout and rate limiting. - Token expiry and revoked permissions. -
Scheduled publishing and retry. - Publishing accepted but not
verified. - Out-of-policy price change. - Destructive action requiring
approval. - Sales reconciliation against platform totals. - Refund and
cancellation treatment. - Missing COGS and partial expense records. -
Multi-currency and timezone handling. - Receipt extraction with low
confidence. - Forecast backtesting against a baseline. - Data export and
account disconnection.

## 17. KPIs

### Product and execution

-   Successful task completion rate.
-   Verified publishing success rate.
-   Task failure and retry rate.
-   Median time to complete common tasks.
-   Duplicate external mutation rate.
-   Exception resolution time.

### Data and financial quality

-   Order ingestion completeness.
-   Sales reconciliation variance.
-   Duplicate transaction rate.
-   Expense classification accuracy.
-   Percentage of financial totals with traceable sources.
-   Percentage of merchants with sufficient data for each financial
    metric.

### Business value

-   Time saved on commerce operations.
-   Merchant active usage and retention.
-   Number of workflows completed autonomously.
-   Adoption of business economics and planning features.
-   Forecast accuracy versus baseline when forecasting is introduced.

## 18. Codex implementation requirements

Codex must: 1. Inspect the existing repository before changing code. 2.
Identify current stack, conventions, tests, integrations and deployment
assumptions. 3. Compare the codebase with this specification. 4.
Identify technical gaps, dependencies, security risks and data-integrity
risks. 5. Validate all external API assumptions, especially Bumpa. 6.
Produce an implementation plan with dependencies and acceptance
criteria. 7. Implement incrementally and preserve existing working
functionality. 8. Build automated tests alongside features. 9. Avoid
mock success, fabricated endpoints and placeholder production claims.
10. Update implementation status and documentation as work proceeds.

Maintain these project documents: - `README.md` -
`MASTER_PRODUCT_SPECIFICATION.md` - `SYSTEM_ARCHITECTURE.md` -
`DATABASE_SCHEMA.md` - `API_DOCUMENTATION.md` -
`INTEGRATION_DOCUMENTATION.md` - `AI_AGENT_SPECIFICATION.md` -
`AUTONOMY_POLICY.md` - `DATA_COLLECTION_AND_FINANCIAL_INTEGRITY.md` -
`USER_STORIES.md` - `DEVELOPMENT_ROADMAP.md` - `TESTING_STRATEGY.md` -
`SECURITY.md` - `CHANGELOG.md` - `IMPLEMENTATION_STATUS.md`

## 19. End-to-end merchant journey

A merchant should eventually be able to: 1. Onboard through WhatsApp. 2.
Connect supported commerce and social accounts. 3. Send product images
and details. 4. Have the agent create product records and channel
listings. 5. Generate and publish content within configured rules. 6.
Receive and monitor orders and sales. 7. Receive daily performance
summaries. 8. Submit receipts, supplier costs and operating expenses
conversationally. 9. Understand product and business profitability. 10.
Set targets and budgets. 11. Monitor progress and receive exception
alerts. 12. Review forecasts and scenarios. 13. Authorise or restrict
actions through clear autonomy settings.

## 20. Final positioning

**CommercePilot AI is an autonomous commerce operations and business
intelligence agent that helps merchants run, understand and grow their
businesses through WhatsApp.**

Its core value is not simply generating content or answering questions.
It is completing authorised business workflows, maintaining a
trustworthy view of business performance and helping merchants make
better decisions.
