# LLM Observatory V1

## 大模型跟踪、测评与对比系统

版本：v0.3（Implementation Ready Draft）
上一版：v0.2（Architecture Draft）
产品定位：个人 AI 技术认知与模型情报基础设施
核心目标：持续跟踪主流 LLM，聚合可信测评，形成统一能力视图，支持模型横向与纵向对比，并自动发现重要变化。

---

## v0.3 变更记录

相对 v0.2 的关键修改：

1. 修复 Evaluation 唯一 fingerprint 与“分数变化保留历史”的冲突，拆分身份键与观察版本键
2. 原始 Evaluation 与归一化结果解耦，新增 `normalization_run`、`normalized_evaluation`、`capability_score_snapshot`
3. 明确 Compare 的比较单元为 Release + Variant + optional Endpoint，并定义默认选择策略
4. Evaluation 补充 Endpoint、数据集 revision、seed、decoding config、scorer version 等可复现字段
5. Benchmark 增加结构化 `benchmark_metric`，避免多指标与自由文本混用
6. 新增 `evidence_link`，Evidence 可关联 Evaluation、价格、字段观察及 Event
7. `model_event` 增加 benchmark / evaluation 关联，完善非模型事件溯源
8. Raw Snapshot 改为元数据入库、载荷外置保存，增加脱敏、许可与保留策略
9. Admin 增加认证、RBAC、审计和并发控制要求
10. Pipeline 增加单实例调度、数据库租约、重试、超时和崩溃恢复约束
11. 数据库配置改为环境变量示例，统一所有时间为 UTC
12. V1 拆分为 V1a–V1d，并增加数据质量、时效性与可靠性成功指标

---

# 1. 项目目标

LLM Observatory 不是一个单纯的模型排行榜。

系统主要解决以下问题：

1. 当前有哪些值得关注的模型？
2. 一个模型属于哪家公司、哪个系列、哪个版本？
3. 模型支持哪些能力？
4. 模型专业 Benchmark 表现如何？
5. Benchmark 分数来源是否可信？
6. 模型之间 Coding、Reasoning、Agent、Long Context 等能力如何比较？
7. 模型价格、速度、上下文长度有什么区别？
8. 一个模型相比上一版本提升了什么？
9. 最近模型生态发生了什么重要变化？
10. 哪些变化值得重点关注？

最终形成：

```text
模型事实
    ↓
评测证据
    ↓
能力理解
    ↓
模型比较
    ↓
变化追踪
```

## 1.1 目标用户与核心场景

V1 首要用户是需要持续进行模型选型与技术跟踪的个人开发者、AI 工程师和技术负责人。

核心场景按优先级排序：

1. 在 10 分钟内完成候选模型的能力、价格、上下文和证据对比。
2. 快速确认某个分数、价格或规格来自哪里、何时采集、是否仍然有效。
3. 每日查看值得关注的模型发布、价格变化和评测变化。
4. 对少量关键模型运行可复现的内部评测。

## 1.2 V1 成功指标

除功能验收外，上线后按以下指标判断产品是否有效：

```text
核心来源每日同步成功率           >= 95%
关键事实具备 source + snapshot   >= 99%
已展示 Evaluation 可复现字段完整率 >= 95%
人工确认后的 Alias 二次命中率     >= 99%
错误实体映射率                   < 1%
数据变更从采集到展示的 P95 延迟    < 24 小时
核心 Compare 查询 P95            < 1 秒（不含首次冷启动）
```

产品价值验证：至少由 3 名目标用户完成真实模型选型任务，并记录完成时间、证据查看率和主要阻塞点。

---

# 2. V1 产品边界

## V1 必须实现

### 2.1 Model Registry

统一管理五层实体：

```text
Provider
    ↓
Model Family
    ↓
Model Release
    ↓
Model Variant
    ↓
Model Endpoint
```

语义定义：

```text
Model Release = 厂商发布的一个实际模型（代际）
Variant       = 同一模型的运行/能力配置差异（standard / thinking 等）
Endpoint      = 谁、以什么方式提供这个 Variant（官方 API / OpenRouter / 第三方托管）
```

字段归属原则：

```text
挂在 Release / Variant：
发布时间、架构、知识截止日期、模态、基本能力开关

挂在 Endpoint：
价格、延迟、吞吐、上下文限制（可覆盖）、可用性
```

解决不同数据源模型命名不一致问题。

例如：

```text
Anthropic (Provider)
└── Claude (Family)
    └── Claude X (Release)
        ├── Standard (Variant)
        │   ├── Anthropic API (Endpoint)
        │   └── OpenRouter (Endpoint)
        └── Thinking (Variant)
            └── Anthropic API (Endpoint)
```

---

### 2.2 Benchmark Registry

统一管理 Benchmark。

记录：

* benchmark 名称
* benchmark 版本
* benchmark 类型
* 测试能力
* metric
* 分数方向（higher better / lower better）
* 归一化方法
* 数据来源
* 是否公开数据集
* 是否容易污染
* 当前状态
* 官方说明

---

### 2.3 Evaluation Warehouse

统一保存所有评测结果，拆分为两层：

```text
evaluation_run    一次执行（外部聚合批次 或 自跑评测）
evaluation        一条结果（Model × Benchmark × 配置）
```

不仅保存：

```text
Model X
SWE-bench = 72.3
```

还必须保存：

```text
Model
Model Variant
Benchmark
Benchmark Version
Score
Metric
Evaluator
Source
Evaluation Date
Reasoning Setting
Harness
Prompt Config
Agent Scaffold
Cost
Sample Size
Confidence
Fingerprint（幂等键）
```

核心原则：

> 所有 Score 必须能追溯来源。

---

### 2.4 Capability System

建立独立于 Benchmark 的能力体系。

V1 能力分类：

```text
Reasoning

Mathematics

Coding
├── Code Generation
├── Debugging
├── Repo-level Coding
└── Agentic Coding

Agent
├── Tool Use
├── Planning
└── Multi-step Task

Long Context

Multimodal
├── Vision
└── Document Understanding

Language
├── Chinese
├── English
└── Multilingual

Efficiency
├── Cost
├── Latency
└── Throughput
```

Benchmark 通过映射表连接 Capability。

例如：

```text
SWE-bench
→ Repo-level Coding

BFCL
→ Tool Use

LiveBench Coding
→ Coding

MMMU
→ Multimodal Reasoning
```

---

### 2.5 Model Compare

用户选择 2–5 个比较项进行比较。

比较项不是模糊的“Model”，而是：

```text
Comparison Item = Model Release + Model Variant + optional Model Endpoint
```

默认规则：

```text
Specs       → Release + Variant
Evaluation  → Variant；有 Endpoint 的内部评测必须显示 Endpoint
Capability  → Variant + 指定 normalization run
Price       → Endpoint；默认优先 official_api，不存在时要求用户选择
Performance → Endpoint；禁止把不同渠道测速静默合并
```

一个 Release 存在多个 Variant 时，必须由 seed 配置 `default_variant_id` 或让用户选择；不得按名称猜测。

比较四类内容：

#### Specs

* 厂商
* 发布时间
* Context Window
* 最大输出
* 模态
* Tool Calling
* Reasoning
* Structured Output
* Open Weight

#### Evaluation

展示各 Benchmark 原始数据。

#### Capability

聚合到统一能力体系。

#### Efficiency

* Input Price
* Output Price
* Tokens/sec
* Time to First Token
* Benchmark Cost

---

### 2.6 Timeline / Change Tracking

记录：

* 新模型发布
* 新模型版本
* Benchmark 更新
* Benchmark 分数变化
* API 价格变化
* Context Window 变化
* Provider 变化
* 重要技术能力变化

