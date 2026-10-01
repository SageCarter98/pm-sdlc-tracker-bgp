# Render-timing and page-weight performance budgets (WP12 / REQ-043)

CI-blocking check for the render-timing (LCP/INP/CLS) and page-weight part of
REQ-043 (Blueprint Sec.6). This is the second of REQ-043's three numeric
sub-parts:

1. API p95/p99 latency — `backend/tests/test_dec08_performance_budgets.py`.
2. Render-timing and page-weight budgets — **this directory.**
3. Export streaming ("asynchronous; must begin streaming within 2 s") —
   `backend/tests/test_wp12_render_and_export_budgets.py`.

The first and third are plain pytest, since they don't need a real browser.
This one does — Lighthouse's LCP/INP/CLS/byte-weight audits require an actual
rendering engine, which is why it's a separate Node harness instead of a
fourth pytest module.

## Where the numbers come from

Every budget number below is DEC08 Q14/Q16's own wording, not this script's
invention — see
`docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md` lines
162–181:

| Budget | Value | DEC08 source |
| --- | --- | --- |
| Primary profile | mid-range Android on Fast 3G (1.6 Mbps, 150 ms RTT) | Q14 |
| Degraded profile | low-end Android on Slow 3G (400 kbps, 400 ms RTT), "must stay usable, not fast" | Q14 |
| LCP, primary | ≤ 2.5 s (DEC08) — CI enforces ≤ 4.0 s | Q16 |
| LCP, degraded | ≤ 5 s (DEC08) — CI enforces ≤ 8.0 s | Q16 |
| INP | ≤ 200 ms | Q16 |
| CLS | ≤ 0.1 | Q16 |
| Critical render path | ≤ 170 KB compressed | Q16 |
| Total first load | ≤ 350 KB | Q16 |
| Heaviest authoring screen | ≤ 1 MB | Q16 |
| Blocking requests before first render | ≤ 2 | Q16 |

