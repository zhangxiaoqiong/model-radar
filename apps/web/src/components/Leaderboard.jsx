import { useMemo } from "react";
import { DIMENSIONS, buildLeaderboard } from "../lib/derive.js";
import { ModelMark } from "./shared.jsx";

function priceLabel(value) { return value==null ? "—" : `$${value.toFixed(value<1?3:2)}`; }

export function Leaderboard({ models, selectedIds, toggle, loading, dimension, setDimension }) {
  const { rows, max }=useMemo(()=>buildLeaderboard(models, dimension), [models, dimension]);
  return <article className="dk-panel leaderboard-panel">
    <header><h2>模型排行榜</h2><span className="dk-hint">Top {rows.length||8} · 点击行加入对比</span></header>
    <div className="lb-tabs" role="tablist" aria-label="排行榜维度">
      {DIMENSIONS.map(d=><button key={d} role="tab" aria-selected={d===dimension} className={`lb-tab ${d===dimension?"active":""}`} onClick={()=>setDimension(d)}>{d.replace("AA ","")}</button>)}
    </div>
    <div className="lb-list">
      {loading && [1,2,3,4,5].map(n=><div className="lb-row skeleton-row" key={n}><span className="lb-rank">{n}</span><span className="skeleton-bar round"/><span className="skeleton-bar line"/><span className="skeleton-bar line short"/><span className="skeleton-bar line short"/></div>)}
      {!loading && rows.length===0 && <p className="quadrant-fallback small">该维度暂无评估数据。</p>}
      {!loading && rows.map((row, index)=><button
        key={row.id}
        className={`lb-row ${selectedIds.includes(row.id)?"checked":""}`}
        onClick={()=>toggle(row.id)}
        aria-pressed={selectedIds.includes(row.id)}
        title={row.name}>
        <span className="lb-rank">{index+1}</span>
        <ModelMark model={row}/>
        <span className="lb-name">
          <strong>{row.name}</strong>
          <span className="lb-bar"><i style={{width: max?`${Math.max(4, (row.score/max)*100)}%`:0}}/></span>
        </span>
        <span className="lb-price">{priceLabel(row.inputPrice)}</span>
        <span className="lb-score">{row.score}</span>
      </button>)}
    </div>
  </article>;
}
