"""Red team (S8) harness: a browser-like HTTP session against the LOCAL stack only. Stdlib only.

RT_BASE defaults to the backend of `docker compose up` (http://127.0.0.1:8000); anything that is not
127.0.0.1/localhost is refused, so the team stand is never attacked.
"""

import http.cookiejar
import json
import os
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("RT_BASE", "http://127.0.0.1:8000")
assert BASE.startswith(("http://127.0.0.1", "http://localhost")), "local stack only"
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "sample", "documents", "")


class S:
    """One browser-like session: cookies, CSRF header on unsafe calls unless told not to."""

    def __init__(self, base=BASE):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.op.addheaders = []

    def cookie(self, name):
        return next((c for c in self.jar if c.name == name), None)

    def req(self, method, path, data=None, *, csrf=True, headers=None, raw=None, ctype=None):
        h = {"Referer": self.base + "/", "Origin": self.base}
        if csrf and self.cookie("csrftoken"):
            h["X-CSRFToken"] = self.cookie("csrftoken").value
        if data is not None:
            raw = json.dumps(data).encode()
            ctype = "application/json"
        if ctype:
            h["Content-Type"] = ctype
        h.update(headers or {})
        r = urllib.request.Request(self.base + path, data=raw, method=method, headers=h)
        try:
            with self.op.open(r, timeout=30) as resp:
                body = resp.read()
                return resp.status, _j(body), resp.headers
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, _j(body), e.headers

    def csrf(self):
        return self.req("GET", "/api/auth/csrf")

    def demo(self, persona):
        self.csrf()
        st, body, _ = self.req("POST", "/api/demo/login", {"persona": persona})
        assert st == 200, (persona, st, body)
        return body

    def upload(self, app_id, kind, content=None, filename=None, mime="application/pdf"):
        if content is None:
            with open(f"{DOCS}{kind}_0001000042_demo.pdf", "rb") as f:
                content = f.read()
        filename = filename or f"{kind}.pdf"
        b = uuid.uuid4().hex
        parts = (
            f'--{b}\r\nContent-Disposition: form-data; name="kind"\r\n\r\n{kind}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + content + f"\r\n--{b}--\r\n".encode()
        return self.req(
            "POST", f"/api/applications/{app_id}/documents", raw=parts,
            ctype=f"multipart/form-data; boundary={b}",
        )


def _j(body):
    try:
        return json.loads(body)
    except Exception:
        return body[:300]


def submit(s, app_id, key=None):
    return s.req("POST", f"/api/applications/{app_id}/submit", CONSENT,
                 headers={"Idempotency-Key": key or str(uuid.uuid4())})


CONSENT = {"bki_consent": True, "consent_version": "bki-2026-10"}

FURNITURE_DRAFT = {
    "need_type": "capex", "product_code": "investment_loan_basic",
    "purpose": "Покупка фрезерного станка с ЧПУ (демо)", "requested_amount": "8000000.00",
    "term_months": 36, "collateral_description": "Станок (демо)",
}
FURNITURE_DOCS = ["bank_statement", "tax_return", "contract", "invoice"]