The `primary` profile's network numbers match Lighthouse's own built-in
`mobileSlow4G` throttling preset (`lighthouse/core/lib/lantern`'s simulation
constants: `rttMs: 150`, `throughputKbps: 1.6 * 1024`) — confirmed by reading
that preset's source, not assumed. The `degraded` profile's CPU multiplier (8,
vs. primary's 4) is this script's own calibration choice, not a DEC08 or
Lighthouse constant — DEC08 names the network numbers for the degraded case
explicitly but not a separate CPU slowdown, so doubling the primary profile's
multiplier is flagged here rather than silently assumed.

Q14 also names three other configurations (an older iPhone on 4G, desktop
broadband, 320/360 px viewports, 400% zoom reflow for WCAG 1.4.10) that this
script does **not** cover — those are usability-testing device/viewport
conditions, not render-timing budgets, and belong with the manual usability
sample (Q13), not a CI gate.

**LCP's CI-enforced numbers are looser than DEC08's own**, by a `CI_RUNNER_VARIANCE_MARGIN`
(currently 1.6x) defined in `check.mjs`. This is a CI-measurement tolerance
for GitHub-hosted runner variance (see "Known limitations"), not a change to
what DEC08 actually approved — any further change to that margin should go
through DEC08's UX/technical leads, not be treated as a routine code tweak.

## Pages measured

Five representative pages, not all ~16 `/ui` routes — DEC08 asks for budgets
to be "tested and reported", not an exhaustive per-page audit:

- `login` — one unauthenticated page.
- `orgs-list` — a list view.
- `my-work` — a cross-tenant dashboard.
- `gate-dashboard` — a per-project dashboard.
- `evidence-form` — DEC08's own named page-weight outlier ("heaviest
  authoring screen"); also the one page INP is measured against, since it's
  the one screen with a genuine client-side interaction (see below).

## How it runs

```
cd tools/perf-budgets
npm install        # one-time
npm run check       # BGP_PERF_BASE_URL defaults to http://127.0.0.1:8000
```

It needs a running dev server (real Postgres behind it) at `BGP_PERF_BASE_URL`
— it is not self-starting. The script then, via Puppeteer + a real headless
Chrome (not Lighthouse's own CLI):

1. Registers a throwaway user, logs in, creates an org, imports and publishes
   the repo's standard synthetic fixture
   (`fixtures/synthetic/frameworks/standard.json` — the same fixture every
   Python test uses), and creates a project from it. This is real
   application data, not a hand-rolled page.
2. For each of the two network/CPU profiles, navigates to each of the five
   pages 3 times and runs Lighthouse's `largest-contentful-paint`,
   `cumulative-layout-shift`, `first-contentful-paint`, `total-byte-weight`,
   `network-requests` and `render-blocking-insight` audits under
   `throttlingMethod: 'simulate'` each time, budget-checking the median of
   the 3 — `throttlingMethod: 'simulate'` still derives its numbers from one
   real captured trace, so confirmed on real CI runs (not just a local
   machine): two runs of the exact same commit on GitHub-hosted runners
   produced primary-profile LCPs of ~1.4s and ~2.6s. "Simulate" is not the
   deterministic escape hatch its name implies, hence the same multi-sample
   discipline `test_dec08_performance_budgets.py` already uses for its own
   latency numbers, applied here too.
3. For `evidence-form` only, additionally measures INP in `timespan` mode
   under real (`devtools`) throttling, also 3 times, budget-checking the
   median.
4. Prints a JSON report of every measurement, then exits non-zero and lists
   each specific breach if any budget was missed.

In CI this is its own job/step (see the repo's `.github/workflows/ci.yml`),
not a dashboard — DEC08's own words: "enforced in CI as a blocking budget
check, not a dashboard someone reads occasionally."

## The INP interaction

INP is only computable by Lighthouse under real (`devtools`) throttling in
`timespan` mode, with a genuine user interaction happening during the
recording — `lighthouse/core/audits/metrics/interaction-to-next-paint.js`
returns `{notApplicable: true}` outright when `throttlingMethod` is
`'simulate'` ("responsiveness isn't yet supported by lantern"). The
interaction used is real, not contrived: typing into the evidence form's
`#reference` field fires a real `input` event handler
(`backend/app/templates/evidence_form.html`'s `sync()`) — the one genuine
client-side interaction this app's progressive-enhancement design actually
has. There is no click-and-navigate substitute standing in for it.

## Known limitations

- **Five pages, not all routes.** See "Pages measured" above.
- **Even with median-of-3, expect some run-to-run variance**, more so for
  INP (real `devtools` throttling) than for LCP/CLS/bytes (`simulate`
  throttling) — simulate reduces the *within-run* variance a lot (median-of-3
  samples landed within ~3ms of each other across every page in a given
  run), but does nothing about *which GitHub-hosted runner VM* a job lands
  on. Confirmed 2026-10-01 on PR #9: two single-trigger CI runs of the exact
  same commit landed on runner tiers ~1.77–1.99x apart in CPU speed
  (heavier pages amplify the gap more). `CI_RUNNER_VARIANCE_MARGIN` in
  `check.mjs` is this script's answer to that — see "Where the numbers come
  from" above — not a claim that the underlying noise is gone.
- **The degraded profile's CPU multiplier is a calibration choice**, not a
  DEC08 number — see "Where the numbers come from".
- **The critical-render-path byte figure is this script's own operational
  definition**, not a single built-in Lighthouse audit: bytes from every
  request that finished before first paint. Blocking-request *count*, by
  contrast, comes straight from Lighthouse's own `render-blocking-insight`
  audit (the current replacement for the older `render-blocking-resources`),
  which identifies requests placed to actually delay first paint — not
  merely ones that happened to finish downloading before FCP. An earlier
  version of this script used a "finished before FCP" heuristic for the
  blocking-request count too, which over-counted: a bottom-of-body script
  that downloads fast on a local connection finishes before FCP without
  being render-blocking at all. `base.html`'s two head stylesheets (Google
  Fonts, `/static/style.css`) are the actual render-blocking resources.
- **Needs a real running dev server with a real Postgres behind it** — there
  is no mocked/offline mode. A broken or unseeded dev server shows up as a
  setup failure before any budget is even checked, not a budget breach.
- **Headless Chrome + Lighthouse is memory-heavy.** On a memory-constrained
  machine, running this alongside the dev server, Postgres and an IDE can
  trigger an OOM kill of the Node process itself — a resource failure, not a
  code or budget failure. CI runners have far more headroom than a small
  local dev machine; a local OOM here is not evidence the harness or budgets
  are broken.
