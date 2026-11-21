import { test, expect, type Locator, type Page } from "@playwright/test";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../src/test-fixture.json" with { type: "json" };
// Test-only credentials remain in worker memory, never in artifacts or storage.
let evaluationToken: string | undefined;
async function activate(locator: Locator) {
  await locator.focus();
  await locator.press("Enter");
}
async function accessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(result.violations).toEqual([]);
}
async function humanSourcesOnly(page: Page) {
  await expect(page.locator(".technical-source, .source-details")).toHaveCount(
    0,
  );
  expect(await page.locator("body").textContent()).not.toMatch(
    /Technical source|Raw source|API endpoint|GRAR API URI|https:\/\/api\.basisregisters\.vlaanderen\.be/,
  );
  await expect(
    page.locator('a[href^="https://api.basisregisters.vlaanderen.be/"]'),
  ).toHaveCount(0);
}

test("address → private dossier → PDF → finding → question → source → print", async ({
  page,
  context,
}, testInfo) => {
  const external: string[] = [];
  page.on("request", (request) => {
    const u = new URL(request.url());
    if (
      ["http:", "https:", "ws:", "wss:"].includes(u.protocol) &&
      !["127.0.0.1", "localhost"].includes(u.hostname)
    )
      external.push(u.origin);
  });
  await page.goto("/");
  await expect(
    page.getByText(
      "Demo data · Fictional property and documents · No live register",
    ),
  ).toBeVisible();
  if (testInfo.project.name === "desktop") await accessible(page);
  if (testInfo.project.name === "mobile") {
    let checks = 0;
    // Exercise mobile ambiguity without spending another public-source quota.
    // Private creation below independently revalidates the selected fixture IDs.
    await page.route("**/api/v1/property-preview", async (route) => {
      checks += 1;
      await route.fulfill({
        json:
          checks === 1
            ? {
                status: "NEEDS_SELECTION",
                property: { ...fixture.property, status: "NEEDS_SELECTION" },
                truncated: false,
                is_demo: true,
                choices: [
                  {
                    address_id: "1",
                    unit_id: "10",
                    label: "Private unit 1 (demo)",
                  },
                  {
                    address_id: "1",
                    unit_id: "11",
                    label: "Private unit 2 (demo)",
                  },
                ],
              }
            : {
                status: "RESOLVED",
                property: fixture.property,
                choices: [],
                truncated: false,
                is_demo: true,
              },
      });
    });
  }
  const address = page.getByLabel("Enter the property address");
  await address.fill("Teststraat 42, 9000 Gent");
  await address.press("Enter");
  if (testInfo.project.name === "mobile") {
    const unit = page.getByRole("radio", { name: "Private unit 1 (demo)" });
    await unit.focus();
    await unit.press("Space");
    await activate(page.getByRole("button", { name: "Continue", exact: true }));
    await expect(
      page.getByRole("region", { name: "Property preview result" }),
    ).toBeFocused();
  }
  await expect(
    page.getByRole("heading", {
      name: "Teststraat 42, 9000 Gent",
      exact: true,
    }),
  ).toBeVisible();
  const create = page.getByRole("button", { name: "Create buyer dossier" });
  await activate(create);
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(create).toBeFocused();
  await activate(create);
  const issued = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/development/session" &&
      response.status() === 200,
  );
  await activate(
    page.getByRole("button", { name: "Start private evaluation" }),
  );
  evaluationToken = (await (await issued).json()).token as string;
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (c) => c.name === "viesett-session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "viesett-session",
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  await activate(page.getByRole("link", { name: "Documents", exact: true }));
  const upload = page.getByLabel("Upload property PDFs");
  await upload.focus();
  await expect(upload).toBeFocused();
  await upload.setInputFiles(path.resolve("e2e/fixtures/epc.pdf"));
  await page.getByRole("checkbox").check();
  await activate(page.getByRole("button", { name: "Continue", exact: true }));
  await expect(page.getByText("Analyzed", { exact: true })).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByRole("heading", { name: /Uploaded documents/ }),
  ).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "May apply", exact: true }),
  ).toBeVisible();
  await activate(page.getByRole("link", { name: /^Findings/ }));
  await expect(
    page.getByRole("heading", { name: "Energy", exact: true }),
  ).toBeVisible();
  await humanSourcesOnly(page);
  await activate(page.getByRole("link", { name: "Questions", exact: true }));
  await activate(page.getByRole("button", { name: "Copy all questions" }));
  await expect(
    page.getByText(/Copied|Select the text to copy/).first(),
  ).toBeVisible();
  await humanSourcesOnly(page);
  await activate(page.getByRole("link", { name: "Evidence", exact: true }));
  await expect(
    page.getByRole("heading", { name: "Official records" }),
  ).toBeVisible();
  await expect(page.locator(".source-details[open]")).toHaveCount(0);
  const reference = page
    .locator(".evidence-row")
    .filter({ hasText: "Address registry reference" });
  await expect(
    reference.getByText("Provider object ID: 1", { exact: true }),
  ).toBeHidden();
  await activate(reference.getByText("Source details", { exact: true }));
  await expect(
    reference.getByText("Provider object ID: 1", { exact: true }),
  ).toBeVisible();
  await expect(
    reference.getByText("Provider: Digitaal Vlaanderen"),
  ).toBeVisible();
  expect(await page.locator("body").textContent()).not.toContain(
    "https://api.basisregisters.vlaanderen.be/",
  );
  await page.emulateMedia({ media: "print" });
  await expect(reference.locator(".source-details")).toBeHidden();
  await page.emulateMedia({ media: "screen" });
  if (testInfo.project.name === "desktop") {
    await accessible(page);
    await reference.screenshot({
      path: testInfo.outputPath("evidence-source-details.png"),
    });
  }
  await activate(page.getByRole("link", { name: /^Findings/ }));
  await activate(page.getByText("Sources & check details").first());
  await humanSourcesOnly(page);
  await activate(page.getByRole("link", { name: /epc.pdf · page 1/i }).first());
  await expect(page.getByText("Target page 1", { exact: true })).toBeVisible();
  await expect(page.locator("iframe")).toHaveAttribute(
    "src",
    /^blob:.*#page=1$/,
  );
  const previousBlob = await page.locator("iframe").getAttribute("src");
  await activate(page.getByRole("button", { name: "Use download instead" }));
  await expect(page.locator("iframe")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Download PDF" })).toBeVisible();
  await activate(page.getByRole("button", { name: "Show PDF viewer" }));
  await page.reload();
  await expect(page.locator("iframe")).toHaveAttribute(
    "src",
    /^blob:.*#page=1$/,
  );
  expect(await page.locator("iframe").getAttribute("src")).not.toBe(
    previousBlob,
  );
  await activate(page.getByRole("link", { name: "Back to documents" }));
  await activate(page.getByRole("link", { name: "Prepare for notary" }));
  await expect(
    page.getByRole("heading", { name: "Source appendix" }),
  ).toBeVisible();
  await humanSourcesOnly(page);
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
  expect(external).toEqual([]);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".print-controls")).toBeHidden();
  await expect(page.locator(".print-help")).toBeHidden();
  await page.screenshot({
    path: testInfo.outputPath("notary-handoff.png"),
    fullPage: true,
  });
  await page.emulateMedia({ media: "screen" });
  await activate(page.getByRole("link", { name: "Back to dossier" }));
  await activate(page.getByRole("button", { name: "Log out", exact: true }));
  await expect(
    page.getByRole("button", { name: "Open my dossiers" }),
  ).toBeVisible();
  await page.reload();
  expect((await page.request.get("/api/v1/workspaces")).status()).toBe(401);
});

