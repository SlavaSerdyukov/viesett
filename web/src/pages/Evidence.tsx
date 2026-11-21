import { Citations, Empty, PageIntro } from "../components";
import { Exposure } from "./CoOwnership";
import type { DossierSnapshotResponse as Dossier } from "../contracts";
import { date } from "../copy";
import { EvidenceSourceDetails, referenceFact } from "../EvidenceSourceDetails";
export function Evidence({ data }: { data: Dossier }) {
  return (
    <>
      <PageIntro
        title="Follow the facts to their source"
        description="Current facts from official records, uploaded documents and explicit derivations. Historical details remain in your private export."
      />
      {(["OFFICIAL", "DOCUMENTED", "INFERRED", "UNVERIFIED"] as const).map(
        (authority) => {
          const rows = data.evidence.filter((e) => e.authority === authority);
          return rows.length ? (
            <section className="panel" key={authority}>
              <h2>
                {authority === "OFFICIAL"
                  ? "Official records"
                  : authority === "DOCUMENTED"
                    ? "From documents"
                    : authority === "INFERRED"
                      ? "Derived / inferred"
                      : "Unverified information"}
              </h2>
              {rows.map((e) => (
                <div className="evidence-row" key={e.id}>
                  <div>
                    <strong>{referenceFact(e)?.title ?? e.label}</strong>
                    {!referenceFact(e) && <p>{e.value}</p>}
                    <Citations sources={e.sources} wid={data.workspace.id} />
                    <EvidenceSourceDetails evidence={e} />
                  </div>
                  <span className="small muted">
                    {e.effective_date ? "Source date" : "Recorded"}{" "}
                    {date(e.effective_date ?? e.date)}
                  </span>
                </div>
              ))}
            </section>
          ) : null;
        },
      )}
      {data.co_ownership?.financial_exposure_estimates.length ? (
        <section>
          <h2>Derived / inferred calculations</h2>
          <Exposure co={data.co_ownership} data={data} />
        </section>
      ) : null}
      {!data.evidence.length && (
        <Empty
          title="No source facts yet"
          text="Resolve a property or add readable documents to begin building the evidence trail."
        />
      )}
    </>
  );
}
