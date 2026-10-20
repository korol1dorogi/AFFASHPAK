# Спецификация синтетических данных (D7)

> v1 · `generator_version = "datagen-2026.10-v1"`. Закрывает T5, O3 ([case.md](case.md)). Исполнитель — генератор S2 (`backend/apps/demo_data/`), потребители — симуляторы S1 и `seed_demo`, калибровка — D9.
> Имена сущностей, полей и значений — только из [data-model.md](data-model.md) и моделей `backend/apps/*/models.py`. Формулы — только функции `backend/apps/credit_math/` ([knowledge/credit.md](knowledge/credit.md)); пометка «**для S2**» — функции нет, S2 пишет её по описанию (где ей жить — раздел 12). Продукты — [products.md](products.md) (D3), скоринг и правила — [decision-model.md](decision-model.md) (D4). Пометка «**допущение**» — значения нет в репозитории, выбрано здесь, причина — одной строкой.

## 1. Назначение и принципы

| Принцип | Что это значит для генератора |
|---|---|
| Один генератор — один источник правды | `generate(seed, generator_version, as_of, n_companies) → dict`, сериализуется в один JSON (раздел 2). Из него читают симуляторы S1 (ответы по ИНН) и `seed_demo` (строки БД). Других источников синтетики нет ([decisions.md](decisions.md), D9) |
| Детерминизм | Тот же `seed` + `generator_version` + `as_of` + `n_companies` → байт-в-байт тот же JSON (ключи отсортированы, `ensure_ascii=False`, отступ 2). Ни текущей даты, ни `uuid4`, ни `hash()` — только `random.Random` от строкового зерна (раздел 6.6) |
| Опорная дата | `as_of = 2026-10-01` (**допущение**: начало недели хакатона, все выписки — полные месяцы до неё). Все даты генератора считаются от `as_of`, а не от «сегодня» |
| Параметры по умолчанию | `seed = 2026`, `n_companies = 240` (засев). Для D9 тот же генератор запускается с `n_companies = 5000` — только расчёт, без засева (раздел 6.5) |
| Всё синтетика (O3) | Компании, люди, адреса, выписки, документы, заявки выдуманы. Реальных людей и компаний нет; данные кейса не используются (их нет, D9) |
| Метка «демо» | `is_demo = true` у каждой `Company` и `UserProfile`. Строка «(демо)» — в конце каждого `name`, `full_name`, `director_name`, `address`, `counterparty`, `purpose`, `summary`, `message`, `original_name`; в PDF-заглушках — водяной знак «ДЕМО» |
| Регион 00 | ИНН и ОГРН — с валидной контрольной суммой и кодом региона `00`: такого региона нет, совпадение с реальной организацией исключено (раздел 3) |
| Без секретов | Паролей, ключей и кодов подписи в JSON нет: пароли задаёт `seed_demo` из `.env`/фикстур, коды подписи — только хеш (раздел 8) |
| Снимок = функция выписки | Поля `FinancialSnapshot` из выписки никогда не задаются «руками»: генератор строит выписку под целевые значения и записывает в снимок то, что **пересчитано** из выписки (раздел 4). Отчётные поля (`revenue`, `ebitda`, …) задаются напрямую |

## 2. Формат выходного JSON

Ключи верхнего уровня и записей — имена полей моделей. Служебные поля генератора (в модели не пишутся) — с префиксом `_`.

| Тип | Формат | Пример |
|---|---|---|
| Деньги (`Decimal(14,2)`) | строка, точка, 2 знака | `"3000000.00"` |
| Коэффициент, ставка (`Decimal(8,4)`) | строка, доля, 4 знака | `"0.1000"`, `"0.2000"` (= 20%) |
| Дата | ISO `YYYY-MM-DD` | `"2023-10-01"` |
| Дата-время | ISO UTC с `Z` | `"2026-09-14T09:30:00Z"` |
| Период снимка | `YYYY-MM` | `"2026-09"` |
| Нет значения | `null` (не `0`, не `""`) | `"ebitda": null` |
| Ссылка на запись | служебный `_key` записи (строка) | `"company": "co_coffee_shop"` |

### 2.1. Разделы

