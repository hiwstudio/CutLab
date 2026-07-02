import { defineConfig } from "@playwright/test";
import path from "path";

// Both servers are started by Playwright. The API server gets an isolated
// data dir so the smoke run never touches real projects.
export const SMOKE_DATA = path.join(__dirname, ".smoke-data");
const serverDir = path.join(__dirname, "..", "server");
const python = path.join(serverDir, ".venv", "Scripts", "python.exe");

export default defineConfig({
  testDir: "./tests",
  timeout: 240_000,
  workers: 1,
  retries: 0,
  globalSetup: "./tests/global-setup.ts",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m cutlab.main`,
      cwd: serverDir,
      url: "http://127.0.0.1:8787/api/v1/projects",
      reuseExistingServer: false,
      timeout: 60_000,
      env: { CUTLAB_DATA_DIR: SMOKE_DATA },
    },
    {
      command: "npm run dev",
      cwd: __dirname,
      url: "http://localhost:3000",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
