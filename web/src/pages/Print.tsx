import { Link } from "react-router-dom";
import { Printer } from "lucide-react";
import { Brand, PropertyFacts, Completeness, Citations } from "../components";
import { FindingCard } from "./Findings";
import { CoOwnership } from "./CoOwnership";
import { Questions } from "./Questions";
import type { DossierSnapshotResponse as Dossier } from "../contracts";
import { label, kind, date, safeUri } from "../copy";
export function PrintDossier({ data }: { data: Dossier }) {
  const sources = Array.from(
    new Map(
      data.findings
        .flatMap((f) => f.sources)
        .concat(data.evidence.flatMap((e) => e.sources))
        .map((s) => [JSON.stringify(s), s]),
    ).values(),
  );
  return (
    <main id="main" className="print-dossier">
      <div className="print-controls">
        <Link to={`/workspaces/${data.workspace.id}/overview`}>
          Back to dossier
        </Link>
        <button className="button" onClick={() => window.print()}>
          <Printer size={16} />
          Print / Save as PDF
        </button>
      </div>
      <Brand />
      <div className="eyebrow">
        Buyer dossier · Prepared for notary review{" "}
        {data.is_demo ? "· DEMO DATA" : ""}
      </div>
      <h1>{data.property.address ?? "Property review"}</h1>
      <p>
        Generated {date(new Date().toISOString())} · Dossier updated{" "}
        {date(data.last_updated)}
      </p>
      <PropertyFacts property={data.property} />
      <Completeness value={data.completeness} />
      <h2>Unresolved findings</h2>
      {data.findings.length ? (
        data.findings.map((f) => (
          <FindingCard key={f.id} finding={f} wid={data.workspace.id} />
        ))
      ) : (
        <p>No current findings from the information analyzed so far.</p>
      )}
      <h2>Missing and conditional information</h2>
      {data.requirements
        .filter(
          (r) => r.presence !== "PRESENT" || r.applicability === "CONDITIONAL",
        )
        .map((r, i) => (
          <p key={i}>
            {kind(r.kind)} · {label(r.applicability)} · {label(r.presence)}.{" "}
            {r.reason}
          </p>
        ))}
      <h2>Documents supplied</h2>
      {data.documents.map((d) => (
        <p key={d.id}>
          {d.filename} · {kind(d.kind)} · {label(d.status)} ·{" "}
          {label(d.association)}. {d.summary.join("; ")}
        </p>
      ))}
      {data.co_ownership && <CoOwnership co={data.co_ownership} data={data} />}
      <Questions data={data} />
      <h2>Source list</h2>
      {data.property.sources.map((source) => (
        <p key={source.provider}>
          <a href={safeUri(source.source_reference)}>
            {source.attribution_text}
          </a>{" "}
          · {date(source.retrieved_at)} ·{" "}
          <a href={safeUri(source.terms_reference)}>
            Published reuse conditions
          </a>
        </p>
      ))}
      <Citations sources={sources} wid={data.workspace.id} />
      <footer className="print-footer">
        Viesett provides automated property and document information assistance.
        Legally significant decisions and binding documents should be reviewed
        with your Belgian notary or another qualified professional.
      </footer>
    </main>
  );
}
