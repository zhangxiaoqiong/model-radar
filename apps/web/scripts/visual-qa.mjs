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
await page.getByRole("heading", { name: "最近发生了什么？" }).waitFor();
await page.screenshot({ path: fileURLToPath(new URL("overview.png", outputDir)), fullPage: true });

await page.getByRole("button", { name: "模型", exact: true }).click();
await page.getByRole("heading", { name: "模型图谱" }).waitFor();
if (new URL(page.url()).pathname !== "/models") throw new Error("Models route did not update");
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

await page.getByRole("button", { name: "选择 GPT-5.2" }).click();
await page.getByText("已选 1 个，再选 1 个即可对比").waitFor();
await page.getByRole("button", { name: "选择 Gemini 2.5 Pro" }).click();
await page.getByText("已选 2 个模型").waitFor();
await page.screenshot({ path: fileURLToPath(new URL("catalog.png", outputDir)), fullPage: true });
await page.getByRole("button", { name: /开始对比/ }).click();
await page.getByRole("heading", { name: "模型对比" }).waitFor();
if (await page.locator(".compare-head").count() !== 2) throw new Error("Expected two selected models in comparison");
await page.screenshot({ path: fileURLToPath(new URL("compare.png", outputDir)), fullPage: true });

await page.getByRole("button", { name: "基准", exact: true }).click();
await page.getByRole("heading", { name: "基准目录" }).waitFor();
if (new URL(page.url()).pathname !== "/benchmarks") throw new Error("Benchmarks route did not update");
await page.getByRole("button", { name: /GPQA Diamond/ }).click();
await page.screenshot({ path: fileURLToPath(new URL("benchmarks.png", outputDir)), fullPage: true });

const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
await mobile.goto("http://127.0.0.1:4173/models", { waitUntil: "networkidle" });
await mobile.getByRole("button", { name: "选择 GPT-5.2" }).click();
await mobile.getByText("已选 1 个，再选 1 个即可对比").waitFor();
const mobileWidth = await mobile.evaluate(() => ({ viewport: window.innerWidth, page: document.documentElement.scrollWidth }));
if (mobileWidth.page > mobileWidth.viewport) throw new Error(`Mobile page overflows: ${mobileWidth.page}px > ${mobileWidth.viewport}px`);
await mobile.screenshot({ path: fileURLToPath(new URL("mobile.png", outputDir)), fullPage: true });

await browser.close();
if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.join(" | ")}`);
console.log(JSON.stringify({ navigation: "passed", rows: 6, filters: "passed", selection: "passed", compare: "passed", benchmarks: "passed", mobile: "passed", consoleErrors: 0 }));
