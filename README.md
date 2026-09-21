# LLM Observatory (model-radar)

Personal LLM tracking / evaluation / comparison system. V1a scope:
**Registry + single core source (Artificial Analysis) + raw Evaluation + basic Compare**.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · MySQL 5.7 (utf8mb4, InnoDB, naive-UTC DATETIME)
· Alembic · PyMySQL · httpx · APScheduler · pytest

## Layout

```
packages/backend_core   # domain models, config, db, services (fingerprints, upsert)
packages/ingestion      # AA adapter, normalizers, entity resolution, sync pipeline
apps/api                # FastAPI app (public read + admin ops)
apps/web                # React/Vite product UI (model catalog + compare)
scripts/                # seed, migrations runner, sync, scheduler
data/seeds/             # tracked_models / tracked_benchmarks / capabilities (YAML)
data/raw/               # raw source snapshots (never committed)
tests/                  # unit + DB integration tests (model_radar_test)
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env    # fill in real values; .env is gitignored
```

`AA_API_KEY` is required for the Artificial Analysis v2 API, including its
free tier. The adapter uses `https://artificialanalysis.ai/api/v2` by default.

## Daily flow

```powershell
# 1. migrations (baseline schema)
python -m alembic upgrade head

# 2. seed registry (idempotent)
python scripts/seed.py

# 3. run tests (uses model_radar_test)
python scripts/create_test_db.py     # once
$env:DB_NAME="model_radar_test"; python -m pytest

# 4. start API
python -m uvicorn api.main:app --port 8000

# 5. sync data
python scripts/run_sync.py --dry-run   # peek at what AA returns
python scripts/run_sync.py             # full pipeline
python scripts/scheduler.py            # or scheduled daily sync
```

## Web product preview

```powershell
cd apps/web
npm install
npm run dev -- --port 4173
```

Open `http://localhost:4173/`. In local development Vite proxies `/api` to the
FastAPI service on port 8000. The UI loads the MySQL-backed registry and the
latest Artificial Analysis snapshot; if the API is unavailable it falls back
to clearly labelled demo data.

## API surface (V1a)

Public (no auth):
- `GET /health`
- `GET /api/v1/models` — cursor-paginated (`?cursor=&limit=&provider=&q=`)
- `GET /api/v1/models/{slug}` — release + variants + endpoints
- `GET /api/v1/models/{slug}/evaluations`
- `GET /api/v1/benchmarks`, `GET /api/v1/benchmarks/{slug}`
- `GET /api/v1/compare/models?items=variantA@endpointA,variantB`

Admin (`X-Admin-Token` header, single token; RBAC deferred):
- `GET /api/v1/admin/resolution-queue?status=pending`
- `POST /api/v1/admin/resolution-queue/{id}/approve | reject | map?variant_id= | create-model`
- `GET /api/v1/admin/pipelines`
- `POST /api/v1/admin/sync` — enqueues a manual run record; the scheduler consumes it

Errors are RFC 9457 `application/problem+json`; every request gets an
`X-Request-ID` (echoed or generated).

## Design invariants

- **Evaluation rows are immutable.** Identity = `evaluation_identity_hash`
  (Model × Benchmark × config); replay → skip; unchanged score in a new
  snapshot → re-confirm (skip); changed score → new row superseding the old.
- **External syncs never create models.** Unmatched names go to
  `entity_resolution_queue` for manual review; `create-model` is the only
  creation path, and every admin mutation writes `admin_audit_log`.
- **Curated seed models start as `preview`.** They are intentionally excluded
  from public active-model listings until their provenance is verified.
- **Raw payloads live outside the DB** (`data/raw/<source>/<sha256>.json`),
  referenced by checksummed `source_snapshot` rows; never committed to Git.
- **UUIDv7 primary keys** — cursor pagination rides on lexicographic order.
- **MySQL 5.7 constraints** — no CHECK/functional indexes/CTEs; app-layer
  validation; every table InnoDB + utf8mb4_unicode_ci; connections pinned to UTC.

## Spec

`LLM Observatory V1 产品与技术设计规格.md` (v0.3) is the frozen baseline.
