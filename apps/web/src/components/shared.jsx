import {
  PiArrowRight, PiCaretDown, PiCheck, PiCrosshair, PiSparkle, PiX,
} from "react-icons/pi";
import { SiAlibabacloud, SiAnthropic, SiDeepseek, SiGoogle, SiMeta } from "react-icons/si";

export const PROVIDER_ICONS = { OpenAI: PiSparkle, Anthropic: SiAnthropic, Google: SiGoogle, Meta: SiMeta, DeepSeek: SiDeepseek, Alibaba: SiAlibabacloud };

export function ModelMark({ model }) { const Icon=PROVIDER_ICONS[model.provider]||PiSparkle; return <span className={`provider-mark provider-${model.provider.toLowerCase()}`}><Icon/></span>; }

export function Filter({ label, value, onChange, options }) { return <label className="filter"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}><option value="all">全部</option>{options.map(x=><option key={x} value={x}>{x}</option>)}</select><PiCaretDown/></label>; }

export function PageHero({ eyebrow, title, description, aside }) {
  return <div className="page-hero"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{aside&&<aside>{aside}</aside>}</div>;
}

export function SelectionDock({ selected, toggle, navigate }) {
  const message=selected.length===0?"选择 2–5 个模型开始对比":selected.length===1?"已选 1 个，再选 1 个即可对比":`已选 ${selected.length} 个模型`;
  return <div className={`selection-dock ${selected.length?"has-selection":""}`} aria-live="polite"><div className="selection-summary"><strong>{message}</strong><span>比较时会明确 Variant 与 Endpoint</span></div><div className="selection-chips">{selected.map(m=><span className="selection-chip" key={m.id}><ModelMark model={m}/><span><b>{m.name}</b><small>{m.variants[0]} · {m.endpoint}</small></span><button onClick={()=>toggle(m.id)} aria-label={`移除 ${m.name}`}><PiX/></button></span>)}</div><button className="primary" disabled={selected.length<2} onClick={()=>navigate("compare")}>{selected.length<2?"继续选择":"开始对比"} <PiArrowRight/></button></div>;
}

export { PiCrosshair, PiCheck };
