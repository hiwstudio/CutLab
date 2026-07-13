/** P7: command palette — open with Ctrl+K, filter, execute a command. */
import { expect, test } from "@playwright/test";

test("command palette opens, filters, and runs a command", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("new-project-name").fill("Palette Test");
  await page.getByTestId("create-project").click();
  await page.waitForURL(/\/p\/proj_/);
  await expect(page.getByTestId("project-name")).toHaveText("Palette Test", {
    timeout: 30_000,
  });

  const lanesBefore = await page.locator("[data-track-kind=caption]").count();

  await page.keyboard.press("Control+k");
  await expect(page.getByTestId("command-palette")).toBeVisible();

  // Filter to "Add caption track" and run it via Enter.
  await page.getByTestId("palette-input").fill("caption track");
  await expect(page.getByTestId("palette-cmd-track-caption")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("command-palette")).toBeHidden();

  // The command actually executed: one more caption lane on the timeline.
  await expect(page.locator("[data-track-kind=caption]")).toHaveCount(lanesBefore + 1, {
    timeout: 15_000,
  });

  // Esc path.
  await page.keyboard.press("Control+k");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("command-palette")).toBeHidden();
});
