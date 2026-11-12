# Print dossier and notary handoff

`/workspaces/{id}/print` is the browser-printable version of the same authorized product snapshot. “Prepare for notary” opens it in the current SPA session; “Print / Save as PDF” invokes the browser. There is no server PDF engine, notary integration, public sharing URL, external account or automatic email.

The view contains property identity and refresh date, generated date, completeness counts, unresolved findings, missing/conditional items, document summaries, available co-ownership/funds/coverage/works/calls/litigation, proportional estimates and assumptions, grouped questions and source/attribution references. Demo labels remain visible. A single concise footer directs legally significant decisions and binding documents to the buyer's Belgian notary or qualified professional; it makes no certification claim.

The print data is obtained from the owner-only dossier endpoint, never an anonymous route. Other users cannot fetch its underlying data or PDFs. Source links contain opaque document identifiers/public official URLs, never bearer tokens or storage keys. If a print route is opened after reloading or in a new tab, the in-memory credential must be re-entered. This is an explicit limitation of the development evaluation bridge.

Responsive styling and print CSS hide navigation/action controls, preserve readable headings and source lists, and reduce card splitting. Exact pagination and native PDF page jumping remain browser-dependent. Browser automation verifies the route, source links, print action and readable desktop/mobile layouts; it does not certify every browser/printer combination or text-coordinate highlighting.
