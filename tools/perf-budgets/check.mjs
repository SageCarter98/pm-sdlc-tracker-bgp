// WP12 / REQ-043 (Blueprint Sec.6): render-timing (LCP/INP/CLS) and
// page-weight budgets, DEC08 Q14/Q16 (docs/blueprint/
// BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md). See README.md for the
// numbers' provenance and this script's known limitations.
//
// Boots a real authenticated session against a running dev server (via
// Puppeteer + real Chrome, reusing cookies for both JSON-API setup calls
// and the /ui pages measured), runs Lighthouse against each target page
// under two network/CPU profiles, and exits non-zero if any budget is
// breached -- this is the CI-blocking check, run as its own job
// (.github/workflows/ci.yml's "Render-timing and page-weight budgets"
// step), not a dashboard someone reads occasionally (DEC08's own words).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as chromeLauncher from 'chrome-launcher';
import lighthouse, { startTimespan } from 'lighthouse';
import puppeteer from 'puppeteer-core';

const BASE_URL = process.env.BGP_PERF_BASE_URL || 'http://127.0.0.1:8000';

// Same real synthetic framework fixture every Python test in this repo
// uses (backend/tests/test_projects.py's FIXTURES_DIR) -- not a
// hand-rolled schema, so it's guaranteed to satisfy whatever the real
// template importer validates.
const FIXTURE_PATH = fileURLToPath(
  new URL('../../fixtures/synthetic/frameworks/standard.json', import.meta.url),
);

// DEC08 Q14: device/network profiles. "primary"'s numbers are Lighthouse's
// own built-in `mobileSlow4G` throttling preset (lighthouse/core/lib/
// lantern's Simulation Constants) -- confirmed by inspecting that preset's
// source: rttMs 150, throughputKbps 1.6*1024, which is DEC08's own "mid-
// range Android on Fast 3G (1.6 Mbps, 150 ms RTT)" word for word, not a
// coincidence this script relies on without having checked.
const DEVTOOLS_RTT_ADJUSTMENT_FACTOR = 3.75;
const DEVTOOLS_THROUGHPUT_ADJUSTMENT_FACTOR = 0.9;

function throttlingFor(rttMs, throughputKbps, cpuSlowdownMultiplier) {
  return {
    rttMs,
    throughputKbps,
    requestLatencyMs: rttMs * DEVTOOLS_RTT_ADJUSTMENT_FACTOR,
    downloadThroughputKbps: throughputKbps * DEVTOOLS_THROUGHPUT_ADJUSTMENT_FACTOR,
    uploadThroughputKbps: throughputKbps * DEVTOOLS_THROUGHPUT_ADJUSTMENT_FACTOR,
    cpuSlowdownMultiplier,
  };
}

const PROFILES = [
  {
    key: 'primary',
    label: 'primary: mid-range Android on Fast 3G (1.6 Mbps, 150 ms RTT)',
    throttling: throttlingFor(150, 1.6 * 1024, 4),
    lcpBudgetMs: 2500,
  },
  {
    key: 'degraded',
    label: 'degraded: low-end Android on Slow 3G (400 kbps, 400 ms RTT)',
    // DEC08 names the network numbers explicitly but not a separate CPU
    // multiplier for this weaker device. Doubling the primary profile's
    // multiplier (4 -> 8) is this script's own calibration choice, not an
    // official DEC08 or Lighthouse constant -- flagged, not silently
    // assumed. The budget itself is also explicitly looser here per
    // DEC08 ("must stay usable, not fast").
    throttling: throttlingFor(400, 400, 8),
    lcpBudgetMs: 5000,
  },
];

// DEC08 Q16's numeric budgets that apply regardless of profile.
const CLS_MAX = 0.1;
const INP_BUDGET_MS = 200;
const CRITICAL_RENDER_PATH_BYTES = 170 * 1024;
const TOTAL_FIRST_LOAD_BYTES = 350 * 1024;
const HEAVIEST_SCREEN_BYTES = 1024 * 1024;
const MAX_BLOCKING_REQUESTS_BEFORE_FIRST_RENDER = 2;

// Representative pages, not all ~16 /ui routes (DEC08 asks for budgets to
// be "tested and reported", not an exhaustive per-page audit) -- one
// unauthenticated page, one list view, one dashboard, and the one DEC08
// itself names as the page-weight outlier ("heaviest authoring screen").
function pagesFor(ctx) {
  return [
    { name: 'login', path: '/ui/login', weightBudget: TOTAL_FIRST_LOAD_BYTES },
    { name: 'orgs-list', path: '/ui/orgs', weightBudget: TOTAL_FIRST_LOAD_BYTES },
    { name: 'my-work', path: `/ui/orgs/${ctx.tenantId}/my-work`, weightBudget: TOTAL_FIRST_LOAD_BYTES },
    {
      name: 'gate-dashboard',
      path: `/ui/orgs/${ctx.tenantId}/projects/${ctx.projectId}/gates`,
      weightBudget: TOTAL_FIRST_LOAD_BYTES,
    },
    {
      name: 'evidence-form',
      path: `/ui/orgs/${ctx.tenantId}/evidence/${ctx.evidenceItemId}`,
      weightBudget: HEAVIEST_SCREEN_BYTES, // DEC08's named "heaviest authoring screen"
      inpTarget: true,
    },
  ];
}

