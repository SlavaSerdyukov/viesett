import path from "node:path";
import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:5173",
    channel: "chromium",
    trace: "off",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1050 },
      },
    },
    {
      name: "tablet",
      use: { viewport: { width: 900, height: 1100 }, hasTouch: true },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command:
        "cd .. && .venv/bin/uvicorn viesett.demo:create_demo_app --factory --host 127.0.0.1 --port 8000 --no-access-log",
      url: "http://127.0.0.1:8000/health/ready",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        VIESETT_STORAGE_ROOT: path.resolve("../.local/e2e-objects"),
        VIESETT_DEMO_MODE: "true",
        VIESETT_ALLOW_DEVELOPMENT_WEB_SESSIONS: "true",
        VIESETT_ALLOW_DEVELOPMENT_SAFETY: "true",
        VIESETT_WEB_ORIGINS: '["http://127.0.0.1:5173"]',
        VIESETT_SOURCE_MIN_INTERVAL: "0",
        VIESETT_SOURCE_RETRY_BASE: "0",
        VIESETT_RATE_LIMIT_PER_MINUTE: "1000",
      },
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
