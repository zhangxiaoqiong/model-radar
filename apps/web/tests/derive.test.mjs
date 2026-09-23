import assert from "node:assert/strict";
import test from "node:test";
import { buildLeaderboard, buildPricePairs, buildPulse, buildQuadrant, buildTradeoff, computeKpis } from "../src/lib/derive.js";

const model = (over={}) => ({
  id: over.id ?? "slug-a", name: over.name ?? "Model A", provider: over.provider ?? "OpenAI",
  release: over.release ?? "2026-09-01", inputPrice: over.inputPrice === undefined ? 2 : over.inputPrice,
  outputPrice: over.outputPrice === undefined ? null : over.outputPrice,
  speed: over.speed === undefined ? null : over.speed,
  contextTokens: over.contextTokens ?? 100_000, score: over.score ?? {},
});

test("computeKpis dedupes variants and computes median price", () => {
  const today = new Date().toISOString().slice(0, 10);
  const models = [
    model({ id: "a-1", name: "A", inputPrice: 1, release: today }),
    model({ id: "a-2", name: "A", inputPrice: 3 }),
    model({ id: "b-1", name: "B", provider: "Google", inputPrice: null, release: "2026-01-01" }),
  ];
  const kpis = computeKpis(models, { latest_snapshot_time: "2026-09-23T00:00:00" });
  assert.equal(kpis.modelCount, 2);
  assert.equal(kpis.providerCount, 2);
  assert.equal(kpis.newLast30Days, 1);
  assert.equal(kpis.medianInputPrice, 2);
  assert.equal(kpis.lastSync, "2026-09-23T00:00:00");
});

test("computeKpis handles empty input", () => {
  const kpis = computeKpis([], null);
  assert.equal(kpis.modelCount, 0);
  assert.equal(kpis.medianInputPrice, null);
  assert.equal(kpis.lastSync, null);
});

test("buildLeaderboard aggregates variants by name and orders with tiebreak", () => {
  const models = [
    model({ id: "a-low", name: "A", score: { "AA Intelligence": 40 } }),
    model({ id: "a-high", name: "A", score: { "AA Intelligence": 52 }, inputPrice: 3 }),
    model({ id: "b", name: "B", score: { "AA Intelligence": 52 }, release: "2026-09-10" }),
    model({ id: "c", name: "C", score: {} }),
  ];
  const { rows, max } = buildLeaderboard(models, "AA Intelligence");
  assert.equal(max, 52);
  assert.deepEqual(rows.map(r => r.id), ["b", "a-high"]); // tie on score -> newer release first; C has no score
  assert.equal(rows[1].inputPrice, 3); // row carries the winning variant's handle
});

test("buildQuadrant excludes free and scoreless models and splits medians", () => {
  const models = [
    model({ id: "a", name: "A", inputPrice: 1, score: { "AA Intelligence": 50 } }),
    model({ id: "a2", name: "A", inputPrice: 9, score: { "AA Intelligence": 55 } }), // same model: best score wins
    model({ id: "b", name: "B", inputPrice: 0, score: { "AA Intelligence": 60 } }),   // free -> excluded
    model({ id: "c", name: "C", inputPrice: 4, score: {} }),                          // no score -> excluded
    model({ id: "d", name: "D", inputPrice: 8, score: { "AA Intelligence": 30 } }),
  ];
  const q = buildQuadrant(models);
  assert.deepEqual(q.points.map(p => p.id).sort(), ["a2", "d"]);
  assert.equal(q.points.find(p => p.id === "a2").x, 9); // winning variant's price
  assert.equal(q.excluded, 2);
  assert.equal(q.total, 4);
  assert.equal(q.medianX, 8.5);
  assert.equal(q.medianY, 42.5);
});

test("buildQuadrant with too few points still reports exclusions", () => {
  const q = buildQuadrant([model({ score: { "AA Intelligence": 10 } })]);
  assert.equal(q.points.length, 1);
  assert.equal(q.medianX, 2);
});

test("buildPulse returns per-dimension leader", () => {
  const models = [
    model({ id: "a", name: "A", score: { "AA Intelligence": 40, "AA Coding": 70 } }),
    model({ id: "b", name: "B", score: { "AA Intelligence": 41 } }),
  ];
  const pulse = buildPulse(models);
  assert.deepEqual(pulse.map(p => [p.label, p.model.id]), [
    ["AA Intelligence", "b"], ["AA Coding", "a"],
  ]);
});

test("buildTradeoff keeps only nondominated price and speed points on each frontier", () => {
  const models = [
    model({ id: "cheap", name: "Cheap", inputPrice: 1, speed: 20, score: { "AA Intelligence": 35 } }),
    model({ id: "balanced", name: "Balanced", inputPrice: 2, speed: 80, score: { "AA Intelligence": 50 } }),
    model({ id: "dominated", name: "Dominated", inputPrice: 3, speed: 30, score: { "AA Intelligence": 42 } }),
    model({ id: "strong", name: "Strong", inputPrice: 5, speed: 50, score: { "AA Intelligence": 60 } }),
    model({ id: "missing", name: "Missing", inputPrice: null, speed: null, score: { "AA Intelligence": 55 } }),
  ];
  const price = buildTradeoff(models, "AA Intelligence");
  assert.deepEqual(price.frontier.map(point => point.id), ["cheap", "balanced", "strong"]);
  assert.equal(price.excluded, 1);
  const speed = buildTradeoff(models, "AA Intelligence", "speed");
  assert.deepEqual(speed.frontier.map(point => point.id), ["balanced", "strong"]);
  assert.equal(speed.excluded, 1);
});

test("buildPricePairs requires both prices and chooses the highest-scoring variant", () => {
  const models = [
    model({ id: "a-low", name: "A", inputPrice: 1, outputPrice: 3, score: { "AA Coding": 60 } }),
    model({ id: "a-high", name: "A", inputPrice: 2, outputPrice: 5, score: { "AA Coding": 70 } }),
    model({ id: "b", name: "B", inputPrice: 1, outputPrice: null, score: { "AA Coding": 80 } }),
  ];
  assert.deepEqual(buildPricePairs(models, "AA Coding").map(item => item.id), ["a-high"]);
});
