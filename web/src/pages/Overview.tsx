import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Completeness, PropertyFacts } from "../components";
import { Exposure } from "./CoOwnership";
import { TransactionContext } from "../TransactionContext";
import type { DossierSnapshotResponse as Dossier } from "../contracts";
import { kind, label, safeUri, componentLabel } from "../copy";
export function Overview({ data }: { data: Dossier }) {
  const missing = data.requirements.filter(
    (r) => r.applicability === "REQUIRED" && r.presence !== "PRESENT",
  );
  const gaps =
    data.co_ownership?.article_3_94_completeness.filter((c) =>
      ["MISSING", "PARTIAL", "UNPARSEABLE"].includes(c.status),
    ) ?? [];
  return (
    <>
      <div className="intro-line">
        <h2>A clearer picture of your next home.</h2>
        <span>Review before a binding offer</span>
      </div>
      <Completeness value={data.completeness} />
      <TransactionContext data={data} />
      <div className="overview-columns">
        <section className="panel">
          <div className="section-heading">
            <h2>Needs attention</h2>
            <span className="count">
              {data.findings.filter((f) => f.severity !== "INFO").length}
            </span>
          </div>
          {data.findings.length ? (
            data.findings.slice(0, 3).map((f) => (
              <div className="attention-row" key={f.id}>
                <span
                  className={`status-dot ${f.severity === "WARNING" ? "amber" : ""}`}
                />
                <div>
                  <strong>{f.title}</strong>
                  <p>
                    {f.group} · {label(f.severity)}
                  </p>
                </div>
              </div>
            ))
          ) : (
            <p className="muted">
              No current findings from the information analyzed so far. This
              does not guarantee the property has no issues.
            </p>
          )}
          <Link
            className="text-button"
            to={`/workspaces/${data.workspace.id}/findings`}
          >
            Review findings <ArrowRight size={15} />
          </Link>
        </section>
        <section className="panel">
          <div className="section-heading">
            <h2>Missing information</h2>
            <span className="count">{missing.length + gaps.length}</span>
          </div>
          {missing.length + gaps.length ? (
            <>
              <p>
                These items need more information before the relevant checks can
                be completed.
              </p>
              <ul className="missing-list">
                {missing.map((r, i) => (
                  <li key={i}>{kind(r.kind)}</li>
                ))}
                {gaps.slice(0, 3).map((g) => (
                  <li key={g.code}>{componentLabel(g.code)}</li>
                ))}
              </ul>
            </>
          ) : (
            <p>
              Check Documents for conditional requirements and source usability.
            </p>
          )}
          <Link
            className="text-button"
            to={`/workspaces/${data.workspace.id}/documents`}
          >
            Review document checklist <ArrowRight size={15} />
          </Link>
        </section>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>Property facts</h2>
          <span className="small muted">
            According to the available official records
          </span>
        </div>
        <PropertyFacts property={data.property} />
        {data.property.source_states.some(
          (s) =>
            s.provider === "HERITAGE" && s.current_refresh_status === "SUCCESS",
        ) ? (
          <p>
            {data.property.heritage.length
              ? `${data.property.heritage.length} heritage record(s) matched the selected area. Review their published status and source.`
              : "No matching heritage designation or inventory record returned for the selected area."}
          </p>
        ) : (
          <p className="muted">
            Heritage information has not been confirmed. Refresh public
            information when the source is available.
          </p>
        )}
        {data.property.sources.map((s) => (
          <a
            className="small source-credit"
            href={safeUri(s.source_reference)}
            key={s.provider}
            target="_blank"
            rel="noreferrer"
          >
            {s.attribution_text}
          </a>
        ))}
      </section>
      {data.co_ownership?.financial_exposure_estimates.length ? (
        <section>
          <div className="section-heading">
            <h2>Major works &amp; potential exposure</h2>
            <Link to={`/workspaces/${data.workspace.id}/co-ownership`}>
              View co-ownership
            </Link>
          </div>
          <Exposure co={data.co_ownership} data={data} />
        </section>
      ) : null}
      <section className="next-action">
        <div>
          <div className="eyebrow">Your next step</div>
          <h2>Turn open points into the right questions.</h2>
          <p>
            Prepare a focused conversation with the seller, syndic or notary.
          </p>
        </div>
        <Link
          className="button"
          to={`/workspaces/${data.workspace.id}/questions`}
        >
          Review your questions <ArrowRight size={16} />
        </Link>
      </section>
    </>
  );
}
