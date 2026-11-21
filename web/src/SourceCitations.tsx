import { Link } from "react-router-dom";
import { ArrowUpRight, FileText } from "lucide-react";
import type {
  CitationResponse,
  DossierSnapshotResponse as Dossier,
} from "./contracts";
import { date } from "./copy";
import { groupSources, humanSourceUrl } from "./sources";

function SourceLink({
  source,
  wid,
}: {
  source: CitationResponse;
  wid: string;
}) {
  const href = humanSourceUrl(source.human_url);
  return source.document_id ? (
    <Link
      to={`/workspaces/${wid}/documents/${source.document_id}?page=${source.page ?? 1}`}
    >
      <FileText size={13} />
      {source.label}
      {source.page ? ` · page ${source.page}` : ""}
    </Link>
  ) : href ? (
    <a href={href} target="_blank" rel="noreferrer">
      {source.label}
      <ArrowUpRight size={12} />
    </a>
  ) : (
    <span>{source.label}</span>
  );
}

export function Citations({
  sources,
  wid,
  compact = false,
}: {
  sources: CitationResponse[];
  wid: string;
  compact?: boolean;
}) {
  const groups = groupSources(sources);
  if (!groups.length) return null;
  return (
    <div className={`citation-groups${compact ? " compact-citations" : ""}`}>
      {[false, true].map((authority) => {
        const rows = groups.filter(
          (g) => (g.source.kind === "RULE_AUTHORITY") === authority,
        );
        return rows.length ? (
          <div
            className="citation-group"
            role="group"
            aria-label={authority ? "Rule / guidance" : "Evidence"}
            key={String(authority)}
          >
            <strong className="citation-group-label">
              {authority ? "Rule / guidance" : "Evidence"}
            </strong>
            <div className="citations">
              {rows.map((group) => (
                <div className="citation-item" key={group.key}>
                  <SourceLink source={group.source} wid={wid} />
                </div>
              ))}
            </div>
          </div>
        ) : null;
      })}
    </div>
  );
}

export function SourceAppendix({
  sources,
  data,
}: {
  sources: CitationResponse[];
  data: Dossier;
}) {
  const groups = groupSources(sources);
  const publicSources = groups.filter(
    (g) =>
      !g.source.document_id &&
      ["OFFICIAL_REGISTER", "PUBLIC_INFORMATION"].includes(g.source.kind),
  );
  const rules = groups.filter((g) => g.source.kind === "RULE_AUTHORITY");
  const other = groups.filter(
    (g) =>
      !g.source.document_id &&
      ["USER_CONTEXT", "DERIVED"].includes(g.source.kind),
  );
  const documents = new Map<string, { label: string; pages: Set<number> }>();
  for (const { source } of groups) {
    if (!source.document_id) continue;
    const document = documents.get(source.document_id) ?? {
      label: source.label,
      pages: new Set<number>(),
    };
    if (source.page) document.pages.add(source.page);
    documents.set(source.document_id, document);
  }
  return (
    <section className="source-appendix">
      <h2>Source appendix</h2>
      <h3>Official registers and public sources</h3>
      {publicSources.length ? (
        <ul>
          {publicSources.map(({ source, key }) => {
            const credit = data.property.sources.find(
              (s) => s.provider === source.provider,
            );
            const terms = humanSourceUrl(credit?.terms_reference);
            return (
              <li key={key}>
                <SourceLink source={source} wid={data.workspace.id} />
                {credit && (
                  <span className="source-credit">
                    {credit.attribution_text} · Retrieved{" "}
                    {date(credit.retrieved_at)}
                    {terms && terms !== source.human_url ? (
                      <>
                        {" "}
                        ·{" "}
                        <a href={terms} target="_blank" rel="noreferrer">
                          Reuse conditions
                        </a>
                      </>
                    ) : terms ? (
                      " · Reuse conditions on the source page"
                    ) : (
                      " · Reuse reference requires review in source metadata"
                    )}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p>No public source references supplied.</p>
      )}
      <h3>Uploaded documents</h3>
      {documents.size ? (
        <ul>
          {[...documents]
            .sort((a, b) => a[1].label.localeCompare(b[1].label))
            .map(([id, doc]) => (
              <li key={id}>
                <Link
                  to={`/workspaces/${data.workspace.id}/documents/${id}?page=${doc.pages.size ? Math.min(...doc.pages) : 1}`}
                >
                  {doc.label}
                </Link>
                {!!doc.pages.size && (
                  <span className="source-pages">
                    Pages:{" "}
                    {[...doc.pages]
                      .sort((a, b) => a - b)
                      .map((page, index) => (
                        <span key={page}>
                          {index > 0 && ", "}
                          <Link
                            to={`/workspaces/${data.workspace.id}/documents/${id}?page=${page}`}
                            aria-label={`${doc.label} · page ${page}`}
                          >
                            {page}
                          </Link>
                        </span>
                      ))}
                  </span>
                )}
              </li>
            ))}
        </ul>
      ) : (
        <p>No uploaded documents cited.</p>
      )}
      <h3>Rules and official guidance</h3>
      {rules.length ? (
        <ul>
          {rules.map(({ source, key }) => (
            <li key={key}>
              <SourceLink source={source} wid={data.workspace.id} />
            </li>
          ))}
        </ul>
      ) : (
        <p>No rule references supplied.</p>
      )}
      {!!other.length && (
        <>
          <h3>Other evidence</h3>
          <ul>
            {other.map(({ source, key }) => (
              <li key={key}>{source.label}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
