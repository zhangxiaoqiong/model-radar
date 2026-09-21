import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const chromePath = process.env.CHROME_PATH
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const outputDir = new URL("../qa/", import.meta.url);
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ executablePath: chromePath, headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1024 },
  deviceScaleFactor: 1,
});
const consoleErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(error.message));

await page.goto("http://127.0.0.1:4173/", { waitUntil: "networkidle" });
await page.screenshot({ path: fileURLToPath(new URL("catalog.png", outputDir)) });

const rows = page.locator("tbody tr");
if (await rows.count() !== 6) throw new Error("Expected six recent model rows");

const providerFilter = page.locator(".filter").filter({ hasText: "Provider" }).locator("select");
await providerFilter.selectOption("Anthropic");
if (await rows.count() !== 1) throw new Error("Provider filter did not narrow the table");
await providerFilter.selectOption("all");

const search = page.locator(".model-search input");
await search.fill("no-such-model");
await page.getByText("没有符合当前筛选条件的模型").waitFor();
await search.fill("");

await page.locator(".selection-action").click();
await page.getByRole("heading", { name: "模型对比" }).waitFor();
if (await page.locator(".compare-head").count() !== 2) {
  throw new Error("Expected two selected models in comparison");
}
const compareLayout = await page.evaluate(() => ({
  viewport: [window.innerWidth, window.innerHeight],
  scroll: [window.scrollX, window.scrollY],
  pageWidth: document.documentElement.scrollWidth,
  brandBox: document.querySelector(".brand")?.getBoundingClientRect().toJSON(),
}));
await page.screenshot({ path: fileURLToPath(new URL("compare.png", outputDir)) });

await page.getByRole("button", { name: "返回模型图谱" }).click();
await page.getByRole("heading", { name: "模型图谱" }).waitFor();

const mobile = await browser.newPage({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 1,
});
await mobile.goto("http://127.0.0.1:4173/", { waitUntil: "networkidle" });
const mobileWidth = await mobile.evaluate(() => ({
  viewport: window.innerWidth,
  page: document.documentElement.scrollWidth,
}));
if (mobileWidth.page > mobileWidth.viewport) {
  throw new Error(`Mobile page overflows: ${mobileWidth.page}px > ${mobileWidth.viewport}px`);
}
await mobile.screenshot({ path: fileURLToPath(new URL("mobile.png", outputDir)) });

await browser.close();
if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.join(" | ")}`);
console.log(JSON.stringify({ rows: 6, filters: "passed", compare: "passed", mobile: "passed", consoleErrors: 0, compareLayout }));
