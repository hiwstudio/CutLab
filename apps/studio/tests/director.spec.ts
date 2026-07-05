/** P2 AI Director UI (manual backend): a natural-language command yields a prompt,
 * the pasted plan becomes a proposal, and accepting it applies the edit. Fast —
 * no ingest/analysis needed. */
import { expect, test } from "@playwright/test";

test("director manual flow: command -> plan -> proposal -> accept", async ({ page }) => {
  test.setTimeout(60_000);

  await page.goto("/");
  await page.getByTestId("new-project-name").fill("Director Test");
  await page.getByTestId("create-project").click();
  await page.waitForURL(/\/p\/proj_/);
  await expect(page.getByTestId("project-name")).toHaveText("Director Test", {
    timeout: 30_000,
  });

  // The panel reports the manual backend (default, no key).
  const director = page.getByTestId("director-panel");
  await expect(director).toContainText("manual");

  // Issue a natural-language command.
  await page.getByTestId("director-input").fill("rename the project to Renamed");
  await page.getByTestId("director-send").click();

  // Manual backend shows the prompt + an answer box.
  const manual = page.getByTestId("director-manual");
  await expect(manual).toBeVisible({ timeout: 15_000 });

  // Paste the plan (as one would after running the prompt through Claude).
  await page
    .getByTestId("director-answer")
    .fill('{"ops": [{"op": "set_project", "name": "Renamed"}], "note": "rename"}');
  await page.getByTestId("director-answer-send").click();

  // A proposal appears in the review panel.
  const review = page.getByTestId("proposal-review");
  await expect(review).toBeVisible({ timeout: 15_000 });
  await expect(review.locator("[data-testid^=proposal-]").first()).toContainText(
    "set project",
  );

  // Accept it → the project is renamed.
  await review.locator("[data-testid^=accept-proposal-]").first().click();
  await expect(page.getByTestId("project-name")).toHaveText("Renamed", {
    timeout: 15_000,
  });
});