每条 Event 必须能反查产生原因（snapshot 对比 + pipeline run）。

输出：

```text
2026-09-18

Model X 发布

Reasoning      ↑
Agentic Coding ↑↑
Price          →
Context        200K → 1M
```

---

### 2.7 Dashboard

首页重点回答：

```text
最近发生了什么？
```

包括：

* Latest Models
* Recently Updated Models
* Major Benchmark Changes
* Price Changes
* Capability Changes
* Latest Evaluation Runs

---

# 3. V1 明确不做

防止 Coding Agent 过度开发。

V1 不实现：

* Twitter / X 舆情抓取
* Reddit 大规模情绪分析
* 论文 RAG
* 全自动新闻 Agent
* Agent Observability
* 用户社区
* 模型在线聊天产品
* FastChat Arena 完整复刻
* 大规模 GPU Benchmark Farm
* 全行业 AI 模型覆盖
* Image / Video / Audio 模型

V1 首先只做：

> Text / Multimodal LLM。

---

# 4. 数据源设计

数据源分四层。

## Tier A：独立第三方评测

优先级最高。

V1：

```text
Artificial Analysis
LiveBench
Arena
SWE-bench
```

## 4.1 Artificial Analysis 能力降级设计

AA API 存在 Free / Pro / Commercial 档位（具体配额数字以实际 key 响应为准，**不要在代码里写死**）。系统按配置的 key 实际能力工作：

```text
Free（默认基线）：
  model 基本身份
  headline indices
  input/output pricing（模型级中位数）
  median performance

Pro（若配置）：
  individual benchmark evaluations
  更完整 model metadata

Commercial（若配置）：
  provider-level pricing / performance
  performance time series
```

工程要求：

```text
1. Adapter 启动时读取响应 RateLimit Header：
   X-RateLimit-Limit
   X-RateLimit-Remaining
   X-RateLimit-Reset

2. 按 tier 探测可用字段，能力不足时静默降级并记录到 sync 日志

3. Sprint 验收不依赖付费档数据
```

注意：AA 的 pricing / performance 在 Free/Pro 档是**模型级聚合值**（中位数），无 provider 归属，落库时挂 variant；Commercial 档的 provider 级数据挂 endpoint。

---

## Tier B：官方模型信息

例如：

```text
OpenAI
Anthropic
Google
DeepSeek
Alibaba Qwen
Meta
Mistral
xAI
```

用于获取：

* 发布时间
* Context
* Modality
* API
* Pricing
* Model Card
* Technical Report
* 官方 Benchmark

必须标记：

```text
source_type = vendor
```

---

## Tier C：模型目录 / 聚合器

包括：

```text
LiteLLM
OpenRouter
```

用途：

* 模型名称发现
* Provider 映射
* API 路由信息
* Price 辅助校验
* Context 辅助校验

不可作为绝对权威源。

**注意：聚合器同步只产生候选，不自动创建模型**（见第 36 节 Tracking Policy）。否则一次 OpenRouter 同步会冒出上千个模型。

---

## Tier D：自己的 Evaluation

包括：

```text
lm-evaluation-harness
Promptfoo
```

后期增加：

```text
DeepEval
```

## 4.2 Source 接入门槛

每个 Adapter 开发前必须填写 Source Contract：

```text
获取方式          API / file / official page
认证方式          key tier 与权限范围
限流与重试        headers、退避、每日预算
字段覆盖          model / benchmark / price / performance
更新频率          来源更新频率与本系统同步频率
稳定身份          external IDs 是否稳定
许可              缓存、内部使用、公开展示、再分发限制
保留策略          full payload / redacted / metadata only
降级行为          来源不可用或字段缺失时如何展示
Owner             维护人及失效检查日期
```

没有明确许可或稳定获取方式的来源只能进入实验状态，不得作为 V1a 发布阻塞项，也不得默认公开再分发其原始载荷。

---

# 5. 核心数据模型

## 5.0 数据库约定（MySQL）

目标实例：

```text
MySQL 5.7.36
Host: ${DB_HOST}:${DB_PORT}
Database: ${DB_NAME}
```

连接信息**只放 `.env`**，禁止硬编码进代码或文档仓库。

设计与约束：

```text
1. Engine: InnoDB
2. Charset: 每张表显式 utf8mb4 / utf8mb4_unicode_ci
   （server 默认 utf8 是 utf8mb3，不显式指定会出乱码）
3. 主键: CHAR(36) UUID，应用层生成，推荐 UUIDv7（时间有序，减少索引碎片）
4. JSON 字段: MySQL JSON 类型（5.7.8+ 支持）
5. 不使用 CHECK 约束（5.7 解析但忽略）→ 数据校验放 Pydantic / service 层
6. 不使用函数索引 / 表达式索引 → fingerprint 等由应用层计算后存为普通列
7. 不使用 8.0 专属特性（CTE、窗口函数、降序索引等不在 SQL 层依赖；
   应用层代码可用 Python 实现）
8. 时间: DATETIME，由应用层以 UTC 写入；API 使用 ISO 8601 UTC（`Z`）输出
9. 5.7 已 EOL：设计保持 8.0 兼容，后续可平滑升级实例
10. 驱动: PyMySQL（SQLAlchemy URL: mysql+pymysql://）
11. 所有外键列显式建索引；业务唯一键由迁移脚本创建并通过并发测试验证
12. UUIDv7 由固定依赖库生成，不依赖 Python 3.12 标准库提供
```

---

## 5.1 provider

```sql
provider
--------
id CHAR(36) PK
slug VARCHAR(64) UNIQUE
name VARCHAR(128)
provider_type VARCHAR(32)
-- vendor / aggregator / platform

website_url VARCHAR(512) NULL
country VARCHAR(64) NULL
description TEXT NULL
created_at DATETIME
updated_at DATETIME
```

注意：OpenRouter / Together 这类聚合平台也是 provider（`provider_type = aggregator`），因为 Endpoint 归属方可能是它们。

---

## 5.2 model_family

例如 Claude、Gemini、GPT、Qwen。

```sql
model_family
------------
id CHAR(36) PK
provider_id CHAR(36) FK
slug VARCHAR(64)
name VARCHAR(128)
description TEXT
created_at DATETIME
updated_at DATETIME

UNIQUE(provider_id, slug)
```

---

## 5.3 model_release

对应具体代际模型。

```sql
model_release
-------------
id CHAR(36) PK

family_id CHAR(36) FK
default_variant_id CHAR(36) NULL FK
-- Variant 创建后回填；应用层保证属于当前 Release

canonical_name VARCHAR(128)
slug VARCHAR(64) UNIQUE

release_date DATE NULL
knowledge_cutoff DATE NULL

architecture_type VARCHAR(64) NULL
parameter_count BIGINT NULL

open_weight BOOLEAN
license VARCHAR(128) NULL

official_url VARCHAR(512) NULL
model_card_url VARCHAR(512) NULL
technical_report_url VARCHAR(512) NULL

source_id CHAR(36) NULL FK
source_snapshot_id CHAR(36) NULL FK
observed_at DATETIME NULL
confidence VARCHAR(16)

status VARCHAR(32)
-- active / preview / deprecated / retired

created_at DATETIME
updated_at DATETIME
```

---

## 5.4 model_variant

区分 reasoning / standard 等。

```sql
model_variant
-------------
id CHAR(36) PK

model_release_id CHAR(36) FK

name VARCHAR(128)
variant_type VARCHAR(32)
-- standard / thinking / preview / distilled / ...

reasoning_level VARCHAR(32) NULL
-- none / low / medium / high

context_window BIGINT NULL
max_output_tokens BIGINT NULL

supports_text BOOLEAN
supports_image BOOLEAN
supports_audio BOOLEAN
supports_video BOOLEAN

supports_reasoning BOOLEAN
supports_tool_calling BOOLEAN
supports_structured_output BOOLEAN

source_id CHAR(36) NULL FK
source_snapshot_id CHAR(36) NULL FK
observed_at DATETIME NULL
confidence VARCHAR(16)

created_at DATETIME
updated_at DATETIME

UNIQUE(model_release_id, name)
```

