import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const chromePath = process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const outputDir = new URL("../qa/", import.meta.url);
await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ executablePath: chromePath, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1024 }, deviceScaleFactor: 1 });
const consoleErrors = [];
page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("pageerror", error => consoleErrors.push(error.message));

await page.goto("http://127.0.0.1:4173/", { waitUntil: "networkidle" });
await page.getByText("来源数据", { exact: true }).waitFor();
await page.getByRole("heading", { name: /看清模型格局/ }).waitFor();
await page.getByLabel("看板全局筛选").waitFor();
await page.screenshot({ path: fileURLToPath(new URL("overview.png", outputDir)), fullPage: true });

await page.getByRole("button", { name: "模型库", exact: true }).click();
await page.getByRole("heading", { name: "模型图谱" }).waitFor();
if (new URL(page.url()).pathname !== "/models") throw new Error("Models route did not update");
const rows = page.locator("tbody tr");
const totalRows = await rows.count();
if (totalRows < 6) throw new Error(`Expected at least six synced model rows, got ${totalRows}`);
if (totalRows > 20) throw new Error(`Pagination failed: ${totalRows} rows on one page`);
if (await page.getByRole("button", { name: "下一页" }).isEnabled()) {
  await page.getByRole("button", { name: "下一页" }).click();
  if (await rows.count() < 1) throw new Error("Next page is empty");
  await page.getByRole("button", { name: "上一页" }).click();
}
const providerFilter = page.locator(".filter").filter({ hasText: "提供商" }).locator("select");
await providerFilter.selectOption("Anthropic");
const providerRows = await rows.count();
if (providerRows < 1) throw new Error("Provider filter returned no rows");
for (let index = 0; index < providerRows; index += 1) {
  if (!await rows.nth(index).getByText("Anthropic", { exact: true }).count()) throw new Error("Provider filter leaked another vendor");
}
await providerFilter.selectOption("all");
const capabilityFilter = page.locator(".filter").filter({ hasText: "能力" }).locator("select");
await capabilityFilter.selectOption("图片");
if (await rows.count() < 1 || !await rows.first().locator(".capability-tags").getByText("图片").count()) throw new Error("Capability filter failed");
await capabilityFilter.selectOption("all");
await page.getByLabel("排序").selectOption("intelligence");
const firstScore = Number(await rows.first().locator(".catalog-scores b").innerText());
const secondScore = Number(await rows.nth(1).locator(".catalog-scores b").innerText());
if (firstScore < secondScore) throw new Error("Intelligence sort failed");
await page.getByLabel("排序").selectOption("release");
const search = page.locator(".model-search input");
await search.fill("no-such-model");
await page.getByText("没有符合当前筛选条件的模型").waitFor();
await search.fill("");

await rows.nth(0).locator(".checkbox").click();
await page.getByText("已选 1 个，再选 1 个即可对比").waitFor();
await rows.nth(1).locator(".checkbox").click();
await page.getByText("已选 2 个模型").waitFor();
await page.screenshot({ path: fileURLToPath(new URL("catalog.png", outputDir)) });
await page.getByRole("button", { name: /开始对比/ }).click();
await page.getByRole("heading", { name: "模型对比" }).waitFor();
if (await page.locator(".compare-head").count() !== 2) throw new Error("Expected two selected models in comparison");
await page.locator(".compare-evidence").waitFor();
if (await page.locator(".compare-evidence-row").count() < 1) throw new Error("Comparison has no evaluation evidence");
if (await page.locator(".cost-row").count() !== 2) throw new Error("Comparison cost chart is missing selected models");
await page.screenshot({ path: fileURLToPath(new URL("compare.png", outputDir)), fullPage: true });

await page.getByRole("button", { name: "最新动态", exact: true }).click();
await page.getByRole("heading", { name: "最新动态" }).waitFor();
if (new URL(page.url()).pathname !== "/updates") throw new Error("Updates route did not update");
await page.screenshot({ path: fileURLToPath(new URL("updates.png", outputDir)), fullPage: true });

await page.getByRole("button", { name: "评测平台", exact: true }).click();
await page.getByRole("heading", { name: "专业评测平台" }).waitFor();
if (new URL(page.url()).pathname !== "/evaluations") throw new Error("Evaluation platforms route did not update");
await page.screenshot({ path: fileURLToPath(new URL("benchmarks.png", outputDir)), fullPage: true });

const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
await mobile.goto("http://127.0.0.1:4173/models", { waitUntil: "networkidle" });
await mobile.locator("tbody tr").first().locator(".checkbox").click();
await mobile.getByText("已选 1 个，再选 1 个即可对比").waitFor();
const mobileWidth = await mobile.evaluate(() => ({ viewport: window.innerWidth, page: document.documentElement.scrollWidth }));
if (mobileWidth.page > mobileWidth.viewport) throw new Error(`Mobile page overflows: ${mobileWidth.page}px > ${mobileWidth.viewport}px`);
await mobile.screenshot({ path: fileURLToPath(new URL("mobile.png", outputDir)) });

await browser.close();
if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.join(" | ")}`);
console.log(JSON.stringify({ navigation: "passed", dashboardFilters: "passed", rows: totalRows, filters: "passed", selection: "passed", compare: "passed", updates: "passed", evaluations: "passed", mobile: "passed", consoleErrors: 0 }));
