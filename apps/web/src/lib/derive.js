export const DIMENSIONS = ["AA Intelligence", "AA Coding", "AA Agentic"];

function finite(value) { return Number.isFinite(value) ? value : null; }

function median(values) {
  if (!values.length) return null;
  const sorted=[...values].sort((a,b)=>a-b), mid=Math.floor(sorted.length/2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid-1]+sorted[mid]) / 2;
}

function groupByName(models) {
  const groups=new Map();
  for (const model of models) {
    const list=groups.get(model.name);
    if (list) list.push(model); else groups.set(model.name, [model]);
  }
  return [...groups.values()];
}

export function computeKpis(models, status) {
  const groups=groupByName(models);
  const cutoff=new Date(Date.now()-30*24*60*60*1000).toISOString().slice(0,10);
  return {
    modelCount: groups.length,
    providerCount: new Set(models.map(m=>m.provider)).size,
    evaluatedCount: groups.filter(group=>group.some(model=>DIMENSIONS.some(dimension=>Number.isFinite(model.score?.[dimension])))).length,
    newLast30Days: groups.filter(group=>group.some(m=>m.release && m.release!=="—" && m.release>=cutoff)).length,
    medianInputPrice: median(models.map(m=>m.inputPrice).filter(Number.isFinite)),
    lastSync: status?.latest_snapshot_time ?? null,
  };
}

export function buildLeaderboard(models, dimension, limit=8) {
  const rows=[];
  for (const group of groupByName(models)) {
    let best=null;
    for (const model of group) {
      const score=finite(model.score?.[dimension]);
      if (score==null) continue;
      if (!best || score>best.score || (score===best.score && (model.release||"")>(best.release||""))) {
        best={ id:model.id, name:model.name, provider:model.provider, score, release:model.release, inputPrice:model.inputPrice };
      }
    }
    if (best) rows.push(best);
  }
  rows.sort((a,b)=> b.score-a.score || (b.release||"").localeCompare(a.release||""));
  const top=rows.slice(0, limit);
  return { rows: top, max: top.length ? top[0].score : null };
}

export function buildQuadrant(models) {
  const groups=groupByName(models);
  const points=[];
  let excluded=0;
  for (const group of groups) {
    let best=null;
    for (const model of group) {
      const value=finite(model.score?.["AA Intelligence"]);
      if (value==null) continue;
      if (!best || value>best.value) best={ value, model };
    }
    if (!best) { excluded++; continue; }
    const price=finite(best.model.inputPrice);
    if (price==null || price<=0) { excluded++; continue; }
    points.push({
      id: best.model.id, name: best.model.name, provider: best.model.provider,
      x: price, y: best.value, z: finite(best.model.contextTokens)||0, release: best.model.release,
    });
  }
  return {
    points,
    medianX: median(points.map(p=>p.x)),
    medianY: median(points.map(p=>p.y)),
    excluded,
    total: groups.length,
  };
}

export function buildTradeoff(models, dimension, measure = "inputPrice") {
  const lowerIsBetter = measure === "inputPrice";
  const points = [];
  let excluded = 0;
  for (const group of groupByName(models)) {
    const eligible = group.filter(model => Number.isFinite(model.score?.[dimension]) && Number.isFinite(model[measure]) && model[measure] > 0);
    if (!eligible.length) { excluded++; continue; }
    const model = eligible.sort((a, b) => b.score[dimension] - a.score[dimension] || (lowerIsBetter ? a[measure] - b[measure] : b[measure] - a[measure]))[0];
    points.push({ id: model.id, name: model.name, provider: model.provider, x: model[measure], y: model.score[dimension], release: model.release });
  }
  const sorted = [...points].sort((a, b) => (lowerIsBetter ? a.x - b.x : b.x - a.x) || b.y - a.y);
  const frontier = [];
  let bestScore = -Infinity;
  for (const point of sorted) {
    if (point.y > bestScore) { frontier.push(point); bestScore = point.y; }
  }
  return {
    points,
    frontier,
    medianX: median(points.map(point => point.x)),
    medianY: median(points.map(point => point.y)),
    excluded,
    total: groupByName(models).length,
  };
}

export function buildPricePairs(models, dimension, limit = 6) {
  return groupByName(models).map(group => group
    .filter(model => Number.isFinite(model.score?.[dimension]) && Number.isFinite(model.inputPrice) && Number.isFinite(model.outputPrice))
    .sort((a, b) => b.score[dimension] - a.score[dimension])[0])
    .filter(Boolean)
    .sort((a, b) => b.score[dimension] - a.score[dimension])
    .slice(0, limit);
}

export function buildPulse(models, dimensions=DIMENSIONS) {
  return dimensions.map(label=>{
    let best=null;
    for (const model of models) {
      const value=finite(model.score?.[label]);
      if (value==null) continue;
      if (!best || value>best.value) best={ value, model };
    }
    return best ? { label, model: best.model, value: best.value } : null;
  }).filter(Boolean);
}
