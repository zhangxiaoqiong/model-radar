import { useEffect, useMemo, useState } from "react";
import {
  PiArrowLeft, PiArrowRight,
  PiCaretDown, PiCaretRight, PiChartLineUp, PiCheck,
  PiClockCounterClockwise, PiCrosshair, PiInfo,
  PiMagnifyingGlass, PiShieldWarning, PiSparkle, PiTrendUp, PiX,
} from "react-icons/pi";
import { SiAlibabacloud, SiAnthropic, SiDeepseek, SiGoogle, SiMeta } from "react-icons/si";

const PROVIDER_ICONS = { OpenAI: PiSparkle, Anthropic: SiAnthropic, Google: SiGoogle, Meta: SiMeta, DeepSeek: SiDeepseek, Alibaba: SiAlibabacloud };
const ROUTES = { overview: "/", models: "/models", compare: "/compare", benchmarks: "/benchmarks" };
const DEMO_MODELS = [
  { id:"gpt-5-2", name:"GPT-5.2", provider:"OpenAI", release:"2026-08-15", context:"1M", reasoning:5, vision:4, tools:5, eval:92.4, benchmark:"MMLU-Pro", source:"Artificial Analysis", variants:["standard","reasoning"], endpoint:"OpenAI API", openWeight:false, score:{"SWE-bench":76.3,GPQA:89.2,"LiveBench Coding":81.4} },
  { id:"claude-opus-4-1", name:"Claude Opus 4.1", provider:"Anthropic", release:"2026-08-05", context:"200K", reasoning:5, vision:4, tools:4, eval:90.1, benchmark:"MMLU-Pro", source:"Artificial Analysis", variants:["standard","thinking"], endpoint:"Anthropic API", openWeight:false, score:{"SWE-bench":72.8,GPQA:88.7,"LiveBench Coding":79.6} },
  { id:"gemini-2-5-pro", name:"Gemini 2.5 Pro", provider:"Google", release:"2026-07-17", context:"1M", reasoning:4, vision:5, tools:4, eval:91.7, benchmark:"MMLU-Pro", source:"Artificial Analysis", variants:["standard","thinking"], endpoint:"Google AI", openWeight:false, score:{"SWE-bench":74.1,GPQA:91.4,"LiveBench Coding":80.1} },
  { id:"llama-4-maverick", name:"Llama 4 Maverick", provider:"Meta", release:"2026-07-29", context:"400K", reasoning:3, vision:4, tools:2, eval:87.3, benchmark:"MMLU-Pro", source:"OpenCompass", variants:["instruct","base"], endpoint:"Meta API", openWeight:true, score:{"SWE-bench":64.8,GPQA:82.2,"LiveBench Coding":72.5} },
  { id:"deepseek-r2", name:"DeepSeek R2", provider:"DeepSeek", release:"2026-08-21", context:"256K", reasoning:4, vision:2, tools:3, eval:88.9, benchmark:"MMLU-Pro", source:"OpenCompass", variants:["chat","reasoner"], endpoint:"DeepSeek API", openWeight:true, score:{"SWE-bench":70.2,GPQA:87.1,"LiveBench Coding":77.8} },
  { id:"qwen3-max", name:"Qwen3 Max", provider:"Alibaba", release:"2026-08-11", context:"1M", reasoning:4, vision:4, tools:4, eval:89.4, benchmark:"MMLU-Pro", source:"Qwen Eval", variants:["standard","thinking"], endpoint:"Alibaba Cloud", openWeight:false, score:{"SWE-bench":71.6,GPQA:86.9,"LiveBench Coding":78.3} },
];
const DEMO_BENCHMARKS = [
  { id:"swe-bench", name:"SWE-bench Verified", category:"代码", capability:"Repo-level Coding", version:"2026.08", metric:"Resolved %", risk:"中", results:6, updated:"09-20", description:"衡量模型在真实 GitHub 仓库中定位、修改并验证软件问题的能力。", method:"500 个经人工验证的软件工程任务，分数越高越好。" },
  { id:"gpqa", name:"GPQA Diamond", category:"推理", capability:"Scientific Reasoning", version:"Diamond", metric:"Accuracy", risk:"低", results:6, updated:"09-18", description:"面向博士级科学问题的高难度推理评测。", method:"198 道精选题目，采用准确率并记录推理设置。" },
  { id:"livebench", name:"LiveBench Coding", category:"代码", capability:"Code Generation", version:"2026-09", metric:"Score", risk:"低", results:6, updated:"09-17", description:"按月更新、减少训练污染影响的动态代码评测。", method:"使用当月新题集，保留版本与评测时间。" },
  { id:"mmlu-pro", name:"MMLU-Pro", category:"推理", capability:"Knowledge & Reasoning", version:"0.3", metric:"Accuracy", risk:"中", results:6, updated:"09-15", description:"覆盖多学科知识与复杂推理的选择题评测。", method:"十选一题型，按统一 prompt 与温度设置比较。" },
  { id:"mmmu", name:"MMMU", category:"多模态", capability:"Vision Reasoning", version:"1.1", metric:"Accuracy", risk:"中", results:4, updated:"09-09", description:"面向大学学科图像、图表与文档理解的多模态评测。", method:"图文混合输入，结果明确关联支持视觉的 Variant。" },
];

