import {
  CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import { providerColor } from "../lib/api.js";

function QuadTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const point=payload[0].payload;
  return <div className="quad-tooltip">
    <strong>{point.name}</strong>
    <span>{point.provider} · 发布 {point.release}</span>
    <span>输入 ${point.x} / 百万 tokens · 智能 {point.y}</span>
  </div>;
}

export function QuadrantChart({ quadrant, toggle, selectedIds, loading }) {
  const { points, medianX, medianY, excluded }=quadrant;
  if (loading) return <div className="quadrant-wrap"><div className="skeleton-block" aria-label="象限图加载中"/></div>;
  if (points.length<3) return <div className="quadrant-fallback">价格与评估数据不足，同步后展示象限视图。</div>;
  const xs=points.map(p=>p.x), ys=points.map(p=>p.y);
  const xMin=Math.min(...xs)*0.7, xMax=Math.max(...xs)*1.3;
  const yMin=Math.min(...ys)-3, yMax=Math.max(...ys)+3;
  const zMax=Math.max(...points.map(p=>p.z), 1);
  // 「便宜且聪明」象限里智能最高者，作为门户的默认答案标注出来
  const champion=points
    .filter(p=>p.x<=medianX && p.y>=medianY)
    .sort((a,b)=>b.y-a.y)[0];
  const flagged=points.map(p=>({ ...p, isChampion: !!champion && p.id===champion.id }));
  const renderBubble=props=>{
    const { cx, cy, payload }=props;
    const color=providerColor(payload.provider);
    const r=4+9*Math.sqrt((payload.z||0)/zMax);
    const isSelected=selectedIds.includes(payload.id);
    return <g key={payload.id} className="quad-bubble">
      <circle className="halo" cx={cx} cy={cy} r={r*2.2} fill={color} opacity={0.10}/>
      <circle className="body" cx={cx} cy={cy} r={r} fill={color} opacity={0.92}
        stroke={isSelected?"#17233a":"#ffffff"} strokeWidth={isSelected?2:1}/>
      {isSelected && <circle cx={cx} cy={cy} r={r+3.5} fill="none" stroke="#285ee8" strokeWidth={1.5} opacity={0.85}/>}
      {payload.isChampion && <text className="quad-label" x={cx+r+7} y={cy+4} fill="#285ee8" fontSize={11}>
        {payload.name.length>22?`${payload.name.slice(0,22)}…`:payload.name}
      </text>}
    </g>;
  };
  return <>
    <div className="quadrant-wrap">
      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 14, right: 24, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e8edf5" strokeDasharray="3 5"/>
          <XAxis type="number" dataKey="x" scale="log" domain={[xMin, xMax]}
            tickFormatter={value=>`$${value}`} tick={{ fill:"#8290a7", fontSize:11 }}
            stroke="#dbe3ef" label={{ value:"输入价 / 百万 tokens（log）", position:"insideBottomRight", offset:-2, fill:"#8290a7", fontSize:11 }}/>
          <YAxis type="number" dataKey="y" domain={[yMin, yMax]} width={38}
            tick={{ fill:"#8290a7", fontSize:11 }} stroke="#dbe3ef"/>
          <ReferenceArea x1={xMin} x2={medianX} y1={medianY} y2={yMax}
            fill="rgba(40,94,232,.07)" stroke="none"
            label={{ value:"低价 · 高分", position:"insideTopLeft", fill:"#285ee8", fontSize:11 }}/>
          <ReferenceLine x={medianX} stroke="#aebbd0" strokeDasharray="4 4"/>
          <ReferenceLine y={medianY} stroke="#aebbd0" strokeDasharray="4 4"/>
          <Tooltip content={<QuadTooltip/>} cursor={{ stroke:"#aebbd0", strokeDasharray:"3 3" }}/>
          <Scatter data={flagged} shape={renderBubble} cursor="pointer"
            onClick={entry=>{ const id=entry?.payload?.id ?? entry?.id; if (id) toggle(id); }}/>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
    {excluded>0 && <p className="quadrant-note">{excluded} 个模型因价格或评估缺失（含免费模型）未绘制 · 气泡大小 = 上下文窗口</p>}
  </>;
}
