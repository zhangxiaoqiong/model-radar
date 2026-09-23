import { buildPricePairs } from "../lib/derive.js";

function price(value) { return `$${value < 1 ? value.toFixed(3) : value.toFixed(2)}`; }

export function PriceBars({ models, dimension, selectedIds, toggle, loading }) {
  const rows = buildPricePairs(models, dimension);
  const max = Math.max(1, ...rows.flatMap(model => [model.inputPrice, model.outputPrice]));
  const width = value => `${Math.max(2, Math.log1p(value) / Math.log1p(max) * 100)}%`;
  return <>
    <div className="price-bars-legend"><span><i className="input"/>输入</span><span><i className="output"/>输出</span><small>价格 / 百万 tokens · 条长为对数刻度</small></div>
    {loading ? <div className="tradeoff-empty">正在载入价格数据…</div> : rows.length === 0 ? <div className="tradeoff-empty">暂无同时具备输入和输出价格的模型。</div> : <div className="price-bars-list">
      {rows.map(model => <button className={`price-bars-row ${selectedIds.includes(model.id) ? "selected" : ""}`} key={model.id} onClick={() => toggle(model.id)} aria-pressed={selectedIds.includes(model.id)} title={`点击${selectedIds.includes(model.id) ? "取消" : "加入"}对比：${model.name}`}>
        <span className="price-bars-model"><strong>{model.name}</strong><small>{model.provider}</small></span>
        <span className="price-bars-pair">
          <span className="price-bars-line"><i className="price-bars-track"><i className="price-bars-fill input" style={{ width: width(model.inputPrice) }}/></i><b>{price(model.inputPrice)}</b></span>
          <span className="price-bars-line"><i className="price-bars-track"><i className="price-bars-fill output" style={{ width: width(model.outputPrice) }}/></i><b>{price(model.outputPrice)}</b></span>
        </span>
      </button>)}
    </div>}
  </>;
}