test("sample co-ownership shows funding assumptions and responsive navigation", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore a sample dossier" }).click();
  if (evaluationToken) {
    await page.getByLabel("Access token").fill(evaluationToken);
    await activate(page.getByRole("button", { name: "Connect", exact: true }));
  } else
    await activate(
      page.getByRole("button", { name: "Start private evaluation" }),
    );
  await page.getByRole("checkbox").check();
  await activate(page.getByRole("button", { name: "Continue", exact: true }));
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible({ timeout: 30_000 });
  await accessible(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("overview.png"),
    fullPage: true,
  });
  await page.getByLabel("Known signed deed date").fill("2026-02-28");
  await activate(
    page.getByRole("button", { name: "Use as unverified transaction context" }),
  );
  await expect(page.getByText(/Buyer-provided deed date/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "One transaction detail to clarify" }),
  ).toBeFocused();
  const pages = [
    ["Documents", "The documents behind your decision"],
    ["Findings", "Energy"],
    ["Co-ownership", "Article 3.94 information"],
    ["Questions", "Ask the notary"],
    ["Evidence", "Official records"],
  ];
  for (const [name, heading] of pages) {
    await activate(
      page.getByRole("link", { name: new RegExp("^" + name) }).first(),
    );
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    if (testInfo.project.name === "desktop") await accessible(page);
    if (name === "Co-ownership") {
      await expect(
        page.getByText("Not determined", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Assumptions & sources", { exact: true }),
      ).toBeVisible();
    }
  }
  await activate(page.getByRole("link", { name: "Prepare for notary" }));
  await expect(
    page.getByRole("heading", { name: "Source appendix" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Notary handoff", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Questions for the notary" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Ask the seller" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Article 3.94 information" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Document checklist" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Legal payment responsibility: Not determined"),
  ).toBeVisible();
  await humanSourcesOnly(page);
  await expect(page.locator(".print-help")).toContainText(
    "Headers and footers",
  );
  await expect(
    page.locator(
      '.citations a[href^="https://api.basisregisters.vlaanderen.be/"]',
    ),
  ).toHaveCount(0);
  if (testInfo.project.name === "desktop") {
    await accessible(page);
    await page.emulateMedia({ media: "print" });
    await expect(page.locator(".print-help")).toBeHidden();
    const notaryPath = testInfo.outputPath("sample-notary.pdf");
    const notaryPdf = await page.pdf({
      path: notaryPath,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
    });
    await page.screenshot({
      path: testInfo.outputPath("notary-handoff.png"),
      fullPage: true,
    });
    await page.emulateMedia({ media: "screen" });
    await activate(
      page.getByRole("link", { name: "Print full dossier", exact: true }),
    );
    await expect(
      page.getByRole("heading", { name: "Article 3.94 information" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Document checklist" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Ask the seller" }),
    ).toBeVisible();
    await humanSourcesOnly(page);
    await page.emulateMedia({ media: "print" });
    await expect(page.locator(".print-help")).toBeHidden();
    const fullPath = testInfo.outputPath("sample-full-dossier.pdf");
    const fullPdf = await page.pdf({
      path: fullPath,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
    });
    const counts = JSON.parse(
      execFileSync(
        path.resolve("../.venv/bin/python"),
        [
          "-c",
          "import json,sys; from pypdf import PdfReader; readers=[PdfReader(p) for p in sys.argv[1:]]; texts=['\\n'.join(page.extract_text() for page in r.pages) for r in readers]; assert all(not any(term in t for term in ['https://api.basisregisters.vlaanderen.be/', 'Technical source', 'Source details', 'Headers and footers']) for t in texts); assert 'Address object:' not in texts[0]; print(json.dumps([len(r.pages) for r in readers]))",
          notaryPath,
          fullPath,
        ],
        { encoding: "utf8" },
      ),
    ) as number[];
    expect(counts[0]).toBeLessThanOrEqual(5);
    expect(counts[0]).toBeLessThan(counts[1]);
    expect(notaryPdf.length).toBeLessThan(fullPdf.length);
    writeFileSync(
      testInfo.outputPath("print-metrics.json"),
      JSON.stringify({
        notary_pages: counts[0],
        full_pages: counts[1],
        notary_bytes: notaryPdf.length,
        full_bytes: fullPdf.length,
      }),
    );
    await page.emulateMedia({ media: "screen" });
  }
  await activate(page.getByRole("link", { name: "Back to dossier" }));
  await expect(
    page.getByRole("heading", { name: "Needs attention", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight),
  ).toBeLessThan(8000);
  await page.screenshot({
    path: testInfo.outputPath("overview-final.png"),
    fullPage: false,
  });
});

test("search catalog and delete a whole dossier @desktop", async ({ page }) => {
  await page.goto("/");
  const input = page.getByLabel("Enter the property address");
  await input.fill("Teststraat 42 Gent");
  await input.press("Enter");
  await expect(
    page.getByRole("heading", {
      name: "Teststraat 42, 9000 Gent",
      exact: true,
    }),
  ).toBeVisible();
  await input.fill("Unrelated fictional street 999");
  await input.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Address not in the demo" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create buyer dossier" }),
  ).toHaveCount(0);
  await input.fill("Teststraat 42 bus 1, 9000 Gent");
  await input.press("Enter");
  await expect(
    page.getByRole("heading", {
      name: "Teststraat 42 bus 1, 9000 Gent",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create buyer dossier" }).click();
  if (evaluationToken) {
    await page.getByLabel("Access token").fill(evaluationToken);
    await page.getByRole("button", { name: "Connect", exact: true }).click();
  } else
    await page
      .getByRole("button", { name: "Start private evaluation" })
      .click();
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  const dossierPath = new URL(page.url()).pathname;
  const wid = dossierPath.split("/")[2];
  const remove = page.getByRole("button", { name: /^Delete dossier for/ });
  for (const width of [900, 393, 1440]) {
    await page.setViewportSize({ width, height: 1050 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await remove.click();
    await page.getByRole("button", { name: "Keep dossier" }).click();
    await expect(remove).toBeFocused();
  }
  await remove.click();
  const deleted = page.waitForResponse(
    (r) =>
      r.request().method() === "DELETE" &&
      new URL(r.url()).pathname === `/api/v1/workspaces/${wid}`,
  );
  await page
    .getByRole("button", { name: "Delete dossier permanently" })
    .click();
  expect((await deleted).status()).toBe(204);
  await expect(
    page.getByRole("button", { name: "Check property" }),
  ).toBeVisible();
  await expect(page.locator(`a[href^="/workspaces/${wid}/"]`)).toHaveCount(0);
  await page.reload();
  const list = await page.request.get("/api/v1/workspaces");
  expect((await list.json()).some((w: { id: string }) => w.id === wid)).toBe(
    false,
  );
  expect(
    (await page.request.get(`/api/v1/workspaces/${wid}/dossier`)).status(),
  ).toBe(404);
});
