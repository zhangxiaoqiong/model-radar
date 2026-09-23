import { useMemo, useState } from "react";
import { PiArrowCounterClockwise, PiArrowRight, PiArrowUpRight, PiCalendarBlank, PiChartScatter, PiClockCountdown } from "react-icons/pi";
import { DIMENSIONS, buildLeaderboard, buildTradeoff, computeKpis } from "../lib/derive.js";
import { KpiBand } from "../components/KpiBand.jsx";
import { TradeoffChart } from "../components/TradeoffChart.jsx";
import { PriceBars } from "../components/PriceBars.jsx";
import { CapabilityProfileChart } from "../components/CapabilityProfileChart.jsx";

const DIMENSION_LABELS = { "AA Intelligence": "综合智能", "AA Coding": "编程", "AA Agentic": "智能体" };

function buildCapabilityRanking(models, dimension) {
  const byName = new Map();
  const completeness = model => DIMENSIONS.filter(dimension => Number.isFinite(model.score?.[dimension])).length;
  for (const model of models) {
    const previous = byName.get(model.name);
    if (!previous || (model.score?.[dimension] ?? -Infinity) > (previous.score?.[dimension] ?? -Infinity) || (model.score?.[dimension] === previous.score?.[dimension] && completeness(model) > completeness(previous))) byName.set(model.name, model);
  }
  const unique = [...byName.values()].filter(model => Number.isFinite(model.score?.[dimension]));
  const rows = [...unique].sort((a, b) => b.score[dimension] - a.score[dimension]).slice(0, 8);
  return { rows };
}

