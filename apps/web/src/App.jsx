import { useMemo, useState } from "react";
import { PiArrowLeft, PiArrowRight, PiCaretDown, PiCheck, PiClockCounterClockwise, PiCrosshair, PiInfo, PiMagnifyingGlass, PiSparkle, PiX } from "react-icons/pi";
import { SiAlibabacloud, SiAnthropic, SiDeepseek, SiGoogle, SiMeta } from "react-icons/si";

const PROVIDER_ICONS = { OpenAI: PiSparkle, Anthropic: SiAnthropic, Google: SiGoogle, Meta: SiMeta, DeepSeek: SiDeepseek, Alibaba: SiAlibabacloud };
const MODELS = [
  { id:"gpt-5-2", name:"GPT-5.2", provider:"OpenAI", release:"2026-08-15", context:"1M", reasoning:5, vision:4, tools:5, eval:92.4, benchmark:"MMLU-Pro", source:"Artificial Analysis", variants:["standard","reasoning"], endpoint:"OpenAI API", openWeight:false, score:{"SWE-bench":76.3,GPQA:89.2,"LiveBench Coding":81.4} },
  { id:"claude-opus-4-1", name:"Claude Opus 4.1", provider:"Anthropic", release:"2026-08-05", context:"200K", reasoning:5, vision:4, tools:4, eval:90.1, benchmark:"MMLU-Pro", source:"Artificial Analysis", variants:["standard","thinking"], endpoint:"Anthropic API", openWeight:false, score:{"SWE-bench":72.8,GPQA:88.7,"LiveBench Coding":79.6} },
  { id:"gemini-2-5-pro", name:"Gemini 2.5 Pro", provider:"Google", release:"2026-07-17", context:"1M", reasoning:4, vision:5, tools:4, eval:91.7, benchmark:"MMLU-Pro", source:"Artificial Analysis", variants:["standard","thinking"], endpoint:"Google AI", openWeight:false, score:{"SWE-bench":74.1,GPQA:91.4,"LiveBench Coding":80.1} },
  { id:"llama-4-maverick", name:"Llama 4 Maverick", provider:"Meta", release:"2026-07-29", context:"400K", reasoning:3, vision:4, tools:2, eval:87.3, benchmark:"MMLU-Pro", source:"OpenCompass", variants:["instruct","base"], endpoint:"Meta API", openWeight:true, score:{"SWE-bench":64.8,GPQA:82.2,"LiveBench Coding":72.5} },
  { id:"deepseek-r2", name:"DeepSeek R2", provider:"DeepSeek", release:"2026-08-21", context:"256K", reasoning:4, vision:2, tools:3, eval:88.9, benchmark:"MMLU-Pro", source:"OpenCompass", variants:["chat","reasoner"], endpoint:"DeepSeek API", openWeight:true, score:{"SWE-bench":70.2,GPQA:87.1,"LiveBench Coding":77.8} },
  { id:"qwen3-max", name:"Qwen3 Max", provider:"Alibaba", release:"2026-08-11", context:"1M", reasoning:4, vision:4, tools:4, eval:89.4, benchmark:"MMLU-Pro", source:"Qwen Eval", variants:["standard","thinking"], endpoint:"Alibaba Cloud", openWeight:false, score:{"SWE-bench":71.6,GPQA:86.9,"LiveBench Coding":78.3} },
];

function Rating({ value, label }) {
  return <div className="rating" aria-label={`${label} ${value}/5`}><span className="rating-bars">{[1,2,3,4,5].map(n=><i key={n} className={n<=value?"filled":""}/>)}</span><small>{value>=5?"极强":value>=4?"强":value>=3?"中":"基础"}</small></div>;
}
function Filter({ label, value, onChange, options }) {
  return <label className="filter"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}><option value="all">全部</option>{options.map(x=><option key={x} value={x}>{x}</option>)}</select><PiCaretDown /></label>;
}
function ModelMark({ model }) {
  const Icon=PROVIDER_ICONS[model.provider];
  return <span className={`provider-mark provider-${model.provider.toLowerCase()}`}><Icon /></span>;
}
function CompareView({ selected, onBack, onRemove }) {
  const benchmarks=["SWE-bench","GPQA","LiveBench Coding"];
  return <section className="compare-view">
    <button className="text-button" onClick={onBack}><PiArrowLeft/> 返回模型图谱</button>
    <div className="compare-title"><div><p className="eyebrow">最近 3 个月 · 数据截至 2026-09-20</p><h1>模型对比</h1><p>对比明确的模型变体与服务端点，不混合不同渠道数据。</p></div><span className="freshness"><PiClockCounterClockwise/> 90 天窗口</span></div>
    <div className="compare-grid" style={{"--columns":selected.length}}>
      <div className="compare-label blank"/>
      {selected.map(m=><article className="compare-head" key={m.id}><button onClick={()=>onRemove(m.id)} aria-label={`移除 ${m.name}`}><PiX/></button><ModelMark model={m}/><strong>{m.name}</strong><span>{m.variants[0]} · {m.endpoint}</span></article>)}
      <div className="compare-label">上下文窗口</div>{selected.map(m=><div className="compare-cell" key={`${m.id}-context`}><b>{m.context}</b></div>)}
      {benchmarks.map(b=><div className="compare-row" key={b}><div className="compare-label">{b}<small>权威评测集</small></div>{selected.map(m=>{const best=Math.max(...selected.map(x=>x.score[b]));return <div className={`compare-cell ${m.score[b]===best?"best":""}`} key={`${m.id}-${b}`}><b>{m.score[b]}</b><span>{m.score[b]===best?"当前最佳":""}</span></div>})}</div>)}
      <div className="compare-label">来源可信度</div>{selected.map(m=><div className="compare-cell evidence" key={`${m.id}-source`}><PiCheck/><div><b>高</b><span>{m.source} · 2026-09-18</span></div></div>)}
    </div>
  </section>;
}

