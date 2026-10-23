"""Scenario 1 over HTTP, standard library only: coffee shop → overdraft → offer → signed → issued.

Run by scripts/check-clean-clone.sh inside the backend container against the `web` service
(Caddy → Django), so the jury's machine needs neither Python nor jq:

    docker compose exec -T backend python - < scripts/smoke_scenario_1.py

BASE_URL (default http://web) and HOST (default localhost, must be in DJANGO_ALLOWED_HOSTS)
can be overridden by environment variables. Exit code 0 = the scenario passed.
"""

import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = os.environ.get("BASE_URL", "http://web").rstrip("/")
HOST = os.environ.get("HOST", "localhost")
CONSENT = {"bki_consent": True, "consent_version": "bki-2026-10"}

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE_URL + path, data=data, method=method)
    request.add_header("Host", HOST)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    csrf = next((c.value for c in jar if c.name == "csrftoken"), None)
    if csrf:
        request.add_header("X-CSRFToken", csrf)
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        fail(f"{method} {path} → {error.code}: {error.read()[:300].decode(errors='replace')}")
    return json.loads(raw) if raw else {}


def fail(message: str) -> None:
    print(f"FAIL  {message}")
    sys.exit(1)


def step(message: str) -> None:
    print(f"ok    {message}")


def wait_for(application_id: int, wanted: str, seconds: int = 60) -> dict:
    deadline = time.monotonic() + seconds
    while True:
        application = call("GET", f"/api/applications/{application_id}")
        if application["status"] == wanted:
            return application
        if time.monotonic() > deadline:
            fail(f"application {application_id}: «{application['status']}», expected «{wanted}»")
        time.sleep(1)


def main() -> None:
    ready = call("GET", "/api/ready")
    if ready.get("status") != "ready":
        fail(f"/api/ready: {ready}")
    step("/api/ready — ready")

    call("GET", "/api/auth/csrf")
    call("POST", "/api/demo/login", {"persona": "coffee_shop"})
    step("signed in as the coffee shop persona")

    match = call("POST", "/api/recommendations", {"need_type": "cash_gap"})
    offer = match["offers"][0]
    if offer["product"]["kind"] != "overdraft":
        fail(f"first recommendation is {offer['product']['kind']}, expected overdraft")
    step(f"recommended overdraft {offer['amount']} ₽ for {offer['term_months']} months")

    application = call(
        "POST",
        "/api/applications",
        {
            "need_type": "cash_gap",
            "purpose": "Демо: проверка чистого клона — кассовый разрыв",
            "requested_amount": offer["amount"],
            "term_months": offer["term_months"],
            "product_code": offer["product"]["code"],
            "prefill_source": "recommendation",
        },
    )
    application_id = application["id"]
    call(
        "POST",
        f"/api/applications/{application_id}/submit",
        CONSENT,
        {"Idempotency-Key": str(uuid.uuid4())},
    )
    step(f"application {application_id} submitted with the consent to the BKI request")

    detail = wait_for(application_id, "offer")
    step(f"automatic offer: {detail['offer']['amount']} ₽")

    call("POST", f"/api/applications/{application_id}/offer/accept")
    challenge = call("POST", f"/api/applications/{application_id}/signature")
    call(
        "POST",
        f"/api/applications/{application_id}/signature/confirm",
        {"code": challenge["code"]},
    )
    step("offer accepted and signed with the on-screen code")

    wait_for(application_id, "issued")
    step("money issued — scenario 1 passed")


if __name__ == "__main__":
    main()