| Раздел | Запись (поля) | Кто читает |
|---|---|---|
| `meta` | `generator_version`, `seed`, `as_of`, `n_companies`, `is_demo: true`, `counts` (число записей по разделам) | все |
| `companies[]` | `_key`, `legal_form`, `name`, `inn`, `ogrn`, `okved`, `okved_name`, `registered_at`, `region`, `address`, `registry_status`, `director_name`, `is_demo`, `created_at`; служебные: `_persona` (код или `null`), `_okved_group` (раздел 6.2) | seed, S1 (`egrul`) |
| `users[]` | `_key`, `username`, `profile: {kind, full_name, is_demo}`; служебное `_login_enabled` (bool, раздел 8) | seed |
| `memberships[]` | `user`, `company`, `role`, `position` | seed |
| `financial_snapshots[]` | `company`, `period`, `source = "simulator"`, `cleaned_credit_turnover`, `cfads`, `debt_service`, `revenue`, `cogs`, `ebitda`, `debt`, `cash`, `receivables`, `inventory`, `payables`, `counterparty_concentration`, `revenue_trend` | seed, S1 (`bank_account`) |
| `statements[]` | `company`, `account_masked`, `period_from`, `period_to`, `transactions[]` — `date`, `direction`, `amount`, `counterparty`, `counterparty_inn`, `category`, `purpose` (формат — [data/SCHEMA.md](../data/SCHEMA.md) + `counterparty_inn`, раздел 4.1) | S1 (`bank_account`) |
| `simulators` | `egrul`, `transparent_business`, `bki`: словари `inn → {status, data}` (раздел 5). `bank_account` отдельно не дублируется: симулятор берёт `statements[]` и `financial_snapshots[]` по ИНН компании | S1 |
| `applications[]` | поля `Application`: `_key`, `company`, `created_by`, `need_type`, `purpose`, `product` (код продукта D3, `null` для черновика без продукта), `requested_amount`, `term_months`, `invoice_amount`, `collateral_description`, `status`, `version`, `assignee`, `prefill_source`, `source_unavailable`, `created_at`, `submitted_at`, `status_changed_at`, `decided_at`; вложенные: `events[]`, `checks[]`, `score`, `decisions[]` (у каждого — `offer` или `null`), `info_requests[]`, `documents[]`, `signature`, `disbursement` (раздел 7) | seed |
| `personas` | `код → {company, application, users}` — ключи записей персон 1–7 (раздел 9) | seed, e2e, тесты D5 |
| `edge_cases[]` | `{code, company, snapshot, checks, application, expected}` — Г1–Г10 и прочие края (раздел 10); `seed_demo` их не засевает | тесты D5, L4 |
| `_latent` | `company → {segment, pd, default_12m}` (раздел 6.4); `seed_demo` раздел не читает | D9 |

Каталог продуктов в JSON не дублируется: его грузит фикстура D3 (`loaddata products`), заявки ссылаются на `Product.code`.

### 2.2. Пример: компания персоны 1 (сокращено)

```json
{
  "companies": [{
    "_key": "co_coffee_shop", "_persona": "coffee_shop", "_okved_group": "food_service",
    "legal_form": "ip", "name": "ИП Лаврова Анна Сергеевна — кофейня «Зерно и пар» (демо)",
    "inn": "000100000170", "ogrn": "323000100000013",
    "okved": "56.10", "okved_name": "Деятельность ресторанов и услуги по доставке продуктов питания",
    "registered_at": "2023-10-01", "region": "Демо-регион (00)",
    "address": "000001, Демо-регион, г. Условный, ул. Кофейная, д. 7 (демо)",
    "registry_status": "active", "director_name": "Лаврова Анна Сергеевна (демо)",
    "is_demo": true, "created_at": "2026-10-01T00:00:00Z"
  }],
  "users": [{
    "_key": "u_coffee_shop", "username": "demo_coffee_shop", "_login_enabled": true,
    "profile": {"kind": "client", "full_name": "Лаврова Анна Сергеевна (демо)", "is_demo": true}
  }],
  "memberships": [{"user": "u_coffee_shop", "company": "co_coffee_shop", "role": "signatory", "position": "Индивидуальный предприниматель"}],
  "financial_snapshots": [{
    "company": "co_coffee_shop", "period": "2026-09", "source": "simulator",
    "cleaned_credit_turnover": "3000000.00", "cfads": "450000.00", "debt_service": "0.00",
    "revenue": null, "cogs": null, "ebitda": null, "debt": null, "cash": null,
    "receivables": null, "inventory": null, "payables": null,
    "counterparty_concentration": "0.1000", "revenue_trend": "1.0500"
  }],
  "statements": [{
    "company": "co_coffee_shop", "account_masked": "40802810••••••••0170",
    "period_from": "2025-04-01", "period_to": "2026-09-30",
    "transactions": [
      {"date": "2025-04-01", "direction": "credit", "amount": "95120.00", "counterparty": "Эквайринг (демо)", "counterparty_inn": null, "category": "revenue", "purpose": "Зачисление по эквайрингу за 31.03 (демо)"},
      {"date": "2025-04-05", "direction": "debit", "amount": "390000.00", "counterparty": "Сотрудники (демо)", "counterparty_inn": null, "category": "payroll", "purpose": "Заработная плата за март (демо)"},
      {"date": "2025-04-10", "direction": "credit", "amount": "143000.00", "counterparty": "ООО «Офис на Северной» (демо)", "counterparty_inn": "0002000013", "category": "revenue", "purpose": "Оплата кейтеринга по договору 7 (демо)"}
    ]
  }],
  "simulators": {
    "egrul": {"000100000170": {"status": "ok", "data": {"registry_status": "active", "registered_at": "2023-10-01", "okved": "56.10", "director_name": "Лаврова Анна Сергеевна (демо)", "founders": [{"name": "Лаврова Анна Сергеевна (демо)", "share": "1.0000"}]}}},
    "transparent_business": {"000100000170": {"status": "ok", "data": {"mass_address": false, "mass_director": false, "tax_arrears": "0.00"}}},
    "bki": {"000100000170": {"status": "ok", "data": {"current_overdue_days": 0, "past_overdue_max_days": 0, "obligations": []}}}
  },
  "applications": [{
    "_key": "app_coffee_shop", "_seed": false, "company": "co_coffee_shop", "created_by": "u_coffee_shop",
    "need_type": "cash_gap", "purpose": "Выплатить зарплату 5-го числа до поступлений от клиентов (демо)",
    "product": "overdraft_basic", "requested_amount": "900000.00", "term_months": 12,
    "invoice_amount": null, "collateral_description": null, "status": "draft", "version": 0,
    "assignee": null, "prefill_source": "recommendation", "source_unavailable": false,
    "created_at": null, "submitted_at": null, "status_changed_at": null, "decided_at": null,
    "events": [], "checks": [], "score": null, "decisions": [], "info_requests": [], "documents": [],
    "signature": null, "disbursement": null
  }]
}
```