export function App() {
  const [view,setView]=useState("models"), [query,setQuery]=useState(""), [provider,setProvider]=useState("all"), [capability,setCapability]=useState("all"), [openWeight,setOpenWeight]=useState("all"), [selectedIds,setSelectedIds]=useState(["gpt-5-2","gemini-2-5-pro"]);
  const selected=MODELS.filter(m=>selectedIds.includes(m.id));
  const filtered=useMemo(()=>MODELS.filter(m=>`${m.name} ${m.provider}`.toLowerCase().includes(query.toLowerCase())&&(provider==="all"||m.provider===provider)&&(openWeight==="all"||(openWeight==="yes"?m.openWeight:!m.openWeight))&&(capability==="all"||m[capability]>=4)),[query,provider,capability,openWeight]);
  const toggle=id=>setSelectedIds(now=>now.includes(id)?now.filter(x=>x!==id):now.length<5?[...now,id]:now);
  const removeFromCompare=id=>{ toggle(id); if(selected.length<=2) setView("models"); };
  return <div className="app-shell">
    <header className="topbar"><button className="brand" onClick={()=>setView("models")}><PiCrosshair/><strong>Model Radar</strong><span>更清晰的模型世界</span></button><nav><button>概览</button><button className={view==="models"?"active":""} onClick={()=>setView("models")}>模型</button><button className={view==="compare"?"active":""} onClick={()=>selected.length>=2&&setView("compare")}>对比</button><button>基准</button></nav><label className="global-search"><PiMagnifyingGlass/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索模型、提供商或能力"/></label><span className="demo-badge">演示数据</span><span className="as-of">数据截至 2026-09-20</span></header>
    <main>{view==="compare"?<CompareView selected={selected} onBack={()=>setView("models")} onRemove={removeFromCompare}/>:<section className="catalog">
      <div className="hero"><div><p className="eyebrow">MODEL INTELLIGENCE · 近 3 个月</p><h1>模型图谱</h1><p>收录经过验证的主流模型、变体与推理端点，快速筛选并进入可信对比。</p></div><aside><strong>独立 · 客观 · 可追溯</strong><span>连接模型、评测与真实应用</span></aside></div>
      <div className="catalog-surface"><div className="filters"><label className="model-search"><PiMagnifyingGlass/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索模型名称、提供商或关键词…"/></label><Filter label="Provider" value={provider} onChange={setProvider} options={["OpenAI","Anthropic","Google","Meta","DeepSeek","Alibaba"]}/><Filter label="能力" value={capability} onChange={setCapability} options={["reasoning","vision","tools"]}/><Filter label="Open Weight" value={openWeight} onChange={setOpenWeight} options={["yes","no"]}/><button className="selection-action" disabled={selected.length<2} onClick={()=>setView("compare")}>已选 {selected.length} / 5 · 去对比 <PiArrowRight/></button></div>
        <div className="table-wrap"><table><thead><tr><th/><th>Model</th><th>Provider</th><th>Release</th><th>Context</th><th>Reasoning</th><th>Vision</th><th>Tool Use</th><th>Latest Eval</th><th>Status</th></tr></thead><tbody>{filtered.map(m=>{const checked=selectedIds.includes(m.id);return <tr key={m.id} className={checked?"selected":""}><td><button className={`checkbox ${checked?"checked":""}`} onClick={()=>toggle(m.id)} aria-label={`${checked?"取消选择":"选择"} ${m.name}`}>{checked&&<PiCheck/>}</button></td><td><div className="model-name"><strong>{m.name}</strong><span>{m.variants.length} variants</span><small>{m.variants.join(" · ")}</small></div></td><td><div className="provider"><ModelMark model={m}/><span>{m.provider}</span></div></td><td>{m.release}</td><td><b>{m.context}</b><small>tokens</small></td><td><Rating value={m.reasoning} label="Reasoning"/></td><td><Rating value={m.vision} label="Vision"/></td><td><Rating value={m.tools} label="Tool use"/></td><td><div className="eval"><b>{m.eval}</b><span>{m.benchmark}</span><small>{m.source}</small></div></td><td><div className="status"><i/>可用<small>{m.endpoint}</small></div></td></tr>})}</tbody></table>{filtered.length===0&&<div className="empty">没有符合当前筛选条件的模型</div>}</div>
        <footer className="table-footer"><span>显示 {filtered.length} 个模型 · 时间范围：2026-06-20 至 2026-09-20</span><span><PiInfo/> 数据来源：官方发布与权威评测集 · 最后更新 2026-09-20</span></footer></div>
      {selected.length>0&&<div className="compare-shelf"><div className="shelf-title"><strong>已选模型 ({selected.length} / 5)</strong><span>确认变体与端点后对比</span></div><div className="shelf-items">{selected.map(m=><div className="shelf-item" key={m.id}><ModelMark model={m}/><div><strong>{m.name}</strong><span>{m.variants[0]} · {m.endpoint}</span></div><button onClick={()=>toggle(m.id)} aria-label={`移除 ${m.name}`}><PiX/></button></div>)}</div><button className="primary" disabled={selected.length<2} onClick={()=>setView("compare")}>对比 {selected.length} 个模型 <PiArrowRight/></button></div>}
    </section>}</main>
  </div>;
}