字段级溯源：`context_window` / `max_output_tokens` 这两个高冲突字段，canonical 值之外另记 `field_observation`（见 35.3）。

---

## 5.5 model_endpoint（v0.2 新增）

谁、以什么方式提供某个 Variant。

```sql
model_endpoint
--------------
id CHAR(36) PK

model_variant_id CHAR(36) FK
provider_id CHAR(36) FK

external_model_id VARCHAR(128)
-- 该 provider 侧的模型标识，如 openrouter 侧的 ID

endpoint_type VARCHAR(32)
-- official_api / third_party_api / self_hosted

api_base_url VARCHAR(512) NULL

context_window BIGINT NULL
-- endpoint 可覆盖 variant 级限制（如 OpenRouter 截断）

max_output_tokens BIGINT NULL

status VARCHAR(32)
-- active / preview / deprecated

source_id CHAR(36) NULL FK

created_at DATETIME
updated_at DATETIME

UNIQUE(provider_id, external_model_id)
```

---

## 5.6 model_alias

解决不同数据源名称不同的问题。

非常重要。

```sql
model_alias
-----------
id CHAR(36) PK

model_variant_id CHAR(36) FK
source_id CHAR(36) FK

alias VARCHAR(256)

external_id VARCHAR(256) NULL

created_at DATETIME

UNIQUE(source_id, alias)
```

例如：

```text
claude-x-sonnet
anthropic/claude-x-sonnet
claude-x-sonnet-20260901
```

都映射到同一个 model_variant。

人工审核通过后自动生成 alias（见 16 节闭环）。

---

# 6. Benchmark 数据模型

## benchmark

```sql
benchmark
---------
id CHAR(36) PK

slug VARCHAR(64) UNIQUE
name VARCHAR(128)

category VARCHAR(64)
description TEXT

official_url VARCHAR(512)

source_id CHAR(36) NULL FK
source_snapshot_id CHAR(36) NULL FK
observed_at DATETIME NULL
confidence VARCHAR(16)

dataset_public BOOLEAN
dynamic BOOLEAN
contamination_risk VARCHAR(32)

status VARCHAR(32)

created_at DATETIME
updated_at DATETIME
```

分数方向与归一化方法属于具体 Metric，不放在 Benchmark 顶层。

---

## benchmark_version

```sql
benchmark_version
-----------------
id CHAR(36) PK

benchmark_id CHAR(36) FK

version VARCHAR(64)

release_date DATE NULL

dataset_size INT NULL

notes TEXT NULL

source_id CHAR(36) NULL FK
source_snapshot_id CHAR(36) NULL FK
observed_at DATETIME NULL
confidence VARCHAR(16)

created_at DATETIME

UNIQUE(benchmark_id, version)
```

一个 Benchmark Version 可以有多个可比较指标，禁止仅靠自由文本区分 split 或 metric：

```sql
benchmark_metric
----------------
id CHAR(36) PK

benchmark_version_id CHAR(36) FK

slug VARCHAR(64)
name VARCHAR(128)
dataset_split VARCHAR(64) NULL

unit VARCHAR(32)
-- percent / ratio / elo / milliseconds / ...

score_direction VARCHAR(16)
-- higher_better / lower_better
normalization_method VARCHAR(16)
-- minmax / percentile / none / custom

created_at DATETIME

UNIQUE(benchmark_version_id, slug, dataset_split)
```

正式 Evaluation 必须关联 `benchmark_metric_id`。Elo / rating 类 Metric（如 Arena rating）不适合 min-max 解释，应设 `normalization_method = none` 或 `custom`。

---

# 7. Capability 数据模型

## capability

```sql
capability
----------
id CHAR(36) PK

parent_id CHAR(36) NULL FK

slug VARCHAR(64) UNIQUE
name VARCHAR(128)

description TEXT

level INT
sort_order INT
```

---

## benchmark_capability_map

```sql
benchmark_capability_map
------------------------
benchmark_id CHAR(36) FK
capability_id CHAR(36) FK

weight DECIMAL(5,4)

PRIMARY KEY (
  benchmark_id,
  capability_id
)
```

例如：

```text
SWE-bench Verified
→ Repo-level Coding
weight = 1.0
```

---

# 8. Evaluation 数据模型（v0.3）

这是系统最核心的部分。保持 Run / Result 两层，并在 v0.3 将 Result 明确为不可变 observation：

```text
evaluation_run    一次执行
evaluation        一条结果（可能一次 run 产出多条）
```

## 8.1 evaluation_run

```sql
evaluation_run
--------------
id CHAR(36) PK

run_type VARCHAR(32)
-- external   外部聚合数据批次（对应一次 source snapshot）
-- internal   自己执行的评测

engine VARCHAR(32) NULL
-- promptfoo / lm_eval / external_aggregate

source_id CHAR(36) NULL FK
source_snapshot_id CHAR(36) NULL FK
-- external run 必须关联 source_snapshot，保证可追溯

status VARCHAR(32)
-- pending / running / success / failed / partial / cancelled

worker_id VARCHAR(128) NULL
lease_expires_at DATETIME NULL
heartbeat_at DATETIME NULL
attempt INT DEFAULT 0
max_attempts INT DEFAULT 1

config JSON NULL
-- tasks、参数等

cost_usd DECIMAL(12,4) NULL

queued_at DATETIME NULL
started_at DATETIME NULL
finished_at DATETIME NULL

created_at DATETIME
```

## 8.2 evaluation（result）

```sql
evaluation
----------
id CHAR(36) PK

run_id CHAR(36) FK

model_variant_id CHAR(36) FK
model_endpoint_id CHAR(36) NULL FK
-- 实际调用渠道明确时必填；纯模型级外部聚合数据可为空

benchmark_id CHAR(36) FK
benchmark_version_id CHAR(36) FK
benchmark_metric_id CHAR(36) FK

score DECIMAL(10,4)

evaluation_date DATETIME NULL

source_id CHAR(36) FK
source_snapshot_id CHAR(36) NULL FK

evaluator VARCHAR(128) NULL

evaluation_type VARCHAR(32)
-- external / vendor / internal

sample_size INT NULL

reasoning_setting VARCHAR(64) NULL
temperature DECIMAL(5,3) NULL
random_seed BIGINT NULL
few_shot_count INT NULL

harness VARCHAR(64) NULL
harness_version VARCHAR(32) NULL

agent_scaffold VARCHAR(64) NULL
agent_scaffold_version VARCHAR(64) NULL

dataset_revision VARCHAR(128) NULL
scorer_version VARCHAR(64) NULL
runtime_image VARCHAR(256) NULL

prompt_config JSON NULL
decoding_config JSON NULL

cost_usd DECIMAL(12,4) NULL

confidence_lower DECIMAL(10,4) NULL
confidence_upper DECIMAL(10,4) NULL
confidence VARCHAR(16)

external_evaluation_id VARCHAR(256) NULL

evaluation_identity_hash CHAR(64)
-- 同一 Model × Benchmark × 配置的稳定身份；允许出现多个历史 observation

observation_fingerprint CHAR(64) UNIQUE
-- 身份 + snapshot/revision + score 的不可变观察版本键

supersedes_evaluation_id CHAR(36) NULL FK

raw_payload JSON NULL

created_at DATETIME
```

## 8.3 幂等规则

每日同步绝不能产生重复 observation，同时必须保留来源改分历史。