export function Overview({ navigate, models, selectedIds, toggle, syncDateLabel, dataStatus, status }) {
  const [dimension, setDimension] = useState(DIMENSIONS[0]);
  const dates = useMemo(() => models.map(model => model.release).filter(value => value && value !== "—").sort(), [models]);
  const minDate = dates[0] || "", maxDate = dates.at(-1) || "";
  const [fromDate, setFromDate] = useState(""), [toDate, setToDate] = useState(""), [vendor, setVendor] = useState("all");
  const effectiveFrom = fromDate || minDate, effectiveTo = toDate || maxDate;
  const vendors = useMemo(() => [...new Set(models.map(model => model.provider))].sort(), [models]);
  const filteredModels = useMemo(() => models.filter(model =>
    model.release && model.release !== "—" &&
    (!effectiveFrom || model.release >= effectiveFrom) &&
    (!effectiveTo || model.release <= effectiveTo) &&
    (vendor === "all" || model.provider === vendor)
  ), [models, effectiveFrom, effectiveTo, vendor]);
  const setRange = days => {
    if (!maxDate) return;
    if (days === "all") { setFromDate(minDate); setToDate(maxDate); return; }
    const start = new Date(`${maxDate}T00:00:00`); start.setDate(start.getDate() - days + 1);
    setFromDate(start.toISOString().slice(0, 10) < minDate ? minDate : start.toISOString().slice(0, 10));
    setToDate(maxDate);
  };
  const resetFilters = () => { setFromDate(minDate); setToDate(maxDate); setVendor("all"); };
  const rangeLabel = effectiveFrom && effectiveTo ? `${effectiveFrom} 至 ${effectiveTo}` : "当前数据范围";
  const loading = dataStatus === "loading";
  const kpis = useMemo(() => computeKpis(filteredModels, status), [filteredModels, status]);
  const priceTradeoff = useMemo(() => buildTradeoff(filteredModels, dimension), [filteredModels, dimension]);
  const speedTradeoff = useMemo(() => buildTradeoff(filteredModels, dimension, "speed"), [filteredModels, dimension]);
  const ranking = useMemo(() => buildCapabilityRanking(filteredModels, dimension), [filteredModels, dimension]);
  const leader = useMemo(() => buildLeaderboard(filteredModels, "AA Intelligence", 1).rows[0], [filteredModels]);
  const hasSelection = selectedIds.length >= 2;

  return <section className="overview-atlas page">
    <div className="atlas-hero">
      <div className="atlas-hero-copy">
        <p className="atlas-eyebrow"><span className="atlas-signal"/> MODEL RADAR / ANALYTICS DASHBOARD</p>
        <h1>看清模型格局，<br/><em>找到更好的选择。</em></h1>
        <p className="atlas-intro">从多维能力、价格取舍到评测排名，把近期模型放在同一张地图上。</p>
        <div className="atlas-hero-actions">
          <button className="atlas-primary" onClick={() => navigate(hasSelection ? "compare" : "models")}>{hasSelection ? `对比已选 ${selectedIds.length} 个模型` : "探索模型图谱"}<PiArrowRight/></button>
          <button className="atlas-secondary" onClick={() => navigate("evaluations")}>查看评测平台 <PiArrowUpRight/></button>
        </div>
      </div>
      <div className="atlas-hero-insight">
        <div className="atlas-insight-top"><span>当前智能评估领先</span><PiChartScatter/></div>
        {loading ? <div className="atlas-insight-loading">正在载入模型数据…</div> : leader ? <>
          <strong title={leader.name}>{leader.name}</strong>
          <span className="atlas-insight-provider">{leader.provider} · AA Intelligence</span>
          <div className="atlas-insight-score"><b>{leader.score}</b><span>评估分数</span></div>
        </> : <div className="atlas-insight-loading">暂无可用评估数据</div>}
        <div className="atlas-insight-foot"><PiClockCountdown/> 来源同步 {syncDateLabel || "待同步"}</div>
      </div>
    </div>

    <section className="dashboard-filterbar" aria-label="看板全局筛选">
      <div className="dashboard-filter-title"><PiCalendarBlank/><span><b>分析范围</b><small>以下图表使用同一筛选口径</small></span></div>
      <div className="dashboard-presets"><button onClick={() => setRange(30)}>近 30 天</button><button onClick={() => setRange(60)}>近 60 天</button><button onClick={() => setRange("all")}>全部</button></div>
      <label><span>开始日期</span><input type="date" min={minDate} max={effectiveTo || maxDate} value={effectiveFrom} onChange={event => setFromDate(event.target.value)}/></label>
      <label><span>结束日期</span><input type="date" min={effectiveFrom || minDate} max={maxDate} value={effectiveTo} onChange={event => setToDate(event.target.value)}/></label>
      <label><span>厂家</span><select value={vendor} onChange={event => setVendor(event.target.value)}><option value="all">全部厂家</option>{vendors.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
      <button className="dashboard-reset" onClick={resetFilters}><PiArrowCounterClockwise/>重置</button>
    </section>
    <div className="dashboard-scope"><span>{rangeLabel}</span><b>{filteredModels.length}</b> 个模型参与当前看板分析{vendor !== "all" ? ` · ${vendor}` : ""}</div>

    <KpiBand kpis={kpis} loading={loading} rangeLabel={rangeLabel}/>

    <div className="atlas-section-heading">
      <div><p className="atlas-section-kicker">01 / VALUE FRONTIER</p><h2>能力与价格，谁在有效边界上</h2><span>越靠左上越有吸引力；虚线连接当前数据中未被同时超越的模型。</span></div>
      <div className="atlas-dimension-switch" role="group" aria-label="评估维度">{DIMENSIONS.map(item => <button key={item} className={item === dimension ? "active" : ""} aria-pressed={item === dimension} onClick={() => setDimension(item)}>{item.replace("AA ", "")}</button>)}</div>
    </div>
    <article className="atlas-panel atlas-tradeoff-panel">
      <div className="atlas-panel-head"><div><strong>{dimension.replace("AA ", "")}分数 × 输入价格</strong><span>使用已同步的 AA 分数和输入单价；价格不等于完整任务成本。</span></div><div className="atlas-frontier-count"><b>{priceTradeoff.frontier.length}</b><span>个前沿模型</span></div></div>
      <TradeoffChart data={priceTradeoff} dimension={dimension} selectedIds={selectedIds} toggle={toggle} loading={loading}/>
    </article>

    <div className="atlas-section-heading atlas-section-heading-second"><div><p className="atlas-section-kicker">02 / CAPABILITY RANKING</p><h2>能力排行榜</h2><span>选择你关心的能力，比较近期模型在同一项评测中的表现。</span></div><div className="atlas-dimension-switch" role="group" aria-label="能力榜单维度">{DIMENSIONS.map(item => <button key={item} className={item === dimension ? "active" : ""} aria-pressed={item === dimension} onClick={() => setDimension(item)}>{DIMENSION_LABELS[item]}</button>)}</div></div>
    <article className="atlas-panel atlas-profile-panel">
      <div className="atlas-panel-head"><div><strong>{DIMENSION_LABELS[dimension]} · 前 {ranking.rows.length || 8} 名</strong><span>{dimension} · 分数越高越好</span></div>{hasSelection ? <button className="atlas-selected-note atlas-selected-action" onClick={() => navigate("compare")}>对比已选 {selectedIds.length} 个 <PiArrowRight/></button> : <span className="atlas-selected-note">{selectedIds.length === 1 ? "已选 1 个，再选 1 个即可对比" : "点击模型加入对比"}</span>}</div>
      <CapabilityProfileChart matrix={ranking} dimension={dimension} selectedIds={selectedIds} toggle={toggle} loading={loading}/>
    </article>

    <div className="atlas-section-heading atlas-section-heading-second"><div><p className="atlas-section-kicker">03 / OPERATING TRADEOFFS</p><h2>运行时的两笔账</h2><span>分数相近时，再看生成速度与输入、输出价格。</span></div><button className="atlas-link" onClick={() => navigate("models")}>查看完整规格 <PiArrowRight/></button></div>
    <div className="atlas-detail-grid">
      <article className="atlas-panel atlas-speed-panel"><div className="atlas-panel-head"><div><strong>{dimension.replace("AA ", "")}分数 × 输出速度</strong><span>右上方的模型兼具较高分数和较快生成速度。</span></div></div><TradeoffChart data={speedTradeoff} dimension={dimension} mode="speed" selectedIds={selectedIds} toggle={toggle} loading={loading}/></article>
      <article className="atlas-panel atlas-pricing-panel"><div className="atlas-panel-head"><div><strong>高分模型的输入 / 输出价格</strong><span>按当前维度排名，展示有完整报价的前 6 个模型。</span></div></div><PriceBars models={filteredModels} dimension={dimension} selectedIds={selectedIds} toggle={toggle} loading={loading}/></article>
    </div>
    <p className="atlas-method-note">当前范围：{rangeLabel} · 所有图表共享日期和厂家筛选；评估、价格与速度缺失值不参与对应图形。{dataStatus === "error" ? " 数据源连接失败，稍后自动重试。" : ""}</p>
  </section>;
}
