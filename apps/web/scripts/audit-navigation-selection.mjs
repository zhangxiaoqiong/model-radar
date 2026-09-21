import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const out = new URL("../audit/", import.meta.url);
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:4173/", { waitUntil: "networkidle" });

const shot = (name) => page.screenshot({ path: fileURLToPath(new URL(name, out)) });
const state = async () => page.evaluate(() => ({
  url: location.href,
  heading: document.querySelector("h1")?.textContent,
  activeNav: document.querySelector("nav .active")?.textContent,
  selectedCount: document.querySelectorAll(".checkbox.checked").length,
  shelf: document.querySelector(".compare-shelf")?.getBoundingClientRect().toJSON() || null,
  shelfBackground: document.querySelector(".compare-shelf") ? getComputedStyle(document.querySelector(".compare-shelf")).backgroundColor : null,
  hasLiveRegion: Boolean(document.querySelector('[aria-live]')),
}));

await shot("01-models-initial.png");
const initial = await state();

await page.getByRole("button", { name: "概览", exact: true }).click();
await page.waitForTimeout(250);
await shot("02-after-overview-click.png");
const afterOverview = await state();

await page.getByRole("button", { name: "基准", exact: true }).click();
await page.waitForTimeout(250);
await shot("03-after-benchmark-click.png");
const afterBenchmark = await state();

await page.getByRole("button", { name: "对比", exact: true }).click();
await page.getByRole("heading", { name: "模型对比" }).waitFor();
await shot("04-compare-destination.png");
const afterCompare = await state();

await page.getByRole("button", { name: "返回模型图谱" }).click();
await page.getByRole("button", { name: "取消选择 GPT-5.2" }).click();
await page.getByRole("button", { name: "取消选择 Gemini 2.5 Pro" }).click();
await page.getByRole("button", { name: "选择 Claude Opus 4.1" }).click();
await page.waitForTimeout(250);
await shot("05-one-model-selected.png");
const afterSelection = await state();

console.log(JSON.stringify({ initial, afterOverview, afterBenchmark, afterCompare, afterSelection }, null, 2));
await browser.close();
