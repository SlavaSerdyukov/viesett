# Viesett architecture

A modular monolith: FastAPI and Pydantic v2 at the boundary, explicit application services, async SQLAlchemy 2, PostgreSQL as authoritative persistence, Alembic migrations, provider-neutral private storage and interpretation ports. Python 3.12+, uv lockfile, no Redis or microservices.

```mermaid
flowchart LR
    Buyer[Authenticated buyer] --> API[Versioned FastAPI]
    API --> Services[Ownership-scoped services]
    Services --> DB[(PostgreSQL)]
    Services --> Safety[Fail-closed safety pipeline]
    Safety --> Objects[(Private objects)]
    Services --> Selected[Selected ready-document sections]
    Selected -. optional .-> AI[Interpretation port]
    AI -. inferred proposals .-> Services
    DB --> Cleanup[Durable deletion tasks]
    Cleanup --> Objects
```

`api` owns HTTP dependencies and response allowlists. `domain` owns vocabulary, typed evidence and provenance validation. `services` owns authorization, transactions, exports and deletion. `db` is persistence, not a generic repository framework. `document_safety`, `storage`, and `ai` contain narrow replaceable boundaries.

Account identity is just a random UUID and creation time. No names, mail addresses or national identifiers are required. API-token hashes and expiry are separate. One account owns many property workspaces. Workspace children contain a workspace UUID rather than copied account identity. Composite foreign keys prevent evidence pointing at another workspace's documents and findings linking another workspace's evidence. UUIDs are random, never user-selected paths or emails.

All private routes require bearer authentication through a router dependency. Ownership checks filter by caller and workspace together; foreign and absent IDs return identical 404 bodies. Document queries also filter by workspace. The same user cannot mix references between their own dossiers. Mutations lock the workspace and account to serialize upload/delete activity. PostgreSQL constraints are a second line of defence. No row-level-security claim is made: the application is the authorization boundary and the DB service role must remain private.

Tokens have 384 random bits, are SHA-256 hashed at rest, expire, and are never returned by export. Hashing is appropriate for random high-entropy tokens; no password authentication exists. Local provisioning prints the token once and is disabled for production. Revocation is deletion of its database row; account deletion cascades all tokens. Public identity onboarding and recovery are intentionally deferred.

Evidence is append-only through the service API. Typed values, source kind, locator, authority and confidence are validated, never arbitrary authoritative LLM JSON. AI proposals have no authority field; the service fixes `INFERRED`. Official and documented values remain distinct immutable rows. A future dossier renderer must show authority and contradictory sources, not choose the latest inferred row as truth. Findings have explicit provenance and constrained references. `BLOCKING_DATA_GAP` means insufficient evidence to run a check, not a legal ban on purchase.

Upload uses raw bounded PDF requests, safe display filenames, opaque keys, workspace-scoped SHA-256 deduplication and explicit safety states. No OCR, classifier, commercial model SDK or rule engine is present. Default unavailable scanning quarantines uploads. Production startup requires reviewed safety adapters and checks enabled processors; runtime interpretation repeats the processor check. Defaults forbid customer-content training. Processor administration is operational, not exposed to buyers.

Filesystem and database transactions cannot be atomic. Before writing an object, upload commits a durable cleanup reservation with a ten-minute lease, reacquires ownership/locks and rechecks duplicates. Successful metadata commit removes that reservation. Exceptions attempt immediate cleanup; crashes leave a scheduled task. The request has a maximum 120-second configurable timeout, safely below the lease. Run the purge command at least every ten minutes. Normal deletion atomically commits logical removal with immediate cleanup tasks, then removes bytes. Failures report pending erasure and retry idempotently. Objects never become API-accessible without a live document row and current authorization.

Metadata export is caller-scoped; binaries use a separate authenticated download. Archive retention is opt-in, not a statutory rule. No persistent application audit-content store exists; structured stdout only contains event name, method, status and random correlation ID. Configure sink access and retention separately from dossier retention; do not retain security logs indefinitely by default.

Locked workspace reads explicitly refresh SQLAlchemy's identity map after any earlier commit. Upload rechecks archive state and current attestation after its cleanup reservation. Scheduled purge rechecks archive status and cutoff under the deletion lock, so a reactivated workspace is retained even if an earlier candidate query included it. Dedicated race regression tests exercise both cases.

Security middleware bounds actual body bytes as well as claimed length, rejects encoded bodies, limits time and request rate, generates correlation IDs, strips sensitive validation error details, and returns private/no-store headers on success and failure. Logs exclude request URLs, headers, tokens, filenames, raw bytes, extracted text and exception representations. SQL parameters are hidden and query timeouts are set. Uvicorn access logging must remain disabled. A bounded in-memory limiter serves a single worker; provide a shared limiter before scaling across processes. TLS termination, encrypted disks/backups and operational key management belong to deployment review.

Production docs endpoints are disabled; trusted hosts are explicit and CORS is absent. There is no automatic schema creation. `/health/ready` checks the migrated schema and production processor registry, and `/health/live` checks process liveness. Production starts only with reviewed injected safety adapters; the development Docker profile is not production approval.

Milestone 2 can add official-source adapters whose results enter the evidence service with precise locators. Milestone 3 can implement sandboxed parsing, reviewed scanners and deterministic rules. Milestone 4 can add cross-document analysis and dossier UX. No future provider implementation or empty microservice layer is included now.
