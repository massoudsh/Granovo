# Competitive analysis and adopted features

> Reviewed 2026-11-24. Purpose: identify what mature recycling and production-analytics
> products do well, and adopt only what Granovo can implement honestly without factory
> data, lab access, or a payments partner.

## Rivals reviewed

### International

| Product | What it is | Strength worth copying |
|---|---|---|
| **EREOMA PredictOn** ([source](https://www.erema.com/en/public-relations-news/new-intelligent-assistance-systems-for-more-uptime--3260)) | Assistance systems on recycling extruders (Drive, Plastification Unit) that watch the plasticising unit and flag drift before breakdown | Predictive-maintenance framing: uptime and availability, not only quality |
| **TOMRA Waste Analyzer / PolyPerception** ([source](https://www.tomra.com/waste-metal-recycling/products/digital-solutions/waste-analyzer)) | Camera-based end-to-end material tracking across a sorting line | Material-flow accounting: where mass is lost, by stream |
| **Cirplus** ([source](https://netzerocompare.com/software/cirplus)) | Recyclate marketplace with DIN SPEC 91446 grading and CIRPASS digital product passports | Standardised, verifiable batch documentation a buyer can check |
| **Recyda** ([source](https://recyda.com/)) | Packaging compliance and recyclability assessment, EPR reporting | Compliance framing and portfolio-level scores |
| **EverestLabs Navigator** ([source](https://everestlabs.ai/news/everestlabs-launches-first-ever-agentic-ai-platform-for-materials-processing-recovery-and-recycling-facilities)) | Multi-agent AI platform for MRFs | Guided onboarding and staged rollout of AI features |

### Iranian

| Product | What it is | Strength worth copying |
|---|---|---|
| **Bazmand** ([source](https://linkedin.com/company/146608305)) | Smart dry-waste collection linked to municipal service | Sit-to-collector supply chain, instant pricing and payment |
| **GAIN / businessscrap** ([source](https://businessscrap.com/who-we-are)) | AI/BI aggregator connecting households, collectors, and recyclers | Aggregation and supply matching across many small sources |
| **Pakdoon Clean Waste** ([source](https://cleanwaste.pakdoon.com/en)) | Waste-management and recycling services group | Operational service layers |
| **Sharif waste-management platform** ([source](https://www.tehrantimes.com/news/437172/Tech-solutions-for-waste-management-in-Iran)) | Municipal solid-waste platform, six web apps | Multi-tenant administration and reporting |
| **Iran Recycling System proposal** ([source](https://github.com/IranAzadAbad/ideas/discussions/15)) | Bilingual standards-based recycling map for citizens and centres | Bilingual, locally adapted standards |

Sector context: Iran generates about four million tonnes of plastic waste yearly
([Tehran Chamber](https://otaghiranonline.ir/news/70013/)), and the industry body for recyclers
is the [Iran Recycling Industries Federation](https://irfederation.ir/faq).

## The five features adopted

Chosen because they are the intersection of "every strong rival has this" and "Granovo can build
it truthfully today, without fabricated data".

### 1. Predictive maintenance and availability — from EREMA PredictOn

Rivals sell uptime, not just quality. Granovo now records downtime, maintenance, and quality-drift
events per machine and reports calendar-window availability and MTBF.

- `POST /api/downtime`, `GET /api/downtime`, `GET /api/availability`
- Honest scope: calendar availability, **not** OEE. It assumes a machine could run the entire
  window and does not model planned production hours or output quality.
- Guards: minutes must be 1–20160, dates cannot be in the future, machines are factory-scoped.

### 2. Recyclate price book and rejection-cost reporting — from Cirplus and Bazmand pricing

Both a marketplace and a collection service make the money legible. Granovo now keeps a
factory-owned price book and reports the cost of rejected mass.

- `PUT /api/prices`, `GET /api/prices`, `GET /api/value-report`
- Values are `your price × recorded mass` — not invoices, not market quotes.
- Currencies are reported per currency and **never summed together**, so an IRR and a USD figure
  cannot be silently added.

### 3. Digital quality passport — from Cirplus CIRPASS and R-Cycle

Buyers need to check a claim. Granovo issues a token-addressed passport for a quality-verified
batch, minted from an immutable snapshot plus a SHA-256 content hash.

- `POST /api/batches/{id}/passport`, `GET /api/passports`, `GET /public/passports/{token}`
- Public page shows the snapshot and recomputes the hash, so a tampered record reports
  `status: "tampered"` instead of appearing valid.
- Only `code`, date, polymer, purity, moisture, masses, and verification status are published —
  no factory ID, operator ID, or email.
- Explicitly **not** a legal, laboratory, or recycled-content certificate.

### 4. Onboarding readiness scorecard — from EverestLabs rollout and Sharif admin platform

Mature products guide setup instead of leaving an empty dashboard. A seven-item scorecard shows
what is still missing before a pilot.

- `GET /api/readiness`
- Tracks machine limits, batches, baseline data, eight verified batches, price book, downtime
  logs, and first passport.
- Describes data completeness only — never claims product quality or pilot success.

### 5. Confidence and expected range on recommendations — from EREMA assistance-system UX

Every rival that shows a prediction also shows how much to trust it. Recommendations now carry a
confidence level and the min–max range of the nearest historical neighbours.

- `predict()` returns `confidence` (`high`/`medium`/`low`) and `expected_range`.
- Still gated by at least eight verified sub-5% batches, range checks, and explicit operator
  approval. No machine control is added.

## Deliberately not adopted

- **Automatic extruder/PLC control (EREOMA):** requires certified safety engineering and real
  hardware validation. Out of scope for a pre-pilot product.
- **Camera/spectral polymer identification (TOMRA):** needs hardware and labelled images.
- **Marketplace settlement (Cirplus, Bazmand):** needs a payments and compliance partner.
- **Recycled-content certification (Cirplus, R-Cycle):** a legal attestation, not a software
  feature; shipping it would be misrepresentation.

## Verification

- 34 backend tests on SQLite, 56 on SQLite + PostgreSQL 17 (including backup restore)
- 13 browser-free dashboard tests
- New coverage: downtime validation and isolation, currency separation, passport tamper
  detection, readiness progression, cross-origin and CSRF rejection on the new routes
