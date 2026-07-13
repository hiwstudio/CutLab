/** P3.3/P3.2 UI acceptance: the L0 compositor plays the timeline live (playhead
 * advances with the media clock) and the L1 button produces an exact segment. */
import { expect, test } from "@playwright/test";
import { FIXTURE } from "./global-setup";

test("L0 compositor playback + L1 segment preview", async ({ page }) => {
  test.setTimeout(180_000);

  await page.goto("/");
  await page.getByTestId("new-project-name").fill("Compositor Test");
  await page.getByTestId("create-project").click();
  await page.waitForURL(/\/p\/proj_/);
  await expect(page.getByTestId("project-name")).toHaveText("Compositor Test", {
    timeout: 30_000,
  });

  // Ingest the 5s fixture and put it on the timeline.
  await page.getByTestId("upload-input").setInputFiles(FIXTURE);
  const assetRow = page.locator("[data-testid^=asset-ast_]");
  await expect(assetRow).toHaveAttribute("data-asset-status", "ready", {
    timeout: 90_000,
  });
  await assetRow.dblclick(); // double-click appends to the first video track

  // L0: compositor appears with a live layer.
  const compositor = page.getByTestId("compositor");
  await expect(compositor).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("video[data-testid^=layer-]")).toHaveCount(1);

  // Transport: play advances the playhead clock; pause holds it. Wait for the
  // proxy to be decodable first so a cold server can't starve the media clock.
  await page.waitForFunction(() => {
    const v = document.querySelector<HTMLVideoElement>("video[data-testid^=layer-]");
    return !!v && v.readyState >= 2;
  }, { timeout: 30_000 });
  const clock = page.locator("span", { hasText: /s \/ / }).last();
  await page.getByTestId("play-button").click();
  await page.waitForFunction(
    (sel) => {
      const el = [...document.querySelectorAll("span")].find((s) =>
        /s \/ /.test(s.textContent ?? ""));
      return parseFloat((el?.textContent ?? "0").split("s /")[0]) > 0.3;
    },
    undefined,
    { timeout: 20_000 },
  );
  await page.getByTestId("play-button").click();
  const t = parseFloat((await clock.textContent())!.split("s /")[0]);
  expect(t).toBeGreaterThan(0.3);

  // L1: exact segment render appears and can be dismissed.
  await page.getByTestId("preview-segment-button").click();
  await expect(page.getByTestId("segment-video")).toBeVisible({ timeout: 90_000 });
  await page.getByTestId("segment-close").click();
  await expect(page.getByTestId("compositor")).toBeVisible();
});
