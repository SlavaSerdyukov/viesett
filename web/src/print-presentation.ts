import type {
  CitationResponse,
  DossierSnapshotResponse as Dossier,
  Requirement,
} from "./contracts";
import { componentLabel, date, kind, label } from "./copy";
import { propertySources, ruleSource, sourcesForEvidence } from "./sources";

export const importantFindings = (data: Dossier) =>
  data.findings.filter((f) =>
    ["WARNING", "REVIEW", "BLOCKING_DATA_GAP"].includes(f.severity),
  );
export const notaryQuestions = (data: Dossier) =>
  data.questions.filter((q) => q.target_role === "NOTARY");
export const requirementName = (r: Requirement) =>
  kind(r.kind) +
  (r.variant && r.variant !== "UNSPECIFIED" ? ` · ${label(r.variant)}` : "");

export function missingInformation(data: Dossier) {
  const rows = data.requirements
    .filter(
      (r) =>
        r.applicability === "REQUIRED" &&
        (r.presence !== "PRESENT" || r.validity_status === "EXPIRED"),
    )
    .map((r) => ({ key: r.rule.code, text: requirementName(r) }));
  if (data.co_ownership?.co_ownership_status !== "NOT_ESTABLISHED")
    for (const component of data.co_ownership?.article_3_94_completeness ??
      []) {
      if (!["MISSING", "PARTIAL", "UNPARSEABLE"].includes(component.status))
        continue;
      const gaps = component.coverage?.gaps
        .map((g) => `${date(g.start)}–${date(g.end)}`)
        .join(", ");
      rows.push({
        key: component.code,
        text:
          componentLabel(component.code) +
          (component.status !== "MISSING"
            ? ` (${label(component.status).toLowerCase()})`
            : "") +
          (gaps ? ` · missing coverage ${gaps}` : ""),
      });
    }
  return rows;
}

export function coEvidenceSources(data: Dossier) {
  const co = data.co_ownership;
  if (!co) return [];
  return sourcesForEvidence(data, [
    ...(co.identity?.evidence_ids ?? []),
    ...(co.current_working_capital?.evidence_ids ?? []),
    ...(co.current_reserve_capital?.evidence_ids ?? []),
    ...co.planned_works
      .filter((w) => w.decision_status === "APPROVED")
      .flatMap((w) => w.evidence_ids),
    ...co.capital_calls.flatMap((c) => c.evidence_ids),
    ...co.pending_litigation.flatMap((l) => l.evidence_ids),
    ...co.financial_exposure_estimates.flatMap((e) => e.source_evidence_ids),
  ]);
}

export function handoffSources(data: Dossier) {
  return [
    ...propertySources(data),
    ...importantFindings(data).flatMap((f) => f.sources),
    ...notaryQuestions(data).flatMap((q) => q.sources),
    ...coEvidenceSources(data),
    ...data.requirements
      .filter((r) =>
        ["REQUIRED", "CONDITIONAL", "UNKNOWN"].includes(r.applicability),
      )
      .map((r) =>
        ruleSource(
          r.rule.official_source_reference,
          r.rule.official_source_name,
        ),
      ),
  ];
}

export function fullDossierSources(data: Dossier): CitationResponse[] {
  return [
    ...handoffSources(data),
    ...data.findings.flatMap((f) => f.sources),
    ...data.questions.flatMap((q) => q.sources),
    ...data.evidence.flatMap((e) => e.sources),
    ...data.documents.map((d): CitationResponse => ({
      label: d.filename,
      kind: "DOCUMENT",
      document_id: d.id,
      page: null,
      human_url: null,
      technical_uri: null,
      uri: null,
      provider: null,
      source_identifier: null,
      retrieved_at: null,
    })),
  ];
}
