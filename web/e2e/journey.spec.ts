import { test, expect } from "@playwright/test";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
// Reuse evaluation credentials only in worker memory; never persist them.
let evaluationToken: string | undefined;

test("address → private dossier → PDF → finding → question → source → print", async ({
  page,
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
  await page
    .getByLabel("Enter the property address")
    .fill("Teststraat 42, 9000 Gent");
  await page.getByRole("button", { name: "Check property" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Teststraat 42, 9000 Gent",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create buyer dossier" }).click();
  const issued = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/development/session" &&
      response.status() === 200,
  );
  await page.getByRole("button", { name: "Start private evaluation" }).click();
  evaluationToken = (await (await issued).json()).token as string;
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await page
    .getByLabel("Upload property PDFs")
    .setInputFiles(path.resolve("e2e/fixtures/epc.pdf"));
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByText("Analyzed", { exact: true })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("link", { name: /^Findings/ }).click();
  await expect(
    page.getByRole("heading", { name: "Energy", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Questions", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Copy all questions" }),
  ).toBeVisible();
  await page.getByRole("link", { name: /^Findings/ }).click();
  await page.getByText("Sources & check details").first().click();
  await page
    .getByRole("link", { name: /epc.pdf · page 1/i })
    .first()
    .click();
  await expect(page.getByText("Target page 1", { exact: true })).toBeVisible();
  await expect(page.locator("iframe")).toHaveAttribute(
    "src",
    /^blob:.*#page=1$/,
  );
  await page.getByRole("link", { name: "Back to documents" }).click();
  await page.getByRole("link", { name: "Prepare for notary" }).click();
  await expect(
    page.getByRole("button", { name: "Print / Save as PDF" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Source list" }),
  ).toBeVisible();
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(external).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("notary-handoff.png"),
    fullPage: true,
  });
});

test("sample co-ownership shows funding assumptions and responsive navigation", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore a sample dossier" }).click();
  if (evaluationToken) {
    await page.getByLabel("Access token").fill(evaluationToken);
    await page.getByRole("button", { name: "Connect", exact: true }).click();
  } else {
    await page
      .getByRole("button", { name: "Start private evaluation" })
      .click();
  }
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dossier completeness" }),
  ).toBeVisible({ timeout: 30_000 });
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("overview.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Co-ownership", exact: true }).click();
  await expect(page.getByText("Not determined", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Assumptions & sources", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Evidence", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Official records" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
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
