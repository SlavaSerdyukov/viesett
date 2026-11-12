import { ConnectScreen } from "./ConnectScreen";
import { useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X, ShieldCheck, LoaderCircle } from "lucide-react";
import { api, setToken } from "./api";
import { AccessContext, type Access } from "./access";
import { Brand, ErrorMessage, Modal } from "./components";
import type { PolicyOut } from "./contracts";
import { Start } from "./pages/Start";
import { PdfViewer } from "./pages/PdfViewer";
import { DossierPage } from "./pages/Dossier";

export function App() {
  const [connected, setConnected] = useState(false),
    [pending, setPending] = useState<(() => Promise<void>) | null>(null);
  const [policies, setPolicies] = useState<PolicyOut[] | null>(null),
    [afterPolicy, setAfterPolicy] = useState<(() => Promise<void>) | null>(
      null,
    );
  const [tokenInput, setTokenInput] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null),
    [accepted, setAccepted] = useState(false);
  const config = useQuery({ queryKey: ["web-config"], queryFn: api.config });
  const client = useQueryClient(),
    navigate = useNavigate();
  function connect(token: string) {
    client.removeQueries({
      predicate: (query) => query.queryKey[0] !== "web-config",
    });
    setToken(token.trim());
    setConnected(true);
    setTokenInput("");
  }
  function disconnect() {
    setToken(null);
    setConnected(false);
    client.clear();
    navigate("/");
  }
  async function run(action: () => Promise<void>) {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function completeConnection(token: string) {
    connect(token);
    const action = pending;
    setPending(null);
    if (action) await run(action);
  }
  const access: Access = {
    connected,
    working: busy,
    connect,
    disconnect,
    request: (action) => {
      if (busy) return;
      if (connected) void run(action);
      else {
        setError(null);
        setPending(() => action);
      }
    },
    uploads: (action) => {
      void run(async () => {
        setPolicies(await api.policies());
        setAfterPolicy(() => action);
        setAccepted(false);
      });
    },
  };
  return (
    <AccessContext.Provider value={access}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      {config.data?.demo && (
        <div className="demo-banner">
          <ShieldCheck size={14} /> Demo data · Fictional property and documents
          · No live register
        </div>
      )}
      <Routes>
        <Route path="/" element={<Start demo={config.data?.demo ?? false} />} />
        <Route
          path="/workspaces/:id/documents/:documentId"
          element={connected ? <PdfViewer /> : <ConnectScreen />}
        />
        <Route
          path="/workspaces/:id/:section?"
          element={
            connected ? (
              <DossierPage
                maxBytes={config.data?.max_upload_bytes ?? 10 * 1024 * 1024}
              />
            ) : (
              <ConnectScreen />
            )
          }
        />
        <Route
          path="*"
          element={
            <main id="main" className="start">
              <Brand />
              <h1>Page not found.</h1>
              <Link to="/">Return to Viesett</Link>
            </main>
          }
        />
      </Routes>
      {!!error && !pending && (
        <div className="toast">
          <ErrorMessage error={error} />
          <button
            className="icon-button"
            onClick={() => setError(null)}
            aria-label="Dismiss message"
          >
            <X size={16} />
          </button>
        </div>
      )}
      {busy && (
        <div className="activity" role="status">
          <LoaderCircle size={15} className="spin" /> Updating your private
          dossier…
        </div>
      )}
      {pending && (
        <Modal
          title="Open your private workspace"
          close={() => setPending(null)}
        >
          <p>
            Connect with your evaluation access token. It stays in this page's
            memory and is forgotten when you reload or disconnect.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void completeConnection(tokenInput);
            }}
          >
            <label htmlFor="access-token">Access token</label>
            <input
              id="access-token"
              type="password"
              autoComplete="off"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              required
              minLength={40}
            />
            <button className="button" type="submit">
              Connect
            </button>
          </form>
          {config.data?.development_session && (
            <>
              <div className="divider">Local development access</div>
              <p className="muted">
                Creates a new, one-hour evaluation session. To reopen an
                existing dossier after a reload, use its original access token.
              </p>
              <button
                className="button secondary"
                disabled={busy}
                onClick={() =>
                  void run(async () =>
                    completeConnection((await api.session()).token),
                  )
                }
              >
                Start private evaluation
              </button>
            </>
          )}
          <ErrorMessage error={error} />
        </Modal>
      )}
      {policies && (
        <Modal title="Before adding documents" close={() => setPolicies(null)}>
          <p>
            Upload only property documents you are entitled to provide. Avoid
            personal identity documents, private banking, health information and
            unrelated correspondence.
          </p>
          {policies
            .filter((p) =>
              ["UPLOAD_ATTESTATION", "PRIVACY_NOTICE"].includes(p.policy_type),
            )
            .map((p) => (
              <details key={p.id}>
                <summary>
                  {p.policy_type === "PRIVACY_NOTICE"
                    ? "Privacy notice"
                    : "Upload attestation"}{" "}
                  · {p.version}
                </summary>
                <p className="policy-text">{p.text}</p>
              </details>
            ))}
          <label className="checkbox">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
            />
            I confirm the upload attestation and have read the privacy notice.
            This does not provide consent on behalf of other people.
          </label>
          <button
            className="button"
            disabled={!accepted || busy}
            onClick={() =>
              void run(async () => {
                for (const p of policies.filter((p) =>
                  ["UPLOAD_ATTESTATION", "PRIVACY_NOTICE"].includes(
                    p.policy_type,
                  ),
                ))
                  await api.acknowledge(p.id);
                setPolicies(null);
                if (afterPolicy) await afterPolicy();
              })
            }
          >
            Continue
          </button>
        </Modal>
      )}
    </AccessContext.Provider>
  );
}
