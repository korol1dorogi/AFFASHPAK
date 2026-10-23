"""Red team (S8) X1 IDOR, X2 roles, X3 CSRF over every endpoint with an id (docs/redteam.md).

    python3 scripts/redteam/access.py      # stack from README must be up, DEMO_MODE=1

Builds a victim application of persona 4 up to an offer, then attacks it as another client, as the
bank and without the CSRF header. Prints every FAIL; exit code 1 if there is one.
"""

import sys
import uuid

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from harness import FURNITURE_DOCS, FURNITURE_DRAFT, S, submit  # noqa: E402

results = []


def check(cid, who, method, path, got, ok, note=""):
    results.append((cid, who, method, path, got, "PASS" if ok else "FAIL", note))


# ---------- victim world: furniture_maker (director + accountant), bank ----------
director, accountant, bank = S(), S(), S()
director.demo("furniture_maker")
accountant.demo("accountant")
bank.demo("bank")

st, app, _ = accountant.req("POST", "/api/applications", FURNITURE_DRAFT)
assert st == 201, (st, app)
A = app["id"]
doc_ids = []
for kind in FURNITURE_DOCS:
    st, d, _ = accountant.upload(A, kind)
    assert st == 201, (kind, st, d)
    doc_ids.append(d["id"])
st, body, _ = submit(director, A)
assert st == 200, (st, body)
st, card, _ = bank.req("GET", f"/api/bank/applications/{A}")
assert card["application"]["status"] == "manual_review", card["application"]["status"]
v = card["application"]["version"]
st, card2, _ = bank.req("POST", f"/api/bank/applications/{A}/request-info",
                        {"version": v, "message": "Загрузите отчётность (демо)"})
assert st == 200, (st, card2)
st, a, _ = accountant.req("GET", f"/api/applications/{A}")
IR = a["open_info_requests"][0]["id"]
st, d, _ = accountant.upload(A, "financial_report")
doc_ids.append(d["id"])
st, a, _ = accountant.req("POST", f"/api/applications/{A}/info-requests/{IR}/respond", {"message": "Загрузили (демо)"})
assert st == 200, (st, a)
st, card, _ = bank.req("GET", f"/api/bank/applications/{A}")
st, b, _ = bank.req("POST", f"/api/bank/applications/{A}/approve", {"version": card["application"]["version"]})
assert st == 200, (st, b)
# second victim application stays a draft (for PATCH / submit / upload)
st, draft, _ = accountant.req("POST", "/api/applications", FURNITURE_DRAFT)
D = draft["id"]
st, notes, _ = director.req("GET", "/api/notifications")
NOTE = notes["results"][0]["id"] if isinstance(notes, dict) and "results" in notes else notes[0]["id"]
st, members, _ = director.req("GET", "/api/company/members")
MEMBER = members[0]["id"] if isinstance(members, list) else members["results"][0]["id"]
DOC = doc_ids[0]
print("victim ids", dict(A=A, D=D, IR=IR, DOC=DOC, NOTE=NOTE, MEMBER=MEMBER))

CLIENT_EPS = [
    ("GET", f"/api/applications/{A}", None),
    ("PATCH", f"/api/applications/{D}", {"version": 0, "purpose": "IDOR (демо)"}),
    ("POST", f"/api/applications/{D}/submit", {"bki_consent": True, "consent_version": "bki-2026-10"}),
    ("POST", f"/api/applications/{D}/cancel", None),
    ("GET", f"/api/applications/{A}/events", None),
    ("GET", f"/api/applications/{A}/decision", None),
    ("POST", f"/api/applications/{A}/offer/accept", None),
    ("POST", f"/api/applications/{A}/offer/decline", None),
    ("POST", f"/api/applications/{A}/signature", None),
    ("POST", f"/api/applications/{A}/signature/confirm", {"code": "123456"}),
    ("POST", f"/api/applications/{A}/info-requests/{IR}/respond", {"message": "x"}),
    ("GET", f"/api/applications/{A}/documents", None),
    ("GET", f"/api/applications/{A}/documents/{DOC}", None),
    ("POST", f"/api/notifications/{NOTE}/read", None),
    ("DELETE", f"/api/company/members/{MEMBER}", None),
]
BANK_EPS = [
    ("GET", f"/api/bank/applications/{A}", None),
    ("POST", f"/api/bank/applications/{A}/assign", {"version": 0}),
    ("POST", f"/api/bank/applications/{A}/approve", {"version": 0}),
    ("POST", f"/api/bank/applications/{A}/counteroffer", {"version": 0}),
    ("POST", f"/api/bank/applications/{A}/request-info", {"version": 0, "message": "x"}),
    ("POST", f"/api/bank/applications/{A}/decline", {"version": 0}),
    ("POST", f"/api/bank/applications/{A}/comments", {"text": "x"}),
    ("GET", f"/api/bank/applications/{A}/documents/{DOC}", None),
    ("GET", "/api/bank/applications", None),
    ("GET", "/api/bank/dashboard", None),
    ("GET", "/api/demo/failures", None),
    ("PUT", "/api/demo/failures", {"egrul": False, "transparent_business": False, "bki": False, "bank_account": False}),
    ("POST", "/api/demo/reset", None),
]

