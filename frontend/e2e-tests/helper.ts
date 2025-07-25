/* Copyright 2024 Marimo. All rights reserved. */

import path from "node:path";
import { expect, type Locator, type Page } from "@playwright/test";
import { type HotkeyAction, HotkeyProvider } from "../src/core/hotkeys/hotkeys";
import { clickWithRetry, waitForMarimoApp } from "./test-utils";

export async function createCellBelow(opts: {
  page: Page;
  cellSelector: string;
  content: string;
  run: boolean;
}) {
  const { page, cellSelector, content, run } = opts;

  // Hover over a cell the 'add cell' button appears
  await page.hover(cellSelector);
  await expect(
    page.getByTestId("create-cell-button").locator(":visible"),
  ).toHaveCount(2);

  // Clicking the first button creates a new cell below
  await page
    .getByTestId("create-cell-button")
    .locator(":visible")
    .last()
    .click();
  // Type into the currently focused cell
  if (content) {
    await page.locator("*:focus").type(content);
  }

  // Run the new cell
  if (run) {
    await page.locator("*:focus").hover();
    await page.getByTestId("run-button").locator(":visible").first().click();
  }
}

export async function openCellActions(page: Page, element: Locator) {
  await element.hover();
  await page
    .getByTestId("cell-actions-button")
    .locator(":visible")
    .first()
    .click();
}

export async function runCell(opts: { page: Page; cellSelector: string }) {
  const { page, cellSelector } = opts;

  // Hover over a cell
  await page.hover(cellSelector);

  // Run the new cell
  await page.getByTestId("run-button").locator(":visible").first().click();
}

const countsForName: Record<string, number> = {};
/**
 * Take a screenshot of the page.
 * @example
 * await takeScreenshot(page, _filename);
 */
export async function takeScreenshot(page: Page, filename: string) {
  const clean = path.basename(filename).replace(".spec.ts", "");

  const count = countsForName[clean] || 0;
  countsForName[clean] = count + 1;
  const fullName = `${clean}.${count}`;
  await page.screenshot({
    path: `e2e-tests/screenshots/${fullName}.png`,
    fullPage: true,
  });
}

/**
 * Press a hotkey on the page.
 *
 * It uses the hotkey provider to get the correct key for the current platform
 * and then maps it to the correct key for playwright.
 */
export async function pressShortcut(page: Page, action: HotkeyAction) {
  const isMac = await page.evaluate(() => navigator.userAgent.includes("Mac"));
  const provider = HotkeyProvider.create(isMac);
  const key = provider.getHotkey(action);
  // playwright uses "Meta" for command key on mac, "Control" for windows/linux
  // we also need to capitalize the first letter of each key
  const split = key.key.split("-");
  const capitalized = split.map((s) => s[0].toUpperCase() + s.slice(1));
  const keymap = capitalized
    .join("+")
    .replace("Cmd", isMac ? "Meta" : "Control")
    .replace("Ctrl", "Control");

  await page.keyboard.press(keymap);
}

/**
 * Download as HTML
 *
 * Download HTML of the current notebook and take a screenshot
 */
export async function exportAsHTMLAndTakeScreenshot(page: Page) {
  // Wait for networkidle so that the notebook is fully loaded
  await page.waitForLoadState("networkidle");

  // Start waiting for download before clicking.
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page
      .getByTestId("notebook-menu-dropdown")
      .click()
      .then(() => {
        return openCommandPalette({ page, command: "Download as HTML" });
      }),
  ]);

  // Wait for the download process to complete and save the downloaded file somewhere.
  const path = `e2e-tests/exports/${download.suggestedFilename()}`;
  await download.saveAs(path);

  // Open a new page and take a screenshot
  const exportPage = await page.context().newPage();
  const fullPath = `${process.cwd()}/${path}`;
  await exportPage.goto(`file://${fullPath}`, {
    waitUntil: "networkidle",
  });
  await takeScreenshot(exportPage, path);

  // Toggle code
  if (await exportPage.isVisible("[data-testid=show-code]")) {
    await exportPage.getByTestId("show-code").click();
    // wait 100ms for the code to be shown
    await exportPage.waitForTimeout(100);
  }

  // Take screenshot of code
  await takeScreenshot(exportPage, `code-${path}`);
}

export async function exportAsPNG(page: Page) {
  // Wait for networkidle so that the notebook is fully loaded
  await page.waitForLoadState("networkidle");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page
      .getByTestId("notebook-menu-dropdown")
      .click()
      .then(() => {
        return openCommandPalette({ page, command: "Download as PNG" });
      }),
  ]);

  // Wait for the download process to complete and save the downloaded file somewhere.
  const path = `e2e-tests/screenshots/${download.suggestedFilename()}`;
  await download.saveAs(path);
}

/**
 * Open the command palette, type something, and hit Enter
 */
export async function openCommandPalette(opts: {
  page: Page;
  command: string;
}) {
  const { page, command } = opts;

  // Open command palette with Ctrl+K (or Cmd+K on Mac)
  await pressShortcut(page, "global.commandPalette");

  // Wait for the command palette to be visible
  await expect(page.getByPlaceholder("Type to search")).toBeVisible();

  // Type the command
  await page.keyboard.type(command);

  // Hit Enter to execute
  await page.keyboard.press("Enter");
}

/**
 * Waits for the page to load. If we have resumed a session, we restart the kernel.
 */
export async function maybeRestartKernel(page: Page) {
  // Wait for cells to appear
  await waitForMarimoApp(page);

  // If it says, "You have connected to an existing session", then restart
  const hasText = await page
    .getByText("You have reconnected to an existing session", { exact: false })
    .isVisible();
  if (!hasText) {
    return;
  }

  await clickWithRetry(page, "[data-testid='notebook-menu-dropdown']");
  await page.getByText("Restart kernel", { exact: true }).click();
  await page.getByLabel("Confirm Restart", { exact: true }).click();
}
