# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Product decisions

- Visual direction: the selected light “Model Atlas” catalog concept.
- Keep the product concise and efficient; prioritize the model catalog and compare flow.
- Default all visible data and freshness filters to the latest three months.
- Keep all four primary sections (Overview, Models, Compare, Benchmarks) visible and functional; each section must have its own stable URL and meaningful content.
- Show selected models directly below the model filters, with clear 0/1/2+ guidance; never hide the active selection only at the bottom of the viewport.
- Prefer the FastAPI/MySQL dataset and label it as real data only after a successful API response; use the static dataset solely as an explicitly labelled fallback.
- Homepage charts should help users shortlist models: capability versus input price with a Pareto frontier, a dimension-switchable ranking, capability versus output speed, and input/output price bars. Use actual loaded data. Weekly release counts are not useful here; historical trends require historical observations.
- The homepage ranking uses models on the x-axis and raw scores on the y-axis. Show one selected metric at a time (Intelligence, Coding, or Agentic), descending, with visible score labels. Detailed multi-dimension comparison belongs in the comparison flow. Avoid combining redundant rankings or implying that different benchmark indices share the same meaning.