应用层先对评测身份字段 canonicalize 后计算 `evaluation_identity_hash`：

```text
model_variant_id
model_endpoint_id
benchmark_id
benchmark_version_id
benchmark_metric_id
source_id
evaluator
harness + harness_version
reasoning_setting
agent_scaffold + agent_scaffold_version
dataset_revision
scorer_version
prompt_config + decoding_config
```

随后用以下字段生成唯一的 `observation_fingerprint`：

```text
evaluation_identity_hash
external_evaluation_id（若来源提供）
source_snapshot_id 或来源 revision
score
confidence interval
sample_size
```

同步规则：

```text
observation_fingerprint 已存在
→ 跳过，保证重放幂等

identity 相同、observation 不同
→ 新增 Evaluation
→ supersedes_evaluation_id 指向上一条 observation
→ Change Detection 生成分数变化事件
```

禁止覆盖旧 Evaluation。来源稳定 ID 只是身份材料，不单独设置唯一约束，因为同一外部记录可能被来源方修订。

---

# 9. Evidence System

系统所有解释必须尽量有 Evidence。

## evidence

```sql
evidence
--------
id CHAR(36) PK

model_variant_id CHAR(36) NULL FK

capability_id CHAR(36) NULL FK

source_id CHAR(36) FK

evidence_type VARCHAR(32)
-- benchmark / vendor / community / internal_eval

title VARCHAR(256)

summary TEXT

source_url VARCHAR(512)

published_at DATETIME NULL

confidence VARCHAR(16)
-- high / medium / low

raw_content MEDIUMTEXT NULL

created_at DATETIME
```

Evidence 与事实使用显式关联表，禁止仅在 JSON 中保存不可校验的 ID：

```sql
evidence_link
-------------
id CHAR(36) PK
evidence_id CHAR(36) FK

target_type VARCHAR(32)
-- evaluation / pricing / performance / field_observation / model_event / benchmark_version

target_id CHAR(36)
relation_type VARCHAR(32)
-- supports / contradicts / explains

created_at DATETIME

UNIQUE(evidence_id, target_type, target_id, relation_type)
```

应用层必须校验 `target_type + target_id` 对应实体存在；删除目标实体前必须先处理关联。V2 可按规模拆成强外键的多张关联表。

---

# 10. Source 数据模型

```sql
source
------
id CHAR(36) PK

slug VARCHAR(64) UNIQUE
name VARCHAR(128)

source_type VARCHAR(32)
-- independent_eval / vendor / aggregator / internal

reliability_level VARCHAR(16)
-- high / medium / low

base_url VARCHAR(512)

api_available BOOLEAN

created_at DATETIME
updated_at DATETIME
```

例如：

```text
Artificial Analysis
source_type = independent_eval
reliability_level = high
```

---

# 11. Pricing 数据模型

价格一定要做时间版本。

## model_pricing

v0.2 调整：Endpoint 优先挂载，同时保留 variant 级挂载能力（AA Free/Pro 的 pricing 是模型级中位数，没有 endpoint 归属）。

```sql
model_pricing
-------------
id CHAR(36) PK

model_variant_id CHAR(36) FK NOT NULL
model_endpoint_id CHAR(36) NULL FK
-- endpoint 明确时必填；模型级聚合值为 NULL

provider_name VARCHAR(128) NULL

input_price_per_million DECIMAL(12,6) NULL
output_price_per_million DECIMAL(12,6) NULL

cached_input_price DECIMAL(12,6) NULL

currency VARCHAR(8) DEFAULT 'USD'

effective_from DATETIME NULL
effective_to DATETIME NULL

source_id CHAR(36) FK
source_snapshot_id CHAR(36) NULL FK
observed_at DATETIME
confidence VARCHAR(16)
ingestion_run_id CHAR(36) NULL FK

pricing_fingerprint CHAR(64) UNIQUE

created_at DATETIME
```

不能直接覆盖旧价格。否则无法做价格时间线。应用层必须校验同一 Endpoint、币种与价格类型的有效时间区间不重叠；相同 observation 重放由 `pricing_fingerprint` 去重。

---

# 12. Performance 数据模型

与 Pricing 同理：endpoint 级优先，模型级聚合（AA median）挂 variant。

```sql
model_performance
-----------------
id CHAR(36) PK

model_variant_id CHAR(36) FK NOT NULL
model_endpoint_id CHAR(36) NULL FK

provider_name VARCHAR(128) NULL

tokens_per_second DECIMAL(10,2) NULL
time_to_first_token_ms DECIMAL(10,2) NULL
latency_ms DECIMAL(10,2) NULL

prompt_length INT NULL

measured_at DATETIME

source_id CHAR(36) FK
source_snapshot_id CHAR(36) NULL FK
confidence VARCHAR(16)
ingestion_run_id CHAR(36) NULL FK

performance_fingerprint CHAR(64) UNIQUE

raw_payload JSON NULL
created_at DATETIME
```

---

# 13. Event / Timeline

## model_event

```sql
model_event
-----------
id CHAR(36) PK

event_type VARCHAR(32)

model_release_id CHAR(36) NULL FK
model_variant_id CHAR(36) NULL FK
model_endpoint_id CHAR(36) NULL FK
benchmark_id CHAR(36) NULL FK
benchmark_version_id CHAR(36) NULL FK
evaluation_id CHAR(36) NULL FK
model_pricing_id CHAR(36) NULL FK
model_performance_id CHAR(36) NULL FK
field_observation_id CHAR(36) NULL FK

title VARCHAR(256)
summary TEXT

event_date DATETIME

importance INT
-- 1 ~ 5

before_value JSON NULL
after_value JSON NULL

source_id CHAR(36) NULL FK

change_detection_run_id CHAR(36) NULL FK
-- 溯源：由哪次 pipeline 产生

snapshot_before_id CHAR(36) NULL FK
snapshot_after_id CHAR(36) NULL FK
-- 溯源：对比的两次 snapshot

created_at DATETIME
```

每条 Event 至少关联一个业务主体。`benchmark_update` 必须关联 Benchmark，评测改分事件必须关联新 Evaluation；不得创建只有标题而没有结构化主体的 Event。

event_type：

```text
model_release
model_update
benchmark_update
pricing_change
context_change
capability_change
provider_change
deprecation
```

一条 Event 必须能完整反查"为什么产生"：pipeline run → snapshot before/after → 原始数据。

---

# 14. 数据采集架构

统一 Adapter 模式，v0.2 起整体作为 DAG 编排（见第 32 节）：

```text
External Source
      ↓
Source Adapter（按 tier 能力降级）
      ↓
Raw Snapshot（按 retention / license policy 持久化）
      ↓
Normalizer
      ↓
Entity Resolution（低置信进人工队列）
      ↓
Validation
      ↓
Warehouse
      ↓
Change Detector
      ↓
Capability Recalculation
```

---

# 15. Raw Data 必须保留

不要 API 数据抓回来直接覆盖数据库。

必须保存原始 Snapshot，但不把大体积载荷长期重复存入 MySQL。

```text
data/raw/

artificial_analysis/
    2026-09-20.json

openrouter/
    2026-09-20.json

livebench/
    2026-09-20.json
```

本地开发可使用 `data/raw/`；生产环境使用对象存储或受控文件存储。`data/raw/` 必须加入 `.gitignore`，原始载荷不得提交 Git。

数据库保存索引与校验信息：

```sql
source_snapshot
---------------
id CHAR(36) PK
source_id CHAR(36) FK
snapshot_time DATETIME
storage_uri VARCHAR(1024)
content_encoding VARCHAR(32) NULL
content_length BIGINT
checksum CHAR(64)
-- payload 的 SHA-256，用于快速判断是否变化
stats JSON NULL
-- 记录数、解析统计等
license_policy VARCHAR(32)
-- retain / metadata_only / no_redistribution
redaction_status VARCHAR(16)
retention_until DATETIME NULL
created_at DATETIME

UNIQUE(source_id, checksum)
```

