// API client over the generated contract types (schema.d.ts ← docs/openapi.yaml).
// Не править руками: меняется только лидом (AGENTS.md). Типы — `npm run gen:api`.
import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1];
}

// Django session auth: unsafe methods must carry the CSRF token from the csrftoken cookie.
const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (UNSAFE_METHODS.has(request.method)) {
      const token = readCookie("csrftoken");
      if (token) request.headers.set("X-CSRFToken", decodeURIComponent(token));
    }
    return request;
  },
};

export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  credentials: "same-origin",
  // Resolve fetch at call time so tests can stub it.
  fetch: (request) => globalThis.fetch(request),
});

api.use(csrfMiddleware);
