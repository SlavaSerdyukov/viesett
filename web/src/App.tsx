import { ConnectScreen } from "./ConnectScreen";
import { useEffect, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X, ShieldCheck, LoaderCircle } from "lucide-react";
import {
  api,
  ApiError,
  configureBrowserSessions,
  setCsrf,
  setToken,
} from "./api";
import { AccessContext, type Access } from "./access";
import { Brand, Busy, ErrorMessage, Modal, RouteFocus } from "./components";
import type { PolicyOut } from "./contracts";
import { Start } from "./pages/Start";
import { PdfViewer } from "./pages/PdfViewer";
import { DossierPage } from "./pages/Dossier";

export function App() {
  const [sessionChecked, setSessionChecked] = useState(false);
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
  useEffect(() => {
    const enabled = config.data?.browser_sessions ?? false;
    configureBrowserSessions(enabled);
    let active = true;
    if (enabled) {
      setSessionChecked(false);
      void api
        .restore()
        .then((s) => {
          if (active) {
            setCsrf(s.csrf_token);
            setConnected(true);
          }
        })
        .catch((e) => {
          if (active && !(e instanceof ApiError && e.status === 401))
            setError(e);
        })
        .finally(() => {
          if (active) setSessionChecked(true);
        });
    }
    return () => {
      active = false;
    };
  }, [config.data?.browser_sessions]);
  useEffect(() => {
    function expired() {
      setConnected(false);
      setCsrf(null);
      setToken(null);
      setPolicies(null);
      setPending(null);
      setAfterPolicy(null);
      client.removeQueries({
        predicate: (q) => q.queryKey[0] !== "web-config",
      });
    }
    window.addEventListener("viesett-session-expired", expired);
    return () => window.removeEventListener("viesett-session-expired", expired);
  }, [client]);
  async function connect(token: string) {
    client.removeQueries({
      predicate: (query) => query.queryKey[0] !== "web-config",
    });
    if (config.data?.browser_sessions) {
      const session = await api.exchange(token.trim());
      setCsrf(session.csrf_token);
      setToken(null);
    } else setToken(token.trim());
    setConnected(true);
    setTokenInput("");
  }
  async function disconnect() {
    if (config.data?.browser_sessions) {
      try {
        await api.logout();
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 401)) {
          setError(e);
          return;
        }
      }
    }
    setToken(null);
    setCsrf(null);
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
    await connect(token);
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
      <RouteFocus />
      <a className="skip" href="#main">
        Skip to content
      </a>
      {config.data?.demo && (
        <div className="demo-banner">
          <ShieldCheck size={14} /> Demo data · Fictional property and documents
          · No live register
        </div>
      )}
      {config.data?.browser_sessions && !sessionChecked ? (
        <main id="main" className="start">
          <Brand />
          <Busy>Restoring your private session…</Busy>
        </main>
      ) : (
        <Routes>
          <Route
            path="/"
            element={<Start demo={config.data?.demo ?? false} />}
          />
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
      )}
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
            {config.data?.browser_sessions
              ? "Enter your operator-provided private access token. It is exchanged for a short-lived HttpOnly browser session; reloads keep your dossier open."
              : "Connect with your evaluation access token. It stays in this page's memory and is forgotten when you reload or disconnect."}
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(() => completeConnection(tokenInput));
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
                {config.data?.browser_sessions
                  ? "Creates new fictional evaluation access. Your browser session survives reload until it expires or you disconnect."
                  : "Creates a new, one-hour evaluation session. To reopen an existing dossier after a reload, use its original access token."}
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
