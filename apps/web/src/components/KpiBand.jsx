import { stampDateTime } from "../lib/api.js";

function priceLabel(value) { return value==null ? "—" : `$${value.toFixed(value<1?3:2)}`; }

function Tile({ label, value, hint, loading }) {
  return <div className="kpi-tile">
    <small>{label}</small>
    {loading ? <b className="skeleton-bar"/> : <b>{value}</b>}
    <span>{loading ? "加载中" : hint}</span>
  </div>;
}

export function KpiBand({ kpis, loading, rangeLabel }) {
  return <div className="kpi-band" role="group" aria-label="全局统计">
    <Tile label="跟踪模型" value={kpis.modelCount} hint={rangeLabel || "当前范围"} loading={loading}/>
    <Tile label="提供商" value={kpis.providerCount} hint="家" loading={loading}/>
    <Tile label="有评估数据" value={kpis.evaluatedCount} hint="个模型可比较" loading={loading}/>
    <Tile label="输入价中位数" value={priceLabel(kpis.medianInputPrice)} hint="/ 百万 tokens" loading={loading}/>
    <Tile label="最新同步" value={stampDateTime(kpis.lastSync)?.slice(5) ?? "—"} hint={stampDateTime(kpis.lastSync) ? "本次来源数据" : "尚未同步"} loading={loading}/>
  </div>;
}
