import { CartesianGrid, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { providerColor } from "../lib/api.js";

const formatPrice = value => `$${value < 1 ? value.toFixed(3) : value.toFixed(2)}`;

function TradeoffTooltip({ active, payload, mode, dimension }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return <div className="tradeoff-tooltip">
    <strong>{point.name}</strong>
    <span>{point.provider} · {dimension.replace("AA ", "")} {point.y}</span>
    <span>{mode === "price" ? `输入价 ${formatPrice(point.x)} / 百万 tokens` : `输出速度 ${Math.round(point.x)} tokens/s`}</span>
  </div>;
}

export function TradeoffChart({ data, dimension, mode = "price", selectedIds, toggle, loading }) {
  const { points, frontier, medianX, medianY, excluded } = data;
  if (loading) return <div className="tradeoff-empty">正在载入图表数据…</div>;
  if (points.length < 3) return <div className="tradeoff-empty">可比较的数据不足，暂时无法绘制这张图。</div>;
  const xs = points.map(point => point.x), ys = points.map(point => point.y);
  const xMin = mode === "price" ? Math.min(...xs) * 0.7 : Math.max(0, Math.min(...xs) * 0.82);
  const xMax = Math.max(...xs) * 1.18;
  const yMin = Math.max(0, Math.min(...ys) - 4), yMax = Math.max(...ys) + 4;
  const frontierIds = new Set(frontier.map(point => point.id));
  const renderPoint = ({ cx, cy, payload }) => {
    const selected = selectedIds.includes(payload.id);
    const onFrontier = frontierIds.has(payload.id);
    const radius = onFrontier ? 7 : 5;
    return <g className="tradeoff-point" key={payload.id}>
      {onFrontier && <circle cx={cx} cy={cy} r={radius + 5} fill={providerColor(payload.provider)} opacity={0.12}/>}
      <circle cx={cx} cy={cy} r={radius} fill={providerColor(payload.provider)} stroke="#fff" strokeWidth={2}/>
      {selected && <circle cx={cx} cy={cy} r={radius + 4} fill="none" stroke="#1e3153" strokeWidth={2}/>}
    </g>;
  };
  const path = [...frontier].sort((a, b) => a.x - b.x);
  return <>
    <div className="tradeoff-chart">
      <ResponsiveContainer width="100%" height={mode === "price" ? 390 : 312}>
        <ScatterChart margin={{ top: 20, right: 28, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#e6ecf5" strokeDasharray="3 5"/>
          <XAxis type="number" dataKey="x" scale={mode === "price" ? "log" : "linear"} domain={[xMin, xMax]}
            tickFormatter={value => mode === "price" ? `$${Number(value).toPrecision(2)}` : `${Math.round(value)}`}
            tick={{ fill: "#8290a7", fontSize: 11 }} stroke="#dce4ef"/>
          <YAxis type="number" dataKey="y" domain={[yMin, yMax]} width={36} tick={{ fill: "#8290a7", fontSize: 11 }} stroke="#dce4ef"/>
          <ReferenceArea x1={mode === "price" ? xMin : medianX} x2={mode === "price" ? medianX : xMax} y1={medianY} y2={yMax} fill="rgba(40,94,232,.055)" stroke="none"/>
          <ReferenceLine x={medianX} stroke="#b7c4d7" strokeDasharray="4 4"/>
          <ReferenceLine y={medianY} stroke="#b7c4d7" strokeDasharray="4 4"/>
          {path.slice(1).map((point, index) => <ReferenceLine key={`${path[index].id}-${point.id}`} segment={[{ x: path[index].x, y: path[index].y }, { x: point.x, y: point.y }]} stroke="#285ee8" strokeWidth={2.5} strokeDasharray="6 4" ifOverflow="extendDomain"/>)}
          <Tooltip content={<TradeoffTooltip mode={mode} dimension={dimension}/>} cursor={{ stroke: "#aebbd0", strokeDasharray: "3 3" }}/>
          <Scatter data={points} shape={renderPoint} cursor="pointer" onClick={entry => { const id = entry?.payload?.id ?? entry?.id; if (id) toggle(id); }}/>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
    <div className="tradeoff-axis"><span>{mode === "price" ? "← 输入价格更低（对数轴）" : "← 输出速度较慢"}</span><span>{mode === "price" ? "输入价格更高 →" : "输出速度更快 →"}</span></div>
    <div className="tradeoff-foot"><span><i/> 虚线：当前数据中的 Pareto 前沿</span><span>{excluded} 个模型因缺少该维度分数或{mode === "price" ? "正价数据" : "速度数据"}未绘制</span></div>
  </>;
}
