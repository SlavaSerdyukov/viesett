import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  FileText,
  House,
  LoaderCircle,
  FolderOpen,
  X,
  ArrowUpRight,
} from "lucide-react";
import type {
  CitationResponse,
  CompletenessResponse,
  DossierSnapshotResponse as Dossier,
} from "./contracts";
import { label, date, safeUri } from "./copy";
export function ErrorMessage({ error }: { error: unknown }) {
  return error ? (
    <p className="error" role="alert">
      {error instanceof Error
        ? error.message
        : "This action could not be completed. Please try again."}
    </p>
  ) : null;
}

export function Busy({
  children = "Loading your dossier…",
}: {
  children?: ReactNode;
}) {
  return (
    <p className="busy" role="status">
      <LoaderCircle size={17} className="spin" />
      {children}
    </p>
  );
}

export function Brand() {
  return (
    <Link className="brand" to="/" aria-label="Viesett home">
      <span className="brand-icon">
        <House size={19} />
      </span>
      viesett<span className="brand-dot">.</span>
    </Link>
  );
}

export function Badge({ status }: { status: string }) {
  return (
    <span
      className={`badge ${["WARNING", "REVIEW", "MISSING", "PARTIAL", "BLOCKING_DATA_GAP", "FAILED", "OCR_REQUIRED", "MISMATCH"].includes(status) ? "review" : ["ANALYZED", "MATCHED", "PRESENT", "EXPLICIT_NONE", "RESOLVED"].includes(status) ? "good" : ""}`}
    >
      {label(status)}
    </span>
  );
}

export function Modal({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    el?.showModal();
    return () => {
      el?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog ref={ref} aria-labelledby="dialog-title" onCancel={close}>
      <button
        className="icon-button dialog-close"
        aria-label="Close dialog"
        onClick={close}
      >
        <X size={20} />
      </button>
      <h2 id="dialog-title">{title}</h2>
      {children}
    </dialog>
  );
}

export function PageIntro({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="page-intro">
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}

export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <section className="panel empty">
      <FolderOpen size={27} />
      <h3>{title}</h3>
      <p>{text}</p>
    </section>
  );
}

export function CopyButton({
  text,
  children = "Copy text",
}: {
  text: string;
  children?: ReactNode;
}) {
  const [done, setDone] = useState(false),
    [failed, setFailed] = useState(false);
  return (
    <>
      <button
        className="button secondary small-button"
        onClick={() =>
          void navigator.clipboard
            .writeText(text)
            .then(() => setDone(true))
            .catch(() => setFailed(true))
        }
      >
        {done ? (
          <>
            <Check size={14} />
            Copied
          </>
        ) : (
          children
        )}
      </button>
      {failed && (
        <span role="status">Select the text to copy it manually.</span>
      )}
    </>
  );
}

export function Citations({
  sources,
  wid,
}: {
  sources: CitationResponse[];
  wid: string;
}) {
  return (
    <div className="citations">
      {Array.from(
        new Map(
          sources.map((s) => [
            JSON.stringify([s.document_id, s.page, s.uri]),
            s,
          ]),
        ).values(),
      ).map((s, i) =>
        s.document_id ? (
          <Link
            key={i}
            to={`/workspaces/${wid}/documents/${s.document_id}?page=${s.page ?? 1}`}
          >
            <FileText size={13} />
            {s.label}
            {s.page ? ` · page ${s.page}` : ""}
          </Link>
        ) : safeUri(s.uri) ? (
          <a key={i} href={safeUri(s.uri)} target="_blank" rel="noreferrer">
            {s.label}
            <ArrowUpRight size={12} />
          </a>
        ) : (
          <span key={i}>{s.label}</span>
        ),
      )}
    </div>
  );
}

export function Completeness({ value }: { value: CompletenessResponse }) {
  return (
    <section className="completeness panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Information, not risk</div>
          <h2>Dossier completeness</h2>
        </div>
        <span className="completion-number">
          {value.percentage == null ? "—" : `${value.percentage}%`}
        </span>
      </div>
      <progress
        aria-label="Dossier completeness"
        value={value.completed_count}
        max={Math.max(1, value.applicable_count)}
      />
      <div className="completion-foot">
        <strong>
          {value.completed_count} of {value.applicable_count} applicable checks
          complete
        </strong>
        <span>{label(value.state)}</span>
      </div>
      <p className="small muted">
        {value.conditional_count
          ? `${value.conditional_count} conditional checks await applicability information and are excluded from the percentage. `
          : ""}
        Completeness does not certify that the property has no issues.
      </p>
    </section>
  );
}

export function PropertyFacts({ property }: { property: Dossier["property"] }) {
  return (
    <dl className="facts">
      <div>
        <dt>Building unit</dt>
        <dd>
          {property.unit_id
            ? "Matched to the official address"
            : "Not confirmed"}
        </dd>
      </div>
      <div>
        <dt>Parcel{property.parcels.length !== 1 ? "s" : ""}</dt>
        <dd>
          {property.parcels.length
            ? property.parcels.join(" · ")
            : "Not available"}
        </dd>
      </div>
      <div>
        <dt>Flood information</dt>
        <dd>
          Official automatic score unavailable{" "}
          <a
            href={safeUri(property.flood.official_reference)}
            target="_blank"
            rel="noreferrer"
          >
            Check via Waterinfo <ArrowUpRight size={13} />
          </a>
        </dd>
      </div>
      <div>
        <dt>Last official refresh</dt>
        <dd>
          {date(property.last_refreshed)}
          {property.stale && " · Previous data, refresh needed"}
        </dd>
      </div>
    </dl>
  );
}
