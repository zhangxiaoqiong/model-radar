import { useEffect, useMemo, useState } from "react";
import { PiArrowLeft, PiArrowRight, PiClockCounterClockwise, PiTrendUp, PiX } from "react-icons/pi";
import { COMPARE_BENCHMARKS, SCORE_LABELS, loadModelEvaluations, stampDate } from "../lib/api.js";
import { monthlyCost } from "../lib/cost.js";
import { ModelMark } from "../components/shared.jsx";

const fmt = value => Number(value).toLocaleString("zh-CN", {maximumFractionDigits:2});
const money = (value, currency) => new Intl.NumberFormat("zh-CN", {style:"currency",currency:currency||"USD",maximumFractionDigits:2}).format(value);
const dateOf = row => stampDate(row?.evaluation_date||row?.data_date)||"日期未记录";
const conditionsOf = row => row?.test_conditions && Object.keys(row.test_conditions).length ? JSON.stringify(row.test_conditions) : null;

function EvaluationComparison({selected}) {
  const [records,setRecords]=useState({}), [loading,setLoading]=useState(true), [failed,setFailed]=useState(false);
  const ids=selected.map(model=>model.id).join("|");
  useEffect(()=>{
    let alive=true;
    setLoading(true);setFailed(false);
    Promise.all(selected.map(async model=>[model.id,await loadModelEvaluations(model.id)]))
      .then(pairs=>{if(alive)setRecords(Object.fromEntries(pairs));})
      .catch(()=>{if(alive){setRecords({});setFailed(true);}})
      .finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;};
  },[ids]);
  const rows=useMemo(()=>{
    const names=new Set(COMPARE_BENCHMARKS);
    Object.values(records).flat().forEach(row=>names.add(row.benchmark_slug));
    return [...names].map(name=>{
      const scores=selected.map(model=>{
        const matching=(records[model.id]||[]).filter(row=>row.benchmark_slug===name);
        return matching.sort((a,b)=>dateOf(b).localeCompare(dateOf(a)))[0]||null;
      });
      const complete=scores.every(Boolean);
      const basis=scores[0];
      const comparable=complete&&!!basis.benchmark_version&&!!basis.score_unit&&!!conditionsOf(basis)
        &&scores.every(row=>row.source===basis.source&&row.benchmark_version===basis.benchmark_version
          &&row.score_unit===basis.score_unit&&conditionsOf(row)===conditionsOf(basis));
      return {name,scores,comparable,hasAny:scores.some(Boolean)};
    }).filter(row=>row.hasAny);
  },[records,selected]);
  return <section className="compare-section">
    <div className="compare-section-heading"><div><p className="section-kicker">EVALUATION EVIDENCE</p><h2>同指标评测对照</h2><span>只有平台、版本、单位和测试条件均一致，才标为严格可比；缺失字段如实标注。</span></div></div>
    {loading?<div className="panel compare-message">正在读取评测明细…</div>:failed?<div className="panel compare-message">评测明细暂时不可用，无法核对测试口径。</div>:rows.length===0?<div className="panel compare-message">所选模型暂无评测记录。</div>:
      <div className="compare-evidence-scroll"><div className="compare-evidence" style={{"--columns":selected.length}}>
        <div className="compare-evidence-head">评测项 / 可比性</div>{selected.map(model=><div className="compare-evidence-head" key={model.id}>{model.name}</div>)}
        {rows.map(row=><div className="compare-evidence-row" key={row.name}>
          <div className="compare-evidence-label"><strong>{SCORE_LABELS[row.name]||row.name}</strong><span className={row.comparable?"evidence-ok":"evidence-warn"}>{row.comparable?"严格可比":"口径待核 · 不判胜负"}</span></div>
          {row.scores.map((score,index)=><div className="compare-evidence-cell" key={selected[index].id}>
            {score?<><strong>{fmt(score.score)}{score.score_unit?` ${score.score_unit}`:""}</strong><small>{score.source||"平台未记录"} · {dateOf(score)}</small><small>版本 {score.benchmark_version||"未记录"} · 条件 {conditionsOf(score)||"未记录"}</small></>:<span className="compare-missing">未收录</span>}
          </div>)}
        </div>)}
      </div></div>}
  </section>;
}

