// One iteration: the stack is ready, then the demo data goes back to the seed (POST /api/demo/reset).
// Run before a load run; after it, `-e SKIP_RESET=1` only checks /api/ready.
import http from "k6/http";
import { check, fail } from "k6";
import { BASE_URL, demoLogin, unsafeParams } from "./lib.js";

export const options = { vus: 1, iterations: 1 };

export default function () {
  const ready = http.get(`${BASE_URL}/api/ready`);
  if (!check(ready, { "ready 200": (r) => r.status === 200 })) {
    fail(`/api/ready: HTTP ${ready.status} ${ready.body}`);
  }
  if (__ENV.SKIP_RESET) return;
  demoLogin("bank");
  const res = http.post(`${BASE_URL}/api/demo/reset`, null, unsafeParams("demo_reset"));
  if (!check(res, { "reset 204": (r) => r.status === 204 })) {
    fail(`/api/demo/reset: HTTP ${res.status} ${res.body}`);
  }
}
