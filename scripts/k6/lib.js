// Shared helpers for the k6 scenarios: base URL, CSRF and the demo sign-in (docs/openapi.yaml, tag demo).
import http from "k6/http";
import { check, fail } from "k6";

export const BASE_URL = (__ENV.BASE_URL || "http://localhost:8080").replace(/\/$/, "");

export const STAGES = [
  { duration: "30s", target: 50 },
  { duration: "2m", target: 50 },
  { duration: "15s", target: 0 },
];

export const SUMMARY_STATS = ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max", "count"];

// The jar is per VU, so every VU keeps its own session, like a separate browser.
function csrfToken() {
  const cookies = http.cookieJar().cookiesForURL(`${BASE_URL}/`);
  return cookies.csrftoken ? cookies.csrftoken[0] : "";
}

// Origin and Referer as a browser sends them: over HTTPS Django's CSRF check requires them.
export function unsafeParams(name) {
  return {
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken(),
      Origin: BASE_URL,
      Referer: `${BASE_URL}/`,
    },
    tags: { name },
  };
}

// GET /api/auth/csrf sets the cookie, POST /api/demo/login opens the session (as the SPA does).
export function demoLogin(persona) {
  http.get(`${BASE_URL}/api/auth/csrf`, { tags: { name: "csrf" } });
  const res = http.post(
    `${BASE_URL}/api/demo/login`,
    JSON.stringify({ persona }),
    unsafeParams("demo_login"),
  );
  if (!check(res, { "demo login 200": (r) => r.status === 200 })) {
    fail(`demo login as ${persona}: HTTP ${res.status}`);
  }
}

export function randomPause(min, max) {
  return min + Math.random() * (max - min);
}

export function pick(items) {
  return items[Math.floor(Math.random() * items.length)];
}