function CostScenario({selected}) {
  const [scenario,setScenario]=useState({requestsPerDay:1000,inputTokens:4000,outputTokens:800,cacheHit:0});
  const update=(key,value)=>setScenario(now=>({...now,[key]:Math.max(0,Number(value)||0)}));
  const rows=selected.map(model=>({model,cost:monthlyCost(model,scenario)}));
  const currencies=new Set(rows.filter(row=>row.cost).map(row=>row.cost.currency));
  const maxByCurrency=Object.fromEntries([...currencies].map(currency=>[currency,Math.max(...rows.filter(row=>row.cost?.currency===currency).map(row=>row.cost.amount))]));
  return <section className="compare-section">
    <div className="compare-section-heading"><div><p className="section-kicker">USAGE-BASED COST</p><h2>同一用量下的月成本</h2><span>按 30 天估算，缓存读取价缺失时按普通输入价计算；不做跨币种排序。</span></div></div>
    <div className="panel cost-scenario">
      <div className="cost-inputs">
        <label>每日请求数<input type="number" min="0" value={scenario.requestsPerDay} onChange={e=>update("requestsPerDay",e.target.value)}/></label>
        <label>每次输入 token<input type="number" min="0" value={scenario.inputTokens} onChange={e=>update("inputTokens",e.target.value)}/></label>
        <label>每次输出 token<input type="number" min="0" value={scenario.outputTokens} onChange={e=>update("outputTokens",e.target.value)}/></label>
        <label>缓存命中率 %<input type="number" min="0" max="100" value={scenario.cacheHit} onChange={e=>update("cacheHit",Math.min(100,Number(e.target.value)))}/></label>
      </div>
      <div className="cost-chart">{rows.map(({model,cost})=><div className="cost-row" key={model.id}>
        <strong title={model.name}>{model.name}</strong>
        {cost?<><div className="cost-track"><div style={{width:`${maxByCurrency[cost.currency]?cost.amount/maxByCurrency[cost.currency]*100:0}%`}}/></div><b>{money(cost.amount,cost.currency)}</b></>:<><div className="cost-track"/><b>价格未收录</b></>}
        {cost?.cacheEstimated&&<small>缓存价格缺失，按普通输入价估算</small>}
      </div>)}</div>
      <p className="cost-note">单价来源：{[...new Set(selected.map(model=>model.pricingProvider).filter(Boolean))].join(" / ")||"未注明"}。此处为 API 价格估算，不包含阶梯价、批量折扣或其他费用。</p>
    </div>
  </section>;
}

export function Compare({selected,navigate,toggle,syncDateLabel}) {
  if(selected.length<2) return <section className="page compare-view"><div className="page-hero"><div><p className="eyebrow">MODEL COMPARE</p><h1>模型对比</h1><p>选择 2–5 个明确的模型，查看同口径评测与用量成本。</p></div></div><div className="panel compare-empty"><span className="empty-icon"><PiTrendUp/></span><h2>{selected.length===1?"再选 1 个模型即可开始":"还没有选择模型"}</h2><p>{selected.length===1?`${selected[0].name} 已加入对比。`:"从模型库中选择你真正关心的候选项。"}</p><button className="primary" onClick={()=>navigate("models")}>去选择模型 <PiArrowRight/></button></div></section>;
  return <section className="compare-view page"><button className="text-button" onClick={()=>navigate("models")}><PiArrowLeft/> 返回模型库</button>
    <div className="compare-title"><div><p className="eyebrow">最近 3 个月 · 数据截至 {syncDateLabel||"待同步"}</p><h1>模型对比</h1><p>先看规格，再核对评测口径，最后按真实用量估算成本。</p></div><span className="freshness"><PiClockCounterClockwise/> 90 天窗口</span></div>
    <div className="compare-basic-scroll"><div className="compare-grid" style={{"--columns":selected.length}}>
      <div className="compare-label blank"/>{selected.map(model=><article className="compare-head" key={model.id}><button onClick={()=>toggle(model.id)} aria-label={`移除 ${model.name}`}><PiX/></button><ModelMark model={model}/><strong>{model.name}</strong><span>{model.variants[0]} · {model.endpoint}</span></article>)}
      <div className="compare-label">上下文窗口</div>{selected.map(model=><div className="compare-cell" key={`${model.id}-context`}><b>{model.context}</b></div>)}
      <div className="compare-label">输入 / 输出价<small>每百万 token · 原币种</small></div>{selected.map(model=><div className="compare-cell" key={`${model.id}-price`}><b className="compare-price">{model.currency&&model.inputPrice!=null&&model.outputPrice!=null?`${money(model.inputPrice,model.currency)} / ${money(model.outputPrice,model.currency)}`:"价格未收录"}</b><small>{model.pricingProvider||"价格来源未注明"}</small></div>)}
    </div></div>
    <EvaluationComparison selected={selected}/>
    <CostScenario selected={selected}/>
  </section>;
}
