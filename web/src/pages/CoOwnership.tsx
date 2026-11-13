import { Badge, Citations, Empty, PageIntro } from "../components";
import type {
  CoOwnershipSummaryResponse as CoSnapshot,
  DossierSnapshotResponse as Dossier,
} from "../contracts";
import { label, date, money, componentLabel } from "../copy";
export function Exposure({ co, data }: { co: CoSnapshot; data: Dossier }) {
  return (
    <div className="exposure-grid">
      {co.financial_exposure_estimates.map((e) => {
        const work = co.planned_works.find((w) => w.key === e.planned_work_key);
        return (
          <article className="panel exposure" key={e.planned_work_key}>
            <div className="eyebrow">Potential proportional exposure</div>
            <h3>{work ? label(work.category) : "Documented work"}</h3>
            {e.status === "CALCULATED" ? (
              <>
                <div className="exposure-amount">
                  {money(
                    e.estimated_proportional_amount?.amount,
                    e.estimated_proportional_amount?.currency,
                  )}
                </div>
                <dl className="calculation">
                  <div>
                    <dt>Approved project cost</dt>
                    <dd>
                      {money(
                        e.gross_project_cost?.amount,
                        e.gross_project_cost?.currency,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Explicit project funding</dt>
                    <dd>
                      {e.explicit_project_funding
                        ? money(
                            e.explicit_project_funding.amount,
                            e.explicit_project_funding.currency,
                          )
                        : "Not confirmed"}
                    </dd>
                  </div>
                  <div>
                    <dt>Remaining financing basis</dt>
                    <dd>
                      {money(
                        e.remaining_financing_basis?.amount,
                        e.remaining_financing_basis?.currency,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Documented applicable share</dt>
                    <dd>
                      {e.share?.original_representation ?? "Not established"}
                    </dd>
                  </div>
                  <div>
                    <dt>Gross proportional amount</dt>
                    <dd>
                      {money(
                        e.gross_proportional_amount?.amount,
                        e.gross_proportional_amount?.currency,
                      )}
                    </dd>
                  </div>
                </dl>
              </>
            ) : (
              <p>{label(e.status)}. A precise estimate is not available.</p>
            )}
            <p className="responsibility">
              Legal payment responsibility: <strong>Not determined</strong>
            </p>
            <details open>
              <summary>Assumptions &amp; sources</summary>
              <ul>
                {e.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
              <Citations
                wid={data.workspace.id}
                sources={data.evidence
                  .filter((f) => e.source_evidence_ids.includes(f.id))
                  .flatMap((f) => f.sources)}
              />
            </details>
          </article>
        );
      })}
    </div>
  );
}

export function CoOwnership({
  co,
  data,
}: {
  co: CoSnapshot | null;
  data: Dossier;
}) {
  if (!co || co.co_ownership_status === "NOT_ESTABLISHED")
    return (
      <Empty
        title="No co-ownership information identified"
        text="Add the syndic information and co-ownership documents if this property forms part of a co-ownership."
      />
    );
  return (
    <>
      <PageIntro
        title="The building beyond your front door"
        description="Co-ownership information, shared costs and decisions to understand before you buy."
      />
      <section className="panel">
        <div className="section-heading">
          <h2>{co.identity?.association_name ?? "Co-ownership association"}</h2>
          <Badge status={co.co_ownership_status} />
        </div>
        <dl className="facts">
          <div>
            <dt>Enterprise number</dt>
            <dd>{co.identity?.enterprise_number ?? "Not available"}</dd>
          </div>
          <div>
            <dt>Documented lot</dt>
            <dd>{co.identity?.lot_identifier ?? "Not confirmed"}</dd>
          </div>
          <div>
            <dt>Ownership share</dt>
            <dd>
              {co.identity?.ownership_share?.original_representation ??
                "Not confirmed"}
            </dd>
          </div>
          <div>
            <dt>Syndic</dt>
            <dd>{co.identity?.syndic_name ?? "Not supplied"}</dd>
          </div>
        </dl>
        <CoSources ids={co.identity?.evidence_ids ?? []} data={data} />
      </section>
      <section className="panel co-package">
        <h2>Article 3.94 information</h2>
        {co.article_3_94_completeness.map((c) => (
          <div className="checklist-row" key={c.code}>
            <div>
              <strong>{componentLabel(c.code)}</strong>
              <details>
                <summary>Context & sources</summary>
                <p>{c.reason}</p>
                <CoSources ids={c.evidence_ids} data={data} />
              </details>
              {c.coverage && (
                <p>
                  Coverage: {date(c.coverage.coverage_start)}–
                  {date(c.coverage.coverage_end)}
                  {c.coverage.gaps.length
                    ? ` · ${c.coverage.gaps.length} gap(s) in supplied coverage`
                    : " · documented coverage available"}
                </p>
              )}
            </div>
            <Badge status={c.status} />
          </div>
        ))}
      </section>
      <div className="fund-grid">
        {[
          ["Working capital", co.current_working_capital],
          ["Reserve capital", co.current_reserve_capital],
        ].map(([title, raw]) => {
          const value = raw as CoSnapshot["current_working_capital"];
          return (
            <section className="panel" key={String(title)}>
              <div className="eyebrow">{String(title)}</div>
              <h2>{money(value?.money.amount, value?.money.currency)}</h2>
              <p className="muted">
                {date(value?.effective_date)} ·{" "}
                {value
                  ? "Building amount"
                  : "Current building amount not established"}
              </p>
              <CoSources ids={value?.evidence_ids ?? []} data={data} />
            </section>
          );
        })}
      </div>
      <section className="panel">
        <h2>Planned works</h2>
        {co.planned_works.length ? (
          co.planned_works.map((w) => (
            <div className="checklist-row" key={w.key}>
              <div>
                <strong>{label(w.category)}</strong>
                <p>
                  {date(w.decision_date)} ·{" "}
                  {money(
                    w.approved_total_cost?.amount ??
                      w.estimated_total_cost?.amount,
                    w.approved_total_cost?.currency ??
                      w.estimated_total_cost?.currency,
                  )}
                </p>
              </div>
              <Badge status={w.decision_status} />
            </div>
          ))
        ) : (
          <p>No supported work decision has been identified.</p>
        )}
      </section>
      <Exposure co={co} data={data} />
      <section className="panel">
        <h2>Capital calls</h2>
        {co.capital_calls.length ? (
          co.capital_calls.map((c, i) => (
            <div className="checklist-row" key={i}>
              <div>
                <strong>{c.reference ?? "Documented capital call"}</strong>
                <p>
                  {label(c.fund_type)} · due {date(c.due_date)} · responsibility
                  needs confirmation
                </p>
                <CoSources ids={c.evidence_ids} data={data} />
              </div>
              <strong>
                {money(
                  c.lot_specific_amount?.amount ?? c.total?.amount,
                  c.lot_specific_amount?.currency ?? c.total?.currency,
                )}
              </strong>
            </div>
          ))
        ) : (
          <p>
            No structured capital call has been identified. Check the package's
            explicit call status above.
          </p>
        )}
        <h2>Pending litigation</h2>
        {co.pending_litigation.length ? (
          co.pending_litigation.map((l, i) => (
            <p key={i}>
              {label(l.subject_category)} ·{" "}
              {money(
                l.amount_in_dispute?.amount,
                l.amount_in_dispute?.currency,
              )}{" "}
              · Confirm status with the syndic/notary.
            </p>
          ))
        ) : (
          <p>
            No supported pending-case disclosure has been identified. Absence
            here is not confirmation that none exists.
          </p>
        )}
      </section>
    </>
  );
}

function CoSources({ ids, data }: { ids: string[]; data: Dossier }) {
  return (
    <Citations
      wid={data.workspace.id}
      sources={data.evidence
        .filter((e) => ids.includes(e.id))
        .flatMap((e) => e.sources)}
    />
  );
}
