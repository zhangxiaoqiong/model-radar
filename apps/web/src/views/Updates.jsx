import { useMemo, useState } from "react";
import { PiArrowRight, PiCalendarBlank, PiCheck, PiSparkle } from "react-icons/pi";
import { ModelMark, PageHero } from "../components/shared.jsx";

const WINDOWS = [["30","近 30 天"],["60","近 60 天"],["90","近 90 天"]];

export function Updates({ models, navigate, selectedIds, toggle }) {
  const [windowDays,setWindowDays]=useState("30"), [vendor,setVendor]=useState("all");
  const vendors=useMemo(()=>[...new Set(models.map(model=>model.provider))].sort(),[models]);
  const latestDate=useMemo(()=>models.map(model=>model.release).filter(value=>value&&value!=="—").sort().at(-1),[models]);
  const cutoff=useMemo(()=>{
    if(!latestDate)return "";
    const day=new Date(latestDate+"T00:00:00");day.setDate(day.getDate()-Number(windowDays)+1);
    return day.toISOString().slice(0,10);
  },[latestDate,windowDays]);
  const rows=useMemo(()=>models.filter(model=>model.release>=cutoff&&(vendor==="all"||model.provider===vendor))
    .sort((a,b)=>b.release.localeCompare(a.release)||a.name.localeCompare(b.name)),[models,cutoff,vendor]);
  const visibleRows=rows.slice(0,30);
  const groups=useMemo(()=>visibleRows.reduce((map,model)=>{
    const month=model.release.slice(0,7);if(!map.has(month))map.set(month,[]);map.get(month).push(model);return map;
  },new Map()),[rows]);
  return <section className="page updates-page">
    <PageHero eyebrow="RELEASE INTELLIGENCE" title="最新动态" description="当前展示近期模型发布记录；调价、开源和状态变化尚无独立事件数据，暂不混入发布时间线。" aside={<><strong>{rows.length} 条发布记录</strong><span>{cutoff || "—"} 至 {latestDate || "—"}</span></>}/>
    <div className="updates-toolbar panel"><div className="updates-window">{WINDOWS.map(([value,label])=><button key={value} className={windowDays===value?"active":""} onClick={()=>setWindowDays(value)}>{label}</button>)}</div><label><span>厂家</span><select value={vendor} onChange={event=>setVendor(event.target.value)}><option value="all">全部厂家</option>{vendors.map(item=><option key={item}>{item}</option>)}</select></label></div>
    <div className="updates-stream">{[...groups].map(([month,items])=><section className="updates-month" key={month}><div className="updates-month-label"><PiCalendarBlank/><b>{month}</b><span>{items.length} 项</span></div><div className="updates-list panel">{items.map(model=>{const checked=selectedIds.includes(model.id);return <article className="update-row" key={model.id}><button className={"checkbox "+(checked?"checked":"")} onClick={()=>toggle(model.id)} aria-label={(checked?"取消选择 ":"选择 ")+model.name}>{checked&&<PiCheck/>}</button><ModelMark model={model}/><div className="update-copy"><span>{model.release} · {model.provider}</span><strong>{model.name}</strong><small>{model.capabilities.length?model.capabilities.join(" · "):"能力信息待补充"} · 上下文 {model.context}</small></div><div className="update-metrics"><span><PiSparkle/>智能 {model.score["AA Intelligence"]??"—"}</span><span>输入 {"$"}{model.inputPrice??"—"} / M</span><span>{model.speed==null?"速度待补充":Math.round(model.speed)+" tok/s"}</span></div><button className="atlas-link" onClick={()=>navigate("models")}>模型库 <PiArrowRight/></button></article>})}</div></section>)}</div>
    {!rows.length&&<div className="panel empty">当前范围没有模型动态</div>}
    {rows.length>visibleRows.length&&<p className="updates-limit-note">当前展示最近 {visibleRows.length} 条，共 {rows.length} 条；可通过厂家或日期范围缩小结果。</p>}
  </section>;
}
