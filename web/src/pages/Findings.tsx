import { Badge, Citations, Empty, PageIntro } from "../components";
import type {
  FindingResponse,
  DossierSnapshotResponse as Dossier,
} from "../contracts";
export function FindingCard({
  finding,
  wid,
}: {
  finding: FindingResponse;
  wid: string;
}) {
  return (
    <article className="panel finding-card">
      <div className="finding-top">
        <Badge status={finding.severity} />
        <span className="small muted">{finding.group}</span>
      </div>
      <h3>{finding.title}</h3>
      <p>{finding.explanation}</p>
      <div className="clarify">
        <strong>What to clarify next</strong>
        <p>{finding.next_step}</p>
      </div>
      <details>
        <summary>Sources &amp; check details</summary>
        <Citations sources={finding.sources} wid={wid} />
        <p className="small muted">
          Check {finding.code} · version{" "}
          {finding.rule_version ?? "not supplied"}
        </p>
      </details>
    </article>
  );
}

export function Findings({ data }: { data: Dossier }) {
  const groups = [...new Set(data.findings.map((f) => f.group))];
  return (
    <>
      <PageIntro
        title="What needs a closer look"
        description="Open points from the available information, with sources and practical next steps."
      />
      {groups.length ? (
        groups.map((g) => (
          <section key={g}>
            <h2 className="group-title">{g}</h2>
            {data.findings
              .filter((f) => f.group === g)
              .map((f) => (
                <FindingCard key={f.id} finding={f} wid={data.workspace.id} />
              ))}
          </section>
        ))
      ) : (
        <Empty
          title="No current findings"
          text="No current findings from the information analyzed so far. This does not guarantee that the property has no issues."
        />
      )}
    </>
  );
}
