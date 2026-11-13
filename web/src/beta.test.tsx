import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import * as requests from "./api";
import {
  api,
  ApiError,
  configureBrowserSessions,
  setCsrf,
  setToken,
} from "./api";
import { Requirements } from "./Requirements";
import { PreviewCard } from "./pages/Start";
import { processingInterval } from "./polling";
import type { DossierSnapshotResponse } from "./contracts";
import raw from "./test-fixture.json";
const fixture = raw as DossierSnapshotResponse;
const session = {
  authenticated: true,
  csrf_token: "synthetic-csrf",
  expires_at: "2026-11-13T18:00:00Z",
};
function mount(
  path = `/workspaces/${fixture.workspace.id}/overview`,
  node = <App />,
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.spyOn(api, "config").mockResolvedValue({
    development_session: false,
    browser_sessions: true,
    demo: false,
    max_upload_bytes: 1024 * 1024,
  });
  vi.spyOn(api, "restore").mockResolvedValue(session);
  vi.spyOn(api, "dossier").mockResolvedValue(structuredClone(fixture));
  vi.spyOn(api, "workspaces").mockResolvedValue([]);
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});
afterEach(() => {
  vi.restoreAllMocks();
  configureBrowserSessions(false);
  setCsrf(null);
  setToken(null);
});