async function setupData(page) {
  const email = `perf-budget-${Date.now()}@example.com`;
  const password = 'correct horse battery staple';
  const schema = JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8'));
  delete schema._meta;

  await page.goto(`${BASE_URL}/ui/login`, { waitUntil: 'load' });

  const result = await page.evaluate(
    async ({ email, password, schema }) => {
      const post = async (url, body) => {
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error(`${url} -> ${resp.status}: ${await resp.text()}`);
        return resp.json();
      };

      await post('/auth/register', { email, password });
      await post('/auth/login', { email, password });
      const org = await post('/orgs', { name: 'Perf budget org' });

      const created = await post(`/orgs/${org.id}/templates/import`, { name: 'Perf budget template', schema_json: schema });
      const publishResp = await fetch(
        `/orgs/${org.id}/templates/${created.template_id}/versions/${created.id}/publish`,
        { method: 'POST' },
      );
      if (!publishResp.ok) throw new Error(`publish -> ${publishResp.status}: ${await publishResp.text()}`);

      const project = await post(`/orgs/${org.id}/projects`, {
        name: 'Perf budget project',
        template_version_id: created.id,
        class_id: 'Standard-High',
        members: [],
      });
      // CreateProjectResponse nests the project under `.project` (alongside
      // `.occurrences` and `.evidence_items`) -- not a top-level `.id`.
      const evidenceItemId = project.evidence_items[0].id;
      return { tenantId: org.id, projectId: project.project.id, evidenceItemId };
    },
    { email, password, schema },
  );

  return result;
}

function sumBytes(networkRequestsDetails, predicate) {
  return networkRequestsDetails.items.filter(predicate).reduce((sum, r) => sum + (r.transferSize || 0), 0);
}

async function measureNavigation(page, url, profile) {
  const result = await lighthouse(
    url,
    { onlyCategories: undefined },
    {
      extends: 'lighthouse:default',
      settings: {
        onlyAudits: [
          'largest-contentful-paint',
          'cumulative-layout-shift',
          'first-contentful-paint',
          'total-byte-weight',
          'network-requests',
          'render-blocking-insight',
        ],
        throttlingMethod: 'simulate',
        throttling: profile.throttling,
        formFactor: 'mobile',
        screenEmulation: { mobile: true, width: 412, height: 823, deviceScaleFactor: 1.75, disabled: false },
      },
    },
    page,
  );

  const audits = result.lhr.audits;
  // Lighthouse replaces an audit's whole result with {score: null,
  // errorMessage, ...} -- no `details` key at all -- when that audit
  // throws internally (core/audits/audit.js generateErrorAuditResult).
  // Checking for that explicitly turns a crash on `.details.items` deep in
  // sumBytes into the actual Lighthouse error message at the point of use.
  for (const id of ['largest-contentful-paint', 'first-contentful-paint', 'cumulative-layout-shift', 'network-requests', 'total-byte-weight', 'render-blocking-insight']) {
    if (audits[id].errorMessage) {
      throw new Error(`lighthouse audit '${id}' errored: ${audits[id].errorMessage}`);
    }
  }
  const lcpMs = audits['largest-contentful-paint'].numericValue;
  const fcpMs = audits['first-contentful-paint'].numericValue;
  const cls = audits['cumulative-layout-shift'].numericValue;
  const networkRequests = audits['network-requests'].details;

  const criticalRenderPathBytes = sumBytes(networkRequests, (r) => r.networkEndTime <= fcpMs);
  const totalBytes = audits['total-byte-weight'].numericValue;
  // Lighthouse's own render-blocking-insight audit (replaces the older
  // render-blocking-resources audit) -- it identifies requests that
  // actually delay first paint (synchronous head stylesheets/scripts),
  // not merely ones that happened to finish downloading before FCP. A
  // bottom-of-body script that downloads fast on a local/fast connection
  // is not render-blocking even though it can finish before FCP, which
  // an earlier "finished before FCP" heuristic here conflated.
  const blockingRequests = (audits['render-blocking-insight'].details?.items ?? []).length;

  return { lcpMs, cls, criticalRenderPathBytes, totalBytes, blockingRequests };
}

