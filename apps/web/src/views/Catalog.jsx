import { Fragment, useMemo, useState } from "react";
import { PiCaretDown, PiCheck, PiInfo, PiMagnifyingGlass } from "react-icons/pi";
import { Filter, ModelMark, PageHero, SelectionDock } from "../components/shared.jsx";

const CATALOG_PAGE_SIZE = 20;
const CAPABILITY_OPTIONS = ["文本", "图片", "音频", "视频", "推理", "工具调用"];
const SORT_OPTIONS = [
  ["release", "最新发布"], ["intelligence", "智能评估最高"],
  ["coding", "编程评估最高"], ["agentic", "智能体评估最高"],
  ["price", "输入价格最低"], ["context", "上下文最大"], ["speed", "输出速度最快"],
];
function priceLabel(value) { return value == null ? "—" : `$${value.toFixed(value < 1 ? 3 : 2)}`; }
function rankHighlight(model, models) {
  const topQuartile = (value, accessor, ascending = false) => {
    if (value == null) return false;
    const values = models.map(accessor).filter(Number.isFinite).sort((a,b)=>ascending?a-b:b-a);
    return values.length >= 8 && value >= 0 && (ascending ? value <= values[Math.ceil(values.length / 4)-1] : value >= values[Math.ceil(values.length / 4)-1]);
  };
  if (topQuartile(model.score["AA Intelligence"], m=>m.score["AA Intelligence"])) return "智能评估前 25%";
  if (topQuartile(model.score["AA Coding"], m=>m.score["AA Coding"])) return "编程评估前 25%";
  if (topQuartile(model.inputPrice, m=>m.inputPrice, true)) return "输入价格较低";
  if (topQuartile(model.speed, m=>m.speed)) return "输出速度较快";
  return null;
}