const PROVIDER_NAMES = { openai:"OpenAI", anthropic:"Anthropic", google:"Google", meta:"Meta", deepseek:"DeepSeek", alibaba:"Alibaba", xai:"xAI", mistral:"Mistral", zhipu:"Zhipu" };
const SCORE_LABELS = {
  artificial_analysis_intelligence_index:"AA Intelligence",
  artificial_analysis_coding_index:"AA Coding",
  artificial_analysis_agentic_index:"AA Agentic",
};
const COMPARE_BENCHMARKS = Object.values(SCORE_LABELS);

function compactTokens(value) {
  if (!value) return "—";
  if (value >= 1_000_000) return `${value / 1_000_000}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}K`;
  return String(value);
}

function stampDate(value) { return value ? String(value).slice(0, 10) : null; }
function stampDateTime(value) { return value ? String(value).slice(0, 16).replace("T", " ") : null; }

function mapApiModel(item) {
  const evaluations=item.evaluations||[], scores={};
  evaluations.forEach(e=>{ if(SCORE_LABELS[e.benchmark_slug]) scores[SCORE_LABELS[e.benchmark_slug]]=Number(e.score); });
  const headline=evaluations.find(e=>e.benchmark_slug==="artificial_analysis_intelligence_index")||evaluations[0];
  const variant=item.variant||{};
  return {
    id:item.slug, name:item.canonical_name, provider:PROVIDER_NAMES[item.provider]||item.provider,
    release:item.release_date||"—", context:compactTokens(variant.context_window),
    reasoning:variant.supports_reasoning?5:2, vision:variant.supports_image?4:1, tools:variant.supports_tool_calling?4:1,
    eval:headline?Number(headline.score):null, benchmark:headline?(SCORE_LABELS[headline.benchmark_slug]||headline.benchmark_name):"待评测",
    source:headline?.source||"Registry", variants:[variant.name||"standard"],
    endpoint:item.endpoint?.external_model_id||"暂无端点", openWeight:Boolean(item.open_weight), score:scores,
    snapshotId:headline?.source_snapshot_id, observedAt:headline?.observed_at, live:true,
  };
}

function mapApiBenchmark(item) {
  const categoryMap={coding:"代码",reasoning:"推理",agent:"智能体",composite:"综合",multimodal:"多模态",knowledge:"知识"};
  const version=item.versions?.[0], metric=version?.metrics?.[0];
  return { id:item.slug, name:item.name, category:categoryMap[item.category]||item.category, capability:item.capabilities?.map(x=>x.name).join(" / ")||item.category,
    version:version?.version||"—", metric:metric?.name||"—", risk:item.contamination_risk==="low"?"低":item.contamination_risk==="high"?"高":"中",
    results:"—", updated:"本次同步", description:item.description||"暂无说明", method:`${metric?.name||"Score"} · ${metric?.score_direction||"higher_better"}` };
}

function ModelMark({ model }) { const Icon=PROVIDER_ICONS[model.provider]||PiSparkle; return <span className={`provider-mark provider-${model.provider.toLowerCase()}`}><Icon/></span>; }
function Rating({ value, label }) { return <div className="rating" aria-label={`${label} ${value}/5`}><span className="rating-bars">{[1,2,3,4,5].map(n=><i key={n} className={n<=value?"filled":""}/>)}</span><small>{value>=5?"极强":value>=4?"强":value>=3?"中":"基础"}</small></div>; }
function Filter({ label, value, onChange, options }) { return <label className="filter"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}><option value="all">全部</option>{options.map(x=><option key={x} value={x}>{x}</option>)}</select><PiCaretDown/></label>; }

