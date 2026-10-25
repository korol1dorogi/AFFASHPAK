// 50 entrepreneurs pick a product on /app/match: POST /api/recommendations (docs/perf.md).
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import { BASE_URL, STAGES, SUMMARY_STATS, demoLogin, pick, randomPause, unsafeParams } from "./lib.js";

// Client personas from GET /api/demo/personas. VUs are spread over them, so the per-user
// throttle (600/min) is shared by ~6 VUs, not by all 50.
const PERSONAS = [
  "coffee_shop",
  "retail_supplier",
  "garden_store",
  "furniture_maker",
  "accountant",
  "dependent_supplier",
  "liquidating_company",
  "bki_outage",
  "equipment_no_collateral",
];

// What the match form sends: the need, and optionally an amount, a term and the invoice amount.
const REQUESTS = [
  { need_type: "cash_gap" },
  { need_type: "cash_gap", amount: "500000.00", term_months: 6 },
  { need_type: "receivable_delay", invoice_amount: "1200000.00" },
  { need_type: "working_capital", amount: "2000000.00", term_months: 12 },
  { need_type: "working_capital" },
  { need_type: "capex", amount: "3500000.00", term_months: 36 },
  { need_type: "capex" },
];

const throttled = new Counter("throttled_429");

export const options = {
  scenarios: {
    match: { executor: "ramping-vus", startVUs: 0, stages: STAGES, gracefulRampDown: "10s" },
  },
  // Latency of 200s only: a 429 comes back in ~3 ms and would hide the real p95.
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{name:recommendations,status:200}": ["p(95)<800"],
  },
  summaryTrendStats: SUMMARY_STATS,
  noCookiesReset: true, // the session from demoLogin lives across iterations, as in a browser
};

let signedIn = false;

export default function () {
  if (!signedIn) {
    demoLogin(PERSONAS[(__VU - 1) % PERSONAS.length]);
    signedIn = true;
  }
  const res = http.post(
    `${BASE_URL}/api/recommendations`,
    JSON.stringify(pick(REQUESTS)),
    unsafeParams("recommendations"),
  );
  if (res.status === 429) throttled.add(1);
  check(res, {
    "recommendations 200": (r) => r.status === 200,
    "is_preliminary": (r) => r.status !== 200 || r.json("is_preliminary") === true,
  });
  sleep(randomPause(1, 3));
}
