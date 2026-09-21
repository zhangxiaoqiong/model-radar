# Design QA

- Source visual truth: `C:\Users\01416344\.codex\generated_images\01a0bceb-44e9-7843-ab10-fbe9052fbad9\exec-352bbee2-fbf9-4e8e-babc-b64e56188092.png`
- Implementation screenshots: `qa/catalog.png`, `qa/compare.png`, `qa/mobile.png`
- Viewport: 1440 × 1024 CSS px, device scale factor 1
- State: model catalog with GPT-5.2 and Gemini 2.5 Pro selected; two-model comparison
- Source pixels: 1488 × 1058
- Implementation pixels: 1440 × 1024
- Density normalization: both images have an equivalent 1.406 aspect ratio; the source was visually compared at the implementation's 1440 × 1024 display scale.

## Evidence

- Full-view comparison: the implementation preserves the source hierarchy and proportions—top navigation, restrained hero, single filter surface, six-row data table, provenance footer, and fixed comparison shelf. The reduced filter count is an intentional response to the request for a concise implementation.
- Focused-region comparison: separate crops were unnecessary because table typography, capability bars, provider marks, selected rows, footer provenance, and shelf controls are legible in the original-resolution captures.
- Fonts and typography: system/Chinese sans-serif fallback closely matches the neutral source hierarchy; headings, table labels, metadata, and numeric emphasis remain readable.
- Spacing and layout: 28–30 px outer margins, compact 68 px navigation, table row rhythm, filter alignment, and bottom shelf match the source's density without clipping.
- Colors and tokens: cool gray surface, ink text, blue selection/action states, teal capability marks, and green availability/best-score semantics match the reference direction with accessible contrast.
- Image and icon quality: no raster placeholders or handcrafted SVGs are used; Phosphor and Simple Icons provide crisp interface/provider marks.
- Copy and content: the three-month window, explicit variant/endpoint labels, source confidence, and demo-data disclosure are visible.
- Primary interactions tested in Chromium: provider filter, empty search result, two-model selection, enter comparison, return to catalog.
- Browser console errors: 0.
- Responsive check: 390 × 844 catalog has no page-level horizontal overflow; the dense data table scrolls within its own surface and the primary compare action remains visible.

## Findings

- No actionable P0, P1, or P2 issues remain.
- P3: provider marks differ slightly from the generated reference because official marks available in the selected icon library were used instead of approximated artwork.
- P3: the mobile table intentionally uses contained horizontal scrolling rather than collapsing technical comparison columns.

## Comparison history

1. Initial pass was blocked because no browser-rendered capture existed.
2. Chromium authorization enabled catalog and compare captures. The pass found two product-level issues: mock data was not disclosed and removing a model could leave an invalid one-item comparison.
3. Added an `演示数据` label and automatic return to the catalog below two comparison items. Rebuilt, reran browser interactions, captured both states, and confirmed zero console errors.

## Implementation checklist

- [x] Source and implementation compared at equivalent aspect ratio.
- [x] Core list/filter/select/compare flow works.
- [x] Three-month scope and provenance are visible.
- [x] Build, Sites packaging tests, and browser QA pass.

final result: passed