小于配置阈值的载荷可选择内联保存到单独的 `source_snapshot_blob` 表，但业务查询不得默认加载 blob。

Adapter 上线前必须记录来源服务条款、缓存许可、再分发限制和必要的字段脱敏规则。这样既能在解析错误后重放，也避免数据库、Git 仓库和备份无限膨胀。

---

# 16. Entity Resolution

这是整个系统最重要的工程模块之一。

例如不同来源：

```text
GPT-X
gpt-x
openai/gpt-x
gpt-x-2026-09
```

需要统一成：

```text
model_variant_id = xxx
```

流程：

```text
Exact external_id
      ↓
Alias Match
      ↓
Normalized Name Match
      ↓
Provider + Family Match
      ↓
Manual Review（进入 queue）
```

禁止 LLM 自动直接确认低置信模型映射。

低置信匹配进入：

```sql
entity_resolution_queue
-----------------------
id CHAR(36) PK

source_id CHAR(36) FK

record_type VARCHAR(32)
-- V1 固定为 model_variant；benchmark / endpoint resolution 在 V1b 后单独建模

external_id VARCHAR(256) NULL
external_name VARCHAR(256)

raw_payload JSON NULL
-- 该条外部记录原文

suggested_variant_id CHAR(36) NULL FK
suggested_release_id CHAR(36) NULL FK
-- 系统的最佳猜测，可为空

match_confidence DECIMAL(5,4) NULL
match_evidence JSON NULL
-- 命中原因明细：provider match / name match / release date mismatch ...

status VARCHAR(32)
-- pending / approved / rejected / created / mapped

resolution_note VARCHAR(512) NULL

version INT DEFAULT 1
resolved_by VARCHAR(128) NULL
resolved_at DATETIME NULL

created_at DATETIME
```

## 16.1 人工审核闭环

审核动作必须产生持久效果：

```text
Approve（确认建议映射）
→ 自动创建 model_alias
→ 下次同来源同名直接命中，不再进队列

Create New Model
→ 创建 canonical 实体 + alias
→ 仅允许对 Tracking Policy 白名单内的模型执行（见 36 节）

Map to Another Model
→ 创建 alias 指向人工指定的 variant

Reject
→ 记录，后续同记录不再重复入队（按 source + external_id 幂等）
```

queue 本身按 `(source_id, record_type, external_id)` 幂等，同一条外部记录不会重复堆积。

---

# 17. 变化检测

每日同步后执行：

```text
Current Snapshot
        ↓
Compare
        ↓
Previous Snapshot
        ↓
Diff
```

重点字段：

```text
New Model
Model Removed

Price Changed

Context Changed

New Benchmark

Benchmark Score Changed

New Capability

Status Changed
```

产生 model_event（带 snapshot 溯源）。

evaluation 分数变化时：**新增记录，不覆盖**。历史 evaluation 是资产。

---

# 18. Capability Score

V1 不做一个"万能综合排名"。

只做每个 Capability 的：

```text
Raw Evidence
Normalized Evidence
Capability Summary
```

例如 Coding：

```text
SWE-bench          75.4
LiveBench Coding   82.3
Aider              79.5
```

后台可以计算：

```text
coding_normalized_score
```

但必须：

```text
标明算法
标明数据源
标明更新时间
允许展开原始分数
```

不能显示：

```text
Model Score = 93
```

却无法解释 93 怎么来的。

---

# 19. 数据归一化（v0.3）

不同 Benchmark 的分数不能直接平均。

V1 流程：

```text
Benchmark Raw Score
      ↓
Benchmark-specific normalization
      ↓
Capability Aggregation
```

归一化和能力分属于可重算的派生数据，不回写不可变的 `evaluation` 表。

## 19.1 默认方法

```text
Min-Max within same benchmark version
```

（v0.1 的 percentile 方案废弃：V1 模型基数小，percentile 只是几个离散台阶，没有解释力。）

按 `benchmark_metric.score_direction` 处理方向；`normalization_method = none / custom` 的 Metric（如 Elo）不参与默认归一化。

## 19.2 样本数阈值

归一化必须达到最低样本量：

```text
n < 5
→ 不生成 normalized_score

5 <= n < 10
→ 生成，标记 low confidence

n >= 10
→ 正常使用
```

n = 同一 benchmark metric、同一可比 cohort 下有成绩的独立 model release 数量。同一 release 的多个 variant 默认只取产品定义的主 variant，避免重复加权。

## 19.3 Capability 聚合

```text
capability_score = Σ (normalized_score × benchmark_capability_map.weight)
                   ─────────────────────────────────────────────
                        Σ weight（仅计入有效 benchmark）
```

聚合结果必须携带：

```text
参与 benchmark 列表
各 benchmark 的 n 与 confidence
算法版本
计算时间
```

## 19.4 归一化与能力快照

每次重算创建独立版本：

```sql
normalization_run
-----------------
id CHAR(36) PK
algorithm VARCHAR(32)
algorithm_version VARCHAR(32)
cohort_definition JSON
as_of_time DATETIME
status VARCHAR(16)
created_at DATETIME

normalized_evaluation
---------------------
id CHAR(36) PK
normalization_run_id CHAR(36) FK
evaluation_id CHAR(36) FK
normalized_score DECIMAL(10,4)
sample_count INT
confidence VARCHAR(16)
created_at DATETIME

UNIQUE(normalization_run_id, evaluation_id)

capability_score_snapshot
-------------------------
id CHAR(36) PK
normalization_run_id CHAR(36) FK
model_variant_id CHAR(36) FK
capability_id CHAR(36) FK
score DECIMAL(10,4)
evidence_summary JSON
calculated_at DATETIME

UNIQUE(normalization_run_id, model_variant_id, capability_id)
```

页面默认读取最新成功的 `normalization_run`，同时展示 `as_of_time` 和算法版本。历史页面固定读取当时的 run，不能用今天的 cohort 重算后冒充历史变化。

---

# 20. 首页设计

## Header

```text
LLM Observatory

Dashboard
Models
Compare
Benchmarks
Evaluations
Timeline
Admin
```

---

## Dashboard 第一屏

### Latest Changes

```text
NEW MODEL
Claude X released

BENCHMARK
Model Y +8.7 Agentic Coding

PRICE
Model Z output price -30%

CONTEXT
Model X 200K → 1M
```

---

## 第二屏

### Capability Snapshot

```text
Reasoning
Coding
Agent
Long Context
Multimodal
Efficiency
```

不是"第一名排行榜"。

展示：

```text
Leading Models
Strong Alternatives
Recent Movers
```

---

## 第三屏

### Performance / Price

散点图：

```text
Y = Capability
X = Price
```

支持：

```text
Reasoning / Coding / Agent
```

切换。

---

# 21. Models 页面

采用 Data Table。

字段：

```text
Model
Provider
Release Date
Context
Reasoning
Vision
Tool Use
Price
Latest Eval
Status
```

筛选：

```text
Provider
Capability
Open Weight
Reasoning
Vision
Tool Calling
Release Date
Price
```

---

# 22. Model Detail 页面

页面结构：

```text
Model Header

Overview

Capability Profile

Benchmarks

Efficiency

Variants & Endpoints

Evidence

Release History

Related Models
```

---

## Model Header

```text
Claude X

Anthropic
Released Sep xx 2026

Reasoning
Vision
Tool Calling

Context 1M
```

---

## Capability Profile

不要只使用雷达图。

采用条形评分：

