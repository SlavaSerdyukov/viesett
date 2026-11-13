# Private browser sessions

M6 retains operator-provisioned API-token authority. It adds an optional opaque browser session, not public signup or final public authentication. The private-beta factory requires it; compatibility bearer APIs remain available.

1. The operator provisions access locally, outside application logs, using `viesett create-private-access` under the validated private-beta profile. This command does not bypass production startup/safety review.
2. The buyer enters that private token once in the page. `POST /api/v1/browser-session/exchange` requires an explicitly allowed Origin and the bearer header. It returns a CSRF token/expiry, never the original bearer or cookie secret.
3. The server stores only the SHA-256 hash of a random 384-bit session secret. The cookie carries the opaque secret: HttpOnly, SameSite=Strict, Path=/, no Domain. Production requires Secure and HTTPS origins and uses the `__Host-` prefix. Loopback HTTP demo testing explicitly uses Secure=false.
4. The server session references the account and its API token through a compound ownership FK. Expiration is the earlier of the parent expiry and the configured session lifetime (default 8 hours, maximum 24). Parent deletion/expiry, session revocation and account deletion reject further access.
5. Reload restores session/CSRF state through `GET /api/v1/browser-session`. The synchronizer token stays in page memory. No bearer, cookie secret or query cache is persisted in localStorage/sessionStorage/IndexedDB.
6. Logout calls the server before clearing private UI/cache. `POST /browser-session/logout` revokes the row and expires the cookie. If revocation fails, the UI reports the error instead of pretending logout succeeded. A new exchange rotates browser sessions for the same API token. The original operator API token is not consumed or silently invalidated; it can be revoked separately through existing account/operator procedures.

## CSRF and origin policy

Every cookie-authenticated mutation requires the per-session synchronizer token in `X-CSRF-Token` **and** an exact configured Origin; cross-site Fetch Metadata is rejected. Missing, wrong, oversized and non-ASCII CSRF input is safely denied. Session exchange is separately Origin-protected. SameSite and explicit credentialed CORS are additional controls, not substitutes for CSRF. An explicit invalid Authorization header never falls back to a valid cookie.

The implementation follows the [OWASP synchronizer-token guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) and [session-management guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html). This is a design reference, not an external security certification. Browser/API tests cover exchange, reload, expiry, rotation, revocation, ownership, origins and production cookie settings. No signed client-side session payload, JWT, new identity provider, password/email flow or analytics is introduced.

Cookie sessions require same-origin frontend/API delivery in the private-beta deployment. Avoid sharing that origin with unrelated applications. Authentication failures remove private UI state and focus reconnect; normal backend error bodies are discarded. Loggers/exports exclude tokens, CSRF values and session hashes. Session rows have bounded authentication validity; a reviewed operational retention/cleanup schedule for expired/revoked metadata is still needed. Account deletion cascades immediately.
