import { Brand, Citations } from "../components";
import { SourceAppendix } from "../SourceCitations";
import { PrintActions, PrintDisclaimer } from "../PrintActions";
import { date, label, money } from "../copy";
import {
  handoffSources,
  importantFindings,
  missingInformation,
  notaryQuestions,
  requirementName,
} from "../print-presentation";
import { sourcesForEvidence } from "../sources";
import type { DossierSnapshotResponse as Dossier } from "../contracts";

export function NotaryHandoff({ data }: { data: Dossier }) {
  const matters = importantFindings(data),
    questions = notaryQuestions(data);
  const missing = missingInformation(data);
  const conditional = data.requirements.filter((r) =>
    ["CONDITIONAL", "UNKNOWN"].includes(r.applicability),
  );
  const co =
    data.co_ownership?.co_ownership_status !== "NOT_ESTABLISHED"
      ? data.co_ownership
      : null;
  const approved =
    co?.planned_works.filter((w) => w.decision_status === "APPROVED") ?? [];
  const litigationState = co?.article_3_94_completeness.find(
    (c) => c.code === "PENDING_LITIGATION",
  );
  return (
    <main id="main" className="print-dossier notary-handoff">
      <PrintActions wid={data.workspace.id} notary />
      <Brand />
      <p className="eyebrow">
        Buyer property review · Prepared for notary review
        {data.is_demo ? " · DEMO DATA" : ""}
      </p>
      <h1>Notary handoff</h1>
      <p className="notary-address">
        {data.property.address ?? "Property identity not confirmed"}
      </p>
      <p className="print-dates">
        Generated {date(new Date().toISOString())} · Information evaluated{" "}
        {date(data.evaluation_date)}
      </p>

      <section className="notary-identity">
        <h2>Property identity</h2>
        <p>
          {label(data.property.status)}
          {data.property.stale
            ? " · Previous official data; refresh needed"
            : ""}
        </p>
        <p>
          Building unit:{" "}
          {data.property.unit_id
            ? "Matched to the official address"
            : "Not confirmed"}
          {data.property.box ? ` · Box ${data.property.box}` : ""}
        </p>
        <p>
          Parcels:{" "}
          {data.property.parcels.length
            ? data.property.parcels.join(" · ")
            : "Not confirmed"}
        </p>
      </section>
      <section className="notary-status">
        <h2>Dossier status</h2>
        <p>
          <strong>
            {data.completeness.percentage == null
              ? "Coverage not established"
              : `${data.completeness.percentage}% information coverage`}
          </strong>{" "}
          · {data.completeness.completed_count}/
          {data.completeness.applicable_count} applicable checks complete ·{" "}
          {Math.max(
            0,
            data.completeness.applicable_count -
              data.completeness.completed_count,
          )}{" "}
          confirmed information gaps · {data.completeness.conditional_count}{" "}
          open applicability checks
        </p>
        <p>
          Completeness is information coverage, not a safety score. A data gap
          does not by itself establish a legally blocked sale.
        </p>
      </section>
      {data.truncated && (
        <p className="notice">
          This handoff uses a bounded current dossier projection. Additional
          sources/history remain in the private export; review the full record
          before relying on completeness.
        </p>
      )}
      <section className="notary-matters">
        <h2>Matters requiring professional attention</h2>
        {matters.length ? (
          matters.map((f) => (
            <article className="notary-matter" key={f.id}>
              <h3>{f.title}</h3>
              <p>{f.explanation}</p>
              <p>
                <strong>Clarify:</strong>{" "}
                {f.next_step
                  .replace(/^Clarify with the (seller|agent|syndic):\s*/i, "")
                  .replace(/^Please provide\b/i, "Verify availability of")}
              </p>
              <Citations sources={f.sources} wid={data.workspace.id} compact />
            </article>
          ))
        ) : (
          <p>
            No current review findings from the information analyzed so far;
            this does not certify the property.
          </p>
        )}
      </section>
      <section className="notary-missing">
        <h2>Missing documents / information</h2>
        {missing.length ? (
          <ul>
            {missing.map((r) => (
              <li key={r.key}>{r.text}</li>
            ))}
          </ul>
        ) : (
          <p>No confirmed gaps in the current applicable checks.</p>
        )}
        {!!conditional.length && (
          <>
            <h3>May apply / unresolved</h3>
            <ul>
              {conditional.map((r) => (
                <li key={r.rule.code}>
                  {requirementName(r)}
                  {r.presence === "PRESENT"
                    ? " — document received; applicability unconfirmed"
                    : " — applicability not established"}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
      {!!data.context_answers?.length && (
        <section className="notary-context">
          <h2>Unverified buyer context</h2>
          {data.context_answers.map((a) => (
            <p key={a.evidence_id}>
              Buyer-provided signed deed date {date(a.value)}. Any provisional
              timeline needs confirmation against the deed or with the notary.
            </p>
          ))}
        </section>
      )}
      {co && (
        <section className="notary-co">
          <h2>Co-ownership / planned works</h2>
          <p>
            <strong>
              {co.identity?.association_name ?? "Association not confirmed"}
            </strong>{" "}
            · Lot {co.identity?.lot_identifier ?? "not confirmed"} · Ownership
            share{" "}
            {co.identity?.ownership_share?.original_representation ??
              "not confirmed"}
          </p>
          <p>
            Working capital:{" "}
            {money(
              co.current_working_capital?.money.amount,
              co.current_working_capital?.money.currency,
            )}{" "}
            ({date(co.current_working_capital?.effective_date)}) · Reserve
            capital:{" "}
            {money(
              co.current_reserve_capital?.money.amount,
              co.current_reserve_capital?.money.currency,
            )}{" "}
            ({date(co.current_reserve_capital?.effective_date)})
          </p>
          <h3>Approved works</h3>
          {approved.length ? (
            <ul>
              {approved.map((w) => (
                <li key={w.key}>
                  {label(w.category)}
                  {w.reference ? ` · ${w.reference}` : ""} ·{" "}
                  {money(
                    w.approved_total_cost?.amount,
                    w.approved_total_cost?.currency,
                  )}{" "}
                  · decision {date(w.decision_date)}
                  {w.expected_start
                    ? ` · expected ${date(w.expected_start)}`
                    : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p>No approved works identified in the analyzed information.</p>
          )}
          <h3>Capital calls</h3>
          {co.capital_calls.length ? (
            <ul>
              {co.capital_calls.map((c, i) => (
                <li key={i}>
                  {c.reference ?? "Documented call"} · {label(c.fund_type)} ·{" "}
                  {money(
                    c.lot_specific_amount?.amount ?? c.total?.amount,
                    c.lot_specific_amount?.currency ?? c.total?.currency,
                  )}{" "}
                  · due {date(c.due_date)}; payment responsibility needs
                  confirmation.
                </li>
              ))}
            </ul>
          ) : (
            <p>
              No structured call identified; confirm the supplied call
              disclosures.
            </p>
          )}
          <h3>Pending litigation</h3>
          {co.pending_litigation.length ? (
            <ul>
              {co.pending_litigation.map((l, i) => (
                <li key={i}>
                  {label(l.subject_category)} ·{" "}
                  {money(
                    l.amount_in_dispute?.amount,
                    l.amount_in_dispute?.currency,
                  )}{" "}
                  · status/responsibility need confirmation.
                </li>
              ))}
            </ul>
          ) : (
            <p>
              {litigationState?.status === "EXPLICIT_NONE"
                ? "Explicitly none in the supplied disclosure."
                : "No supported pending-case disclosure identified; absence is not confirmation that none exists."}
            </p>
          )}
        </section>
      )}
      {!!co?.financial_exposure_estimates.length && (
        <section className="notary-finance">
          <h2>Financial exposure</h2>
          {co.financial_exposure_estimates.map((e) => (
            <article className="notary-exposure" key={e.planned_work_key}>
              <h3>
                Potential proportional exposure ·{" "}
                {label(
                  co.planned_works.find((w) => w.key === e.planned_work_key)
                    ?.category ?? "Documented work",
                )}
              </h3>
              {e.status === "CALCULATED" ? (
                <>
                  <p className="notary-amount">
                    {money(
                      e.estimated_proportional_amount?.amount,
                      e.estimated_proportional_amount?.currency,
                    )}
                  </p>
                  <p>
                    Project cost{" "}
                    {money(
                      e.gross_project_cost?.amount,
                      e.gross_project_cost?.currency,
                    )}{" "}
                    · Explicit project funding{" "}
                    {e.explicit_project_funding
                      ? money(
                          e.explicit_project_funding.amount,
                          e.explicit_project_funding.currency,
                        )
                      : "Not confirmed"}{" "}
                    · Applicable share{" "}
                    {e.share?.original_representation ?? "Not established"}
                  </p>
                  <p>
                    Remaining financing basis{" "}
                    {money(
                      e.remaining_financing_basis?.amount,
                      e.remaining_financing_basis?.currency,
                    )}{" "}
                    · Gross proportional amount{" "}
                    {money(
                      e.gross_proportional_amount?.amount,
                      e.gross_proportional_amount?.currency,
                    )}
                  </p>
                </>
              ) : (
                <p>{label(e.status)}. A precise estimate is not available.</p>
              )}
              <p>
                <strong>Legal payment responsibility: Not determined</strong>
              </p>
              <ul className="notary-assumptions">
                {e.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
              <Citations
                sources={sourcesForEvidence(data, e.source_evidence_ids)}
                wid={data.workspace.id}
                compact
              />
            </article>
          ))}
        </section>
      )}
      <section className="notary-questions">
        <h2>Questions for the notary</h2>
        {questions.length ? (
          <ol>
            {questions.map((q) => (
              <li key={q.key}>
                <strong>{q.question_text}</strong>
                <p>{q.reason}</p>
                <Citations
                  sources={q.sources}
                  wid={data.workspace.id}
                  compact
                />
              </li>
            ))}
          </ol>
        ) : (
          <p>
            No notary-targeted question generated from the current information.
          </p>
        )}
      </section>
      <SourceAppendix data={data} sources={handoffSources(data)} />
      <PrintDisclaimer />
    </main>
  );
}
