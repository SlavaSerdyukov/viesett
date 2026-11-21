import { useLayoutEffect, useRef } from "react";
import { Brand, PropertyFacts, Completeness } from "../components";
import { FindingCard } from "./Findings";
import { CoOwnership } from "./CoOwnership";
import { Questions } from "./Questions";
import type { DossierSnapshotResponse as Dossier } from "../contracts";
import { label, kind, date } from "../copy";
import { Requirements } from "../Requirements";
import { PrintActions, PrintDisclaimer } from "../PrintActions";
import { SourceAppendix } from "../SourceCitations";
import { fullDossierSources } from "../print-presentation";
export function PrintDossier({ data }: { data: Dossier }) {
  const root = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    root.current
      ?.querySelectorAll<HTMLDetailsElement>("details:not(.source-details)")
      .forEach((detail) => {
        detail.open = true;
      });
  }, [data]);
  return (
    <main id="main" className="print-dossier" ref={root}>
      <PrintActions wid={data.workspace.id} notary={false} />
      <Brand />
      <div className="eyebrow">
        Full buyer dossier {data.is_demo ? "· DEMO DATA" : ""}
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
      <SourceAppendix data={data} sources={fullDossierSources(data)} />
      <PrintDisclaimer />
    </main>
  );
}
