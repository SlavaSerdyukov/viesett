import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { Overview } from "./pages/Overview";
import { Findings } from "./pages/Findings";
import { Questions } from "./pages/Questions";
import { Documents } from "./pages/Documents";
import { CoOwnership } from "./pages/CoOwnership";
import { NotaryHandoff } from "./pages/Notary";
import { PrintDossier } from "./pages/Print";
import { Evidence } from "./pages/Evidence";
import { EvidenceSourceDetails, referenceFact } from "./EvidenceSourceDetails";
import { catalogSource } from "./sources";
import { SOURCE_CATALOG, type DossierSnapshotResponse } from "./contracts";
import raw from "./test-fixture.json";

const fixture = raw as DossierSnapshotResponse;
const apiUri = "https://api.basisregisters.vlaanderen.be/v2/adressen/43126";
const provenance = {
  ...catalogSource("GRAR", apiUri),
  source_identifier: `${apiUri}#property.address.canonical`,
  retrieved_at: "2026-11-19T10:00:00Z",
};

function data() {
  const d = structuredClone(fixture);
  for (const row of [...d.findings, ...d.questions, ...d.evidence])
    row.sources.push({ ...provenance });
  return d;
}
function mount(node: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

it.each([
  ["Overview", (d: DossierSnapshotResponse) => <Overview data={d} />],
  ["Findings", (d: DossierSnapshotResponse) => <Findings data={d} />],
  ["Questions", (d: DossierSnapshotResponse) => <Questions data={d} />],
  [
    "Documents",
    (d: DossierSnapshotResponse) => <Documents data={d} maxBytes={1024} />,
  ],
  [
    "Co-ownership",
    (d: DossierSnapshotResponse) => (
      <CoOwnership co={d.co_ownership!} data={d} />
    ),
  ],
  [
    "Notary handoff",
    (d: DossierSnapshotResponse) => <NotaryHandoff data={d} />,
  ],
  ["Full dossier", (d: DossierSnapshotResponse) => <PrintDossier data={d} />],
] as const)(
  "%s contains human sources without technical disclosures or API URIs",
  (_, view) => {
    const d = data(),
      before = JSON.stringify(d);
    const { container } = mount(view(d));
    expect(container.textContent).not.toContain(apiUri);
    expect(container.querySelector(".source-details")).toBeNull();
    expect(
      screen.queryByText(
        /Technical source|Raw source|API endpoint|Provider URI|GRAR API URI/,
      ),
    ).not.toBeInTheDocument();
    expect(container.querySelector(`a[href="${apiUri}"]`)).toBeNull();
    expect(JSON.stringify(d)).toBe(before);
  },
);

it("retains human official links and private document/page links in findings", async () => {
  mount(<Findings data={data()} />);
  await userEvent.click(screen.getAllByText("Sources & check details")[0]);
  expect(
    screen.getAllByRole("link", {
      name: "Official Flemish Address Register",
    })[0],
  ).toHaveAttribute("href", SOURCE_CATALOG.GRAR.human_url);
  expect(
    screen.getByRole("link", { name: /Syndic demo.pdf · page 1/i }),
  ).toHaveAttribute(
    "href",
    expect.stringMatching(/\/workspaces\/[^/]+\/documents\/[^/]+\?page=1$/),
  );
});

it("keeps registry object numbers out of the notary identity block", () => {
  const d = data();
  d.property.address_id = "ADDRESS_OBJECT_SENTINEL";
  d.property.unit_id = "UNIT_OBJECT_SENTINEL";
  const { container } = mount(<NotaryHandoff data={d} />);
  expect(container.textContent).not.toMatch(
    /ADDRESS_OBJECT_SENTINEL|UNIT_OBJECT_SENTINEL|Address object:/,
  );
  expect(
    screen.getByText(/Building unit: Matched to the official address/),
  ).toBeVisible();
  expect(screen.getByText(/Parcels:/)).toBeVisible();
});

it("Evidence keeps source details closed, with readable facts, authority, source and date", async () => {
  const d = data();
  d.co_ownership = null;
  const canonical = { ...d.evidence[0], sources: [provenance] };
  const ref = {
    ...canonical,
    id: "object-reference",
    key: "property.address.object_id",
    label: "address · object id",
    value: "43126",
  };
  d.evidence = [canonical, ref];
  const { container } = mount(<Evidence data={d} />);
  expect(
    screen.getByRole("heading", { name: "Official records" }),
  ).toBeVisible();
  expect(screen.getByText(canonical.value)).toBeVisible();
  expect(
    screen.getAllByRole("link", {
      name: "Official Flemish Address Register",
    })[0],
  ).toBeVisible();
  for (const details of container.querySelectorAll<HTMLDetailsElement>(
    ".source-details",
  ))
    expect(details.open).toBe(false);
  expect(
    screen.getAllByText("Provider: Digitaal Vlaanderen")[0],
  ).not.toBeVisible();
  const row = screen
    .getByText("Address registry reference")
    .closest(".evidence-row") as HTMLElement;
  expect(within(row).getByText("Provider object ID: 43126")).not.toBeVisible();
  await userEvent.click(within(row).getByText("Source details"));
  expect(within(row).getByText("Provider object ID: 43126")).toBeVisible();
  expect(within(row).getByText("Provider: Digitaal Vlaanderen")).toBeVisible();
  expect(within(row).getByText("Retrieved: 19 Nov 2026")).toBeVisible();
  expect(container.textContent).not.toContain(apiUri);
});

it("opened Evidence details ignore secrets, raw JSON, filesystem/storage keys and URI identifiers", async () => {
  const d = data();
  d.co_ownership = null;
  const source = Object.assign(
    { ...provenance },
    {
      credentials: "SECRET_SENTINEL",
      storage_key: "STORAGE_SENTINEL",
      filesystem_path: "/private/PRIVATE_PATH_SENTINEL",
      provider_response: { body: "RAW_JSON_SENTINEL" },
      database_id: "DATABASE_ID_SENTINEL",
    },
  );
  d.evidence = [{ ...d.evidence[0], sources: [source] }];
  const { container } = mount(<Evidence data={d} />);
  await userEvent.click(screen.getByText("Source details"));
  expect(screen.getByText("Provider: Digitaal Vlaanderen")).toBeVisible();
  expect(container.textContent).not.toMatch(
    /SENTINEL|\/private\/|https:\/\/api\./,
  );
  expect(container.querySelector("pre, code")).toBeNull();
  expect(source.technical_uri).toBe(apiUri);
});

it.each(["property.heritage.type_uri", "property.heritage.match_basis"])(
  "Evidence keeps %s machine references out of both primary and opened details",
  async (key) => {
    const d = data();
    d.co_ownership = null;
    d.evidence = [
      { ...d.evidence[0], key, value: apiUri, sources: [provenance] },
    ];
    const { container } = mount(<Evidence data={d} />);
    await userEvent.click(screen.getByText("Source details"));
    expect(container.textContent).not.toContain(apiUri);
    expect(d.evidence[0].value).toBe(apiUri);
  },
);

it("does not render empty details or unknown providers or treat unverified facts as registry references", () => {
  const e = { ...data().evidence[0], sources: [] };
  const { container, rerender } = mount(<EvidenceSourceDetails evidence={e} />);
  expect(container.querySelector("details")).toBeNull();
  rerender(
    <EvidenceSourceDetails
      evidence={{
        ...e,
        sources: [{ ...provenance, provider: "__proto__", retrieved_at: null }],
      }}
    />,
  );
  expect(container.querySelector("details")).toBeNull();
  expect(
    referenceFact({
      ...e,
      key: "property.address.object_id",
      authority: "UNVERIFIED",
    }),
  ).toBeUndefined();
});
