import type { EvidenceResponse } from "./contracts";
import { date } from "./copy";

// These are provider record references, rather than buyer-facing property facts.
// Use the explicit fact key, never labels or guessed URI shapes, to select them.
const referenceFacts: Record<string, { title: string; valueLabel?: string }> = {
  "property.address.object_id": {
    title: "Address registry reference",
    valueLabel: "Provider object ID",
  },
  "property.address.municipality_code": {
    title: "Municipality registry reference",
    valueLabel: "Municipality code",
  },
  "property.building_unit.object_id": {
    title: "Building unit registry reference",
    valueLabel: "Provider object ID",
  },
  "property.building.object_id": {
    title: "Building registry reference",
    valueLabel: "Provider object ID",
  },
  "property.parcel.object_id": {
    title: "Parcel registry reference",
    valueLabel: "Provider object ID",
  },
  "property.heritage.object_id": {
    title: "Heritage registry reference",
    valueLabel: "Provider object ID",
  },
  "property.heritage.type_uri": { title: "Heritage type reference" },
  "property.heritage.match_basis": { title: "Heritage matching reference" },
};
const providers: Record<string, string> = {
  GRAR: "Digitaal Vlaanderen",
  HERITAGE: "Onroerend Erfgoed",
  FLOOD: "Waterinfo",
};

export function referenceFact(evidence: EvidenceResponse) {
  return evidence.authority === "OFFICIAL" &&
    Object.hasOwn(referenceFacts, evidence.key)
    ? referenceFacts[evidence.key]
    : undefined;
}

// An Evidence-page-only disclosure. Raw URIs, fact identifiers, arbitrary
// metadata and internal IDs are deliberately not rendered, even when opened.
export function EvidenceSourceDetails({
  evidence,
}: {
  evidence: EvidenceResponse;
}) {
  const reference = referenceFact(evidence);
  const rows = [
    ...new Map(
      evidence.sources
        .map((s) => ({
          provider:
            s.provider && Object.hasOwn(providers, s.provider)
              ? providers[s.provider]
              : undefined,
          retrieved: s.retrieved_at,
        }))
        .filter((s) => s.provider || s.retrieved)
        .map((s) => [JSON.stringify([s.provider, s.retrieved]), s]),
    ).values(),
  ];
  if (!rows.length && !reference?.valueLabel) return null;
  return (
    <details className="source-details">
      <summary>Source details</summary>
      {reference?.valueLabel && (
        <p>
          {reference.valueLabel}: {evidence.value}
        </p>
      )}
      {rows.map((row, i) => (
        <p key={i}>
          {row.provider && <span>Provider: {row.provider}</span>}
          {row.provider && row.retrieved && " · "}
          {row.retrieved && <span>Retrieved: {date(row.retrieved)}</span>}
        </p>
      ))}
    </details>
  );
}