function PageHero({ eyebrow, title, description, aside }) {
  return <div className="page-hero"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{aside&&<aside>{aside}</aside>}</div>;
}

function Overview({ navigate, models, syncDateLabel }) {
  const ranked=[...models].filter(m=>m.eval!==null).sort((a,b)=>b.eval-a.eval);
  const liveUpdates=ranked.slice(0,4).map((model,index)=>({type:"真实评测",icon:PiChartLineUp,tone:["blue","violet","amber","green"][index],title:`${model.name} · ${model.benchmark} ${model.eval}`,detail:`${model.provider} · ${model.variants[0]} · ${model.endpoint}`,date:stampDate(model.observedAt)||syncDateLabel||"待同步",source:model.source}));
  const pulse=COMPARE_BENCHMARKS.map(label=>({label,model:models.filter(m=>Number.isFinite(m.score[label])).sort((a,b)=>b.score[label]-a.score[label])[0]})).filter(item=>item.model);
  return <section className="page overview-page">
    <PageHero eyebrow="LIVE DATA · ARTIFICIAL ANALYSIS" title="最新模型雷达" description="展示已同步、可追溯到原始 Snapshot 的真实评测数据；未匹配的外部模型进入人工解析队列。" aside={<><strong>本次真实数据同步</strong><span>{syncDateLabel?`${syncDateLabel} · 近三个月范围`:"尚未同步 · 近三个月范围"}</span></>}/>
    <div className="overview-grid">
      <article className="panel activity-panel"><header><div><p className="section-kicker">LATEST SYNC</p><h2>最新真实评测</h2></div><button className="text-button" onClick={()=>navigate("models")}>查看模型 <PiArrowRight/></button></header>
        <div className="activity-list">{liveUpdates.map(({type,icon:Icon,tone,title,detail,date,source})=><div className="activity-row" key={title}><span className={`activity-icon ${tone}`}><Icon/></span><div><small>{type}</small><strong>{title}</strong><p>{detail}</p></div><div className="activity-meta"><b>{date}</b><span>{source}</span></div></div>)}</div>
      </article>
      <aside className="panel watch-panel"><p className="section-kicker">WATCHLIST</p><h2>值得关注</h2><p className="panel-intro">按 AA Intelligence 当前分数排序。</p>{ranked.slice(0,4).map((m,index)=><div className="watch-row" key={m.id}><span>{index+1}</span><ModelMark model={m}/><div><strong>{m.name}</strong><small>{m.provider} · {m.context}</small></div><b>{m.eval}</b></div>)}<button className="primary wide" onClick={()=>navigate("models")}>选择模型进行对比 <PiArrowRight/></button></aside>
    </div>
    <article className="panel pulse-panel"><header><div><p className="section-kicker">BENCHMARK PULSE</p><h2>真实评测速览</h2></div><button className="text-button" onClick={()=>navigate("benchmarks")}>查看全部基准 <PiArrowRight/></button></header><div className="pulse-list">{pulse.map(({label,model})=><div key={label}><span>{label}</span><strong>{model.name}</strong><b className="positive">{model.score[label]}</b></div>)}</div></article>
  </section>;
}

function SelectionDock({ selected, toggle, navigate }) {
  const message=selected.length===0?"选择 2–5 个模型开始对比":selected.length===1?"已选 1 个，再选 1 个即可对比":`已选 ${selected.length} 个模型`;
  return <div className={`selection-dock ${selected.length?"has-selection":""}`} aria-live="polite"><div className="selection-summary"><strong>{message}</strong><span>比较时会明确 Variant 与 Endpoint</span></div><div className="selection-chips">{selected.map(m=><span className="selection-chip" key={m.id}><ModelMark model={m}/><span><b>{m.name}</b><small>{m.variants[0]} · {m.endpoint}</small></span><button onClick={()=>toggle(m.id)} aria-label={`移除 ${m.name}`}><PiX/></button></span>)}</div><button className="primary" disabled={selected.length<2} onClick={()=>navigate("compare")}>{selected.length<2?"继续选择":"开始对比"} <PiArrowRight/></button></div>;
}

