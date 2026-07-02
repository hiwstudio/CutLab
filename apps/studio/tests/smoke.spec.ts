/** B5 acceptance test 6 — UI smoke:
 * create project → upload fixture video → wait ingest → drag to timeline →
 * split → trim → undo → render → job done and output file exists. */
import { expect, test } from "@playwright/test";
import fs from "fs";
import path from "path";
import { SMOKE_DATA } from "../playwright.config";
import { FIXTURE } from "./global-setup";

test("editor smoke: ingest, edit, undo, render", async ({ page }) => {
  // Create a project.
  await page.goto("/");
  await page.getByTestId("new-project-name").fill("Smoke Test");
  await page.getByTestId("create-project").click();
  await page.waitForURL(/\/p\/proj_/);
  const projectId = page.url().split("/p/")[1];
  await expect(page.getByTestId("project-name")).toHaveText("Smoke Test");

  // Upload the synthetic 5s fixture and wait for ingest to finish.
  await page.getByTestId("upload-input").setInputFiles(FIXTURE);
  const assetRow = page.locator("[data-testid^=asset-ast_]");
  await expect(assetRow).toHaveCount(1);
  await expect(assetRow).toHaveAttribute("data-asset-status", "ready", {
    timeout: 90_000,
  });

  // Drag the asset onto the video lane (custom pointer-based drag).
  const videoLane = page.locator("[data-track-kind=video]").first();
  await assetRow.dragTo(videoLane, {
    targetPosition: { x: 10, y: 20 },
  });
  const clips = page.locator("[data-clip-id]");
  await expect(clips).toHaveCount(1, { timeout: 15_000 });

  // Set the playhead to ~2s (default zoom: 80 px/s; lane x = 2s * 80px).
  const timeline = page.getByTestId("timeline");
  const box = (await timeline.boundingBox())!;
  await page.mouse.click(box.x + 72 + 160, box.y + 12);

  // Select the clip and split at the playhead.
  await clips.first().click();
  await page.keyboard.press("s");
  await expect(clips).toHaveCount(2, { timeout: 15_000 });

  // Trim: drag the right edge of the second clip 40px left.
  const secondClip = clips.nth(1);
  const clipId = await secondClip.getAttribute("data-clip-id");
  const trimHandle = page.getByTestId(`trim-r-${clipId}`);
  const hb = (await trimHandle.boundingBox())!;
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
  await page.mouse.down();
  await page.mouse.move(hb.x - 40, hb.y + hb.height / 2, { steps: 5 });
  await page.mouse.up();
  await expect(
    page.locator("[data-testid^=revision-]").filter({ hasText: "trim" }).first(),
  ).toBeVisible({ timeout: 15_000 });
  const revCountAfterTrim = await page.locator("[data-testid^=revision-]").count();

  // Undo (Ctrl+Z): head moves back, trim revision no longer HEAD.
  await page.keyboard.press("Control+z");
  await expect(
    page
      .locator("[data-testid^=revision-]")
      .filter({ hasText: "split" })
      .filter({ hasText: "HEAD" }),
  ).toBeVisible({ timeout: 15_000 });
  expect(await page.locator("[data-testid^=revision-]").count()).toBe(
    revCountAfterTrim,
  );

  // Render and wait for the job to reach done.
  await page.getByTestId("render-button").click();
  const result = page.getByTestId("render-result");
  await expect(result).toBeVisible({ timeout: 180_000 });

  // The output file exists on disk.
  const fileName = (await result.textContent())!.trim();
  const outPath = path.join(SMOKE_DATA, "projects", projectId, "renders", fileName);
  expect(fs.existsSync(outPath)).toBe(true);
  expect(fs.statSync(outPath).size).toBeGreaterThan(10_000);
});
