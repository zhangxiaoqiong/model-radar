import { useState } from "react";
import { PiCaretRight, PiMagnifyingGlass, PiShieldWarning } from "react-icons/pi";
import { Filter, PageHero } from "../components/shared.jsx";

export function Benchmarks({ benchmarks }) {
  const [search,setSearch]=useState(""), [category,setCategory]=useState("all"), [active,setActive]=useState("swe-bench");
  const categories=[...new Set(benchmarks.map(b=>b.category))];
  const rows=benchmarks.filter(b=>(b.name+b.capability).toLowerCase().includes(search.toLowerCase())&&(category==="all"||b.category===category));
  const detail=benchmarks.find(b=>b.id===active)||benchmarks[0];
  return <section className="page benchmark-page"><PageHero eyebrow="PROFESSIONAL EVALUATION SOURCES" title="专业评测平台" description="先理解评测平台的数据来源和方法，再查看平台下的评测项目与模型成绩。" aside={<><strong>1 个已接入平台</strong><span>{benchmarks.length} 项可追溯评测</span></>}/>
    <article className="evaluation-platform-card panel"><div className="platform-monogram">AA</div><div><span>已接入 · 独立评测平台</span><h2>Artificial Analysis</h2><p>提供模型智能、编程、智能体能力，以及价格与运行性能数据。当前看板使用同一平台口径进行横向比较。</p></div><dl><div><dt>更新方式</dt><dd>Data API</dd></div><div><dt>已同步指标</dt><dd>{benchmarks.length}</dd></div><div><dt>适用场景</dt><dd>近期模型横向比较</dd></div></dl></article>
    <div className="platform-section-title"><p className="section-kicker">PLATFORM METRICS</p><h2>Artificial Analysis 评测项目</h2></div>
    <div className="panel benchmark-panel"><div className="benchmark-tools"><label className="model-search"><PiMagnifyingGlass/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索基准或能力…"/></label><Filter label="分类" value={category} onChange={setCategory} options={categories}/></div><div className="benchmark-list"><div className="benchmark-list-head"><span>Benchmark</span><span>能力</span><span>版本 / Metric</span><span>污染风险</span><span>最近更新</span><span/></div>{rows.map(b=><button className={`benchmark-row ${active===b.id?"active":""}`} key={b.id} onClick={()=>setActive(b.id)}><span><b>{b.name}</b><small>{b.category} · {b.results} 个模型结果</small></span><span>{b.capability}</span><span><b>{b.version}</b><small>{b.metric}</small></span><span className={`risk risk-${b.risk}`}>{b.risk}</span><span>{b.updated}</span><PiCaretRight/></button>)}</div></div>
    {detail&&<article className="panel benchmark-detail"><div><p className="section-kicker">BENCHMARK DETAIL</p><h2>{detail.name}</h2><p>{detail.description}</p></div><dl><div><dt>评测方法</dt><dd>{detail.method}</dd></div><div><dt>当前版本</dt><dd>{detail.version}</dd></div><div><dt>Metric</dt><dd>{detail.metric}</dd></div><div><dt>污染风险</dt><dd><PiShieldWarning/> {detail.risk}</dd></div></dl></article>}
  </section>;
}