```text
Reasoning          █████████
Coding             ████████
Agent              ████████
Long Context       █████████
Vision             ████████
```

点击能力展开 Evidence。

Efficiency 区域按 Endpoint 维度展示价格与速度（同一模型不同渠道差异很大）。

---

# 23. Compare 页面

支持最多：

```text
5 Models
```

URL 使用稳定 ID 明确 Variant 与可选 Endpoint：

```text
/compare?
items=variantA@endpointA,variantB,variantC@endpointC
```

页面顶部始终显示当前比较的 Release、Variant、Endpoint 和数据时间点。缺失 Endpoint 时，Price / Performance 显示“请选择渠道”，不得自动展示跨渠道聚合值。

比较区域：

### Overview

### Specs

### Capability

### Benchmarks

### Price

### Performance

### Evidence

---

# 24. Benchmark Detail

例如：

```text
SWE-bench Verified
```

展示：

```text
它测什么

Benchmark Version

Dataset Size

Metric

Score Direction

Evaluation Method

Contamination Risk

Model Results

Historical Results
```

不要只是排行榜。

---

# 25. Evaluation 页面

两个 Tab：

```text
External Evaluations

Internal Evaluations
```

Internal：

```text
Evaluation Run
Model
Dataset
Framework
Date
Cost
Result
Status
```

---

# 26. 自己的 Evaluation Suite

V1 先建立四类：

```text
Coding

Reasoning

Agent

Chinese
```

目录：

```text
evals/

coding/
reasoning/
agent/
chinese/
```

使用 Promptfoo。

Promptfoo 当前仍然高频更新，且持续加入新的模型 provider、Agent API 和 tool 能力，因此适合作为 V1 自定义评测执行层。

每次执行创建 `evaluation_run`（run_type = internal），结果写入 `evaluation`。

---

# 27. lm-evaluation-harness 集成

作为标准 Benchmark Runner。

例如：

```text
POST /evaluation-runs
```

参数：

```json
{
  "engine": "lm_eval",
  "model_variant_id": "...",
  "model_endpoint_id": "...",
  "tasks": [
    "mmlu_pro",
    "gpqa",
    "ifeval"
  ]
}
```

Internal Evaluation 必须指定 Endpoint；服务端校验该 Endpoint 属于所选 Variant。请求还必须固定 dataset revision、seed 与 decoding config，或由版本化 suite 配置补齐。

执行结果自动进入：

```text
evaluation_run + evaluation
```

lm-evaluation-harness 当前已经支持插件式 backend、filter、metric 和 aggregation 注册，适合保持独立，不要 fork 修改核心源码。

---

# 28. 后端技术栈

```text
Python 3.12

FastAPI

SQLAlchemy 2

Pydantic v2

MySQL 5.7（兼容 8.0）

PyMySQL 驱动

Alembic

APScheduler（仅作触发器，编排见第 32 节）
```

V1 不强制使用 Celery，但长任务必须通过数据库任务表交给独立 worker，不能在 API 或 Scheduler 进程内执行。

什么时候需要 Celery：

```text
Evaluation 大规模并行
大量爬取任务
GPU Worker
```

再增加。

---

# 29. 前端与契约

```text
Next.js 15+

TypeScript

Tailwind CSS

shadcn/ui

TanStack Query

TanStack Table

ECharts
```

## 29.1 前后端契约

后端 Python 和前端 TypeScript **不共享 package**。契约链路：

```text
FastAPI Pydantic Schemas
        ↓
OpenAPI schema（唯一契约）
        ↓
openapi-typescript / Orval codegen
        ↓
generated/api-client（TS types + client）
```

前端禁止手写与后端重复的类型定义。

---

# 30. 项目结构

```text
llm-observatory/

apps/

  api/
    Python / FastAPI

  web/
    TypeScript / Next.js

packages/

  backend_core/
    Python
    domain/          SQLAlchemy models
    schemas/         Pydantic
    services/        业务逻辑

  ingestion/
    Python
    adapters/
      artificial_analysis.py
      openrouter.py
      livebench.py
    normalizers/
    entity_resolution/
    change_detection/
    pipeline/        DAG 编排

  evaluation/
    Python
    lm_eval/
    promptfoo/

generated/

  api-client/
    TypeScript（codegen 产物，不手改）

infra/

  docker/

data/

  raw/               snapshot 文件

  seeds/
    tracked_models.yaml
    tracked_benchmarks.yaml

evals/

  coding/
  reasoning/
  agent/
  chinese/

tests/

docs/
```

---

# 31. 后端 API

公共约定：

```text
Base Path      /api/v1
Pagination     cursor + limit，列表默认 50、最大 200
Time           ISO 8601 UTC
Error          RFC 9457 Problem Details
Tracing        每个响应返回 X-Request-ID
Versioning     破坏性变更升级 Base Path；字段新增保持向后兼容
Provenance     事实响应包含 source、observed_at、confidence、snapshot_id
```

以下路径均省略 `/api/v1` 前缀。

## Model

```text
GET /models

GET /models/{id}

GET /models/{id}/evaluations

GET /models/{id}/capabilities

GET /models/{id}/events

GET /models/{id}/endpoints
```

---

## Compare

```text
GET /compare/models

?items=variantA@endpointA,variantB
```

---

## Benchmark

```text
GET /benchmarks

GET /benchmarks/{id}

GET /benchmarks/{id}/results
```

---

## Timeline

```text
GET /events
```

筛选：

```text
type
provider
model
date
importance
```

---

## Sources & Pipeline

```text
POST /admin/sources/sync

GET  /admin/sources/status

GET  /admin/pipelines

GET  /admin/pipelines/{id}
```

---

## Admin: Resolution Queue

```text
GET  /admin/resolution-queue
     ?status=pending

POST /admin/resolution-queue/{id}/approve

POST /admin/resolution-queue/{id}/reject

POST /admin/resolution-queue/{id}/create-model

POST /admin/resolution-queue/{id}/map
     body: { "model_variant_id": "..." }
```

## 31.1 Admin 安全与审计

所有 `/api/v1/admin/**` 接口必须满足：

```text
Authentication  API token 或 OIDC session
Authorization   RBAC：viewer / editor / admin
Audit           记录 actor、action、target、before、after、request_id、timestamp
Concurrency     更新携带 version，使用 optimistic locking，冲突返回 409
Idempotency     同步触发、Approve、Create、Map 支持 Idempotency-Key
Protection      非浏览器 token 禁止写入前端包；Session 模式启用 CSRF 防护
```

新增审计表：

```sql
admin_audit_log
---------------
id CHAR(36) PK
actor_id VARCHAR(128)
action VARCHAR(64)
target_type VARCHAR(32)
target_id CHAR(36) NULL
before_value JSON NULL
after_value JSON NULL
request_id VARCHAR(64)
created_at DATETIME
```

生产环境默认关闭匿名 Admin 访问；个人本地部署也必须显式配置 admin token。

---

# 32. Pipeline 编排（v0.3）

v0.1 的固定时间表（01:00 / 01:30 / 02:00 ...）只是产品示意。独立 cron job 互相不知情，上游失败下游照样跑，会产生脏数据。

实际架构：**单一触发 + DAG 顺序编排**。

```text
Daily Trigger（APScheduler，建议 01:00 左右）
        ↓
┌─ Sync: Artificial Analysis ─┐
│  Sync: OpenRouter           │  顺序执行
│  Sync: Official Metadata    │┘
        ↓
Snapshot Validation
        ↓
Normalization
        ↓
Entity Resolution
        ↓
Data Validation
        ↓
Persist（幂等）
        ↓
Change Detection
        ↓
Capability Recalculation
```

规则：