export function Catalog({ models, query, setQuery, selected, selectedIds, toggle, provider, setProvider, capability, setCapability, navigate, syncDateLabel, dataStatus }) {
  const [sort, setSort] = useState("release"), [page, setPage] = useState(1), [expanded, setExpanded] = useState(null);
  const providers = useMemo(()=>[...new Set(models.map(m=>m.provider))].sort(), [models]);
  const filtered = useMemo(()=>models.filter(m=>
    `${m.name} ${m.provider} ${m.description||""}`.toLowerCase().includes(query.toLowerCase()) &&
    (provider === "all" || m.provider === provider) &&
    (capability === "all" || m.capabilities.includes(capability))
  ).sort((a,b)=>{
    if (sort === "release") return b.release.localeCompare(a.release);
    const field = sort === "intelligence" ? m=>m.score["AA Intelligence"] :
      sort === "coding" ? m=>m.score["AA Coding"] :
      sort === "agentic" ? m=>m.score["AA Agentic"] :
      sort === "price" ? m=>m.inputPrice :
      sort === "context" ? m=>m.contextTokens : m=>m.speed;
    const av=field(a), bv=field(b);
    if (av == null) return bv == null ? b.release.localeCompare(a.release) : 1;
    if (bv == null) return -1;
    return (sort === "price" ? av-bv : bv-av) || b.release.localeCompare(a.release);
  }), [models, query, provider, capability, sort]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / CATALOG_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visible = filtered.slice((currentPage-1)*CATALOG_PAGE_SIZE, currentPage*CATALOG_PAGE_SIZE);
  const updateQuery = value => { setQuery(value); setPage(1); };
  const updateProvider = value => { setProvider(value); setPage(1); };
  const updateCapability = value => { setCapability(value); setPage(1); };
  return <section className="catalog page"><PageHero eyebrow="MODEL INTELLIGENCE · 近 3 个月" title="模型图谱" description="近期模型来自 Artificial Analysis；能力与上下文由 OpenRouter 严格匹配补充。价格与评估均保留来源，缺失数据不推断。" aside={<><strong>{models.length} 个近期模型</strong><span>按评估、价格或上下文排序</span></>}/>
    <div className="catalog-surface"><div className="filters catalog-filters"><label className="model-search"><PiMagnifyingGlass/><input value={query} onChange={e=>updateQuery(e.target.value)} placeholder="搜索模型、提供商或特点…"/></label><Filter label="提供商" value={provider} onChange={updateProvider} options={providers}/><Filter label="能力" value={capability} onChange={updateCapability} options={CAPABILITY_OPTIONS}/><label className="filter"><span>排序</span><select aria-label="排序" value={sort} onChange={e=>{setSort(e.target.value);setPage(1);}}>{SORT_OPTIONS.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select><PiCaretDown/></label></div>
    <SelectionDock selected={selected} toggle={toggle} navigate={navigate}/>
    {models.length===0&&<div className="empty" role="status">{dataStatus==="loading"?"正在加载真实模型数据…":dataStatus==="error"?"数据源连接失败，稍后自动重试。":"最近 90 天暂无已发现的模型。"}</div>}
    <div className="table-wrap"><table className="catalog-table"><thead><tr><th/><th>模型 / 能力</th><th>提供商</th><th>发布日期</th><th>上下文</th><th>价格 / 百万 tokens</th><th>AA 评估</th><th>数据亮点</th><th>详情</th></tr></thead><tbody>{visible.map(m=>{const checked=selectedIds.includes(m.id), highlight=rankHighlight(m,models), isOpen=expanded===m.id;return <Fragment key={m.id}><tr className={checked?"selected":""}><td><button className={`checkbox ${checked?"checked":""}`} onClick={()=>toggle(m.id)} aria-label={`${checked?"取消选择":"选择"} ${m.name}`}>{checked&&<PiCheck/>}</button></td><td><div className="catalog-model"><strong>{m.name}</strong><div className="capability-tags">{m.capabilities.length?m.capabilities.map(tag=><span key={tag}>{tag}</span>):<small>能力待补充</small>}</div></div></td><td><div className="provider"><ModelMark model={m}/><span>{m.provider}</span></div></td><td>{m.release}</td><td><b>{m.context}</b></td><td><div className="catalog-price"><b>{priceLabel(m.inputPrice)} / {priceLabel(m.outputPrice)}</b><small>输入 / 输出 · AA 参考价</small></div></td><td><div className="catalog-scores"><b>{m.score["AA Intelligence"] ?? "—"}</b><small>智能 · 编程 {m.score["AA Coding"] ?? "—"} · 智能体 {m.score["AA Agentic"] ?? "—"}</small></div></td><td>{highlight?<span className="highlight-chip">{highlight}</span>:<span className="muted">—</span>}</td><td><button className="detail-button" onClick={()=>setExpanded(isOpen?null:m.id)} aria-expanded={isOpen} aria-label={`${isOpen?"收起":"查看"} ${m.name} 详情`}>{isOpen?"收起":"详情"} <PiCaretDown/></button></td></tr>{isOpen&&<tr className="catalog-detail-row"><td colSpan="9"><div className="catalog-detail"><p>{m.description||"暂无来源简介。"}</p><dl><div><dt>能力 / 上下文</dt><dd>{m.capabilitySource||"待补充"}</dd></div><div><dt>价格、性能与评估</dt><dd>Artificial Analysis · 输入 {priceLabel(m.inputPrice)} / 输出 {priceLabel(m.outputPrice)} · {m.speed==null?"速度待补充":`${Math.round(m.speed)} tokens/s`}</dd></div><div><dt>评估得分</dt><dd>智能 {m.score["AA Intelligence"]??"—"} · 编程 {m.score["AA Coding"]??"—"} · 智能体 {m.score["AA Agentic"]??"—"}</dd></div></dl>{m.description&&<small>简介来源：OpenRouter；亮点仅代表近三个月模型的数据相对位置。</small>}</div></td></tr>}</Fragment>})}</tbody></table>{models.length>0&&filtered.length===0&&<div className="empty">没有符合当前筛选条件的模型</div>}</div>
    <footer className="table-footer catalog-footer"><span>显示 {filtered.length?`${(currentPage-1)*CATALOG_PAGE_SIZE+1}–${Math.min(currentPage*CATALOG_PAGE_SIZE,filtered.length)}`:"0"} / {filtered.length} 个模型 · 近三个月</span><div className="catalog-pagination"><button disabled={currentPage===1} onClick={()=>setPage(currentPage-1)}>上一页</button><span>第 {currentPage} / {pageCount} 页</span><button disabled={currentPage===pageCount} onClick={()=>setPage(currentPage+1)}>下一页</button></div><span><PiInfo/> <a href="https://artificialanalysis.ai/data-api/docs" target="_blank" rel="noreferrer">AA</a> · <a href="https://openrouter.ai/docs/api/api-reference/models/get-models" target="_blank" rel="noreferrer">OpenRouter</a> · 同步 {syncDateLabel||"待同步"}</span></footer></div>
  </section>;
}
