# Granovo threat model

## Assets

- Factory identity and access sessions
- Production batch measurements and machine limits
- Model fingerprints, evaluation metrics and operator approvals
- Future images, quality measurements and commercial records

## Trust boundaries

1. Browser to API: all browser input is untrusted and must pass schema validation, same-origin checks and CSRF protection.
2. API to database: every operational query must be scoped by `factory_id`; database credentials are deployment-only secrets.
3. Historical data to model: only explicitly quality-verified, sub-5% batches for the same factory, machine and polymer enter the experimental dataset.
4. Recommendation to equipment: no integration exists; approval is an audit event and cannot control a machine.

## Threats and controls

| Threat | Control | Remaining work |
|---|---|---|
| Cross-factory data access | Factory-scoped queries and isolation tests | Roles and independent authorization review |
| Credential theft | scrypt passwords, opaque hashed sessions, Secure/HttpOnly/SameSite cookies | Password recovery and rotation |
| Cross-site request forgery | Same-origin check and CSRF token on state changes | Review deployment proxy configuration |
| Malicious or oversized CSV | Exact headers, Pydantic validation, row/size limits, atomic insert | Malware scanning if files become persistent |
| XSS through factory data | DOM text APIs; CSP and security headers | Browser accessibility/security audit |
| Unsafe model action | Machine range checks, data gate, stale fingerprint rejection, no PLC path | Independent process-safety review |
| Database outage | `/ready`, PostgreSQL integration and dump/restore test | Production backup schedule, retention and restore drill |
| Secret leakage | Ignored env/runtime files, CI gitleaks | Configure repository secret alerts |
| Dependency vulnerability | Dependabot, CodeQL and SBOM workflows | Review and triage alerts on each PR |

## Release gates

Do not deploy with real factory data until HTTPS termination, backup recovery, shared rate limiting, access roles, consent/retention policy, migration tooling and independent quality verification are complete. Do not describe the historical-neighbor estimator as a validated industrial ML model.
