import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { date } from "./copy";
import { ErrorMessage } from "./components";
import type { DossierSnapshotResponse } from "./contracts";

export function TransactionContext({
  data,
}: {
  data: DossierSnapshotResponse;
}) {
  const client = useQueryClient(),
    heading = useRef<HTMLHeadingElement>(null);
  const [value, setValue] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  if (!data.context_questions?.length && !data.context_answers?.length)
    return null;
  async function save(clear = false) {
    setBusy(true);
    setError(null);
    try {
      const result = clear
        ? await api.clearContext(data.workspace.id)
        : await api.answerContext(data.workspace.id, value);
      client.setQueryData(["dossier", data.workspace.id], result);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      heading.current?.focus();
    }
  }
  return (
    <section className="panel context-panel" aria-busy={busy}>
      <h2 tabIndex={-1} ref={heading}>
        One transaction detail to clarify
      </h2>
      {data.context_questions?.map((q) => (
        <form
          key={q.code}
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <p>{q.question}</p>
          <p>{q.why_needed}</p>
          <p className="small muted">{q.source_preference}</p>
          <label htmlFor="deed-date">Known signed deed date</label>
          <input
            id="deed-date"
            type="date"
            min="1900-01-01"
            max={new Date().toLocaleDateString("en-CA")}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
            disabled={busy}
          />
          <button className="button secondary" disabled={busy}>
            Use as unverified transaction context
          </button>
          <p className="small">
            Optional. If you do not know, leave this for your notary; the rest
            of your dossier remains usable.
          </p>
        </form>
      ))}
      {data.context_answers?.map((a) => (
        <div key={a.evidence_id}>
          <p>
            Buyer-provided deed date: <strong>{date(a.value)}</strong> ·
            Unverified
          </p>
          <p>
            Only a provisional EPC timeline may use this answer. It does not
            establish an obligation or who pays. Official or matched documentary
            information takes precedence.
          </p>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => void save(true)}
          >
            Remove my answer
          </button>
        </div>
      ))}
      <ErrorMessage error={error} />
    </section>
  );
}
