import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Upload, FileText } from "lucide-react";
import { api } from "../api";
import { useAccess } from "../access";
import {
  Badge,
  Busy,
  CopyButton,
  Empty,
  ErrorMessage,
  Modal,
  PageIntro,
} from "../components";
import type {
  DocumentSummaryResponse,
  DossierSnapshotResponse as Dossier,
} from "../contracts";
import { date, kind } from "../copy";
import { Requirements } from "../Requirements";
export function Documents({
  data,
  maxBytes,
}: {
  data: Dossier;
  maxBytes: number;
}) {
  const uploadedHeading = useRef<HTMLHeadingElement>(null);
  const access = useAccess(),
    client = useQueryClient(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null),
    [removing, setRemoving] = useState<DocumentSummaryResponse | null>(null),
    [draft, setDraft] = useState<string | null>(null);
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    const list = Array.from(files);
    if (
      list.some(
        (f) => f.size > maxBytes || !f.name.toLowerCase().endsWith(".pdf"),
      )
    ) {
      setError(
        new Error(
          `Choose PDF files up to ${Math.floor(maxBytes / 1024 / 1024)} MB each.`,
        ),
      );
      return;
    }
    access.uploads(async () => {
      setBusy(true);
      setError(null);
      try {
        for (const file of list)
          client.setQueryData(
            ["dossier", data.workspace.id],
            await api.upload(data.workspace.id, file),
          );
      } catch (e) {
        setError(e);
      } finally {
        setBusy(false);
        await client.invalidateQueries({
          queryKey: ["dossier", data.workspace.id],
        });
        uploadedHeading.current?.focus();
      }
    });
  }
  async function change(did: string, kind?: string) {
    setBusy(true);
    setError(null);
    try {
      if (kind) await api.classify(data.workspace.id, did, kind);
      else await api.retry(data.workspace.id, did);
      await client.invalidateQueries({
        queryKey: ["dossier", data.workspace.id],
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      uploadedHeading.current?.focus();
    }
  }
  const requested = [
    ...new Set([
      ...data.requirements
        .filter(
          (r) =>
            !["NOT_REQUIRED", "NOT_YET_EFFECTIVE"].includes(r.applicability) &&
            r.presence !== "PRESENT",
        )
        .map((r) => r.kind),
      ...(data.co_ownership ? ["SYNDIC_INFORMATION"] : []),
    ]),
  ];
  return (
    <>
      <PageIntro
        title="The documents behind your decision"
        description="Drop in the PDFs you received. Viesett identifies supported documents and updates your dossier."
      />
      <label
        className={`upload-zone ${busy ? "disabled" : ""}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!busy) void upload(e.dataTransfer.files);
        }}
      >
        <Upload size={29} />
        <strong>
          {busy
            ? "Uploading, checking & reading documents…"
            : "Drop property documents here"}
        </strong>
        <span>
          PDF · up to {Math.floor(maxBytes / 1024 / 1024)} MB per file
        </span>
        <span className="button secondary">Choose files</span>
        <input
          aria-label="Upload property PDFs"
          type="file"
          accept="application/pdf,.pdf"
          multiple
          disabled={busy}
          onChange={(e) => {
            void upload(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
      {busy && <Busy>Updating the dossier after document analysis…</Busy>}
      <ErrorMessage error={error} />
      <section className="panel">
        <div className="section-heading">
          <h2>Document checklist</h2>
          <button
            className="text-button"
            disabled={!requested.length}
            onClick={() =>
              void api
                .draft(data.workspace.id, requested)
                .then((r) =>
                  setDraft(
                    r.generated_text +
                      (data.requirements.some(
                        (item) => item.applicability === "CONDITIONAL",
                      )
                        ? "\n\nFor conditional items, please confirm applicability or provide the documented reason for an exemption."
                        : ""),
                  ),
                )
                .catch(setError)
            }
          >
            Generate request <ArrowUpRight size={15} />
          </button>
        </div>
        <Requirements items={data.requirements} />
      </section>
      <h2 className="group-title" tabIndex={-1} ref={uploadedHeading}>
        Uploaded documents{" "}
        <span className="muted">{data.documents.length}</span>
      </h2>
      {data.documents.length ? (
        data.documents.map((d) => (
          <article className="panel document-row" key={d.id}>
            <FileText size={23} />
            <div className="document-info">
              <h3>{d.filename}</h3>
              <p>
                {kind(d.kind)} · {date(d.created_at)}
              </p>
              <div className="status-row">
                <Badge status={d.status} />
                <Badge status={d.association} />
              </div>
              {d.summary.map((s) => (
                <p key={s}>{s}</p>
              ))}
              {d.status === "OCR_REQUIRED" && (
                <p>
                  This PDF appears to be scanned. Viesett cannot read it
                  automatically yet. You can keep the document or delete it.
                </p>
              )}
              {d.status === "UNKNOWN" && (
                <>
                  <p>We couldn't confidently identify this document.</p>
                  <label>
                    Document type
                    <select
                      aria-label={`Document type for ${d.filename}`}
                      defaultValue="UNKNOWN"
                      disabled={busy}
                      onChange={(e) => void change(d.id, e.target.value)}
                    >
                      {d.supported_kinds.map((k) => (
                        <option key={k} value={k}>
                          {kind(k)}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              {d.can_retry && (
                <button
                  className="text-button"
                  onClick={() => void change(d.id)}
                >
                  Retry reading
                </button>
              )}
            </div>
            <div className="document-actions">
              {d.can_view && (
                <Link
                  className="text-button"
                  to={`/workspaces/${data.workspace.id}/documents/${d.id}?page=1`}
                >
                  View PDF <ArrowUpRight size={14} />
                </Link>
              )}
              <button
                className="text-button muted"
                onClick={() => setRemoving(d)}
              >
                Delete
              </button>
            </div>
          </article>
        ))
      ) : (
        <Empty
          title="No property documents yet"
          text="Drop the documents you received from the seller or agent. Viesett will identify supported documents automatically."
        />
      )}
      {removing && (
        <Modal title="Delete this document?" close={() => setRemoving(null)}>
          <p>
            {removing.filename} and its derived evidence will be removed.
            Findings and completeness will update from the remaining sources.
          </p>
          <button
            className="button"
            onClick={() =>
              void api
                .remove(data.workspace.id, removing.id)
                .then(() => {
                  setRemoving(null);
                  return client.invalidateQueries({
                    queryKey: ["dossier", data.workspace.id],
                  });
                })
                .catch(setError)
            }
          >
            Delete document
          </button>
          <button
            className="button secondary"
            onClick={() => setRemoving(null)}
          >
            Keep document
          </button>
        </Modal>
      )}
      {draft !== null && (
        <Modal title="Request missing information" close={() => setDraft(null)}>
          <label htmlFor="request-text">Review and edit your request</label>
          <textarea
            id="request-text"
            rows={12}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <CopyButton text={draft} />
          <p className="small muted">
            Copy and send this yourself. Viesett does not contact anyone.
          </p>
        </Modal>
      )}
    </>
  );
}
