import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function ProfileTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const model = payload[0].payload;
  return <div className="tradeoff-tooltip">
    <strong>{model.name}</strong><span>{model.provider}</span>
    <span>{model.dimension}：{model.value}</span>
  </div>;
}

export function CapabilityProfileChart({ matrix, dimension, selectedIds, toggle, loading }) {
  if (loading) return <div className="atlas-chart-loading">正在载入评估数据…</div>;
  if (!matrix.rows.length) return <div className="atlas-chart-loading">暂无可比较的评估数据</div>;
  const data = matrix.rows.map(model => ({ id: model.id, name: model.name, provider: model.provider, value: model.score[dimension], dimension }));
  const yMax = Math.max(10, Math.ceil(Math.max(...data.map(model => model.value)) * 1.12 / 10) * 10);
  const modelTick = ({ x, y, payload }) => {
    const name = payload.value.replace(/Adaptive Reasoning,?\s*|Effort|Default /g, "");
    const words = name.split(/\s+/), lines = [""];
    words.forEach(word => {
      const last = lines.length - 1;
      if (lines[last] && (lines[last] + " " + word).length > 19) lines.push(word);
      else lines[last] += (lines[last] ? " " : "") + word;
    });
    return <text x={x} y={y + 14} textAnchor="middle" fill="#52637f" fontSize={10}><title>{payload.value}</title>{lines.slice(0, 4).map((line, index) => <tspan key={index} x={x} dy={index ? 14 : 0}>{line}{index === 3 && lines.length > 4 ? "…" : ""}</tspan>)}</text>;
  };
  return <>
    <div className="capability-profile-chart">
      <div className="capability-profile-chart-inner"><ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} barGap={2} barCategoryGap="28%" margin={{ top: 12, right: 18, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} stroke="#edf1f7" strokeDasharray="3 5"/>
          <XAxis type="category" dataKey="name" interval={0} height={82} tick={modelTick} axisLine={false} tickLine={false}/>
          <YAxis type="number" domain={[0, yMax]} width={36} tick={{ fill: "#8b98ac", fontSize: 10 }} axisLine={false} tickLine={false}/>
          <Tooltip content={<ProfileTooltip/>} cursor={{ fill: "#f4f8ff" }}/>
          <Bar dataKey="value" fill="#6490ed" radius={[5, 5, 0, 0]} maxBarSize={48} cursor="pointer" onClick={entry => { const id = entry?.payload?.id ?? entry?.id; if (id) toggle(id); }}>
            {data.map(model => <Cell key={model.id} fill={selectedIds.includes(model.id) ? "#1747b6" : "#6490ed"} stroke={selectedIds.includes(model.id) ? "#17233a" : "none"} strokeWidth={selectedIds.includes(model.id) ? 1.5 : 0}/>)}
            <LabelList dataKey="value" position="top" fill="#26364f" fontSize={12}/>
          </Bar>
        </BarChart>
      </ResponsiveContainer></div>
    </div>
    <div className="atlas-matrix-foot">来源：Artificial Analysis · {dimension} · 点击柱形选择模型，选满两个即可对比</div>
  </>;
}
