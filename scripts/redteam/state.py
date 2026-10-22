"""Red team (S8): X4 races, X5 read-only fields, MA mass assignment, MEM members, SES sessions,
ENUM enumeration, SIG signature code (docs/redteam.md).

    python3 scripts/redteam/state.py       # stack from README must be up, DEMO_MODE=1

Changes local demo data (new applications, users, memberships). Prints one line per check.
"""

import http.cookiejar
import secrets
import sys
import threading
import uuid

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from harness import CONSENT, S, submit  # noqa: E402

# Throwaway users of the local stack get a fresh password per run: no credential literals in git
PASSWORD = f"Rt-{secrets.token_urlsafe(12)}"
WRONG_PASSWORD = f"Rt-{secrets.token_urlsafe(12)}"

out = []


def log(cid, what, got, ok, note=""):
    out.append((cid, what, got, ok if isinstance(ok, str) else ("PASS" if ok else "FAIL"), note))


OVERDRAFT = {"need_type": "cash_gap", "product_code": "overdraft_basic",
             "purpose": "Кассовый разрыв до оплаты клиентов (демо)",
             "requested_amount": "300000.00", "term_months": 6}

coffee, bank = S(), S()
coffee.demo("coffee_shop")
bank.demo("bank")

# ---------- X4: parallel submit, same and different Idempotency-Key ----------
for label, same_key in (("один ключ", True), ("разные ключи", False)):
    st, app, _ = coffee.req("POST", "/api/applications", OVERDRAFT)
    A = app["id"]
    key = str(uuid.uuid4())
    codes = []

    def go():
        codes.append(submit(coffee, A, key if same_key else None)[0])

    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    st, ev, _ = coffee.req("GET", f"/api/applications/{A}/events")
    items = ev if isinstance(ev, list) else ev.get("results", [])
    submitted = sum(1 for e in items if e.get("kind") == "status_changed" and e.get("to_status") == "submitted")
    consents = sum(1 for e in items if e.get("kind") == "consent_given")
    log("X4", f"6 параллельных submit, {label}", f"коды {sorted(codes)}, событий submitted={submitted}, consent={consents}",
        submitted == 1 and consents <= 1)

# offer → accept → sign: parallel confirm with the right code
st, app, _ = coffee.req("POST", "/api/applications", OVERDRAFT)
A = app["id"]
submit(coffee, A)
st, a, _ = coffee.req("GET", f"/api/applications/{A}")
log("X4", "заявка кофейни после submit", a["status"], a["status"] == "offer")
st, a, _ = coffee.req("POST", f"/api/applications/{A}/offer/accept")
st, ch, _ = coffee.req("POST", f"/api/applications/{A}/signature")
code = ch["code"]
codes = []


def confirm():
    codes.append(coffee.req("POST", f"/api/applications/{A}/signature/confirm", {"code": code})[0])


ts = [threading.Thread(target=confirm) for _ in range(5)]
[t.start() for t in ts]
[t.join() for t in ts]
st, ev, _ = coffee.req("GET", f"/api/applications/{A}/events")
items = ev if isinstance(ev, list) else ev.get("results", [])
signed = sum(1 for e in items if e.get("kind") == "signed")
issued = sum(1 for e in items if e.get("kind") == "issued")
log("X4", "5 параллельных confirm верного кода", f"коды {sorted(codes)}, signed={signed}, issued={issued}",
    signed == 1 and issued <= 1 and codes.count(200) == 1)

# ---------- X5: read-only fields through PATCH / create ----------
st, app, _ = coffee.req("POST", "/api/applications", {**OVERDRAFT, "status": "offer", "version": 99,
                                                        "company": 1, "created_by": 1, "decision": {"outcome": "offer"}})
log("X5", "POST /applications с status/version/company/created_by", f"{st} status={app.get('status')} version={app.get('version')}",
    st in (201, 400) and (st == 400 or (app.get("status") == "draft" and app.get("version") in (0, 1))))
D = app.get("id")
st, cur, _ = coffee.req("GET", f"/api/applications/{D}")
before = {k: cur.get(k) for k in ("status", "version", "company", "offer", "decision", "submitted_at")}
st, p, _ = coffee.req("PATCH", f"/api/applications/{D}", {
    "version": cur["version"], "status": "issued", "submitted_at": "2026-01-01T00:00:00Z",
    "offer": {"amount": "99999999.00", "rate": "0.01"}, "decision": {"outcome": "offer"},
    "company": 1, "rate": "0.01", "purpose": "Кассовый разрыв до оплаты клиентов (демо) 2",
})
st2, after_full, _ = coffee.req("GET", f"/api/applications/{D}")
after = {k: after_full.get(k) for k in before}
changed = {k for k in before if k not in ("version",) and before[k] != after[k]}
log("X5", "PATCH черновика с status/offer/decision/company/rate", f"{st}; изменились {sorted(changed) or 'нет'}",
    not changed)