function ModelCatalog({ models, query, setQuery, selected, selectedIds, toggle, provider, setProvider, capability, setCapability, openWeight, setOpenWeight, navigate, syncDateLabel, dataStatus }) {
  const providerOptions=[...new Set(models.map(m=>m.provider))];
  const filtered=useMemo(()=>models.filter(m=>`${m.name} ${m.provider}`.toLowerCase().includes(query.toLowerCase())&&(provider==="all"||m.provider===provider)&&(openWeight==="all"||(openWeight==="yes"?m.openWeight:!m.openWeight))&&(capability==="all"||m[capability]>=4)),[models,query,provider,capability,openWeight]);
  return <section className="catalog page"><PageHero eyebrow="MODEL INTELLIGENCE · 近 3 个月" title="模型图谱" description="收录经过验证的主流模型、变体与推理端点，快速筛选并进入可信对比。" aside={<><strong>独立 · 客观 · 可追溯</strong><span>连接模型、评测与真实应用</span></>}/>
    <div className="catalog-surface"><div className="filters"><label className="model-search"><PiMagnifyingGlass/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索模型名称、提供商或关键词…"/></label><Filter label="Provider" value={provider} onChange={setProvider} options={providerOptions}/><Filter label="能力" value={capability} onChange={setCapability} options={["reasoning","vision","tools"]}/><Filter label="Open Weight" value={openWeight} onChange={setOpenWeight} options={["yes","no"]}/></div>
      <SelectionDock selected={selected} toggle={toggle} navigate={navigate}/>
      {models.length===0&&<div className="empty" role="status">{dataStatus==="loading"?"正在加载真实模型数据…":"暂无已同步模型数据，请稍后重试。"}</div>}
      <div className="table-wrap"><table><thead><tr><th/><th>Model</th><th>Provider</th><th>Release</th><th>Context</th><th>Reasoning</th><th>Vision</th><th>Tool Use</th><th>Latest Eval</th><th>Status</th></tr></thead><tbody>{filtered.map(m=>{const checked=selectedIds.includes(m.id);return <tr key={m.id} className={checked?"selected":""}><td><button className={`checkbox ${checked?"checked":""}`} onClick={()=>toggle(m.id)} aria-label={`${checked?"取消选择":"选择"} ${m.name}`}>{checked&&<PiCheck/>}</button></td><td><div className="model-name"><strong>{m.name}</strong><span>{m.variants.length} variants</span><small>{m.variants.join(" · ")}</small></div></td><td><div className="provider"><ModelMark model={m}/><span>{m.provider}</span></div></td><td>{m.release}</td><td><b>{m.context}</b><small>tokens</small></td><td><Rating value={m.reasoning} label="Reasoning"/></td><td><Rating value={m.vision} label="Vision"/></td><td><Rating value={m.tools} label="Tool use"/></td><td><div className="eval"><b>{m.eval??"—"}</b><span>{m.benchmark}</span><small>{m.source}</small></div></td><td><div className="status"><i/>{m.live?"已同步":"演示"}<small>{m.endpoint}</small></div></td></tr>})}</tbody></table>{filtered.length===0&&<div className="empty">没有符合当前筛选条件的模型</div>}</div>
      <footer className="table-footer"><span>显示 {filtered.length} 个模型 · 近三个月跟踪范围</span><span><PiInfo/> 评测来源：Artificial Analysis · 本次同步 {syncDateLabel||"尚未同步"}</span></footer></div>
  </section>;
}