Суммы транзакций в примере иллюстративны; точные месячные итоги персоны 1 — в разделе 9.2.

## 3. Идентификаторы, имена, адреса

### 3.1. ИНН и ОГРН (код региона 00)
`d1…dn` — цифры слева направо; `Σ` — сумма произведений цифр на веса.

| Идентификатор | Кому | Структура | Контрольные цифры |
|---|---|---|---|
| ИНН, 10 цифр | ООО | `00` (регион) + `01` (инспекция) + 5 цифр номера + 1 контрольная | `d10 = (Σ d1…d9 × [2, 4, 10, 3, 5, 9, 4, 6, 8]) mod 11 mod 10` |
| ИНН, 12 цифр | ИП (и физлица — учредители, раздел 8) | `00` + `01` + 6 цифр номера + 2 контрольные | `d11 = (Σ d1…d10 × [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) mod 11 mod 10`; `d12 = (Σ d1…d11 × [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) mod 11 mod 10` |
| ОГРН, 13 цифр | ООО | `1` + `ГГ` (две последние цифры года `registered_at`) + `00` (регион) + `01` (инспекция) + 5 цифр номера + 1 контрольная | `d13 = (число из d1…d12) mod 11 mod 10` |
| ОГРНИП, 15 цифр | ИП | `3` + `ГГ` + `00` + `01` + 7 цифр номера + 1 контрольная | `d15 = (число из d1…d14) mod 13 mod 10` |

- **Номера.** Номер записи — сквозной счётчик по виду идентификатора. `1–99` зарезервированы за персонами и не зависят от `seed` (персона N — номер N), `100–999` — за краевыми случаями (раздел 10, по порядку), популяция — с `1000` подряд в порядке генерации. Так ИНН уникальны по построению, а ИНН персон одинаковы при любом зерне.
- **Контрагенты в выписках** с `counterparty_inn` — ООО с инспекцией `02` (`0002…`), номер из своего счётчика; в `companies[]` их нет, это только плательщики и получатели.
- **Проверка** (раздел 11): у каждого ИНН и ОГРН контрольные цифры совпадают с пересчитанными, длина — 10/13 у ООО и 12/15 у ИП, `inn[0:2] == "00"`, у ОГРН `ogrn[3:5] == "00"` и `ogrn[1:3]` = год `registered_at`.
- Реквизиты персон — в разделе 9.1.

### 3.2. Маска счёта
`account_masked` (в `statements[]` и `Disbursement`): 20 символов = балансовый счёт (`40802` у ИП, `40702` у ООО) + `810` (рубли) + `••••••••` (8 точек) + последние 4 цифры ИНН. Пример: `40802810••••••••0170`. Полного номера счёта в JSON нет; контрольный разряд не считается (**допущение**: номер не показывается целиком и ни с чем не сверяется).

### 3.3. Имена, названия, адреса
- **Люди.** ФИО собираются из фиксированных списков в коде генератора: 40 фамилий, 30 мужских и 30 женских имён, 30 отчеств (частотные, но в сочетании вымышленные), с согласованием по роду; к `full_name` и `director_name` добавляется « (демо)». Совпадение сочетания с реальным человеком не исключено, поэтому метка «(демо)» обязательна, а других персональных данных (дат рождения, паспортов, телефонов, email) генератор не создаёт.
- **ООО:** `ООО «{прилагательное} {существительное}» (демо)` из списков по группе ОКВЭД (раздел 6.2), например «ООО «Северная мебель» (демо)». **ИП:** `ИП {Фамилия} {Имя} {Отчество} — {вид бизнеса} «{вывеска}» (демо)`. Слова, повторяющие известные бренды, в списки не включаются.
- **`region`** = `"Демо-регион (00)"` у всех (**допущение**: формат поля в data-model не задан; так видно, что регион вымышленный).
- **`address`** = `{индекс 0000NN}, Демо-регион, г. {Условный | Примерный | Тестовск | Образцовск}, ул. {из списка 30 улиц}, д. {1–120} (демо)`. У компаний с флагом `mass_address` (раздел 5) — один из 3 «массовых» адресов, общий для нескольких компаний.
- **`okved_name`** — официальное наименование кода ОКВЭД 2 (раздел 6.2): это публичный классификатор, не персональные данные.