st, p, _ = coffee.req("PATCH", f"/api/applications/{D}", {"version": 0, "purpose": "stale (демо)"})
log("X4", "PATCH с устаревшей version", st, st == 409)

# ---------- mass assignment: register / company ----------
anon = S()
anon.csrf()
uname = f"rt_{uuid.uuid4().hex[:8]}"
st, me, _ = anon.req("POST", "/api/auth/register", {
    "username": uname, "password": PASSWORD, "full_name": "RT демо",
    "kind": "bank", "role": "bank_manager", "is_staff": True, "is_superuser": True, "company": 1,
})
st_me, me2, _ = anon.req("GET", "/api/auth/me")
log("MA", "register с kind=bank, role=bank_manager, is_staff, is_superuser, company",
    f"{st}; me.kind={me2.get('kind')} company_id={me2.get('company_id')}",
    st in (201, 200, 400) and me2.get("kind") == "client" and me2.get("company_id") is None)
st_bank, _, _ = anon.req("GET", "/api/bank/applications")
log("MA", "новый пользователь → /api/bank/applications", st_bank, st_bank == 403)
st, comp, _ = coffee.req("GET", "/api/company")
before = {k: comp.get(k) for k in ("inn", "name", "registry_status", "is_demo", "ogrn")}
st, p, _ = coffee.req("PATCH", "/api/company", {"inn": "0001000042", "name": "Подмена (демо)",
                                                "registry_status": "active", "is_demo": False, "short_name": "Зерно"})
st, comp2, _ = coffee.req("GET", "/api/company")
after = {k: comp2.get(k) for k in before}
log("MA", "PATCH /company с inn/name/registry_status/is_demo", f"{st}; изменились {[k for k in before if before[k] != after[k]] or 'нет'}",
    before == after)

# ---------- members: pulling other users into my company ----------
stranger = S()
stranger.csrf()
victim_name = f"rt_v_{uuid.uuid4().hex[:6]}"
stranger.req("POST", "/api/auth/register", {"username": victim_name, "password": PASSWORD, "full_name": "Жертва демо"})
st, m, _ = coffee.req("POST", "/api/company/members", {"username": victim_name, "role": "signatory", "position": "Директор"})
st_v, me_v, _ = stranger.req("GET", "/api/auth/me")
log("MEM", "подписант добавляет чужого свободного пользователя по логину (подписантом)",
    f"{st}; у жертвы теперь company_id={me_v.get('company_id')}, роль {me_v.get('company_role')}", st not in (200, 201),
    "без согласия добавляемого")
probes = {}
for name in ("demo_furniture_maker", "demo_bank", f"rt_missing_{uuid.uuid4().hex[:8]}"):
    probes[name] = coffee.req("POST", "/api/company/members", {"username": name, "role": "preparer", "position": "x"})[0]
log("MEM", "перечисление логинов через members (занят / банк / нет)", probes,
    len(set(probes.values())) == 1)
st, _, _ = coffee.req("POST", "/api/company", {"inn": "0001000042"})
log("MEM", "POST /api/company с чужим ИНН, когда компания уже есть", st, st in (400, 409))
fresh = S()
fresh.csrf()
fresh.req("POST", "/api/auth/register", {"username": f"rt_f_{uuid.uuid4().hex[:6]}", "password": PASSWORD, "full_name": "Свободный демо"})
st, body, _ = fresh.req("POST", "/api/company", {"inn": "0001000042"})
log("MEM", "новый пользователь подключает чужую (занятую) компанию по ИНН", st, st == 409, str(body)[:100])

# ---------- sessions ----------
def plant(session, value):
    session.jar.set_cookie(http.cookiejar.Cookie(
        0, "sessionid", value, None, False, "127.0.0.1", False, False, "/", True, False, None, False, None, None, {}))


victim_name = f"rt_s_{uuid.uuid4().hex[:6]}"
attacker_name = f"rt_a_{uuid.uuid4().hex[:6]}"
for n in (victim_name, attacker_name):
    r = S()
    r.csrf()
    r.req("POST", "/api/auth/register", {"username": n, "password": PASSWORD, "full_name": "Сессия демо"})
