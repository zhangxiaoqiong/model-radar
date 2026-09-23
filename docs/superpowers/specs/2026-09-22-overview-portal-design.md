# 概览页门户化升级设计（Overview Portal Redesign）

日期：2026-09-22
状态：已评审冻结
范围：`apps/web` 前端-only；后端零改动

## 1. 背景与目标

当前概览页（`apps/web/src/App.jsx` 的 `Overview`）数据叙事弱：「最新真实评测」
按变体重复罗列同一模型（长名称噪声大），Benchmark Pulse 三个卡片常指向同一模型，
视觉为素色浅灰面板，缺乏门户（portal）应有的全局感与质感。

目标：把概览升级为「深色驾驶舱」门户——一眼建立全局认知（规模、排名、性价比），
并提供进入模型图谱 / 对比的动线。内页（模型 / 对比 / 基准）保持浅色与现有结构，
仅迁移到新设计令牌。

冻结的用户决策：
- 信息架构与视觉语言一起升级。
- 门户模块 = 全局 KPI 统计带 + 多维排行榜 + 性价比象限图；**不做**最新变化 delta 流。
- 视觉 = 深色驾驶舱概览 + 浅色内页。
- 实现路径 = 组件化重构 + 设计令牌（方案 A）。

## 2. 信息架构与布局

自上而下四层；旧「最新真实评测」活动流与 Watchlist 退役（职能并入排行榜），
Benchmark Pulse 保留并改深色样式。

```
┌────────────────────────────────────────────────────────────────┐
│ HERO 深色：最新模型雷达 · 一句话定位 · 同步状态徽章                 │
│ KPI 带：跟踪模型 | 提供商 | 近30天新发布 | 输入价中位数 | 最新同步    │
├───────────────────────────────┬────────────────────────────────┤
│ 排行榜 Leaderboard（约42%宽）   │ 性价比象限 Quadrant（约58%宽）    │
│ Tab 三维度：Intelligence/      │ X=输入价(log) Y=AA Intelligence  │
│ Coding/Agentic                 │ 气泡大小=上下文，颜色=provider    │
│ Top8：排名·mark·名称·分数条·价格 │ 虚线=中位数，标注「便宜且聪明」象限 │
│ 行点击 = 加入/移出对比选择       │ hover 详情，点击同样加入对比       │
├───────────────────────────────┴────────────────────────────────┤
│ Benchmark Pulse（3 卡保留，深色化） + [选择模型进行对比] CTA        │
└────────────────────────────────────────────────────────────────┘
```

- KPI 带 5 瓷砖；loading 显示 `—`。
- 排行榜按**模型维度聚合**（同模型多变体取最高分），分数条宽度 = 分数 / 榜首分数。
- 象限图缺失价格或分数的模型不绘制，panel 脚注注明「N 个模型因数据缺失未绘制」，不推断。
- 交互闭环：排行榜行与象限气泡均可一键加入对比选择（与 SelectionDock 共用状态）；
  底部 CTA 进入对比页。

## 3. 视觉语言

设计令牌定义于 `src/theme.css`：`:root` 为浅色，`.theme-dark` 覆盖为深色；
组件只引用令牌，不写死颜色。

| 令牌 | 浅色（内页不变） | 深色（概览） |
|---|---|---|
| `--bg` | 现有灰白 | `#0a0f1e` + 顶部径向光晕 |
| `--panel` | 白 | `rgba(255,255,255,.04)` + 1px `rgba(255,255,255,.08)` 描边 + 背景模糊 |
| `--text` / `--muted` | 现有 | `#e6ebf5` / `#8b94a7` |
| `--accent` | 现有蓝 | 同蓝提亮 + 发光投影；提供商沿用品牌色 |

质感手法（克制）：
- 玻璃拟态仅用于概览三层卡片；KPI 瓷砖用更浅一档底 + 细描边形成层次。
- 数字 `font-variant-numeric: tabular-nums`。
- 象限网格线 `rgba(255,255,255,.06)`；中位虚线；「便宜且聪明」象限 4% accent 填充。
- 动效仅三处：面板载入 12px 上浮淡入、Tab 下划线滑动、分数条宽度过渡；
  全部尊重 `prefers-reduced-motion`。
