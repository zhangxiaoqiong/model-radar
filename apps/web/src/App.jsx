import { useEffect, useState } from "react";
import { PiCrosshair, PiMagnifyingGlass } from "react-icons/pi";
import { loadBenchmarks, loadModels, loadStatus, stampDate, stampDateTime } from "./lib/api.js";
import { Overview } from "./views/Overview.jsx";
import { Catalog } from "./views/Catalog.jsx";
import { Compare } from "./views/Compare.jsx";
import { Benchmarks } from "./views/Benchmarks.jsx";
import { Updates } from "./views/Updates.jsx";

const ROUTES = { dashboard: "/", models: "/models", compare: "/compare", updates: "/updates", evaluations: "/evaluations" };

export function App() {
  const pathToView=()=>Object.entries(ROUTES).find(([,path])=>path===location.pathname)?.[0]||"dashboard";
  const [view,setView]=useState(pathToView), [query,setQuery]=useState(""), [provider,setProvider]=useState("all"), [capability,setCapability]=useState("all"), [selectedIds,setSelectedIds]=useState([]);
  const [models,setModels]=useState([]), [benchmarks,setBenchmarks]=useState([]), [dataStatus,setDataStatus]=useState("loading"), [syncInfo,setSyncInfo]=useState(null);
  const selected=models.filter(m=>selectedIds.includes(m.id));
  const syncDateLabel=stampDate(syncInfo?.latest_snapshot_time);
  const syncTimeLabel=stampDateTime(syncInfo?.latest_snapshot_time);
  const navigate=next=>{ setView(next); if(location.pathname!==ROUTES[next]) history.pushState({},"",ROUTES[next]); window.scrollTo({top:0,behavior:"instant"}); };
  useEffect(()=>{ const onPop=()=>setView(pathToView()); addEventListener("popstate",onPop); return()=>removeEventListener("popstate",onPop); },[]);
  useEffect(()=>{
    let cancelled=false, hasLiveModels=false, benchmarksDone=false;
    async function refreshModels(){
      try {
        const recent=await loadModels();
        if(!cancelled){ hasLiveModels=true; setModels(recent); setDataStatus("live"); }
      } catch {
        if(!cancelled&&!hasLiveModels){ setModels([]); setDataStatus("error"); }
      }
    }
    async function refreshBenchmarks(){
      if(benchmarksDone) return; // benchmark registry is near-static: fetch until success, then stop
      try {
        const mapped=await loadBenchmarks();
        if(!cancelled){ benchmarksDone=true; setBenchmarks(mapped); }
      } catch {
        if(!cancelled) setBenchmarks([]);
      }
    }
    async function refreshStatus(){
      try {
        const status=await loadStatus();
        if(!cancelled) setSyncInfo(status);
      } catch { /* status is cosmetic: fail silently */ }
    }
    const loadData=()=>{ refreshModels(); refreshBenchmarks(); refreshStatus(); };
    loadData();
    const retryTimer=setInterval(loadData,300000);
    return()=>{cancelled=true; clearInterval(retryTimer);};
  },[]);
  const toggle=id=>setSelectedIds(now=>now.includes(id)?now.filter(x=>x!==id):now.length<5?[...now,id]:now);
  const globalSearch=e=>{ setQuery(e.target.value); if(view!=="models") navigate("models"); };
  const nav=[{id:"dashboard",label:"看板"},{id:"models",label:"模型库"},{id:"compare",label:"对比"},{id:"updates",label:"最新动态"},{id:"evaluations",label:"评测平台"}];
  return <div className={`app-shell ${view==="dashboard"?"theme-dark":""}`}><header className="topbar"><button className="brand" onClick={()=>navigate("dashboard")}><PiCrosshair/><strong>Model Radar</strong><span>更清晰的模型世界</span></button><nav aria-label="主导航">{nav.map(item=><button key={item.id} className={view===item.id?"active":""} aria-current={view===item.id?"page":undefined} onClick={()=>navigate(item.id)}>{item.label}</button>)}</nav><label className="global-search"><PiMagnifyingGlass/><input value={query} onChange={globalSearch} placeholder="搜索模型、提供商或能力"/></label><span className={`demo-badge ${dataStatus==="live"?"live-data":""}`}>{dataStatus==="live"?"来源数据":dataStatus==="loading"?"加载中":"连接失败"}</span><span className="as-of">同步于 {syncTimeLabel||"尚未同步"}</span></header><main>
    {view==="dashboard"&&<Overview navigate={navigate} models={models} selectedIds={selectedIds} toggle={toggle} syncDateLabel={syncDateLabel} dataStatus={dataStatus} status={syncInfo}/>}
    {view==="models"&&<Catalog models={models} query={query} setQuery={setQuery} selected={selected} selectedIds={selectedIds} toggle={toggle} provider={provider} setProvider={setProvider} capability={capability} setCapability={setCapability} navigate={navigate} syncDateLabel={syncDateLabel} dataStatus={dataStatus}/>}
    {view==="compare"&&<Compare selected={selected} navigate={navigate} toggle={toggle} syncDateLabel={syncDateLabel}/>}
    {view==="updates"&&<Updates models={models} navigate={navigate} selectedIds={selectedIds} toggle={toggle}/>}
    {view==="evaluations"&&<Benchmarks benchmarks={benchmarks}/>}
  </main></div>;
}