async function measureInp(page, url, profile) {
  // INP is only computable by Lighthouse under real (devtools) throttling
  // in `timespan` mode with a genuine user interaction during the
  // recording -- lighthouse/core/audits/metrics/interaction-to-next-paint.js
  // returns {notApplicable: true} outright when throttlingMethod is
  // 'simulate' ("responsiveness isn't yet supported by lantern"). Real
  // CDP throttling is less deterministic than simulation, so this is run
  // 3x and the median is budget-checked -- same multi-sample discipline
  // test_dec08_performance_budgets.py already uses for its own latency
  // numbers, not a new pattern invented here.
  const samples = [];
  for (let i = 0; i < 3; i++) {
    await page.goto(url, { waitUntil: 'load' });
    const flow = await startTimespan(page, {
      config: {
        extends: 'lighthouse:default',
        settings: {
          onlyAudits: ['interaction-to-next-paint'],
          throttlingMethod: 'devtools',
          throttling: profile.throttling,
          formFactor: 'mobile',
          screenEmulation: { mobile: true, width: 412, height: 823, deviceScaleFactor: 1.75, disabled: false },
        },
      },
    });
    // The real, in-page, non-navigating interaction this app actually
    // has (backend/app/templates/evidence_form.html): typing into the
    // #reference field fires a real `input` event handler (`sync()`).
    // No contrived click-and-navigate substitute -- this is the one
    // genuine client-side interaction the app's own progressive-
    // enhancement design provides.
    await page.click('#reference');
    await page.keyboard.type('perf budget probe', { delay: 20 });
    const result = await flow.endTimespan();
    const audit = result.lhr.audits['interaction-to-next-paint'];
    if (audit.notApplicable || audit.numericValue == null) continue;
    samples.push(audit.numericValue);
  }
  if (samples.length === 0) return null;
  samples.sort((a, b) => a - b);
  return samples[Math.floor(samples.length / 2)];
}

async function main() {
  const chrome = await chromeLauncher.launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
  const browser = await puppeteer.connect({ browserURL: `http://127.0.0.1:${chrome.port}` });
  const page = await browser.newPage();

  const failures = [];
  const report = [];

  try {
    const ctx = await setupData(page);
    const pages = pagesFor(ctx);

    for (const profile of PROFILES) {
      for (const pageSpec of pages) {
        const url = `${BASE_URL}${pageSpec.path}`;
        const nav = await measureNavigation(page, url, profile);
        const row = { profile: profile.key, page: pageSpec.name, ...nav };
        report.push(row);

        if (nav.lcpMs > profile.lcpBudgetMs) {
          failures.push(`${pageSpec.name}/${profile.key}: LCP ${nav.lcpMs.toFixed(0)}ms > budget ${profile.lcpBudgetMs}ms`);
        }
        if (nav.cls > CLS_MAX) {
          failures.push(`${pageSpec.name}/${profile.key}: CLS ${nav.cls.toFixed(3)} > budget ${CLS_MAX}`);
        }
        if (nav.criticalRenderPathBytes > CRITICAL_RENDER_PATH_BYTES) {
          failures.push(
            `${pageSpec.name}/${profile.key}: critical render path ${(nav.criticalRenderPathBytes / 1024).toFixed(1)}KB > budget ${CRITICAL_RENDER_PATH_BYTES / 1024}KB`,
          );
        }
        if (nav.totalBytes > pageSpec.weightBudget) {
          failures.push(
            `${pageSpec.name}/${profile.key}: total weight ${(nav.totalBytes / 1024).toFixed(1)}KB > budget ${(pageSpec.weightBudget / 1024).toFixed(0)}KB`,
          );
        }
        if (nav.blockingRequests > MAX_BLOCKING_REQUESTS_BEFORE_FIRST_RENDER) {
          failures.push(
            `${pageSpec.name}/${profile.key}: ${nav.blockingRequests} blocking requests before first render > budget ${MAX_BLOCKING_REQUESTS_BEFORE_FIRST_RENDER}`,
          );
        }

        if (pageSpec.inpTarget) {
          const inpMs = await measureInp(page, url, profile);
          report.push({ profile: profile.key, page: pageSpec.name, inpMs });
          if (inpMs == null) {
            failures.push(`${pageSpec.name}/${profile.key}: INP not measurable (no qualifying interaction captured)`);
          } else if (inpMs > INP_BUDGET_MS) {
            failures.push(`${pageSpec.name}/${profile.key}: INP ${inpMs.toFixed(0)}ms > budget ${INP_BUDGET_MS}ms`);
          }
        }
      }
    }
  } finally {
    await browser.close();
    await chrome.kill();
  }

  console.log(JSON.stringify(report, null, 2));

  if (failures.length > 0) {
    console.error(`\n${failures.length} budget breach(es):`);
    for (const f of failures) console.error(`  - ${f}`);
    process.exitCode = 1;
  } else {
    console.log('\nAll render-timing and page-weight budgets within limits.');
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
