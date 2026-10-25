// 50 bank employees work the queue on /bank: GET /api/bank/applications with filters and
// pages, as the SPA builds them (bank-queue/params.ts), and open cards (docs/perf.md).
// PROFILE=realistic (default): the SPA's pace — the queue every 15 ± 2 s (refetchInterval),
//   a card on every third pass with 5–10 s on it; ~250 requests/min for 50 VUs.
// PROFILE=stress: a pause of 1–3 s — shows where the per-user throttle cuts in; 429 is the
//   expected protection, counted in throttled_429 and kept out of http_req_failed.
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import { BASE_URL, STAGES, SUMMARY_STATS, demoLogin, pick, randomPause } from "./lib.js";

const PAGE_SIZE = 20; // frontend/src/features/bank-queue/params.ts

// Query strings the queue screen produces: default view, status chips, product, grade,
// assignee, SLA, search, ordering and the next page.
const FILTERS = [
  "",
  "status=submitted&status=manual_review",
  "status=manual_review&ordering=-status_changed_at",
  "status=info_requested&status=offer",
  "product_kind=overdraft",
  "product_kind=working_capital_loan&grade=B",
  "grade=C&ordering=-requested_amount",
  "assignee=none",
  "assignee=me",
  "min_hours_in_status=24",
  "overdue=true",
  "search=%D0%9E%D0%9E%D0%9E", // «ООО»
  "ordering=created_at",
  "page=2",
];

const PROFILE = __ENV.PROFILE || "realistic";
if (!["realistic", "stress"].includes(PROFILE)) {
  throw new Error(`PROFILE must be realistic or stress, got ${PROFILE}`);
}
const STRESS = PROFILE === "stress";

const throttled = new Counter("throttled_429");

if (STRESS) http.setResponseCallback(http.expectedStatuses(200, 429));

export const options = {
  scenarios: {
    queue: { executor: "ramping-vus", startVUs: 0, stages: STAGES, gracefulRampDown: "10s" },
  },
  // Latency of 200s only: a 429 comes back in ~3 ms and would hide the real p95.
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{name:bank_queue,status:200}": ["p(95)<500"],
    "http_req_duration{name:bank_card,status:200}": ["p(95)<500"],
  },
  summaryTrendStats: SUMMARY_STATS,
  noCookiesReset: true, // the session from demoLogin lives across iterations, as in a browser
};

let signedIn = false;
let knownIds = [];

export default function () {
  if (!signedIn) {
    demoLogin("bank"); // the only bank persona: all 50 VUs share one user's throttle bucket
    signedIn = true;
  }
  const filter = pick(FILTERS);
  const query = `page_size=${PAGE_SIZE}${filter.startsWith("page=") ? "" : "&page=1"}${filter ? `&${filter}` : ""}`;
  const res = http.get(`${BASE_URL}/api/bank/applications?${query}`, { tags: { name: "bank_queue" } });
  if (res.status === 429) throttled.add(1);
  const ok = check(res, { "queue 200": (r) => r.status === 200 });
  if (ok) {
    const ids = res.json("results.#.id");
    if (ids && ids.length) knownIds = ids;
  }
  const openCard = STRESS || __ITER % 3 === 2;
  if (openCard && knownIds.length) {
    const card = http.get(`${BASE_URL}/api/bank/applications/${pick(knownIds)}`, {
      tags: { name: "bank_card" },
    });
    if (card.status === 429) throttled.add(1);
    check(card, { "card 200": (r) => r.status === 200 });
    if (!STRESS) sleep(randomPause(5, 10)); // reading the card
  }
  sleep(STRESS ? randomPause(1, 3) : randomPause(13, 17));
}
