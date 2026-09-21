# Design QA

- Source visual truth: `C:\Users\01416344\.codex\generated_images\01a0bceb-44e9-7843-ab10-fbe9052fbad9\exec-352bbee2-fbf9-4e8e-babc-b64e56188092.png`
- Implementation screenshots: `qa/overview.png`, `qa/catalog.png`, `qa/compare.png`, `qa/benchmarks.png`, `qa/mobile.png`
- Desktop viewport: 1440 x 1024 CSS px; mobile viewport: 390 x 844 CSS px
- Scope: all four primary sections, model selection, comparison, benchmark detail, and mobile behavior
- Data state: FastAPI/MySQL live response with 20 tracked releases, 17 benchmarks, and Artificial Analysis snapshot-backed scores

## Evidence

- The selected light “Model Atlas” direction remains intact: cool-gray canvas, crisp white surfaces, restrained blue accents, compact metadata, and dense but readable tables.
- Overview now gives the previously inactive entry a useful job: recent changes, a watchlist, and benchmark movement, all scoped to the latest 90 days.
- Models keeps the six-row catalog and exposes the selected models immediately below the filters. The 0/1/2+ states provide explicit guidance and the action is enabled only when comparison is valid.
- Compare supports direct navigation with a useful empty state and a complete two-model state with variant, endpoint, benchmark, and provenance context.
- Benchmarks now provides a searchable/filterable registry and in-page detail instead of a dead navigation item.
- All four top-level actions update the URL (`/`, `/models`, `/compare`, `/benchmarks`) and active navigation state.
- Chromium regression coverage passed for navigation, filtering, empty search, model selection, comparison, benchmark expansion, and mobile layout.
- The header displays `真实数据` only after successful API loading. The model table and comparison now use AA Intelligence, Coding, and Agentic index values from the stored snapshot rather than the static sample scores.
- Browser console errors: 0.
- Mobile has no page-level horizontal overflow. The technical model table intentionally scrolls inside its bounded surface.

## Comparison history

1. The first implementation matched the selected catalog visual but left Overview and Benchmarks inactive and placed selected models in a fixed bottom shelf.
2. The UX audit reproduced both issues at desktop size and documented the hidden-selection risk.
3. The current pass implemented meaningful Overview and Benchmarks pages, stable routes, direct Compare guidance, and a selection dock beneath the filters.
4. Visual review at desktop and mobile found no clipping, broken hierarchy, or inaccessible active state.

## Findings

- No actionable P0, P1, or P2 issues remain.
- P3: provider marks differ slightly from the generated reference because official marks from the selected icon library are used.
- P3: the mobile data table uses contained horizontal scrolling to preserve technical columns.

## Verification

- [x] Production build passes.
- [x] Sites packaging and route fallback tests pass.
- [x] Browser interaction test passes with zero console errors.
- [x] Desktop overview, catalog, compare, and benchmark screenshots inspected.
- [x] Mobile selected-model state inspected.

final result: passed