function CompareView({ selected, navigate, toggle, syncDateLabel }) {
  const benchmarks=COMPARE_BENCHMARKS;
  if(selected.length<2) return <section className="page compare-view"><PageHero eyebrow="MODEL COMPARE" title="模型对比" description="选择 2–5 个明确的 Variant 与 Endpoint，避免混合不同渠道的数据。"/><div className="panel compare-empty"><span className="empty-icon"><PiTrendUp/></span><h2>{selected.length===1?"再选 1 个模型即可开始":"还没有选择模型"}</h2><p>{selected.length===1?`${selected[0].name} 已加入对比。`:"从模型图谱中选择你真正关心的候选项。"}</p><button className="primary" onClick={()=>navigate("models")}>去选择模型 <PiArrowRight/></button></div></section>;
  return <section className="compare-view page"><button className="text-button" onClick={()=>navigate("models")}><PiArrowLeft/> 返回模型图谱</button><div className="compare-title"><div><p className="eyebrow">最近 3 个月 · 数据截至 {syncDateLabel||"待同步"}</p><h1>模型对比</h1><p>对比明确的模型变体与服务端点，不混合不同渠道数据。</p></div><span className="freshness"><PiClockCounterClockwise/> 90 天窗口</span></div><div className="compare-grid" style={{"--columns":selected.length}}><div className="compare-label blank"/>{selected.map(m=><article className="compare-head" key={m.id}><button onClick={()=>toggle(m.id)} aria-label={`移除 ${m.name}`}><PiX/></button><ModelMark model={m}/><strong>{m.name}</strong><span>{m.variants[0]} · {m.endpoint}</span></article>)}<div className="compare-label">上下文窗口</div>{selected.map(m=><div className="compare-cell" key={`${m.id}-context`}><b>{m.context}</b></div>)}{benchmarks.map(b=><div className="compare-row" key={b}><div className="compare-label">{b}<small>权威评测集</small></div>{selected.map(m=>{const best=Math.max(...selected.map(x=>x.score[b]));return <div className={`compare-cell ${m.score[b]===best?"best":""}`} key={`${m.id}-${b}`}><b>{m.score[b]}</b><span>{m.score[b]===best?"当前最佳":""}</span></div>})}</div>)}<div className="compare-label">来源可信度</div>{selected.map(m=><div className="compare-cell evidence" key={`${m.id}-source`}><PiCheck/><div><b>高</b><span>{m.source} · {stampDate(m.observedAt)||syncDateLabel||"待同步"}</span></div></div>)}</div></section>;
}

function Benchmarks({ benchmarks }) {
  const [search,setSearch]=useState(""), [category,setCategory]=useState("all"), [active,setActive]=useState("swe-bench");
  const categories=[...new Set(benchmarks.map(b=>b.category))];
  const rows=benchmarks.filter(b=>(b.name+b.capability).toLowerCase().includes(search.toLowerCase())&&(category==="all"||b.category===category));
  const detail=benchmarks.find(b=>b.id===active)||benchmarks[0];
  return <section className="page benchmark-page"><PageHero eyebrow="BENCHMARK REGISTRY · 近 3 个月" title="基准目录" description="理解每个分数测量什么、使用哪个版本，以及结果是否存在污染风险。" aside={<><strong>{benchmarks.length} 个核心基准</strong><span>版本、Metric 与来源可追溯</span></>}/>
    <div className="panel benchmark-panel"><div className="benchmark-tools"><label className="model-search"><PiMagnifyingGlass/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索基准或能力…"/></label><Filter label="分类" value={category} onChange={setCategory} options={["代码","推理","多模态"]}/></div><div className="benchmark-list"><div className="benchmark-list-head"><span>Benchmark</span><span>能力</span><span>版本 / Metric</span><span>污染风险</span><span>最近更新</span><span/></div>{rows.map(b=><button className={`benchmark-row ${active===b.id?"active":""}`} key={b.id} onClick={()=>setActive(b.id)}><span><b>{b.name}</b><small>{b.category} · {b.results} 个模型结果</small></span><span>{b.capability}</span><span><b>{b.version}</b><small>{b.metric}</small></span><span className={`risk risk-${b.risk}`}>{b.risk}</span><span>{b.updated}</span><PiCaretRight/></button>)}</div></div>
    {detail&&<article className="panel benchmark-detail"><div><p className="section-kicker">BENCHMARK DETAIL</p><h2>{detail.name}</h2><p>{detail.description}</p></div><dl><div><dt>评测方法</dt><dd>{detail.method}</dd></div><div><dt>当前版本</dt><dd>{detail.version}</dd></div><div><dt>Metric</dt><dd>{detail.metric}</dd></div><div><dt>污染风险</dt><dd><PiShieldWarning/> {detail.risk}</dd></div></dl></article>}
  </section>;
}

