/** P1 UI acceptance: upload -> ingest -> Analyze -> understanding job runs ->
 * "Insights" panel shows scene/silence/word stats. Uses the real analyzer stack
 * (ffmpeg + faster-whisper + librosa) end-to-end. */
import { expect, test } from "@playwright/test";
import { FIXTURE } from "./global-setup";

test("analyze an asset and view its understanding insights", async ({ page }) => {
  test.setTimeout(240_000);

  await page.goto("/");
  await page.getByTestId("new-project-name").fill("Understanding Test");
  await page.getByTestId("create-project").click();
  await page.waitForURL(/\/p\/proj_/);

  // Upload the synthetic fixture and wait for ingest.
  await page.getByTestId("upload-input").setInputFiles(FIXTURE);
  const assetRow = page.locator("[data-testid^=asset-ast_]");
  await expect(assetRow).toHaveAttribute("data-asset-status", "ready", {
    timeout: 90_000,
  });
  const assetId = (await assetRow.getAttribute("data-testid"))!.replace("asset-", "");

  // Kick off analysis.
  await page.getByTestId(`analyze-${assetId}`).click();

  // The understanding job runs (real whisper + scene/silence/beats). When it
  // finishes, the "Insights" button appears.
  const insightsBtn = page.getByTestId(`view-understanding-${assetId}`);
  await expect(insightsBtn).toBeVisible({ timeout: 180_000 });

  // Open the insights panel and assert it summarizes the analysis.
  await insightsBtn.click();
  const panel = page.getByTestId("understanding-panel");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Scenes");
  await expect(panel).toContainText("Silences");
  await expect(panel).toContainText("Tempo");

  // Close it.
  await panel.getByText("Close").click();
  await expect(panel).toBeHidden();
});
