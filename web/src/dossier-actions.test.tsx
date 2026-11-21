import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { api, ApiError, configureBrowserSessions, setCsrf } from "./api";
import type { DossierSnapshotResponse, PreviewResponse } from "./contracts";
import raw from "./test-fixture.json";

const fixture = raw as DossierSnapshotResponse;
function mount(path = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(["dossier", fixture.workspace.id], fixture);
  client.setQueryData(["dossier", "other-dossier"], { retained: true });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}
beforeEach(() => {
  vi.spyOn(api, "config").mockResolvedValue({
    development_session: false,
    browser_sessions: true,
    demo: true,
    max_upload_bytes: 1024,
  });
  vi.spyOn(api, "restore").mockResolvedValue({
    authenticated: true,
    csrf_token: "synthetic-csrf",
    expires_at: "2030-01-01T00:00:00Z",
  });
  vi.spyOn(api, "workspaces").mockResolvedValue([fixture.workspace]);
  vi.spyOn(api, "dossier").mockResolvedValue(structuredClone(fixture));
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
});

it("confirms whole-dossier deletion, updates the list and clears only its private cache", async () => {
  const remove = vi.spyOn(api, "removeDossier").mockImplementation(async () => {
    vi.mocked(api.workspaces).mockResolvedValue([]);
  });
  const client = mount();
  const button = await screen.findByRole("button", {
    name: /^Delete dossier for/,
  });
  await userEvent.click(button);
  expect(screen.getByRole("dialog")).toHaveTextContent(
    "uploaded PDFs, findings, evidence and history",
  );
  expect(remove).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Keep dossier" }));
  expect(button).toHaveFocus();
  expect(remove).not.toHaveBeenCalled();
  await userEvent.click(button);
  await userEvent.click(
    screen.getByRole("button", { name: "Delete dossier permanently" }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: /^Delete dossier for/ }),
    ).not.toBeInTheDocument(),
  );
  expect(remove).toHaveBeenCalledExactlyOnceWith(fixture.workspace.id);
  expect(
    client.getQueryData(["dossier", fixture.workspace.id]),
  ).toBeUndefined();
  expect(client.getQueryData(["dossier", "other-dossier"])).toEqual({
    retained: true,
  });
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: /Check a property/ }),
    ).toHaveFocus(),
  );
  expect(screen.getByRole("status")).toHaveTextContent("Dossier deleted.");
});

it("keeps the dossier and shows deletion errors inside the confirmation dialog", async () => {
  vi.spyOn(api, "removeDossier").mockRejectedValue(new ApiError(403));
  const client = mount(`/workspaces/${fixture.workspace.id}/overview`);
  await screen.findByRole("heading", { name: "Dossier completeness" });
  await userEvent.click(
    screen.getByRole("button", { name: /^Delete dossier for/ }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Delete dossier permanently" }),
  );
  const error = await screen.findByRole("alert");
  expect(screen.getByRole("dialog")).toContainElement(error);
  expect(error).toHaveTextContent("Reload your private session");
  expect(client.getQueryData(["dossier", fixture.workspace.id])).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
});

it("returns from a deleted open dossier to the refreshed start page", async () => {
  vi.spyOn(api, "removeDossier").mockImplementation(async () => {
    vi.mocked(api.workspaces).mockResolvedValue([]);
  });
  mount(`/workspaces/${fixture.workspace.id}/overview`);
  await screen.findByRole("heading", { name: "Dossier completeness" });
  await userEvent.click(
    screen.getByRole("button", { name: /^Delete dossier for/ }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Delete dossier permanently" }),
  );
  expect(
    await screen.findByRole("button", { name: "Check property" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "Dossier completeness" }),
  ).not.toBeInTheDocument();
});

it("ignores an older search result after the user checks a different address", async () => {
  let finishOld!: (value: PreviewResponse) => void;
  vi.spyOn(api, "preview")
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve;
        }),
    )
    .mockResolvedValueOnce({
      status: "NOT_FOUND",
      property: { ...fixture.property, status: "NOT_FOUND", address: null },
      choices: [],
      truncated: false,
      is_demo: true,
    });
  mount();
  await screen.findByRole("button", { name: "Log out" });
  const input = await screen.findByLabelText("Enter the property address");
  await userEvent.type(input, "Teststraat 42 Gent");
  await userEvent.click(screen.getByRole("button", { name: "Check property" }));
  await userEvent.clear(input);
  await userEvent.type(input, "Unrelated fictional street 999");
  await userEvent.click(screen.getByRole("button", { name: "Check property" }));
  await screen.findByRole("heading", { name: "Address not in the demo" });
  await act(async () =>
    finishOld({
      status: "RESOLVED",
      property: fixture.property,
      choices: [],
      truncated: false,
      is_demo: true,
    }),
  );
  expect(
    screen.getByRole("heading", { name: "Address not in the demo" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Create buyer dossier" }),
  ).not.toBeInTheDocument();
});
