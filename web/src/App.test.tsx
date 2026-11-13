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
import { api, setToken } from "./api";
import { App } from "./App";
import { Badge, Citations, Completeness } from "./components";
import { FindingCard } from "./pages/Findings";
import { PreviewCard } from "./pages/Start";
import { PrintDossier } from "./pages/Print";
import { Questions } from "./pages/Questions";
import { Exposure } from "./pages/CoOwnership";
import type {
  DossierSnapshotResponse,
  PolicyOut,
  PreviewResponse,
} from "./contracts";
import raw from "./test-fixture.json";
const fixture = raw as DossierSnapshotResponse;
function data() {
  return structuredClone(fixture);
}
function mount(node: React.ReactNode, path = "/") {
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
async function page(section: string, d = data()) {
  vi.spyOn(api, "dossier").mockResolvedValue(d);
  mount(<App />, `/workspaces/${d.workspace.id}/${section}`);
  await userEvent.click(
    screen.getByRole("button", { name: "Connect to dossier" }),
  );
  await userEvent.type(screen.getByLabelText("Access token"), "t".repeat(64));
  await userEvent.click(screen.getByRole("button", { name: "Connect" }));
  await screen.findByRole("heading", { name: d.property.address! });
}
beforeEach(() => {
  vi.spyOn(api, "config").mockResolvedValue({
    development_session: false,
    browser_sessions: false,
    demo: false,
    max_upload_bytes: 10 * 1024 * 1024,
  });
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
  setToken(null);
});

it("submits the address form and renders the official preview", async () => {
  vi.spyOn(api, "preview").mockResolvedValue({
    status: "RESOLVED",
    property: fixture.property,
    choices: [],
    truncated: false,
    is_demo: false,
  });
  mount(<App />);
  await userEvent.type(
    screen.getByLabelText("Enter the property address"),
    "Teststraat 42 Gent",
  );
  await userEvent.click(screen.getByRole("button", { name: "Check property" }));
  expect(api.preview).toHaveBeenCalledWith({ query: "Teststraat 42 Gent" });
  expect(
    await screen.findByRole("heading", { name: fixture.property.address! }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Create buyer dossier" }),
  ).toBeVisible();
});
it("requires selection for ambiguity and keeps identifiers out of labels", async () => {
  const choose = vi.fn(),
    check = vi.fn();
  const preview: PreviewResponse = {
    status: "NEEDS_SELECTION",
    property: fixture.property,
    choices: [{ address_id: "999", unit_id: "34", label: "Bus 2" }],
    truncated: false,
    is_demo: false,
  };
  mount(
    <PreviewCard
      preview={preview}
      selection={{ query: "Teststraat" }}
      choose={choose}
      check={check}
      create={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: "Bus 2" }));
  expect(choose).toHaveBeenCalledWith({
    query: "Teststraat",
    selected_address_object_id: "999",
    selected_building_unit_object_id: "34",
  });
  expect(screen.queryByText("999")).not.toBeInTheDocument();
});
it.each(["UPSTREAM_UNAVAILABLE", "NOT_FOUND"] as const)(
  "explains preview outcome %s without conflating missing and unavailable",
  (status) => {
    mount(
      <PreviewCard
        preview={{
          status,
          property: fixture.property,
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
        name:
          status === "NOT_FOUND"
            ? "Property not found"
            : "Official source temporarily unavailable",
      }),
    ).toBeVisible();
    if (status === "UPSTREAM_UNAVAILABLE")
      expect(screen.getByText(/has not been marked as invalid/)).toBeVisible();
  },
);
it("renders overview identity, completeness, missing information and next actions", async () => {
  await page("overview");
  expect(
    screen.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Needs attention" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Missing information" }),
  ).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Review your questions" }),
  ).toHaveAttribute("href", expect.stringContaining("/questions"));
});
it("opens a selected preview as a private dossier after connecting", async () => {
  vi.spyOn(api, "preview").mockResolvedValue({
    status: "RESOLVED",
    property: fixture.property,
    choices: [],
    truncated: false,
    is_demo: false,
  });
  vi.spyOn(api, "create").mockResolvedValue(data());
  vi.spyOn(api, "dossier").mockResolvedValue(data());
  mount(<App />);
  await userEvent.type(
    screen.getByLabelText("Enter the property address"),
    "Teststraat",
  );
  await userEvent.click(screen.getByRole("button", { name: "Check property" }));
  await userEvent.click(
    await screen.findByRole("button", { name: "Create buyer dossier" }),
  );
  await userEvent.type(screen.getByLabelText("Access token"), "t".repeat(64));
  await userEvent.click(screen.getByRole("button", { name: "Connect" }));
  expect(
    await screen.findByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  expect(api.create).toHaveBeenCalledWith({ query: "Teststraat" });
});
it("shows transparent completeness counts, conditional exclusions and a separate meaning from risk", () => {
  mount(
    <Completeness
      value={{
        state: "INCOMPLETE",
        completed_count: 6,
        applicable_count: 8,
        percentage: 75,
        conditional_count: 2,
        basis: "unweighted",
      }}
    />,
  );
  expect(screen.getByText("75%")).toBeVisible();
  expect(screen.getByText("6 of 8 applicable checks complete")).toBeVisible();
  expect(screen.getByText(/2 conditional checks/)).toBeVisible();
  expect(screen.getByText(/does not certify/)).toBeVisible();
});
it("shows unknown completeness without claiming 100 percent", () => {
  mount(
    <Completeness
      value={{
        state: "BLOCKED_BY_MISSING_DATA",
        completed_count: 0,
        applicable_count: 0,
        percentage: null,
        conditional_count: 3,
        basis: "unweighted",
      }}
    />,
  );
  expect(screen.getByText("—")).toBeVisible();
  expect(screen.queryByText("100%")).not.toBeInTheDocument();
});
it("groups findings by meaning and keeps codes in details", async () => {
  await page("findings");
  expect(screen.getByRole("heading", { name: "Energy" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Electrical" })).toBeVisible();
  expect(screen.getAllByText("What to clarify next").length).toBeGreaterThan(0);
});
it("offers expandable rule details and source citations", async () => {
  mount(
    <FindingCard finding={fixture.findings[0]} wid={fixture.workspace.id} />,
  );
  await userEvent.click(screen.getByText("Sources & check details"));
  expect(screen.getByText(new RegExp(fixture.findings[0].code))).toBeVisible();
});
it("links a citation to a private document at the requested page", () => {
  mount(
    <Citations
      wid="w"
      sources={[
        {
          document_id: "d",
          label: "EPC.pdf",
          page: 3,
          uri: null,
          retrieved_at: null,
        },
      ]}
    />,
  );
  expect(
    screen.getByRole("link", { name: "EPC.pdf · page 3" }),
  ).toHaveAttribute("href", "/workspaces/w/documents/d?page=3");
});
it("renders required and conditional checklist states without declaring all conditional items missing", async () => {
  await page("documents");
  expect(
    screen.getByRole("heading", { name: "Document checklist" }),
  ).toBeVisible();
  expect(screen.getAllByText("May apply").length).toBeGreaterThan(0);
  expect(screen.getByText("Soil certificate", { exact: true })).toBeVisible();
});
it("represents OCR required honestly and retains keep/delete choice", async () => {
  const d = data();
  d.documents[0].status = "OCR_REQUIRED";
  await page("documents", d);
  expect(screen.getByText(/appears to be scanned/)).toBeVisible();
  expect(screen.getByText(/keep the document or delete it/)).toBeVisible();
});
it("uses the existing manual classification path for an unknown document", async () => {
  const d = data();
  d.documents[0].status = "UNKNOWN";
  d.documents[0].kind = "UNKNOWN";
  vi.spyOn(api, "classify").mockResolvedValue({});
  await page("documents", d);
  const select = screen.getByLabelText(
    `Document type for ${d.documents[0].filename}`,
  );
  await userEvent.selectOptions(select, "EPC");
  expect(api.classify).toHaveBeenCalledWith(
    d.workspace.id,
    d.documents[0].id,
    "EPC",
  );
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: /Uploaded documents/ }),
    ).toHaveFocus(),
  );
});
it("shows upload work while the real orchestration request is pending", async () => {
  const policy: PolicyOut = {
    id: "p",
    policy_type: "UPLOAD_ATTESTATION",
    version: "test",
    text: "Upload only relevant documents.",
    current: true,
    created_at: "2026-11-12T00:00:00Z",
  };
  vi.spyOn(api, "policies").mockResolvedValue([policy]);
  vi.spyOn(api, "acknowledge").mockResolvedValue(undefined);
  let finish!: (d: DossierSnapshotResponse) => void;
  vi.spyOn(api, "upload").mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  await page("documents");
  await userEvent.upload(
    screen.getByLabelText("Upload property PDFs"),
    new File(["%PDF-demo"], "fixture.pdf", { type: "application/pdf" }),
  );
  await userEvent.click(await screen.findByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(
    await screen.findByText("Uploading, checking & reading documents…"),
  ).toBeVisible();
  await act(async () => finish(data()));
  expect(api.upload).toHaveBeenCalled();
});
it("renders co-ownership funds and package coverage", async () => {
  await page("co-ownership");
  expect(
    screen.getByRole("heading", { name: "Article 3.94 information" }),
  ).toBeVisible();
  expect(screen.getByText("Working capital", { exact: true })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Planned works" })).toBeVisible();
});
it("shows financial assumptions and never describes an estimate as buyer debt", () => {
  mount(<Exposure co={fixture.co_ownership!} data={fixture} />);
  expect(screen.getByText(/6,000/)).toBeVisible();
  expect(screen.getByText("Not determined")).toBeVisible();
  expect(screen.getByText("Assumptions & sources")).toBeVisible();
  expect(screen.queryByText(/you owe/i)).not.toBeInTheDocument();
});
it("does not show a precise number when allocation is unknown", () => {
  const d = data();
  d.co_ownership!.financial_exposure_estimates[0].status = "UNKNOWN_ALLOCATION";
  mount(<Exposure co={d.co_ownership!} data={d} />);
  expect(screen.getByText(/precise estimate is not available/)).toBeVisible();
  expect(screen.queryByText(/6,000/)).not.toBeInTheDocument();
});
it("groups questions by target and includes reasons and copy actions", () => {
  mount(<Questions data={fixture} />);
  expect(screen.getByRole("heading", { name: "Ask the notary" })).toBeVisible();
  expect(screen.getAllByText(/Why:/).length).toBeGreaterThan(0);
  expect(
    screen.getByRole("button", { name: "Copy all questions" }),
  ).toBeVisible();
});
it("separates official, documented and derived evidence", async () => {
  await page("evidence");
  expect(
    screen.getByRole("heading", { name: "Official records" }),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "From documents" })).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Derived / inferred calculations" }),
  ).toBeVisible();
});
it("shows an intentional empty documents state", async () => {
  const d = data();
  d.documents = [];
  await page("documents", d);
  expect(
    screen.getByRole("heading", { name: "No property documents yet" }),
  ).toBeVisible();
});
it("shows a safe error state for a failed preview", async () => {
  vi.spyOn(api, "preview").mockRejectedValue(
    new Error("Connection interrupted. Please try again."),
  );
  mount(<App />);
  await userEvent.type(
    screen.getByLabelText("Enter the property address"),
    "Teststraat",
  );
  await userEvent.click(screen.getByRole("button", { name: "Check property" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Connection interrupted",
  );
});
it("requires document deletion confirmation", async () => {
  vi.spyOn(api, "remove").mockResolvedValue(undefined);
  await page("documents");
  await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
  expect(
    screen.getByRole("heading", { name: "Delete this document?" }),
  ).toBeVisible();
  expect(api.remove).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Keep document" }));
  expect(api.remove).not.toHaveBeenCalled();
  expect(screen.getAllByRole("button", { name: "Delete" })[0]).toHaveFocus();
});
it("prepares an honest print dossier and a browser print action", () => {
  mount(<PrintDossier data={fixture} />);
  expect(
    screen.getByRole("button", { name: "Print / Save as PDF" }),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "Source list" })).toBeVisible();
  expect(screen.getByText(new RegExp(fixture.findings[0].code))).toBeVisible();
  expect(screen.getByText(/Legally significant decisions/)).toBeVisible();
});
it("maps missing data to information language rather than a blocked purchase", () => {
  mount(<Badge status="BLOCKING_DATA_GAP" />);
  expect(screen.getByText("Missing information")).toBeVisible();
});
it("offers a manual clipboard fallback without exposing errors", () => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: {
      writeText: vi.fn().mockRejectedValue(new Error("private browser error")),
    },
  });
  mount(<Questions data={fixture} />);
  fireEvent.click(screen.getByRole("button", { name: "Copy all questions" }));
  return screen.findByText("Select the text to copy it manually.");
});

