# Private-beta operational checklist

This checklist records work to verify for the actual deployment. M6 local tests do not check these boxes on behalf of an operator and do not provide legal approval.

- [ ] Name the operator, controller/contact and authorized private tester cohort; keep public signup disabled.
- [ ] Use the fail-closed beta factory, reviewed production settings and exactly one worker; verify duplicate-worker rejection on the actual database connection/pool.
- [ ] Use a dedicated migrated real-data PostgreSQL database; verify M5→M6 preservation and current schema readiness.
- [ ] Separate private storage and backups from demo/static/build directories; verify permissions, encryption/access, bounded capacity and restoration.
- [ ] Keep database/provider secrets outside Git/logs/browser bundles; define issuance, expiry, rotation and revocation procedures.
- [ ] Verify actual TLS, host/origin allowlists, same-origin frontend/API delivery and request/body limits.
- [ ] Check HttpOnly/Secure/SameSite cookies, parent/session expiry, reload, logout, CSRF failures and Origin rejection in the deployed browser.
- [ ] Keep demo/development bootstrap/safety flags off; confirm the real-data database contains no demo marker.
- [ ] Install/review the production malware/sensitive-content adapters and any processors; satisfy the existing startup guards, access/location/transfer and no-training requirements.
- [ ] Repeat the opt-in official-source smoke from the deployment network; record real status, key plan/limits, attribution and any source failures. One M6 success is not an uptime guarantee.
- [ ] Review/finalize the privacy notice, cookie/session transparency, bases/roles, Article 14 and rights/restriction procedures with qualified review; do not publish draft placeholders.
- [ ] Define document/dossier, expired/revoked session metadata, security-log and backup retention/cleanup responsibilities; do not invent statutory retention.
- [ ] Demonstrate owner-only export and source/workspace/account deletion, including physical cleanup retries and backup expiry.
- [ ] Record an authorized compatibility sample and its OCR/partial/unsupported rates using local aggregate tooling; retain no customer PDFs in Git.
- [ ] Run real-device/browser smoke, including Firefox where supported, keyboard/focus, native PDF fallback and a notary print sample.
- [ ] Establish incident detection, containment, access suspension, notification assessment and a tested recovery/contact procedure.
- [ ] Run the [buyer evaluation tasks](evaluation-guide.md); keep observation notes outside the product and report misunderstandings rather than inferring trust from automated tests.

Known M6 boundaries: no deployed/hosted beta validation, no real authorized corpus or buyer study, Firefox unable to launch on this local host, and prior production/legal review gates still open. No M7 feature work is implied by this list.