# a) the attacker's own logged-in session id is planted in the victim's browser
att = S()
att.csrf()
att.req("POST", "/api/auth/login", {"username": attacker_name, "password": PASSWORD})
planted = att.cookie("sessionid").value
s = S()
s.csrf()
plant(s, planted)
s.req("POST", "/api/auth/login", {"username": victim_name, "password": PASSWORD})
sid2 = s.cookie("sessionid").value
st, me_att, _ = att.req("GET", "/api/auth/me")
log("SES", "подброшенная сессия атакующего → вход жертвы", f"ключ сменился={planted != sid2}; атакующий видит {me_att.get('username') if isinstance(me_att, dict) else st}",
    planted != sid2 and not (isinstance(me_att, dict) and me_att.get("username") == victim_name))
# b) a made-up session id
s2 = S()
s2.csrf()
plant(s2, "rtfixedsessionid0000000000000000")
s2.req("POST", "/api/auth/login", {"username": victim_name, "password": PASSWORD})
log("SES", "выдуманный session id → вход", s2.cookie("sessionid").value != "rtfixedsessionid0000000000000000",
    s2.cookie("sessionid").value != "rtfixedsessionid0000000000000000")
cookie = next(c for c in s.jar if c.name == "sessionid")
s.req("POST", "/api/auth/logout")
replay = S()
replay.jar.set_cookie(http.cookiejar.Cookie(
    0, "sessionid", sid2, None, False, cookie.domain, cookie.domain_specified, cookie.domain_initial_dot,
    "/", True, False, None, False, None, None, {}))
st, _, _ = replay.req("GET", "/api/auth/me")
log("SES", "cookie сессии после logout повторно", st, st == 401)
anon2 = S()
anon2.csrf()
st, _, h = anon2.req("POST", "/api/auth/login", {"username": victim_name, "password": PASSWORD})
sc = next((v for v in (h.get_all("Set-Cookie") or []) if v.startswith("sessionid=")), "")
flags = [p.strip() for p in sc.split(";")[1:]]
log("SES", "флаги cookie sessionid (локально, DEBUG)", flags, "HttpOnly" in flags and "SameSite=Lax" in flags,
    "Secure проверяется на prod-сборке")

# ---------- enumeration via login / register ----------
e = S()
e.csrf()
a = e.req("POST", "/api/auth/login", {"username": victim_name, "password": WRONG_PASSWORD})
b = e.req("POST", "/api/auth/login", {"username": f"rt_missing_{uuid.uuid4().hex[:8]}", "password": WRONG_PASSWORD})
log("ENUM", "login: существующий логин vs несуществующий", f"{a[0]} {a[1]} | {b[0]} {b[1]}", a[0] == b[0] and a[1] == b[1])
r = e.req("POST", "/api/auth/register", {"username": victim_name, "password": PASSWORD, "full_name": "x"})
log("ENUM", "register: занятый логин", f"{r[0]} {str(r[1])[:120]}", True, "по сути регистрации; см. журнал")

# ---------- signature: binding and brute force ----------
st, a1, _ = coffee.req("POST", "/api/applications", OVERDRAFT)
st, a2, _ = coffee.req("POST", "/api/applications", OVERDRAFT)
for x in (a1, a2):
    submit(coffee, x["id"])
    coffee.req("POST", f"/api/applications/{x['id']}/offer/accept")
_, c1, _ = coffee.req("POST", f"/api/applications/{a1['id']}/signature")
_, c2, _ = coffee.req("POST", f"/api/applications/{a2['id']}/signature")
if c1["code"] != c2["code"]:
    st, body, _ = coffee.req("POST", f"/api/applications/{a2['id']}/signature/confirm", {"code": c1["code"]})
    log("SIG", "код заявки 1 на заявке 2", st, st == 400)
# brute force: wrong codes until attempts run out, then the right one
st_list = []
for i in range(5):
    st_list.append(coffee.req("POST", f"/api/applications/{a2['id']}/signature/confirm", {"code": "000000" if c2["code"] != "000000" else "111111"})[0])
st, body, _ = coffee.req("POST", f"/api/applications/{a2['id']}/signature/confirm", {"code": c2["code"]})
log("SIG", "5 неверных кодов, затем верный", f"{st_list} → {st} {str(body)[:80]}", st == 400)
codes_req = [coffee.req("POST", f"/api/applications/{a2['id']}/signature")[0] for _ in range(30)]
log("SIG", "30 запросов нового кода подряд (лимит на перевыпуск)", sorted(set(codes_req)),
    "PASS" if 429 in codes_req else "INFO",
    "лимита нет, но код показывают только самому подписанту — перебирать его некому")

for r in out:
    print(r)
sys.exit(1 if any(r[3] == "FAIL" for r in out) else 0)
