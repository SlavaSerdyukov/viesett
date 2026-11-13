import { Link } from "react-router-dom";
import { useLayoutEffect, useRef } from "react";
import { Printer } from "lucide-react";
import { Brand, PropertyFacts, Completeness, Citations } from "../components";
import { FindingCard } from "./Findings";
import { CoOwnership } from "./CoOwnership";
import { Questions } from "./Questions";
import type { DossierSnapshotResponse as Dossier } from "../contracts";
import { label, kind, date, safeUri } from "../copy";
import { Requirements } from "../Requirements";
export function PrintDossier({ data }: { data: Dossier }) {
  const root = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    root.current?.querySelectorAll("details").forEach((detail) => {
      detail.open = true;
    });
  }, [data]);
  const sources = Array.from(
    new Map(
      data.findings
        .flatMap((f) => f.sources)
        .concat(data.evidence.flatMap((e) => e.sources))
        .map((s) => [JSON.stringify(s), s]),
    ).values(),
  );
  return (
    <main id="main" className="print-dossier" ref={root}>
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
        Generated {date(new Date().toISOString())} · Information evaluated{" "}
        {date(data.evaluation_date)} · Dossier updated {date(data.last_updated)}
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
      <h2>Document checklist</h2>
      <Requirements items={data.requirements} interactive={false} />
      <h2>Documents supplied</h2>
      {data.documents.map((d) => (
        <p key={d.id}>
          {d.filename} · {kind(d.kind)} · {label(d.status)} ·{" "}
          {label(d.association)}. {d.summary.join("; ")}
        </p>
      ))}
      {!!data.context_answers?.length && (
        <section>
          <h2>Buyer-provided transaction context · Unverified</h2>
          {data.context_answers.map((a) => (
            <p key={a.evidence_id}>
              Signed deed date {date(a.value)}. Any provisional timeline based
              on this answer needs confirmation against the deed or with the
              notary.
            </p>
          ))}
        </section>
      )}
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
