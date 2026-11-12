import { afterEach, expect, it, vi } from "vitest";
import { request, setToken } from "./api";
afterEach(() => {
  setToken(null);
  vi.unstubAllGlobals();
});
it("keeps bearer access in a header and does not expose server error bodies", async () => {
  const storage = { setItem: vi.fn() };
  vi.stubGlobal("localStorage", storage);
  const fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ detail: "PRIVATE_DOCUMENT_CONTENT" }), {
      status: 401,
    }),
  );
  vi.stubGlobal("fetch", fetch);
  setToken("synthetic-private-token");
  await expect(request("/workspaces")).rejects.toThrow(
    "Your private session has ended",
  );
  expect(fetch.mock.calls[0][1]).toMatchObject({
    credentials: "omit",
    cache: "no-store",
    headers: { Authorization: "Bearer synthetic-private-token" },
  });
  expect(storage.setItem).not.toHaveBeenCalled();
});
it("omits credentials for the public preview", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  setToken("synthetic-private-token");
  await request("/property-preview", { method: "POST", body: "{}" }, false);
  expect(fetch.mock.calls[0][1].headers.Authorization).toBeUndefined();
});