it("restores a private browser session across a remount without entering a bearer", async () => {
  const first = mount();
  await screen.findByRole("heading", { name: "Dossier completeness" });
  first.unmount();
  mount();
  expect(
    await screen.findByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  expect(api.restore).toHaveBeenCalledTimes(2);
  expect(screen.queryByLabelText("Access token")).not.toBeInTheDocument();
});
it("exchanges private access rather than keeping a raw bearer", async () => {
  vi.mocked(api.restore).mockRejectedValue(new ApiError(401));
  vi.spyOn(api, "exchange").mockResolvedValue(session);
  mount("/");
  await screen.findByRole("button", { name: "Open my dossiers" });
  await waitFor(() => expect(api.restore).toHaveBeenCalled());
  await userEvent.click(
    screen.getByRole("button", { name: "Open my dossiers" }),
  );
  await userEvent.type(screen.getByLabelText("Access token"), "s".repeat(64));
  await userEvent.click(screen.getByRole("button", { name: "Connect" }));
  expect(await screen.findByRole("button", { name: "Log out" })).toBeVisible();
  expect(api.exchange).toHaveBeenCalledWith("s".repeat(64));
  expect(screen.queryByLabelText("Access token")).not.toBeInTheDocument();
});
it("logs out on the server before removing private content", async () => {
  vi.spyOn(api, "logout").mockResolvedValue(undefined);
  mount();
  await screen.findByRole("heading", { name: "Dossier completeness" });
  await userEvent.click(screen.getAllByRole("button", { name: "Log out" })[0]);
  expect(api.logout).toHaveBeenCalledOnce();
  expect(
    await screen.findByRole("button", { name: "Check property" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "Dossier completeness" }),
  ).not.toBeInTheDocument();
});
it("reports a CSRF/logout error without pretending revocation succeeded", async () => {
  vi.spyOn(api, "logout").mockRejectedValue(new ApiError(403));
  mount();
  await screen.findByRole("heading", { name: "Dossier completeness" });
  await userEvent.click(screen.getAllByRole("button", { name: "Log out" })[0]);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Reload your private session",
  );
  expect(
    screen.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
});
it("expiry removes private state and gives keyboard focus to reconnect", async () => {
  mount();
  await screen.findByRole("heading", { name: "Dossier completeness" });
  act(() => window.dispatchEvent(new Event("viesett-session-expired")));
  expect(
    await screen.findByRole("button", { name: "Connect to dossier" }),
  ).toHaveFocus();
  expect(
    screen.queryByRole("heading", { name: "Dossier completeness" }),
  ).not.toBeInTheDocument();
});
it("separates May apply from confirmed missing information", () => {
  const item = structuredClone(fixture.requirements[0]);
  item.applicability = "CONDITIONAL";
  item.presence = "MISSING";
  mount("/", <Requirements items={[item]} />);
  expect(screen.getByRole("heading", { name: "Required now" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "May apply" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Received" })).toBeVisible();
  expect(
    screen.queryByText("Missing", { exact: true }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/Not counted as a confirmed missing requirement/),
  ).toBeVisible();
});
it("asks only the structured date need and keeps its unverified meaning visible", async () => {
  const d = structuredClone(fixture);
  d.context_questions = [
    {
      code: "KNOWN_DEED_DATE",
      question: "Do you know the signed deed date?",
      why_needed: "For a provisional timeline only.",
      answer_type: "DATE",
      affected_rule_codes: ["FL_EPC_RENOVATION"],
      source_preference: "A matched deed takes precedence.",
    },
  ];
  vi.mocked(api.dossier).mockResolvedValue(d);
  const updated = {
    ...d,
    context_questions: [],
    context_answers: [
      {
        code: "KNOWN_DEED_DATE" as const,
        value: "2026-02-28",
        authority: "UNVERIFIED" as const,
        evidence_id: "synthetic-answer",
      },
    ],
  };
  vi.spyOn(api, "answerContext").mockResolvedValue(updated);
  mount();
  const input = await screen.findByLabelText("Known signed deed date");
  fireEvent.change(input, { target: { value: "2026-02-28" } });
  await userEvent.click(
    screen.getByRole("button", {
      name: "Use as unverified transaction context",
    }),
  );
  expect(api.answerContext).toHaveBeenCalledWith(d.workspace.id, "2026-02-28");
  expect(await screen.findByText(/Buyer-provided deed date/)).toBeVisible();
  expect(
    screen.getByText(/does not establish an obligation or who pays/),
  ).toBeVisible();
});
it("offers a native viewer fallback and revokes its Blob on close", async () => {
  const revoke = vi.fn();
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: revoke,
  });
  vi.spyOn(requests, "privatePdf").mockResolvedValue(
    "blob:synthetic-private-pdf",
  );
  const view = mount(
    `/workspaces/${fixture.workspace.id}/documents/${fixture.documents[0].id}?page=3`,
  );
  expect(
    await screen.findByRole("link", { name: "Download PDF" }),
  ).toHaveAttribute("href", "blob:synthetic-private-pdf");
  await userEvent.click(
    screen.getByRole("button", { name: "Use download instead" }),
  );
  expect(
    screen.queryByTitle("Private document · target page 3"),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Target page 3", { exact: true })).toBeVisible();
  view.unmount();
  expect(revoke).toHaveBeenCalledWith("blob:synthetic-private-pdf");
});
it("distinguishes invalid official responses from register downtime", () => {
  mount(
    "/",
    <PreviewCard
      preview={{
        status: "UPSTREAM_UNAVAILABLE",
        property: { ...fixture.property, status: "INVALID_SOURCE_RESPONSE" },
        choices: [],
        truncated: false,
        is_demo: false,
      }}
      selection={{ query: "Teststraat" }}
      choose={vi.fn()}
      check={vi.fn()}
      create={vi.fn()}
    />,
  );
  expect(
    screen.getByRole("heading", {
      name: "Official source response could not be confirmed",
    }),
  ).toBeVisible();
  expect(screen.getByText(/has not been marked as invalid/)).toBeVisible();
});
it("polls only recent processing, backs off and stops after bounded failures", () => {
  const d = structuredClone(fixture),
    now = Date.now();
  d.documents[0].status = "IN_PROGRESS";
  d.documents[0].processing_since = new Date(now).toISOString();
  expect(processingInterval(d, 0, now)).toBe(3000);
  expect(processingInterval(d, 2, now)).toBe(12000);
  expect(processingInterval(d, 4, now)).toBe(false);
  expect(processingInterval(d, 0, now + 121000)).toBe(false);
  d.documents[0].status = "ANALYZED";
  expect(processingInterval(d, 0, now)).toBe(false);
});
