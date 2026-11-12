import { useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  House,
  ArrowUpRight,
  FileText,
  Layers,
  ListChecks,
  MessageSquare,
  ShieldCheck,
  ChevronRight,
  Printer,
  RefreshCw,
} from "lucide-react";
import { api, type Selection } from "../api";
import { useAccess } from "../access";
import { Brand, Busy, Badge, ErrorMessage, Modal } from "../components";
import { date } from "../copy";
import { Overview } from "./Overview";
import { Documents } from "./Documents";
import { Findings } from "./Findings";
import { CoOwnership } from "./CoOwnership";
import { Questions } from "./Questions";
import { Evidence } from "./Evidence";
import { PreviewCard } from "./Start";
import type { PreviewResponse } from "../contracts";
import { PrintDossier } from "./Print";
const sections = [
  ["overview", "Overview", House],
  ["documents", "Documents", FileText],
  ["findings", "Findings", ListChecks],
  ["co-ownership", "Co-ownership", Layers],
  ["questions", "Questions", MessageSquare],
  ["evidence", "Evidence", ShieldCheck],
] as const;

export function DossierPage({ maxBytes }: { maxBytes: number }) {
  const { id = "", section = "overview" } = useParams(),
    client = useQueryClient(),
    access = useAccess();
  const q = useQuery({
    queryKey: ["dossier", id],
    queryFn: () => api.dossier(id),
    refetchInterval: (query) =>
      query.state.data?.documents.some(
        (d) =>
          ["PENDING", "IN_PROGRESS"].includes(d.status) &&
          Date.now() - new Date(d.created_at).getTime() < 120000,
      )
        ? 3000
        : false,
  });
  const [error, setError] = useState<unknown>(null),
    [refreshing, setRefreshing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [selection, setSelection] = useState<Selection>({ query: "" });
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  async function checkProperty() {
    setRefreshing(true);
    setError(null);
    try {
      setPreview(await api.preview(selection));
    } catch (e) {
      setError(e);
    } finally {
      setRefreshing(false);
    }
  }
  async function confirmProperty() {
    setRefreshing(true);
    setError(null);
    try {
      await api.resolve(id, selection);
      setConfirming(false);
      await client.invalidateQueries({ queryKey: ["dossier", id] });
    } catch (e) {
      setError(e);
    } finally {
      setRefreshing(false);
    }
  }
  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      client.setQueryData(["dossier", id], await api.refresh(id));
    } catch (e) {
      setError(e);
    } finally {
      setRefreshing(false);
    }
  }
  if (q.isPending)
    return (
      <main id="main" className="start">
        <Brand />
        <Busy />
      </main>
    );
  if (q.isError || !q.data)
    return (
      <main id="main" className="start">
        <Brand />
        <h1>Dossier unavailable</h1>
        <ErrorMessage error={q.error} />
        <button className="button secondary" onClick={() => void q.refetch()}>
          Try again
        </button>
        <Link to="/">Return to start</Link>
      </main>
    );
  const data = q.data;
  if (section === "print") return <PrintDossier data={data} />;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-caption">BUYER DOSSIER</div>
        <nav aria-label="Dossier sections">
          {sections.map(([path, title, Icon]) => (
            <NavLink key={path} to={`/workspaces/${id}/${path}`}>
              <Icon size={18} />
              {title}
              {path === "findings" && data.findings.length > 0 && (
                <span className="nav-count">{data.findings.length}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="small muted">Your private workspace</span>
          <Link to="/">
            All dossiers <ArrowUpRight size={14} />
          </Link>
          <button className="text-button muted" onClick={access.disconnect}>
            Disconnect
          </button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-header">
          <span>
            <span className="muted">My dossiers</span>
            <ChevronRight size={13} />
            Property review
          </span>
          <Link className="text-button" to={`/workspaces/${id}/print`}>
            <Printer size={16} />
            Prepare for notary
          </Link>
        </header>
        <main id="main" className="dossier-content">
          <div className="property-header">
            <div>
              <div className="eyebrow">
                {data.is_demo
                  ? "Demo data · Fictional buyer dossier"
                  : "Your property dossier"}
              </div>
              <h1>{data.property.address ?? "Property to be resolved"}</h1>
              <div className="property-meta">
                <Badge status={data.property.status} />
                <span>Updated {date(data.last_updated)}</span>
              </div>
            </div>
            <button
              className="button secondary"
              disabled={
                refreshing ||
                !["RESOLVED", "PARTIALLY_RESOLVED"].includes(
                  data.property.status,
                )
              }
              onClick={() => void refresh()}
            >
              <RefreshCw size={15} className={refreshing ? "spin" : ""} />
              {refreshing ? "Refreshing sources…" : "Refresh public sources"}
            </button>
          </div>
          <ErrorMessage error={error} />
          {!["RESOLVED", "PARTIALLY_RESOLVED"].includes(
            data.property.status,
          ) && (
            <section className="panel">
              <h2>Confirm the property</h2>
              <p>
                The official property selection is not confirmed. Source
                downtime does not mean your address is invalid.
              </p>
              <button
                className="button secondary"
                onClick={() => {
                  setSelection({
                    query: data.property.query ?? data.property.address ?? "",
                  });
                  setPreview(null);
                  setConfirming(true);
                }}
              >
                Check this property again
              </button>
            </section>
          )}
          {confirming && (
            <Modal
              title="Confirm the property"
              close={() => setConfirming(false)}
            >
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void checkProperty();
                }}
              >
                <label htmlFor="property-query">Property address</label>
                <input
                  id="property-query"
                  value={selection.query}
                  required
                  minLength={3}
                  onChange={(e) => {
                    setSelection({ query: e.target.value });
                    setPreview(null);
                  }}
                />
                <button className="button" disabled={refreshing}>
                  Check official address
                </button>
              </form>
              {refreshing && (
                <Busy>Checking official property information…</Busy>
              )}
              {preview && (
                <PreviewCard
                  preview={preview}
                  selection={selection}
                  choose={setSelection}
                  check={() => void checkProperty()}
                  create={() => void confirmProperty()}
                  actionLabel="Confirm this selection"
                  busy={refreshing}
                />
              )}
            </Modal>
          )}
          {data.truncated && (
            <p className="notice">
              This view is limited to 100 documents, 200 current findings and
              500 facts. Additional sources and older details remain in your
              private dossier; this is a limited current view.
            </p>
          )}
          {section === "overview" ? (
            <Overview data={data} />
          ) : section === "documents" ? (
            <Documents data={data} maxBytes={maxBytes} />
          ) : section === "findings" ? (
            <Findings data={data} />
          ) : section === "co-ownership" ? (
            <CoOwnership co={data.co_ownership} data={data} />
          ) : section === "questions" ? (
            <Questions data={data} />
          ) : section === "evidence" ? (
            <Evidence data={data} />
          ) : (
            <>
              <h2>Section not found</h2>
              <Link to={`/workspaces/${id}/overview`}>Open Overview</Link>
            </>
          )}
          <footer className="dossier-footer">
            <span>Source-backed information. A clearer next step.</span>
            <span>Private dossier · Viesett</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