export function App() {
  const pathToView=()=>Object.entries(ROUTES).find(([,path])=>path===location.pathname)?.[0]||"overview";
  const [view,setView]=useState(pathToView), [query,setQuery]=useState(""), [provider,setProvider]=useState("all"), [capability,setCapability]=useState("all"), [openWeight,setOpenWeight]=useState("all"), [selectedIds,setSelectedIds]=useState([]);
  const [models,setModels]=useState([]), [benchmarks,setBenchmarks]=useState([]), [dataStatus,setDataStatus]=useState("loading"), [syncInfo,setSyncInfo]=useState(null);
  const selected=models.filter(m=>selectedIds.includes(m.id));
  const syncDateLabel=stampDate(syncInfo?.latest_snapshot_time);
  const syncTimeLabel=stampDateTime(syncInfo?.latest_snapshot_time);
  const navigate=next=>{ setView(next); if(location.pathname!==ROUTES[next]) history.pushState({},"",ROUTES[next]); window.scrollTo({top:0,behavior:"instant"}); };
  useEffect(()=>{ const onPop=()=>setView(pathToView()); addEventListener("popstate",onPop); return()=>removeEventListener("popstate",onPop); },[]);
  useEffect(()=>{
    let cancelled=false, hasLiveModels=false, benchmarksDone=false;
    async function loadModels(){
      try {
        const response=await fetch("/api/v1/models?status=preview&limit=100&include_summary=true");
        if(!response.ok) throw new Error("Model API unavailable");
        const body=await response.json();
        if(!cancelled){ hasLiveModels=true; setModels(body.items.map(mapApiModel)); setDataStatus("live"); }
      } catch {
        if(!cancelled&&!hasLiveModels){ setModels(DEMO_MODELS); setDataStatus("demo"); }
      }
    }
    async function loadBenchmarks(){
      if(benchmarksDone) return; // benchmark registry is near-static: fetch until success, then stop
      try {
        const benchmarkResponse=await fetch("/api/v1/benchmarks?limit=100");
        if(!benchmarkResponse.ok) throw new Error("Benchmark API unavailable");
        const benchmarkBody=await benchmarkResponse.json();
        const benchmarkDetails=await Promise.all(benchmarkBody.items.map(async item=>{
          const response=await fetch(`/api/v1/benchmarks/${item.slug}`);
          return response.ok?response.json():item;
        }));
        if(!cancelled){ benchmarksDone=true; setBenchmarks(benchmarkDetails.map(mapApiBenchmark)); }
      } catch {
        if(!cancelled) setBenchmarks(DEMO_BENCHMARKS);
      }
    }
    async function loadStatus(){
      try {
        const response=await fetch("/api/v1/status");
        if(response.ok&&!cancelled) setSyncInfo(await response.json());
      } catch { /* status is cosmetic: fail silently */ }
    }
    const loadData=()=>{ loadModels(); loadBenchmarks(); loadStatus(); };
    loadData();
    const retryTimer=setInterval(loadData,300000);
    return()=>{cancelled=true; clearInterval(retryTimer);};
  },[]);
  const toggle=id=>setSelectedIds(now=>now.includes(id)?now.filter(x=>x!==id):now.length<5?[...now,id]:now);
  const globalSearch=e=>{ setQuery(e.target.value); if(view!=="models") navigate("models"); };
  const nav=[{id:"overview",label:"概览"},{id:"models",label:"模型"},{id:"compare",label:"对比"},{id:"benchmarks",label:"基准"}];
  return <div className="app-shell"><header className="topbar"><button className="brand" onClick={()=>navigate("overview")}><PiCrosshair/><strong>Model Radar</strong><span>更清晰的模型世界</span></button><nav aria-label="主导航">{nav.map(item=><button key={item.id} className={view===item.id?"active":""} aria-current={view===item.id?"page":undefined} onClick={()=>navigate(item.id)}>{item.label}</button>)}</nav><label className="global-search"><PiMagnifyingGlass/><input value={query} onChange={globalSearch} placeholder="搜索模型、提供商或能力"/></label><span className={`demo-badge ${dataStatus==="live"?"live-data":""}`}>{dataStatus==="live"?"真实数据":dataStatus==="loading"?"同步中":"演示数据"}</span><span className="as-of">同步于 {syncTimeLabel||"尚未同步"}</span></header><main>
    {view==="overview"&&<Overview navigate={navigate} models={models} syncDateLabel={syncDateLabel}/>}
    {view==="models"&&<ModelCatalog models={models} query={query} setQuery={setQuery} selected={selected} selectedIds={selectedIds} toggle={toggle} provider={provider} setProvider={setProvider} capability={capability} setCapability={setCapability} openWeight={openWeight} setOpenWeight={setOpenWeight} navigate={navigate} syncDateLabel={syncDateLabel} dataStatus={dataStatus}/>}
    {view==="compare"&&<CompareView selected={selected} navigate={navigate} toggle={toggle} syncDateLabel={syncDateLabel}/>}
    {view==="benchmarks"&&<Benchmarks benchmarks={benchmarks}/>}
  </main></div>;
}
