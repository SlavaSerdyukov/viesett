import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  Search,
  ShieldCheck,
  ListChecks,
  MessageSquare,
  FolderOpen,
  ChevronRight,
} from "lucide-react";
import { api, type Selection } from "../api";
import { useAccess } from "../access";
import { Brand, Busy, ErrorMessage, Badge, PropertyFacts } from "../components";
import type {
  PreviewResponse,
  DossierSnapshotResponse as Dossier,
} from "../contracts";
export function Start({ demo }: { demo: boolean }) {
  const [selection, setSelection] = useState<Selection>({ query: "" }),
    [preview, setPreview] = useState<PreviewResponse | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  const queryClient = useQueryClient();
  const access = useAccess(),
    navigate = useNavigate();
  const saved = useQuery({
    queryKey: ["workspaces"],
    queryFn: api.workspaces,
    enabled: access.connected,
  });
  async function check(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setPreview(await api.preview(selection));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function open(data: Dossier) {
    queryClient.setQueryData(["dossier", data.workspace.id], data);
    navigate(`/workspaces/${data.workspace.id}/overview`);
  }
  return (
    <div className="landing">
      <header className="landing-header">
        <Brand />
        <span className="product-label">A clearer view before you buy</span>
        {access.connected ? (
          <button className="text-button" onClick={access.disconnect}>
            Log out
          </button>
        ) : (
          <button
            className="text-button"
            onClick={() => access.request(async () => {})}
          >
            Open my dossiers <ArrowUpRight size={15} />
          </button>
        )}
      </header>
      <main id="main" className="start">
        <div className="eyebrow">
          <span className="small-line" /> Buyer-side property due diligence
        </div>
        <h1>
          Check a property
          <br />
          before you buy<span className="brand-dot">.</span>
        </h1>
        <p className="lead">
          Know what you're buying. See what's missing.
          <br />
          Understand what to ask next.
        </p>
        <form className="address-form" onSubmit={check}>
          <label htmlFor="address">Enter the property address</label>
          <div className="address-control">
            <Search size={20} />
            <input
              id="address"
              name="address"
              placeholder="Street, house number, city"
              value={selection.query}
              onChange={(e) => {
                setSelection({ query: e.target.value });
                setPreview(null);
              }}
              minLength={3}
              maxLength={500}
              required
              autoComplete="street-address"
            />
            <button className="button" disabled={busy}>
              Check property <ArrowRight size={17} />
            </button>
          </div>
        </form>
        <p className="small muted">
          {demo
            ? "Fictional local records. No query is sent to an external register."
            : "Address queries are checked with official public sources. Preview history is not saved."}
        </p>
        <ErrorMessage error={error} />
        {busy && <Busy>Checking the official property register…</Busy>}
        {preview && (
          <PreviewCard
            busy={access.working}
            preview={preview}
            selection={selection}
            choose={setSelection}
            check={() => void check()}
            create={() =>
              access.request(async () => open(await api.create(selection)))
            }
          />
        )}
        {demo && (
          <div className="demo-entry">
            <span>Want to take a look around?</span>
            <button
              className="text-button"
              onClick={() =>
                access.request(async () =>
                  access.uploads(async () => open(await api.demo())),
                )
              }
            >
              Explore a sample dossier <ArrowRight size={16} />
            </button>
            <small>Fictional data. No personal documents needed.</small>
          </div>
        )}
        {access.connected && saved.data && saved.data.length > 0 && (
          <section className="saved">
            <h2>Your dossiers</h2>
            {saved.data.map((w) => (
              <Link
                key={w.id}
                to={`/workspaces/${w.id}/overview`}
                className="saved-row"
              >
                <FolderOpen size={18} />
                <span>{w.canonical_address ?? "Property to be resolved"}</span>
                {w.is_demo && <small className="badge">Demo data</small>}
                <ChevronRight size={17} />
              </Link>
            ))}
          </section>
        )}
        <div className="principles">
          <div>
            <ShieldCheck />
            <h3>Start with the source</h3>
            <p>
              Official records and the documents you receive, with references
              you can follow.
            </p>
          </div>
          <div>
            <ListChecks />
            <h3>See the missing pieces</h3>
            <p>
              One clear checklist of available, missing and conditional
              information.
            </p>
          </div>
          <div>
            <MessageSquare />
            <h3>Know what to ask</h3>
            <p>
              Specific questions to clarify with your seller, syndic or notary.
            </p>
          </div>
        </div>
      </main>
      <footer className="landing-footer">
        Viesett · Property information for informed decisions
        <span>Flanders, Belgium</span>
      </footer>
    </div>
  );
}

export function PreviewCard({
  preview,
  selection,
  choose,
  check,
  create,
  actionLabel = "Create buyer dossier",
  busy = false,
}: {
  preview: PreviewResponse;
  selection: Selection;
  choose: (s: Selection) => void;
  check: () => void;
  create: () => void;
  actionLabel?: string;
  busy?: boolean;
}) {
  const result = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    result.current?.focus();
  }, [preview]);
  return (
    <section
      ref={result}
      tabIndex={-1}
      aria-label="Property preview result"
      className="preview panel"
      aria-live="polite"
    >
      <div className="eyebrow">
        {preview.is_demo ? "Demo property preview" : "Property preview"}
      </div>
      {preview.status === "UPSTREAM_UNAVAILABLE" ? (
        <>
          <h2>
            {preview.property.status === "INVALID_SOURCE_RESPONSE"
              ? "Official source response could not be confirmed"
              : "Official source temporarily unavailable"}
          </h2>
          <p>
            {preview.property.status === "INVALID_SOURCE_RESPONSE"
              ? "The official register returned information we could not validate. Your"
              : "We couldn't reach the official property register right now. Your"}{" "}
            address has not been marked as invalid.
          </p>
          <button className="button secondary" onClick={check}>
            Try again
          </button>
        </>
      ) : preview.status === "NOT_FOUND" ? (
        <>
          <h2>Property not found</h2>
          <p>
            No matching official address was returned. Check the spelling or try
            a more complete address.
          </p>
        </>
      ) : preview.status === "NEEDS_SELECTION" ? (
        <>
          <h2>Choose the right property</h2>
          <p>
            We found more than one address or private unit. Select the one you
            are reviewing.
          </p>
          <fieldset>
            <legend className="sr-only">Property selection</legend>
            {preview.choices.map((c) => (
              <label className="choice" key={c.address_id + ":" + c.unit_id}>
                <input
                  type="radio"
                  name="property-choice"
                  checked={
                    selection.selected_address_object_id === c.address_id &&
                    selection.selected_building_unit_object_id ===
                      (c.unit_id ?? undefined)
                  }
                  onChange={() =>
                    choose({
                      ...selection,
                      selected_address_object_id: c.address_id,
                      selected_building_unit_object_id: c.unit_id ?? undefined,
                    })
                  }
                />
                {c.label}
              </label>
            ))}
          </fieldset>
          {preview.truncated && (
            <p>
              More results exist. Refine the address if yours is not listed.
            </p>
          )}
          <button
            className="button"
            disabled={!selection.selected_address_object_id || busy}
            onClick={check}
          >
            Continue <ArrowRight size={16} />
          </button>
        </>
      ) : (
        <>
          <Badge status={preview.property.status} />
          <h2>{preview.property.address}</h2>
          <PropertyFacts property={preview.property} />
          <p className="muted">
            Heritage has not been checked in this preview. Public information
            can be refreshed in your dossier.
          </p>
          <button className="button" disabled={busy} onClick={create}>
            {actionLabel} <ArrowRight size={16} />
          </button>
        </>
      )}
    </section>
  );
}
