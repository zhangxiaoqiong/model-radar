import { useState } from "react";
import { PiCaretRight, PiMagnifyingGlass, PiShieldWarning } from "react-icons/pi";
import { Filter, PageHero } from "../components/shared.jsx";

export function Benchmarks({ benchmarks }) {
  const [search,setSearch]=useState(""), [category,setCategory]=useState("all"), [active,setActive]=useState("swe-bench");
  const categories=[...new Set(benchmarks.map(b=>b.category))];
  const rows=benchmarks.filter(b=>(b.name+b.capability).toLowerCase().includes(search.toLowerCase())&&(category==="all"||b.category===category));
  const detail=benchmarks.find(b=>b.id===active)||benchmarks[0];
  return <section className="page benchmark-page"><PageHero eyebrow="BENCHMARK REGISTRY · 近 3 个月" title="基准目录" description="理解每个分数测量什么、使用哪个版本，以及结果是否存在污染风险。" aside={<><strong>{benchmarks.length} 个核心基准</strong><span>版本、Metric 与来源可追溯</span></>}/>
    <div className="panel benchmark-panel"><div className="benchmark-tools"><label className="model-search"><PiMagnifyingGlass/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索基准或能力…"/></label><Filter label="分类" value={category} onChange={setCategory} options={["代码","推理","多模态"]}/></div><div className="benchmark-list"><div className="benchmark-list-head"><span>Benchmark</span><span>能力</span><span>版本 / Metric</span><span>污染风险</span><span>最近更新</span><span/></div>{rows.map(b=><button className={`benchmark-row ${active===b.id?"active":""}`} key={b.id} onClick={()=>setActive(b.id)}><span><b>{b.name}</b><small>{b.category} · {b.results} 个模型结果</small></span><span>{b.capability}</span><span><b>{b.version}</b><small>{b.metric}</small></span><span className={`risk risk-${b.risk}`}>{b.risk}</span><span>{b.updated}</span><PiCaretRight/></button>)}</div></div>
    {detail&&<article className="panel benchmark-detail"><div><p className="section-kicker">BENCHMARK DETAIL</p><h2>{detail.name}</h2><p>{detail.description}</p></div><dl><div><dt>评测方法</dt><dd>{detail.method}</dd></div><div><dt>当前版本</dt><dd>{detail.version}</dd></div><div><dt>Metric</dt><dd>{detail.metric}</dd></div><div><dt>污染风险</dt><dd><PiShieldWarning/> {detail.risk}</dd></div></dl></article>}
  </section>;
}
