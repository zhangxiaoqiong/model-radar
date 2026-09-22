import { chromium } from "playwright-core";

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  headless: true,
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("http://127.0.0.1:4173/models", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => document.querySelector(".demo-badge")?.textContent === "来源数据");
  const rows = page.locator("tbody tr");
  const count = await rows.count();
  const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const topRelease = await rows.first().locator("td").nth(3).innerText();
  if (count < 2 || topRelease < cutoff) {
    throw new Error(`Recent catalog invalid: ${count} rows, newest ${topRelease}`);
  }
  await rows.nth(0).locator(".checkbox").click();
  await rows.nth(1).locator(".checkbox").click();
  await page.locator(".selection-dock .primary").click();
  if (await page.locator(".compare-head").count() !== 2) {
    throw new Error("Comparison did not receive two recent models");
  }
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto("http://127.0.0.1:4173/models", { waitUntil: "domcontentloaded" });
  await mobile.waitForFunction(() => document.querySelector(".demo-badge")?.textContent === "来源数据");
  const widths = await mobile.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  if (widths.document > widths.viewport) throw new Error("Mobile page overflows");
  if (errors.length) throw new Error(errors.join(" | "));
  console.log(JSON.stringify({ recentModels: count, newestRelease: topRelease, compare: "ok", mobile: "ok" }));
} finally {
  await browser.close();
}
