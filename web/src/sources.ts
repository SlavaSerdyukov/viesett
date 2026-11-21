import {
  SOURCE_CATALOG,
  type CitationResponse,
  type DossierSnapshotResponse,
} from "./contracts";

export function humanSourceUrl(value: string | null | undefined) {
  return value &&
    Object.values(SOURCE_CATALOG).some((s) => s.human_url === value)
    ? value
    : undefined;
}

export function catalogSource(
  key: keyof typeof SOURCE_CATALOG,
  technical: string | null = null,
): CitationResponse {
  return {
    ...SOURCE_CATALOG[key],
    document_id: null,
    page: null,
    uri: technical,
    technical_uri: technical,
    retrieved_at: null,
    source_identifier: null,
  };
}

export function providerSource(
  provider: string,
  technical: string | null = null,
) {
  return ["GRAR", "HERITAGE", "FLOOD"].includes(provider)
    ? catalogSource(provider as "GRAR" | "HERITAGE" | "FLOOD", technical)
    : undefined;
}

export function ruleSource(uri: string, name: string): CitationResponse {
  const entry = Object.values(SOURCE_CATALOG).find(
    (s) => s.kind === "RULE_AUTHORITY" && s.human_url === uri,
  );
  return {
    label: entry?.label ?? name,
    kind: "RULE_AUTHORITY",
    human_url: entry?.human_url ?? null,
    provider: entry?.provider ?? null,
    technical_uri: uri,
    uri,
    document_id: null,
    page: null,
    retrieved_at: null,
    source_identifier: null,
  };
}

export function sourcesForEvidence(
  data: DossierSnapshotResponse,
  ids: string[],
) {
  const selected = new Set(ids);
  return data.evidence
    .filter((e) => selected.has(e.id))
    .flatMap((e) => e.sources);
}

export function propertySources(
  data: DossierSnapshotResponse,
): CitationResponse[] {
  const sources: CitationResponse[] = data.property.sources.flatMap(
    (source) => {
      const display = providerSource(source.provider, source.source_reference);
      return display ? [{ ...display, retrieved_at: source.retrieved_at }] : [];
    },
  );
  if (data.property.flood.status !== "NOT_APPLICABLE")
    sources.push(
      catalogSource("FLOOD", data.property.flood.official_reference),
    );
  return sources;
}

export type SourceGroup = {
  key: string;
  source: CitationResponse;
  references: CitationResponse[];
};

export function groupSources(sources: CitationResponse[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const original of sources) {
    const source = original.document_id
      ? { ...original, kind: "DOCUMENT" as const }
      : original;
    const key = source.document_id
      ? `document:${source.document_id}:${source.page ?? "all"}`
      : source.kind === "OFFICIAL_REGISTER" || source.provider === "FLOOD"
        ? `provider:${source.kind}:${source.provider ?? source.human_url ?? source.label}`
        : `${source.kind}:${source.human_url ?? source.technical_uri ?? source.label}`;
    const group = groups.get(key);
    if (group) group.references.push(source);
    else groups.set(key, { key, source, references: [source] });
  }
  return [...groups.values()];
}
