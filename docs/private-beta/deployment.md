# Controlled private-beta profile

This is a deployment preparation profile, **not a deployed or legally approved service**. M1 production safety/processor/hosting gates remain. No real buyer evaluation or customer corpus was available in M6.

Use a dedicated real-data database and absolute private storage root, separated from every demo database/root. Copy [.env.private-beta.example](../../.env.private-beta.example) to the gitignored `.env.private-beta.local` and fill values outside Git. Empty template values deliberately fail validation. Settings are supplied through the process environment; no other project's `.env` is read.

| Configuration | Required private-beta behavior |
| --- | --- |
| `VIESETT_ENVIRONMENT=production`, `VIESETT_PRIVATE_BETA=true` | Production guards plus beta constraints |
| `VIESETT_DATABASE_URL` | Dedicated PostgreSQL credentials/connection, not development defaults |
| `VIESETT_STORAGE_ROOT` | Absolute private path; not repo root, web files or the shared default object directory |
| `VIESETT_ALLOWED_HOSTS`, `VIESETT_WEB_ORIGINS` | Nonempty exact production host/HTTPS-origin allowlists, no wildcard or URL path |
| `VIESETT_BROWSER_SESSIONS_ENABLED=true` | Operator-token exchange and session restoration |
| `VIESETT_BROWSER_COOKIE_SECURE=true` | HttpOnly/Secure/SameSite=Strict host cookie |
| `VIESETT_BROWSER_SESSION_HOURS` | 1–24, default 8, also bounded by parent token expiry |
| `VIESETT_APPLICATION_WORKERS=1` / `WEB_CONCURRENCY` | One application worker; inconsistent >1 settings fail |
| `VIESETT_OFFICIAL_SOURCES_REVIEWED` | Explicit reviewed operational decision if official sources are enabled; not consent/counsel approval |
| `VIESETT_GRAR_API_KEY` | Optional assigned-plan secret, backend only |
| demo/development session/safety flags | All false; startup rejects persisted demo markers |

The chosen deployment option is **one worker**. A dedicated PostgreSQL connection holds a session advisory lock for the lifespan; a second worker/instance sharing this beta DB fails closed. The lock requires session-affine/direct database connectivity. Do not use a transaction-pooled proxy for it. This enforces the existing process-local provider/preview/session limiters without adding Redis. A future multi-worker/public deployment requires a shared limiting design and new verification.

Keep the process manager at one worker and restart that worker as part of database restart/failover recovery before resuming evaluation; the advisory lock is a session-based startup guard, not an independent distributed supervisor.

After configuration and prior production gates are actually satisfied, the intended command is:

```sh
uv run alembic upgrade head
uv run uvicorn viesett.beta:create_beta_app --factory --workers 1 --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

Serve the frontend production build and `/api` on one reviewed TLS origin. Configure request/body/time limits and private/no-store behavior at the edge; keep private objects outside static roots. Default peer-based limiting may share a bucket behind a proxy. Forward client identity only through an explicit trusted-proxy design; arbitrary forwarded headers must not bypass limits.

M6 did not deploy TLS, issue real tester credentials, select production processors or implement a reviewed malware/sensitive-content adapter. The existing default production pipeline still refuses startup without those adapters. Complete [the checklist](checklist.md), confirm actual live/provider and authorized-document behavior, and resolve the privacy/operational gates before real-data use. Account/token provisioning, revocation, deletion/export, backups and incidents need named operator procedures. Browser token entry is private access, not public signup/recovery.
