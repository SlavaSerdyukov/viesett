import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { Citations, SourceAppendix } from "./SourceCitations";
import { catalogSource, groupSources } from "./sources";
import type { CitationResponse, DossierSnapshotResponse } from "./contracts";
import { SOURCE_CATALOG } from "./contracts";
import raw from "./test-fixture.json";
const data = raw as DossierSnapshotResponse;
const apiUri = "https://api.basisregisters.vlaanderen.be/v2/adressen/1";
const register = {
  ...catalogSource("GRAR", apiUri),
  source_identifier: "address:1",
};
const docCitation: CitationResponse = {
  label: "EPC.pdf",
  kind: "DOCUMENT",
  document_id: "private-document",
  page: 1,
  uri: null,
  technical_uri: null,
  human_url: null,
  provider: null,
  source_identifier: null,
  retrieved_at: null,
};
function mount(sources: CitationResponse[], appendix = false) {
  return render(
    <MemoryRouter>
      {appendix ? (
        <SourceAppendix sources={sources} data={data} />
      ) : (
        <Citations sources={sources} wid="workspace" />
      )}
    </MemoryRouter>,
  );
}

it("uses the reviewed GRAR page while retaining exact API provenance in data only", () => {
  mount([register]);
  expect(
    screen.getByRole("link", { name: "Official Flemish Address Register" }),
  ).toHaveAttribute("href", SOURCE_CATALOG.GRAR.human_url);
  expect(screen.queryByText(apiUri)).not.toBeInTheDocument();
  expect(document.querySelector(`a[href="${apiUri}"]`)).toBeNull();
  expect(screen.queryByText(/Technical source/)).not.toBeInTheDocument();
  expect(register.technical_uri).toBe(apiUri);
  expect(register.source_identifier).toBe("address:1");
});

it("collapses a provider's multiple objects without dropping underlying technical references", () => {
  const otherUri = "https://api.basisregisters.vlaanderen.be/v2/gebouwen/100";
  const sources = [
    register,
    {
      ...register,
      technical_uri: otherUri,
      uri: otherUri,
      source_identifier: "building:100",
    },
    register,
  ];
  mount(sources);
  expect(
    screen.getAllByRole("link", { name: "Official Flemish Address Register" }),
  ).toHaveLength(1);
  expect(screen.queryByText(apiUri)).not.toBeInTheDocument();
  expect(screen.queryByText(otherUri)).not.toBeInTheDocument();
  expect(groupSources(sources)[0].references).toHaveLength(3);
  expect(
    groupSources(sources)[0].references.map((s) => s.technical_uri),
  ).toEqual([apiUri, otherUri, apiUri]);
});

it("keeps private document page navigation and separates evidence from rule guidance", () => {
  mount([register, docCitation, docCitation, catalogSource("SOIL")]);
  const evidence = screen.getByRole("group", { name: "Evidence" });
  expect(
    within(evidence).getByRole("link", { name: "EPC.pdf · page 1" }),
  ).toHaveAttribute(
    "href",
    "/workspaces/workspace/documents/private-document?page=1",
  );
  expect(
    within(evidence).queryByText("OVAM — Soil certificate"),
  ).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("group", { name: "Rule / guidance" })).getByRole(
      "link",
      { name: "OVAM — Soil certificate" },
    ),
  ).toHaveAttribute("href", SOURCE_CATALOG.SOIL.human_url);
});

it.each([
  "javascript:alert(1)",
  "data:text/html,private",
  "//unapproved.example/source",
  "https://unapproved.example/",
  "https://www.vlaanderen.be@unapproved.example/",
  "https://www.vlaanderen.be/unreviewed",
  SOURCE_CATALOG.GRAR.human_url + "?redirect=elsewhere",
])("does not turn unapproved human URL %s into a link", (uri) => {
  mount([
    {
      ...register,
      label: "Unapproved source",
      human_url: uri,
      technical_uri: uri,
      uri,
    },
  ]);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(screen.getByText("Unapproved source")).toBeVisible();
});

it("does not promote arbitrary legacy HTTPS provenance into a primary link", () => {
  mount([
    {
      ...register,
      human_url: null,
      provider: null,
      uri: "https://unapproved.example/data",
      technical_uri: null,
    },
  ]);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("groups appendix sources once per provider and document, with sorted distinct pages", () => {
  mount(
    [
      register,
      { ...register, uri: "https://data.vlaanderen.be/id/gebouw/100" },
      docCitation,
      { ...docCitation, page: 3 },
      docCitation,
      catalogSource("SOIL"),
      catalogSource("SOIL"),
    ],
    true,
  );
  expect(
    screen.getByRole("heading", {
      name: "Official registers and public sources",
    }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Uploaded documents" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Rules and official guidance" }),
  ).toBeVisible();
  expect(
    screen.getAllByRole("link", { name: "Official Flemish Address Register" }),
  ).toHaveLength(1);
  expect(
    screen.getAllByRole("link", { name: "OVAM — Soil certificate" }),
  ).toHaveLength(1);
  const link = screen.getByRole("link", { name: "EPC.pdf" });
  expect(link.closest("li")).toHaveTextContent("Pages: 1, 3");
});
