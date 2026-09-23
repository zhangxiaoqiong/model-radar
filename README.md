# Model Radar

面向大模型数据分析与可视化的轻量数仓。数据链路采用
**ODS（按来源保真）→ DWD（统一分析明细）→ ADS（首页宽表）**。

## 数据模型

共 9 张业务表：

- ODS：`ods_aa_model`、`ods_aa_evaluation`、`ods_openrouter_model`
- DWD：`dwd_model`、`dwd_model_evaluation`、`dwd_model_price`、`dwd_model_performance`
- ADS：`ads_model_wide`
- 调度控制：`etl_batch`

ODS 保留源字段和原始 JSON；DWD 统一模型身份、评测、价格和性能；
ADS 每日生成一行一个模型版本的分析快照，直接供首页、排名和对比使用。

## 初始化

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
python -m alembic upgrade head
```

开发环境需要彻底重建时：

```powershell
python scripts/reset_warehouse.py
```

该命令会删除配置数据库中的全部旧表和数据，并创建当前 9 张数仓表。

## 数据同步

```powershell
python scripts/run_sync.py --dry-run
python scripts/run_sync.py
```

同步过程先写入 AA 和 OpenRouter 的 ODS 表，再生成 DWD 明细，最后刷新
`ads_model_wide`。所有 DWD 事实均保留来源表、来源记录 ID 和批次 ID。

## 运行

```powershell
python -m uvicorn apps.api.main:app --port 8000
cd apps/web
npm install
npm run dev
```

## 验证

```powershell
python -m pytest
python -m alembic check
cd apps/web
npm test
npm run build
```