# ---------- X1: another client → 404 on every client endpoint with an id ----------
outsider = S()
outsider.demo("retail_supplier")
for m, p, body in CLIENT_EPS:
    st, resp, _ = outsider.req(m, p, body, headers={"Idempotency-Key": str(uuid.uuid4())})
    check("X1", "чужой клиент", m, p, st, st == 404)
# bank user on client endpoints: must not act as the client
for m, p, body in CLIENT_EPS:
    st, resp, _ = bank.req(m, p, body, headers={"Idempotency-Key": str(uuid.uuid4())})
    check("X1", "сотрудник банка", m, p, st, st in (403, 404))

own = outsider.req("POST", "/api/applications", {"need_type": "cash_gap", "product_code": "overdraft_basic",
                  "purpose": "Кассовый разрыв до оплаты клиентов (демо)", "requested_amount": "300000.00", "term_months": 6})[1]["id"]
for m, p, body in (("GET", f"/api/applications/{own}/documents/{DOC}", None),
                   ("POST", f"/api/applications/{own}/info-requests/{IR}/respond", {"message": "x"})):
    st, resp, _ = outsider.req(m, p, body)
    check("X1", "чужой клиент, своя заявка + чужой вложенный id", m, p, st, st == 404)

# ---------- X2: the preparer of the same company on the signatory's actions → 403 ----------
st, a_now, _ = accountant.req("GET", f"/api/applications/{A}")
for m, p, body in (
    ("POST", f"/api/applications/{D}/submit", {"bki_consent": True, "consent_version": "bki-2026-10"}),
    ("POST", f"/api/applications/{A}/offer/accept", None),
    ("POST", f"/api/applications/{A}/offer/decline", None),
    ("POST", f"/api/applications/{A}/signature", None),
    ("POST", f"/api/applications/{A}/signature/confirm", {"code": "123456"}),
    ("POST", f"/api/applications/{A}/cancel", None),
    ("DELETE", f"/api/company/members/{MEMBER}", None),
):
    st, resp, _ = accountant.req(m, p, body, headers={"Idempotency-Key": str(uuid.uuid4())})
    check("X2", "бухгалтер (preparer) своей компании", m, p, st, st == 403)
st, a_after, _ = accountant.req("GET", f"/api/applications/{A}")
check("X2", "бухгалтер: статус заявки не изменился", "GET", f"/api/applications/{A}",
      f"{a_now['status']} → {a_after['status']}", a_now["status"] == a_after["status"] == "offer")

# ---------- X2: client (even the owner) on bank endpoints → 403 ----------
for who, s in (("клиент-владелец", director), ("чужой клиент", outsider), ("бухгалтер", accountant)):
    for m, p, body in BANK_EPS:
        st, resp, _ = s.req(m, p, body)
        # The bank download hides even the document's existence from clients: 404 by design (L2)
        expected = (403, 404) if "/documents/" in p else (403,)
        check("X2", who, m, p, st, st in expected)

# ---------- X3: CSRF — the same unsafe calls without the header → 403 ----------
for who, s, eps in (("подписант", director, CLIENT_EPS), ("банк", bank, BANK_EPS)):
    for m, p, body in eps:
        if m in ("GET",):
            continue
        st, resp, _ = s.req(m, p, body, csrf=False, headers={"Idempotency-Key": str(uuid.uuid4())})
        csrf_msg = isinstance(resp, dict) and "проверка безопасности" in str(resp)
        check("X3", who, m, p, st, st == 403 and csrf_msg, "" if csrf_msg else str(resp)[:120])
extra_unsafe = [
    ("POST", "/api/applications", FURNITURE_DRAFT),
    ("PATCH", "/api/company", {"short_name": "x"}),
    ("POST", "/api/company/members", {"username": "x", "full_name": "x", "role": "preparer", "password": "x"}),
    ("POST", "/api/notifications/read-all", None),
    ("POST", "/api/recommendations", {}),
    ("POST", "/api/calculators/annuity", {}),
    ("POST", "/api/company/integrations/bank_account/connect", None),
    ("POST", "/api/auth/logout", None),
]
for m, p, body in extra_unsafe:
    st, resp, _ = director.req(m, p, body, csrf=False)
    csrf_msg = isinstance(resp, dict) and "проверка безопасности" in str(resp)
    check("X3", "подписант", m, p, st, st == 403 and csrf_msg, "" if csrf_msg else str(resp)[:120])
anon = S()
anon.csrf()
for m, p, body in (("POST", "/api/auth/login", {"username": "x", "password": "y"}),
                   ("POST", "/api/auth/register", {"username": "x", "password": "y", "full_name": "x"}),
                   ("POST", "/api/demo/login", {"persona": "bank"})):
    st, resp, _ = anon.req(m, p, body, csrf=False)
    check("X3", "аноним", m, p, st, st == 403)

fails = [r for r in results if r[5] == "FAIL"]
print(f"{len(results)} checks, {len(fails)} FAIL")
for r in fails:
    print(r)
sys.exit(1 if fails else 0)
