import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NotaryHandoff } from "./pages/Notary";
import { App } from "./App";
import { api, configureBrowserSessions, setCsrf } from "./api";
import type { DossierSnapshotResponse } from "./contracts";
import raw from "./test-fixture.json";
const fixture = raw as DossierSnapshotResponse;
function mount(data = structuredClone(fixture)) {
  return render(
    <MemoryRouter>
      <NotaryHandoff data={data} />
    </MemoryRouter>,
  );
}
afterEach(() => {
  vi.restoreAllMocks();
  configureBrowserSessions(false);
  setCsrf(null);
});

it("routes Prepare for notary and Print full dossier to different, dedicated views", async () => {
  vi.spyOn(api, "config").mockResolvedValue({
    demo: true,
    development_session: false,
    browser_sessions: true,
    max_upload_bytes: 1024,
  });
  vi.spyOn(api, "restore").mockResolvedValue({
    authenticated: true,
    csrf_token: "synthetic-csrf",
    expires_at: "2030-01-01T00:00:00Z",
  });
  vi.spyOn(api, "dossier").mockResolvedValue(structuredClone(fixture));
  vi.spyOn(api, "workspaces").mockResolvedValue([]);
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter
        initialEntries={[`/workspaces/${fixture.workspace.id}/overview`]}
      >
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Dossier completeness" });
  expect(
    screen.getByRole("link", { name: "Prepare for notary" }),
  ).toHaveAttribute("href", `/workspaces/${fixture.workspace.id}/notary`);
  expect(
    screen.getByRole("link", { name: "Print full dossier" }),
  ).toHaveAttribute("href", `/workspaces/${fixture.workspace.id}/print`);
  await userEvent.click(
    screen.getByRole("link", { name: "Prepare for notary" }),
  );
  await screen.findByRole("heading", { name: "Notary handoff" });
  expect(
    screen.queryByRole("heading", { name: "Document checklist" }),
  ).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("link", { name: "Print full dossier" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Document checklist" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Article 3.94 information" }),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "Ask the seller" })).toBeVisible();
});

it("keeps important unresolved matters without INFO cards, check codes or interactive details", () => {
  const data = structuredClone(fixture);
  data.findings.push({
    ...data.findings[0],
    id: "info-only",
    severity: "INFO",
    title: "INFO_ONLY_TITLE",
  });
  const before = JSON.stringify(data);
  const { container } = mount(data);
  for (const f of data.findings.filter((f) => f.severity !== "INFO"))
    expect(screen.getByRole("heading", { name: f.title })).toBeVisible();
  expect(screen.queryByText("INFO_ONLY_TITLE")).not.toBeInTheDocument();
  expect(container.querySelector("details")).toBeNull();
  for (const f of data.findings)
    expect(
      screen.queryByText(new RegExp(`Check ${f.code}`)),
    ).not.toBeInTheDocument();
  expect(JSON.stringify(data)).toBe(before);
});

it("prints only notary-targeted questions, preserving their reason and evidence", () => {
  const data = structuredClone(fixture);
  for (const role of ["SELLER", "AGENT", "SYNDIC"])
    data.questions.push({
      ...data.questions[0],
      key: role,
      target_role: role,
      question_text: `${role}_ONLY_QUESTION`,
    });
  const { container } = mount(data);
  const section = container.querySelector(".notary-questions")! as HTMLElement;
  for (const q of data.questions.filter((q) => q.target_role === "NOTARY"))
    expect(within(section).getByText(q.question_text)).toBeVisible();
  for (const role of ["SELLER", "AGENT", "SYNDIC"])
    expect(screen.queryByText(`${role}_ONLY_QUESTION`)).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: /Ask the (seller|agent|syndic)/ }),
  ).not.toBeInTheDocument();
});

it("summarizes gaps instead of reproducing the complete checklist and Article 3.94 table", () => {
  mount();
  expect(
    screen.getByRole("heading", { name: "Missing documents / information" }),
  ).toBeVisible();
  expect(screen.getByText("Soil certificate", { exact: true })).toBeVisible();
  expect(
    screen.getByText(/Latest approved balance copy \(partial\)/),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "May apply / unresolved" }),
  ).toBeVisible();
  for (const name of [
    "Required now",
    "Received",
    "Article 3.94 information",
    "Documents supplied",
    "Working capital amount",
  ])
    expect(screen.queryByRole("heading", { name })).not.toBeInTheDocument();
  expect(
    screen.getByText(
      /Completeness is information coverage, not a safety score/,
    ),
  ).toBeVisible();
});

it("preserves the exact financial result, input amounts, assumptions and undetermined legal responsibility", () => {
  mount();
  expect(
    screen.getByRole("heading", { name: "Financial exposure" }),
  ).toBeVisible();
  expect(screen.getByText(/€6,000\.00/)).toBeVisible();
  expect(screen.getByText(/Project cost €120,000\.00/)).toHaveTextContent(
    "Explicit project funding €40,000.00",
  );
  expect(screen.getByText(/Applicable share 75\/1000/)).toBeVisible();
  expect(
    screen.getByText("Legal payment responsibility: Not determined"),
  ).toBeVisible();
  for (const assumption of fixture.co_ownership!.financial_exposure_estimates[0]
    .assumptions)
    expect(screen.getByText(assumption)).toBeVisible();
});

it("does not print a precise exposure when allocation is unestablished", () => {
  const data = structuredClone(fixture);
  data.co_ownership!.financial_exposure_estimates[0].status =
    "UNKNOWN_ALLOCATION";
  const { container } = mount(data);
  expect(screen.getByText(/A precise estimate is not available/)).toBeVisible();
  expect(container.querySelector(".notary-amount")).toBeNull();
});

it("groups the source appendix and explains native browser header/footer settings", async () => {
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  mount();
  for (const name of [
    "Official registers and public sources",
    "Uploaded documents",
    "Rules and official guidance",
  ])
    expect(screen.getByRole("heading", { name })).toBeVisible();
  expect(screen.getByText(/disable “Headers and footers”/)).toHaveClass(
    "print-help",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Print / Save as PDF" }),
  );
  expect(print).toHaveBeenCalledOnce();
});

it("preserves every important matter in larger inputs and exposes upstream projection limits", () => {
  const data = structuredClone(fixture);
  data.truncated = true;
  for (let i = 0; i < 25; i++)
    data.findings.push({
      ...data.findings[0],
      id: `extra-${i}`,
      title: `Extra matter ${i}`,
    });
  mount(data);
  expect(screen.getByText(/bounded current dossier projection/)).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Extra matter 24" }),
  ).toBeVisible();
});
