/** P2 UI acceptance: analyze an asset, propose a smart edit (reframe) from its
 * Insights, review it in the AI Director panel, and accept it. */
import { expect, test } from "@playwright/test";
import { FIXTURE } from "./global-setup";

test("propose a smart edit and accept it", async ({ page }) => {
  test.setTimeout(240_000);

  await page.goto("/");
  await page.getByTestId("new-project-name").fill("Proposal Test");
  await page.getByTestId("create-project").click();
  await page.waitForURL(/\/p\/proj_/);

  // Upload + ingest.
  await page.getByTestId("upload-input").setInputFiles(FIXTURE);
  const assetRow = page.locator("[data-testid^=asset-ast_]");
  await expect(assetRow).toHaveAttribute("data-asset-status", "ready", {
    timeout: 90_000,
  });
  const assetId = (await assetRow.getAttribute("data-testid"))!.replace("asset-", "");

  // Analyze, then open Insights.
  await page.getByTestId(`analyze-${assetId}`).click();
  const insightsBtn = page.getByTestId(`view-understanding-${assetId}`);
  await expect(insightsBtn).toBeVisible({ timeout: 180_000 });
  await insightsBtn.click();

  // Propose a reframe (always available regardless of speech/silence content).
  await page.getByTestId("propose-reframe").click();

  // The proposal appears in the AI Director review panel; the panel closed.
  const review = page.getByTestId("proposal-review");
  await expect(review).toBeVisible({ timeout: 15_000 });
  const proposal = review.locator("[data-testid^=proposal-]").first();
  await expect(proposal).toContainText("reframe");

  // Accept it → the proposal clears and the canvas is now 9:16.
  await review.locator("[data-testid^=accept-proposal-]").first().click();
  await expect(review).toBeHidden({ timeout: 15_000 });
  await expect(page.getByTestId("project-name")).toBeVisible();
  // Header shows the new canvas dimensions after accept.
  await expect(page.locator("header")).toContainText("1080×1920", { timeout: 15_000 });
});