```text
任何 critical stage 失败
→ 下游不执行
→ pipeline_run 标记 failed / partial
→ 记录 error_message
```

非 critical（如某个非核心 source 同步失败）可标记 partial 继续下游。

运行约束：

```text
1. Scheduler 作为独立单实例进程运行，不嵌入多 worker FastAPI 进程。
2. 每次触发先获取数据库 lease；同一 pipeline_type 同一时间只允许一个 active run。
3. lease 包含 owner_id、acquired_at、expires_at、heartbeat_at，进程崩溃后可恢复。
4. 每个 stage 定义 timeout、max_attempts、retry_backoff 和是否 critical。
5. 重启时扫描超时的 running stage：幂等 stage 可重试，其余标记 failed 等待人工处理。
6. Internal Evaluation 由独立 worker 拉取任务，不占用 API 或 Scheduler 进程。
```

## 32.1 pipeline_run

```sql
pipeline_run
------------
id CHAR(36) PK

pipeline_type VARCHAR(32)
-- daily_sync / manual / backfill

trigger VARCHAR(16)
-- schedule / manual

lease_owner VARCHAR(128) NULL
lease_expires_at DATETIME NULL
heartbeat_at DATETIME NULL

status VARCHAR(32)
-- pending / running / success / partial / failed

started_at DATETIME NULL
finished_at DATETIME NULL

error_message TEXT NULL

attempt INT
max_attempts INT
timeout_seconds INT NULL

created_at DATETIME
```

## 32.2 pipeline_stage_run

```sql
pipeline_stage_run
------------------
id CHAR(36) PK

run_id CHAR(36) FK

stage_name VARCHAR(64)
-- aa_sync / openrouter_sync / official_sync
-- normalize / resolve / persist
-- change_detect / capability_recalc

status VARCHAR(32)
-- pending / running / success / failed / skipped

detail JSON NULL
-- 处理条数、跳过原因等

error_message TEXT NULL

attempt INT
max_attempts INT
timeout_seconds INT NULL
retry_backoff_seconds INT NULL
critical BOOLEAN

started_at DATETIME NULL
finished_at DATETIME NULL
```

Orchestrator 是 packages/ingestion/pipeline 里的一个顺序状态机，不需要 Airflow / Celery。

V1 可以使用数据库任务表 + 独立 worker，不要求引入 Celery；但“无需 Celery”不等于允许在 Web 请求进程内执行长任务。

---

# 33. Intelligence Layer

V1 不让 LLM 自由生成模型评价。

采用：

```text
Structured Data
      ↓
Rules / Statistics
      ↓
LLM Summary
```

LLM 只能做：

```text
Summarization
Explanation
Comparison narrative
```

不能直接生成：

```text
Benchmark Score
Price
Model Specs
```

这些必须来自数据库。

---

# 34. 模型摘要

系统生成：

```text
Strength

Weakness

Best For

Recent Change
```

输入必须明确包含 Evidence。

输出保存：

```sql
generated_insight
-----------------
id CHAR(36) PK

model_variant_id CHAR(36) NULL FK

insight_type VARCHAR(32)
-- model_summary / comparison / change_brief

model_used VARCHAR(64)
prompt_version VARCHAR(32)

input_evidence_ids JSON
-- 仅作生成输入快照，不作为唯一关联关系

content MEDIUMTEXT

generated_at DATETIME
```

同时写入强关联表：

```sql
generated_insight_evidence
--------------------------
generated_insight_id CHAR(36) FK
evidence_id CHAR(36) FK
PRIMARY KEY (generated_insight_id, evidence_id)
```

---

# 35. 数据可信度

每条数据必须有：

```text
source
retrieved_at
source_type
confidence
```

落库约定：事实表直接或通过其 run 关联以下 provenance 字段：

```text
source_id
source_snapshot_id
observed_at（UTC）
confidence
ingestion_run_id
```

`source_type` 由 `source_id` 关联获得，避免冗余不一致。API 输出统一展开这些字段；缺少必要 provenance 的数据不得进入面向用户的默认视图。

不存在适用于所有字段的全局来源排名。`source.reliability_level` 只表示来源基础可靠度，最终 canonical 选择必须使用字段级 Source Policy：官方来源通常是产品规格与官方价格的权威，独立评测通常是能力分数的优先来源，聚合器主要用于发现和交叉校验。

## 35.1 字段级 Source Policy

不同字段应有不同优先策略：

```text
Model Specs（context / max output）:
Official > AA > OpenRouter

Pricing:
Official Endpoint > AA > OpenRouter

Benchmark:
Independent Eval > Vendor Eval
```

## 35.2 事实冲突处理

冲突是常态，不是异常：

```text
Official docs:  context = 1M
OpenRouter:     context = 200K
AA:             context = 1M
```

系统不能让"最后一次同步"盲目覆盖。

## 35.3 field_observation（v0.2 新增，V1 简化实现）

V1 对白名单字段记录所有来源的观察值，canonical 值由 sync 时按 35.1 的字段级 policy 物化到实体列上：

```sql
field_observation
-----------------
id CHAR(36) PK

entity_type VARCHAR(32)
-- model_variant / model_endpoint

entity_id CHAR(36)

field_name VARCHAR(64)
-- V1 白名单: context_window / max_output_tokens

value VARCHAR(256)

source_id CHAR(36) FK
source_snapshot_id CHAR(36) NULL FK

observed_at DATETIME
confidence VARCHAR(16)
ingestion_run_id CHAR(36) NULL FK

created_at DATETIME
```

V1 范围：

```text
只写白名单字段
读取走实体上的 canonical 列（物化）
观察表用于审计与冲突排查
```

V2 再扩展：全字段覆盖、冲突对比 UI、多值并存展示。

Pricing 天然有时间版本表（第 11 节），不进此机制。

---

# 36. Seed 与 Tracking Policy（v0.2 新增）

外部同步只负责**发现候选**，不负责**创建模型**。

否则一次 OpenRouter 同步会创建上千个模型实体。

## 36.1 流程

```text
Source Discovery
      ↓
Candidate Models（进 resolution queue）
      ↓
Seed Selection（人工确认）
      ↓
Canonical Registry
```

## 36.2 tracked_models.yaml

第一批 20–30 个模型由人工维护的种子文件确定，进版本库：

```yaml
# data/seeds/tracked_models.yaml
- release_slug: claude-x
  family: claude
  provider: anthropic
  release_date: 2026-09-01
  tiers: [frontier]

- release_slug: gpt-x
  family: gpt
  provider: openai
  tiers: [frontier, popular]
```

筛选原则：

```text
Provider ∈
OpenAI / Anthropic / Google / DeepSeek
Alibaba / Meta / xAI / Mistral

AND

status = active

AND

( frontier OR popular OR representative OR recently_released )
```

## 36.3 同步行为规则

```text
外部模型 ID 命中 alias
→ 正常关联，更新数据

未命中 且 属于 tracked 集合（通过规则匹配）
→ 进 resolution queue，人工确认后创建

未命中 且 不属于 tracked 集合
→ 进 resolution queue 标记为 untracked candidate
  默认不创建，仅记录（供未来扩充 tracked 集合参考）
```

---

# 37. V1 模型数量

第一阶段：

```text
20–30 个模型
```

覆盖主要 Provider。

不要追求全部模型。

原则：

```text
Frontier
Popular
Representative
Recently Released
```

以 tracked_models.yaml 为准。

---

# 38. V1 Benchmark 数量

目标：

```text
10–20
```

重点覆盖：

```text
Reasoning

Coding

Agent

Long Context

Multimodal

Instruction Following
```

不是 Benchmark 越多越好。

---

# 39. 开发优先级

V1 分阶段交付，每阶段都必须可运行、可回滚、可独立验收：