it("can confirm a previously unavailable property inside the same dossier", async () => {
  const d = data();
  d.property.status = "UPSTREAM_UNAVAILABLE";
  d.property.address = null;
  vi.spyOn(api, "preview").mockResolvedValue({
    status: "RESOLVED",
    property: fixture.property,
    choices: [],
    truncated: false,
    is_demo: false,
  });
  vi.spyOn(api, "resolve").mockResolvedValue({});
  vi.spyOn(api, "dossier").mockResolvedValue(d);
  mount(<App />, `/workspaces/${d.workspace.id}/overview`);
  await userEvent.click(
    screen.getByRole("button", { name: "Connect to dossier" }),
  );
  await userEvent.type(screen.getByLabelText("Access token"), "t".repeat(64));
  await userEvent.click(screen.getByRole("button", { name: "Connect" }));
  await userEvent.click(
    await screen.findByRole("button", { name: "Check this property again" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Check official address" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Confirm this selection" }),
  );
  expect(api.resolve).toHaveBeenCalledWith(d.workspace.id, {
    query: d.property.query,
  });
});
it("retries processing without recording a new manual classification", async () => {
  const d = data();
  d.documents[0].status = "FAILED";
  d.documents[0].can_retry = true;
  vi.spyOn(api, "retry").mockResolvedValue({});
  await page("documents", d);
  await userEvent.click(screen.getByRole("button", { name: "Retry reading" }));
  expect(api.retry).toHaveBeenCalledWith(d.workspace.id, d.documents[0].id);
});