- 不引新字体；Hero 标题 40–44px 收紧字距；建立 title/section/body/caption 四级文字令牌。
- 提供商色板抽共享常量（light/dark 各一套亮度），排行榜分数条、象限气泡、
  内页 provider mark 三处共用。

## 4. 数据推导与边界

所有洞察集中于 `src/lib/derive.js` 纯函数（输入 `models[]` + `status`，无 fetch、
无副作用、可单测）：

| 函数 | 输出 | 规则 |
|---|---|---|
| `computeKpis(models, status)` | 5 瓷砖 | 模型数 / provider 去重数 / 近30天新发布（`release_date`）/ 输入价中位数（仅非 null）/ 最新同步（status） |
| `buildLeaderboard(models, dimension)` | Top8 | 模型维度取变体最高分；降序，同分按发布日期降序；分数条 = 分 / 榜首 |
| `buildQuadrant(models)` | 散点 + 中位线 + 排除数 | 仅 `inputPrice` 与 Intelligence 双全者；X log 轴；中位数四分；气泡半径 sqrt(context) 设上限 |
| `buildPulse(models)` | 3 卡 | 沿用现有逻辑（各维度 top1），仅改样式 |

边界：
- loading：KPI 与排行榜深色骨架条；象限呼吸占位。
- error：沿用「数据源连接失败」语义改深色横幅，不造演示数据。
- 象限有效点 < 3：不画图，面板提示「价格与评估数据不足，同步后展示象限视图」。
- 某维度全缺分数：该 Tab 显示空态说明，不显示空表。
- 中位数空集：瓷砖 `—`。
- 超长模型名：排行榜单行省略 + title tooltip；象限 tooltip 全名。

后端零改动：不新增/修改端点；轮询（300s）与重试逻辑不变。

## 5. 代码结构

```
apps/web/src/
  App.jsx              # shell：路由、数据加载、轮询 → 约90行
  theme.css            # 新：设计令牌 + base
  styles.css           # 现有样式迁移为令牌引用
  lib/api.js           # fetch 封装 + mapApiModel/mapApiBenchmark（原样搬迁）
  lib/derive.js        # 新：computeKpis/buildLeaderboard/buildQuadrant/buildPulse
  components/shared.jsx    # ModelMark, Rating, Filter, PageHero, SelectionDock, Panel
  components/KpiBand.jsx       # 新
  components/Leaderboard.jsx   # 新
  components/QuadrantChart.jsx # 新（Recharts ScatterChart 封装）
  views/Overview.jsx   # 新：组装 Hero+KpiBand+Leaderboard+QuadrantChart+Pulse+CTA
  views/Catalog.jsx    # 原样搬迁（ModelCatalogV2）
  views/Compare.jsx    # 原样搬迁
  views/Benchmarks.jsx # 原样搬迁
```

- 唯一新依赖：Recharts。
- 删除死代码：`DEMO_MODELS` / `DEMO_BENCHMARKS` 常量、旧版 `ModelCatalog` 组件。
- 保留概览标题文案「最新模型雷达」与顶栏「来源数据」徽章（visual-qa 断言依赖）。

## 6. 测试与验证

1. 单元：`tests/derive.test.mjs`（node --test）覆盖 KPI 中位数/空集、排行榜排序与
   tiebreak、模型维度聚合、象限过滤与中位切分、pulse top1。
2. 回归：`tests/sites-worker.test.mjs` 与后端 pytest（65 例）保持全绿。
3. 视觉回归：`scripts/visual-qa.mjs` 保留既有断言，新增——KPI 带 5 瓷砖、
   排行榜 Tab 切换后首行变化、象限 `<svg>` 存在且点数与 derive 输出一致；
   重新生成 `qa/overview.png`、`qa/mobile.png`。
4. 手动：内页抽查深色令牌无串色；console 无报错（脚本已收集 consoleErrors）。

响应式：<900px KPI 带折 2 列、排行榜与象限上下堆叠、象限高 320px。

## 7. 明确不做（YAGNI）

最新变化 delta 流、任何后端改动、内页深色、i18n、新字体、动效库。

## 8. 风险与回滚

唯一新依赖 Recharts（约 +45KB gzip）；若包体成问题可换手写 SVG 散点，
`QuadrantChart` props 接口不变。回滚 = revert 前端提交；不触数据库与后端。
