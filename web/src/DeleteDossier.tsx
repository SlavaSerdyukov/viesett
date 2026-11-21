import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "./api";
import { ErrorMessage, Modal } from "./components";
import type { WorkspaceOut } from "./contracts";

export function DeleteDossier({
  id,
  address,
}: {
  id: string;
  address: string;
}) {
  const [confirming, setConfirming] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  const client = useQueryClient(),
    navigate = useNavigate();
  function close() {
    if (!busy) setConfirming(false);
  }
  async function remove() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.removeDossier(id);
      await client.cancelQueries({ queryKey: ["dossier", id] });
      client.removeQueries({ queryKey: ["dossier", id] });
      client.setQueryData<WorkspaceOut[]>(["workspaces"], (old) =>
        old?.filter((workspace) => workspace.id !== id),
      );
      await client.invalidateQueries({ queryKey: ["workspaces"] });
      setConfirming(false);
      navigate("/", { state: { dossierDeleted: true } });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="text-button danger"
        aria-label={`Delete dossier for ${address}`}
        onClick={() => {
          setError(null);
          setConfirming(true);
        }}
      >
        Delete dossier
      </button>
      {confirming && (
        <Modal title="Delete this dossier?" close={close}>
          <p>
            <strong>{address}</strong>
          </p>
          <p>
            This removes the whole dossier, its uploaded PDFs, findings,
            evidence and history. This cannot be undone.
          </p>
          <ErrorMessage error={error} />
          <button
            className="button"
            disabled={busy}
            onClick={() => void remove()}
          >
            {busy ? "Deleting dossier…" : "Delete dossier permanently"}
          </button>
          <button className="button secondary" disabled={busy} onClick={close}>
            Keep dossier
          </button>
        </Modal>
      )}
    </>
  );
}