```text
V1a  Registry + 单一核心来源 + 原始 Evaluation + 基础 Compare
V1b  多来源解析 + Resolution Queue + Timeline
V1c  版本化归一化 + Capability
V1d  少量关键模型的 Internal Evaluation
```

V1a 是首个可发布 MVP；V1b–V1d 不阻塞 V1a 上线。每个阶段进入下一阶段前，必须达到第 1.2 节对应的数据质量指标。

## Sprint 1

数据库 + Registry。

实现：

```text
Provider
Model Family
Model Release
Model Variant
Model Endpoint
Model Alias
Source

Alembic + MySQL 连接 + .env
```

验收：

```text
可以正确保存和查询 20 个模型（含 variant 与 endpoint）。
所有表 utf8mb4，迁移可重放。
```

---

## Sprint 2

外部数据同步 + Entity Resolution。

实现：

```text
Artificial Analysis Adapter（tier 感知 + 降级）
Raw Snapshot（外置载荷 + source_snapshot 元数据表）
Normalizer
Entity Resolution + resolution queue
Pipeline DAG 骨架（pipeline_run / pipeline_stage_run）
Admin: 同步触发 / 状态 / 队列 API
```

验收：

```text
同步成功且不产生重复模型。
未知模型进入队列而非直接创建。
Approve 后自动生成 alias，二次同步直接命中。
AA 不可用字段按 tier 降级且记录在 sync 日志。
```

---

## Sprint 3

Benchmark + Evaluation。

实现：

```text
Benchmark Registry（含 score_direction / normalization_method）
Evaluation Run / Result 拆分
Identity Hash + Observation Fingerprint 幂等与历史版本
Benchmark Metric
External Scores 入库
```

验收：

```text
模型详情页能看到专业评测，每条分数可追溯 source + snapshot。
重复同步不产生重复 evaluation。
来源改分时新增 observation 且正确关联 supersedes，不覆盖历史。
```

---

## Sprint 4

Compare。

实现：

```text
2–5 Model Compare
Specs
Benchmark
Price（按 Endpoint）
Performance
```

---

## Sprint 5

Capability。

实现：

```text
Capability Taxonomy
Benchmark Mapping
Min-Max 归一化 + 样本数阈值
Normalization Run + Normalized Evaluation + Capability Score Snapshot
```

---

## Sprint 6

Timeline + Change Detection。

实现：

```text
Snapshot Diff
Price Change
New Model
Benchmark Change
model_event 溯源（run + snapshot）
Dashboard Latest Changes
```

---

## Sprint 7

Own Eval。

接入：

```text
Promptfoo
lm-evaluation-harness
```

结果写入 evaluation_run + evaluation。

V1d 仅选择 3–5 个关键模型和少量固定任务，先验证可复现性、成本记录和独立 worker 稳定性；不追求大规模并行。

---

# 40. MVP 验收标准

## 40.1 V1a 发布门槛

1. 可以查看 20 个种子模型的 Release、Variant 与 Endpoint。
2. 至少一个核心来源可以自动同步，并按 key tier 静默降级。
3. Raw Snapshot 可由数据库 metadata 定位并通过 checksum 校验。
4. 外部 Evaluation 可入库；重复重放不重复，来源改分不覆盖历史。
5. 每条公开展示的 Evaluation 均可追溯到 source、snapshot、benchmark version 和 metric。
6. 可以选择至少两个明确的 Variant 进行 Specs 与 Benchmark 比较。
7. 价格和性能仅按明确 Endpoint 比较，不静默混合渠道。
8. Admin 接口默认需要认证，关键写操作产生审计记录。
9. Pipeline stage 状态可查，critical stage 失败阻断下游，崩溃后可识别并恢复 stale run。

## 40.2 V1b 验收

1. 多来源 Alias 不重复生成 canonical Model，未知模型进入人工队列。
2. Resolution Queue 可 Approve / Reject / Create / Map；操作支持幂等和并发冲突检测。
3. Approve 后自动生成 Alias，二次同步直接命中。
4. 可以查看模型发布、价格和 Benchmark 变化，且 Event 关联业务主体与 before/after snapshot。

## 40.3 V1c 验收

1. 可以查看版本化 Capability，展示样本数、置信标记、算法版本和 as-of time。
2. 同一 normalization run 可重复计算得到相同结果。
3. 新增模型只创建新的 run，不修改旧 run 的历史分数。
4. 所有聚合分均可展开到参与的原始 Evaluation。

## 40.4 V1d 验收

1. 可以通过独立 worker 执行 Promptfoo 或 lm-evaluation-harness 任务。
2. Evaluation Run 记录 Endpoint、数据集 revision、seed、配置、运行环境和成本。
3. 同一固定配置可复跑，结果差异可解释并保留为不同 observation。
4. API/Scheduler 重启不丢失任务，也不会重复计费执行已成功任务。

## 40.5 非功能验收

1. 达到第 1.2 节的数据质量和时效性指标。
2. 所有数据库时间使用 UTC，所有表和连接使用 utf8mb4。
3. Alembic 可在空库完整升级，并可从上一发布版本回滚。
4. 核心写入路径具备并发与幂等测试，核心查询具备最小性能基准。
5. Git 仓库不包含 `.env`、API Key、数据库地址或 Raw Snapshot。

---

# 41. Coding Agent 开发约束

给开发 Agent 的明确要求：

## 不允许

* 不要修改数据 Schema 含义。
* 不要擅自添加微服务。
* 不要把所有东西塞进一个表。
* 不要使用 LLM 生成事实数据。
* 不要绕过 retention / license policy 擅自删除或永久保留 Raw Snapshot。
* 不要直接覆盖历史价格。
* 不要直接覆盖历史 evaluation 分数（变化=新增记录）。
* 不要假定模型名称唯一。
* 不要让外部同步自动创建 canonical 模型实体。
* 不要把 Benchmark 分数直接做简单平均。
* 不要在 V1 引入 Kubernetes。
* 不要引入复杂消息队列。
* 不要做过度抽象。
* 不要在代码或文档中硬编码数据库密码。
* 不要使用 MySQL 8.0 专属 SQL 特性（目标实例 5.7）。

---

## 必须

所有外部数据：

```text
Raw
→ Normalize
→ Resolve
→ Validate
→ Persist（幂等）
```

所有 Evaluation：

```text
Score
+
Source
+
Method
+
Version
+
Identity Hash
+
Observation Fingerprint
+
Reproducibility Config
```

所有变化：

```text
Old Value
+
New Value
+
Timestamp
+
Snapshot 溯源
```

所有数据库写入：

```text
显式 utf8mb4
应用层生成 UUID
应用层校验（不依赖 MySQL CHECK）
```

---

# 42. 开发原则

整个项目围绕一句话：

> Track facts, preserve evidence, understand capability, detect change.

中文：

> 跟踪事实、保留证据、理解能力、发现变化。

系统真正的资产不是 UI。

真正的资产是：

```text
Model Registry

Evaluation History

Evidence

Capability Taxonomy

Historical Change
```

这些数据积累一年之后，价值会远大于页面本身。

---

# 43. V1 成功后的 V2

后续再考虑：

```text
Paper Tracking

Technical Report Extraction

AI News Intelligence

GitHub Release Tracking

Community Signal

RAG

Model Recommendation

Agent Benchmark

Arena Mode

Custom Leaderboards

Personal AI Research Assistant

field_observation 全字段冲突对比 UI
```

长期方向：

```text
LLM Observatory
        ↓
AI Model Observatory
        ↓
AI Capability Observatory
```

最终不只是跟踪模型，而是跟踪：

```text
Models
Agents
Coding Agents
Deep Research
Computer Use
Image
Video
Audio
```

但 V1 不提前实现。
