import { Badge } from "./components";
import type { Requirement } from "./contracts";
import { kind, label } from "./copy";

export function conditionalExplanation(item: Requirement) {
  if (item.kind === "ASBESTOS_CERTIFICATE")
    return "The relevant construction date, accessible area and transfer conditions are not yet established.";
  if (item.kind === "EPC")
    return "The type of transfer and any applicable exceptions need reliable confirmation.";
  if (item.kind === "ELECTRICAL_INSPECTION")
    return "Installation history, previous inspections and the transfer situation can change which report is needed.";
  if (item.kind === "SOIL_CERTIFICATE")
    return "The transfer type and coverage of the official parcels still need confirmation.";
  return "We need reliable information to establish whether this check applies.";
}

export function Requirements({
  items,
  interactive = true,
}: {
  items: Requirement[];
  interactive?: boolean;
}) {
  const received = items.filter((r) => r.presence === "PRESENT");
  const required = items.filter(
    (r) => r.applicability === "REQUIRED" && r.presence !== "PRESENT",
  );
  const may = items.filter(
    (r) =>
      ["CONDITIONAL", "UNKNOWN"].includes(r.applicability) &&
      r.presence !== "PRESENT",
  );
  const other = items.filter(
    (r) =>
      ["NOT_REQUIRED", "NOT_YET_EFFECTIVE"].includes(r.applicability) &&
      r.presence !== "PRESENT",
  );
  function rows(values: Requirement[], conditional = false) {
    return values.map((r, i) => (
      <div className="checklist-row" key={r.rule.code + ":" + i}>
        <div>
          <strong>
            {kind(r.kind)}
            {r.variant && r.variant !== "UNSPECIFIED"
              ? ` · ${label(r.variant)}`
              : ""}
          </strong>
          <p>{conditional ? conditionalExplanation(r) : r.reason}</p>
          {conditional && (
            <p className="small">
              Not counted as a confirmed missing requirement.
              {interactive &&
                " No answer is needed unless a specific transaction question is shown."}
            </p>
          )}
          {r.presence === "PRESENT" && r.applicability === "CONDITIONAL" && (
            <p className="small">
              Available document; applicability still needs confirmation.
            </p>
          )}
          {conditional && (
            <details>
              <summary>Check details</summary>
              <p>{r.reason}</p>
            </details>
          )}
        </div>
        <Badge status={conditional ? "CONDITIONAL" : r.presence} />
      </div>
    ));
  }
  return (
    <>
      <h3>Required now</h3>
      {required.length ? (
        <>
          <p className="small">
            Missing information for {required.length} confirmed applicable check
            {required.length === 1 ? "" : "s"}. A data gap does not by itself
            establish a legally blocked sale.
          </p>
          {rows(required)}
        </>
      ) : (
        <p>
          No confirmed required documents are missing from the checks
          established so far.
        </p>
      )}
      <h3>May apply</h3>
      {may.length ? (
        rows(may, true)
      ) : (
        <p>No additional conditional checks await applicability information.</p>
      )}
      <h3>Received</h3>
      {received.length ? (
        rows(received)
      ) : (
        <p>No usable certificate has satisfied a checklist item yet.</p>
      )}
      {!!other.length && (
        <details className="requirements-deferred">
          <summary>Not required now / not yet applicable</summary>
          {rows(other)}
        </details>
      )}
    </>
  );
}
