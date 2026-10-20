# Тестовые сценарии (S5)

> Закрывает T7 «тестовые сценарии» ([case.md](case.md)). Здесь связаны персоны, шаги, ожидаемый исход и автотесты для семи сценариев из [plan.md](plan.md#ключевые-сценарии-каждый--e2e-тест-и-шаг-демо).
> Источники: статусы, переходы, роли и `available_actions` — [state-machine.md](state-machine.md); операции — [openapi.yaml](openapi.yaml); продукты — [products.md](products.md) (D3); грейды, исходы, суммы и граничные случаи — [decision-model.md](decision-model.md) (D4, раздел 8); учётки, данные персон и края — [data-spec.md](data-spec.md) (D7, разделы 8–11); сюжет демо — [demo.md](demo.md). Если числа здесь расходятся с decision-model.md, верен decision-model.md, а этот файл нужно исправить.
> Клиенту любой автоматический исход показываем как «предварительную оценку», не как «решение банка» ([domain.md](domain.md#правила-языка-в-интерфейсе)).

## 1. Как читать

### Уровни тестов
| Уровень | Что проверяет | Где | Инструмент |
|---|---|---|---|
| unit | формулы и балльная карта: чистые функции на эталонных числах | `backend/apps/credit_math/tests/`, `backend/apps/scoring/tests/` (появится в D5), `backend/apps/applications/tests/test_transitions.py` (стейт-машина) | pytest |
| API | эндпоинты: контракт (`assert_matches_contract`), роли, доступ, переходы, журнал, уведомления | `backend/apps/*/tests/test_api*.py`, `backend/apps/documents/tests/` | pytest + DRF APIClient |
| e2e | путь человека в браузере: экраны `/app/*` и `/bank/*` | `e2e/journey.spec.ts`, `e2e/smoke.spec.ts` | Playwright |
| коллекция | те же шаги через HTTP, прогон в CI | `postman/` (S4) | Postman + newman |

### Статусы тестов
| Статус | Значит |
|---|---|
| **есть** | тест в main, зелёный, проверяет то, что заявлено в строке |
| **есть частично** | тест в main, зелёный, но проверяет не всё; что именно он пропускает, написано в колонке «Что не проверяет» |
| **заготовка** | `test.fixme(...)` в `e2e/journey.spec.ts`: имя и место есть, тела нет, Playwright его пропускает |
| **план: <ID>** | теста нет; написать его должна задача <ID> из [tasks.md](tasks.md). Имени у такого теста пока нет, и здесь мы его не придумываем |

### Обозначения в таблицах шагов
- **Кто**: `signatory` (подписант: собственник или директор), `preparer` (бухгалтер, готовит заявку), `bank_manager` (сотрудник банка), «система» (конвейер L4 и симуляторы S1).
- **Действие**: экран, затем операция API в виде `МЕТОД путь` (operationId). Для `{id}` подставляется id заявки.
- **Ожидаемый результат**: статус; `available_actions` текущего пользователя; деньги — строки-десятичные, как их отдаёт API (`"900000.00"`, ставка — доля, `0.20` = 20 %; число знаков у ставки контракт не фиксирует, поэтому в тестах ставку сравниваем как Decimal); ключевые `reasons` в формате `metric: value / threshold → ✓ или ✗`; событие журнала (`ApplicationEvent.kind`); уведомление клиенту (`Notification.title` из [state-machine.md](state-machine.md#переходы)).
- Уведомление при переходе получают участники компании, кроме того, кто сам сделал действие: так написано в `test_transition_moves_status_bumps_version_writes_event_and_notifies`.

## 2. Учётки и данные

### Учётки
Логины взяты из [data-spec.md](data-spec.md), раздел 8 (таблица 9.1). **Пароли здесь не пишем: их задаёт `seed_demo` из `.env` или фикстур.** На стенде (`DEMO_MODE=1`) можно войти без пароля, быстрым входом: `/bank/demo`, `POST /api/demo/login` (`demoLogin`).

| Сценарий | Персона (код) | Компания (демо) | `username` | Роль | Вход |
|---|---|---|---|---|---|
| 1 | `coffee_shop` | ИП, кофейня «Зерно и пар», ИНН 000100000170 | `demo_coffee_shop` | `signatory` | да |
| 2 | `retail_supplier` | ООО «Северный поставщик», ИНН 0001000028 | `demo_retail_supplier` | `signatory` | да |
| 3 | `garden_store` | ИП, садовый центр «Зелёный двор», ИНН 000100000318 | `demo_garden_store` | `signatory` | да |
| 4 | `furniture_maker` | ООО «Дубрава Мебель», ИНН 0001000042 | `demo_furniture_maker` | `signatory` (генеральный директор) | да |
| 4 | `furniture_maker` | то же | `demo_accountant` | `preparer` (главный бухгалтер): создаёт заявку, отвечает на запрос | да |
| 5 | `dependent_supplier` | ООО «Опора Снаб», ИНН 0001000050 | `demo_dependent_supplier` | `signatory` | да |
| 6 | `liquidating_company` | ООО «Вектор Сервис», ИНН 0001000067, `registry_status = liquidating` | `demo_liquidating_company` | `signatory` | да |
| 7 | `bki_outage` | ИП, кофейня «Северный ветер», ИНН 000100000702 | `demo_bki_outage` | `signatory` | да |
| 4, 7, все | — | — | `demo_bank` | `bank_manager` | да |
| очередь | — | — | `demo_bank_2`, `demo_bank_3` | `bank_manager` (нужны, чтобы фильтр очереди по исполнителю что-то показывал) | да |

Пользователи из популяции (`demo_c{i:04d}_dir`, `demo_c{i:04d}_acc`) войти не могут: `seed_demo` ставит им `set_unusable_password`. В сценариях они не участвуют.

### Откуда данные
| Что | Откуда | Кто делает |
|---|---|---|
| Компании, люди, выписки, снимки `FinancialSnapshot`, ответы симуляторов, заявки популяции | генератор `generate(seed=2026, n_companies=240)` по [data-spec.md](data-spec.md) → JSON → `seed_demo` | S2 (генератор), L5 (init-контейнер) |
| Каталог продуктов (`overdraft_basic`, `factoring_basic`, `working_capital_loan_basic`, `investment_loan_basic`, `leasing_basic`) | фикстура D3: `docker compose run --rm backend python manage.py loaddata products` | D3 |
| Черновики заявок персон 2–6 и их обязательные документы | `seed_demo` по data-spec 9.3. Заявки персон 1 и 7 не засеваются (`_seed: false`): в сценарии их создают подбор или ассистент | S2 |
| Граничные случаи `edge_cases[]` (Г1–Г10 и края) | тот же JSON. `seed_demo` их **не** засевает, их читают тесты D5 и L4 | S2 → D5, L4 |
| Сбой источника (сценарий 7) | `DemoState(source).failing`. `seed_demo` выставляет всем `false`; включается в `/bank/demo` → `PUT /api/demo/failures` (`setDemoFailures`). Пока флаг стоит, симулятор отвечает `unavailable` на любой ИНН | S1 (симулятор), L5/B7 (панель) |
| Сброс демо | `POST /api/demo/reset` (`resetDemo`), только при `DEMO_MODE=1` | L5/B7 |

Тесты API в main на эти данные не опираются. Каждый тест строит свой мир: фикстура `world` в `backend/apps/applications/tests/conftest.py` и фабрики `apps/core/factories.py`. В этом мире пользователи `director` (signatory), `accountant` (preparer), `outsider` (signatory чужой компании) и `manager` (банк), продукты фабрики `overdraft_demo` и `working_capital_demo`, заявка по умолчанию на 100 000.00 ₽ и 12 мес. Поэтому числа персон в них не проверяются (см. «есть частично»).

## 3. Сценарии 1–7

Путь по переходам каждого сценария — [state-machine.md](state-machine.md#сценарии-плана--переходы). Номера переходов ниже взяты из таблицы «Переходы» того же файла.

### Общий блок «Подписание и выдача» (переходы 11 → 13 → 14)
Сценарии 1–4 заканчиваются этим блоком. Заявка стоит в `offer`, активный оффер `status = active`, действует подписант персоны.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| П-1 | signatory | `/app/applications/:id` → «Принять» · `POST /api/applications/{id}/offer/accept` (`acceptOffer`) | `signing`; `offer.status = accepted`; `available_actions = [sign]`; событие `status_changed` |
| П-2 | signatory | `/app/applications/:id/sign` · `POST /api/applications/{id}/signature` (`startSignature`) | 200 `SignatureChallenge`: `code` из 6 цифр **показан на экране** (никаких SMS и почты, O5), `expires_at`, `attempts_left`. Повторный вызов выдаёт новый код |
| П-3 | signatory | ввести неверный код · `POST /api/applications/{id}/signature/confirm` (`confirmSignature`) | 400; статус остаётся `signing`; `attempts_left` уменьшается на 1 |
| П-4 | signatory | ввести код с экрана · `POST …/signature/confirm` | `signed`; событие `signed`; уведомление «Договор подписан» |
| П-5 | система | симулятор выдачи: `disbursement.done` (переход 14) | `issued`; событие `issued`; уведомление «Деньги выданы»; `available_actions = []`. Таймлайн `GET /api/applications/{id}/events` (`listApplicationEvents`) заканчивается на `… offer → signing → signed → issued` |

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `test_scenario_1_offer_signing_and_disbursement` (`backend/apps/applications/tests/test_api_client.py`) | API | есть частично | проверяет П-1…П-5 и таймлайн `submitted → processing → offer → signing → signed → issued`. Выдачу вызывает напрямую через `services.mark_issued`, симулятор выдачи S1 не участвует (план: S1, L4). Подписание проверено только для овердрафта (фабричного `overdraft_demo`) |
| `test_available_actions` (`test_transitions.py`, случаи `offer`/`signing`) | unit | есть | — |
| `test_cancel_by_signatory_from_offer_declines_the_offer` | API | есть | ветка отказа от оффера (переход 12), в демо её нет |

---

### Сценарий 1. Кофейня: подбор → овердрафт → автоматический оффер → подписание → выдача
- **Цель:** провести клиента по всему пути от потребности до выдачи без участия сотрудника.
- **Доказывает:** F3 (кабинет, выбор продукта, путь до результата), F5 (статус меняется последовательно, журнал), F9 (исход «одобрение»), F10 (подписание и выдача), F11, F12 (заявка предзаполнена из подбора), O5 (код на экране).
- **Персона:** 1 `coffee_shop`, вход `demo_coffee_shop`. ИП, 36 мес, очищенный оборот 3 000 000 ₽/мес, `cfads` 450 000, долгов нет, тренд 1.05, концентрация 0.10. Проверки все `ok`.
- **Предусловия:** `seed_demo` выполнен; заявки у персоны нет (`_seed: false`); все флаги `DemoState.failing = false`.
- **Переходы:** 1 → 2 → 4 (оффер) → 11 → 13 → 14.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | signatory | `/login` · `POST /api/auth/login` (`login`); на стенде можно `POST /api/demo/login` (`demoLogin`) → `/app` · `GET /api/auth/me` (`getMe`), `GET /api/company/metrics` (`getCompanyMetrics`) | открыт кабинет; метрики компании с пояснениями (демо-данные из выписки) |
| 2 | signatory | `/app/match`, потребность «кассовый разрыв» · `POST /api/recommendations` (`createRecommendations`), `need_type = cash_gap` | `is_preliminary = true`; первый оффер (`rank = 1`) — `overdraft_basic`, `amount = "900000.00"`, `monthly_payment = null`; в `reasons` есть `overdraft_limit` 900 000 (`overdraft_limit(3 000 000, 0.3)`); `stop_factors = []` |
| 3 | signatory | «Оформить» → `/app/applications/new` · `POST /api/applications` (`createApplication`): `need_type = cash_gap`, `product_code = overdraft_basic`, `requested_amount = "900000.00"`, `term_months = 12`, `prefill_source = recommendation` | 201; `draft`, `version = 0`; поля заполнены из подбора, повторно ничего вводить не нужно (F12); `available_actions = [edit, upload_document, submit, cancel]` |
| 4 | signatory | автосохранение · `PATCH /api/applications/{id}` (`updateApplication`) с `version` | 200, `version + 1`; черновик сохраняется после перезагрузки страницы |
| 5 | signatory | «Отправить» · `POST /api/applications/{id}/submit` (`submitApplication`) с заголовком `Idempotency-Key` | `submitted` (переход 1); событие `status_changed`; уведомление «Заявка отправлена» |
| 6 | система | `pipeline.start` → validation → enrichment → scoring | `processing` (переход 2); `Check` по `egrul`, `transparent_business`, `bki`, `bank_account` — все `ok` (события `check_completed`); `Score`: **92, грейд A**, `model_version = "scorecard-2026.10-v1"` (событие `score_calculated`) |
| 7 | система | decision: правило П8 (`auto_offer`) | `offer` (переход 4); `Decision`: `outcome = offer`, `decided_by = auto`, `is_preliminary = true`, `grade = A`, `policy_version = "2026.10-v1"`; оффер **`amount = "900000.00"`, `rate` = 0.20 (20 %), `term_months = 12`, `monthly_payment = null`**, `is_counteroffer = false`, `product_changed = false`. Reasons: `score_total` 92 / 75 → ✓; `overdraft_limit` 900 000 / 900 000 → ✓; `dscr` null → ✓ «долгов нет». Событие `decision`, уведомление «Готово предложение». `available_actions = [accept_offer, decline_offer, cancel]`. В интерфейсе написано «предварительная оценка» |
| 8–12 | signatory, система | блок «Подписание и выдача» П-1…П-5 | `issued` |
| 13 | bank_manager | `/bank` · `GET /api/bank/applications` (`listBankApplications`) → `/bank/applications/:id` · `GET /api/bank/applications/{id}` (`getBankApplication`) | та же заявка видна в очереди банка; в карточке проверки, скоринг 92/A, журнал. Действий у банка нет: заявка не в `manual_review` |

**Итог:** `issued`, овердрафт 900 000 ₽ под 20 % на 12 мес, грейд A (92), решение автоматическое (П8).

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `test_scenario_1_offer_signing_and_disbursement` | API | есть частично | числа задаёт сам тест: в `record_auto_decision` переданы 100 000 ₽, 20 %, грейд A, продукт `overdraft_demo`; конвейера нет, решение вызвано напрямую. Расчёт 900 000 ₽ и грейда A из данных персоны — план: D5, L4. Подбор (шаг 2) не проверяет |
| `test_create_list_and_get_match_contract` | API | есть частично | создание черновика по контракту и `available_actions`; продукт `overdraft_demo`, не `overdraft_basic` |
| `test_autosave_with_version_and_conflict` | API | есть | шаг 4 |
| `test_submit_is_idempotent_by_key` | API | есть | шаг 5 |
| `test_card_example_overdraft_limit` (`backend/apps/credit_math/tests/test_limits.py`) | unit | есть | `overdraft_limit(3 000 000, 0.3) = 900 000.00` |
| `test_dscr_without_debt_is_none_with_reason` (`test_metrics.py`) | unit | есть частично | DSCR = None с причиной при отсутствии долга. Что фактор дальше получает 25 баллов — план: D5 |
| `scenario 1 › client logs in as the persona and sees the dashboard (C2, C8)` | e2e | заготовка | — |
| `scenario 1 › match recommends an overdraft of 900 000 ₽ with reasons (C4)` | e2e | заготовка | — |
| `scenario 1 › wizard prefills the application; director submits (C5)` | e2e | заготовка | — |
| `scenario 1 › auto offer → accept → sign with the on-screen code → issued (C6, C7)` | e2e | заготовка | — |
| баллы и грейд персоны 1 (92, A) | unit | план: D5 | — |
| персона 1 через конвейер до `offer` с 900 000 ₽ | API | план: L4 (критерий готовности L4) | — |
| подбор для `cash_gap` → `overdraft_basic` 900 000 ₽ | API | план: D6 | — |
| шаги 1–13 через HTTP | коллекция | план: S4 | — |

---

### Сценарий 2. Поставщик: факторинг под отгрузку
- **Цель:** показать продукт под конкретную отгрузку (УПД) с прозрачной комиссией.
- **Доказывает:** F3, F8 (грейд B при концентрации ✗ всё равно даёт оффер: скоринг ≠ решение), F9 (одобрение), F10.
- **Персона:** 2 `retail_supplier`, вход `demo_retail_supplier`. ООО, 72 мес, `cfads` 550 000, `debt_service` 250 000, `debt` 18 600 000, `ebitda` 7 000 000, `cash` 600 000, тренд 1.00, концентрация 0.60.
- **Предусловия:** `seed_demo` засеял черновик: `receivable_delay`, `factoring_basic`, `requested_amount = "4500000.00"`, `term_months = 2`, `invoice_amount = "5000000.00"`; документы `contract` и `shipment_document` загружены.
- **Переходы:** 1 → 2 → 4 → 11 → 13 → 14.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | signatory | вход (как в сценарии 1, шаг 1) → `/app/applications` · `GET /api/applications` (`listApplications`) → `/app/applications/:id` · `GET /api/applications/{id}` (`getApplication`), `GET /api/applications/{id}/documents` (`listApplicationDocuments`) | черновик с полями из предусловий; два документа; `available_actions = [edit, upload_document, submit, cancel]` |
| 2 | signatory | (необязательно) `/app/match` · `POST /api/recommendations`, `need_type = receivable_delay`, `invoice_amount = "5000000.00"` | первый оффер — `factoring_basic`, `amount = "4500000.00"` (`factoring_advance(5 000 000, 0.9)`) |
| 3 | signatory | `POST /api/applications/{id}/submit` с `Idempotency-Key` | `submitted`; уведомление «Заявка отправлена» |
| 4 | система | конвейер | `processing`; проверки все `ok`; **88, грейд B** |
| 5 | система | П8 `auto_offer` | `offer`; `Decision.outcome = offer`, `grade = B`, `is_preliminary = true`; оффер **`amount = "4500000.00"`, `rate` = 0.225 (22.5 %), `term_months = 2`**, `monthly_payment = null`, `is_counteroffer = false`. Reasons: `score_total` 88 / 75 → ✓; `factoring_advance` 4 500 000 / 4 500 000 → ✓; `factoring_commission` 25 000 «Разовая комиссия — 25 000 ₽ (0,5 % отгрузки)»; `counterparty_concentration` 0.6 / 0.5 → ✗ (видна, но грейд B). Уведомление «Готово предложение» |
| 6–10 | signatory, система | блок «Подписание и выдача» | `issued` |

**Итог:** `issued`, факторинг 4 500 000 ₽ под 22.5 % на 2 мес, комиссия 25 000 ₽, грейд B (88).

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `test_card_example_factoring_advance` (`test_limits.py`) | unit | есть | `factoring_advance(5 000 000, 0.9) = 4 500 000.00` |
| `test_scenario_1_offer_signing_and_disbursement` | API | есть частично | путь статусов тот же, но для фабричного овердрафта. Факторинг, `invoice_amount` и комиссию не проверяет |
| `scenario 2 › factoring offer of 4 500 000 ₽ for the UPD amount → issued (C4, C7)` | e2e | заготовка | исполнителя нет: C10 закрывает сценарии 1 и 3, S6 — сценарии 3–7 (см. раздел 9) |
| баллы и грейд персоны 2 (88, B); `factoring_commission` = 25 000 | unit | план: D5 | функции `factoring_commission` в `credit_math` пока нет (D4, раздел 5) |
| персона 2 через конвейер до `offer` | API | план: L4 | — |
| подбор для `receivable_delay` | API | план: D6 | — |

---

### Сценарий 3. Сезонный магазин: контроффер по DSCR
- **Цель:** клиент просит больше, чем может обслуживать; система предлагает посильную сумму и объясняет почему.
- **Доказывает:** F8 (грейд B, но сумму ограничивает правило П7, а не скоринг), F9 (иные условия), F10, F11 (понятное объяснение и «что улучшить»).
- **Персона:** 3 `garden_store`, вход `demo_garden_store`. ИП, 96 мес; `cfads` 300 000, `debt_service` 50 000, дебиторка 4 500 000, запасы 2 400 000, кредиторка 1 600 000, тренд 0.95, концентрация 0.05.
- **Предусловия:** засеян черновик `working_capital`, `working_capital_loan_basic`, `requested_amount = "5300000.00"`, `term_months = 12`; документы `bank_statement` и `tax_return` загружены.
- **Переходы:** 1 → 2 → 4 (контроффер) → 11 → 13 → 14.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | signatory | вход → `/app/applications/:id` · `GET /api/applications/{id}` | черновик на 5 300 000 ₽, 12 мес |
| 2 | signatory | `POST /api/applications/{id}/submit` с `Idempotency-Key` | `submitted`; уведомление «Заявка отправлена» |
| 3 | система | конвейер | `processing`; проверки `ok`; **87, грейд B** |
| 4 | система | П7 `auto_counteroffer` | `offer`; `Decision.outcome = counteroffer`, `grade = B`, `is_preliminary = true`; оффер **`amount = "2009314.00"`, `requested_amount = "5300000.00"`, `rate` = 0.24 (24 %), `term_months = 12`, `monthly_payment = "189999.92"`**, `is_counteroffer = true`, `product_changed = false`; переплата 270 685.07 (`annuity_summary`). Reasons: `score_total` 87 / 75 → ✓; `working_capital_need` 5 300 000 / 5 300 000 → ✓; `max_loan_by_dscr` 2 009 314 / 5 300 000 → ✗ (`max_loan_by_dscr(300 000, 50 000, 0.24, 12, 1.25)`); `dscr_after` 1.2500 / 1.25 → ✓. `improvements`: «При сроке 24 мес допустимо 3 593 645 ₽»; «Снизьте текущие платежи по долгам». Уведомление «Готово предложение» |
| 5 | signatory | `/app/applications/:id`: экран контроффера | видны запрошенная и предложенная суммы, причина (DSCR) и «что улучшить»; написано «предварительная оценка». `available_actions = [accept_offer, decline_offer, cancel]` |
| 6–10 | signatory, система | блок «Подписание и выдача» | `issued` на 2 009 314 ₽ |

**Итог:** `issued`, КПО 2 009 314 ₽ под 24 % на 12 мес вместо запрошенных 5 300 000 ₽, грейд B (87).

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `test_scenario_3_counteroffer_by_dscr` (`test_api_client.py`) | API | есть частично | числа задаёт сам тест: 2 009 314.00 и 0.24 переданы в `record_auto_decision`, продукт `working_capital_demo`; проверяет `is_counteroffer`, `product_changed`, `amount`, `requested_amount`, наличие `monthly_payment`. Не проверяет значение платежа 189 999.92, `improvements`, принятие и выдачу. Расчёт из данных персоны — план: D5, L4 |
| `test_card_example_max_loan_by_dscr` (`test_limits.py`) | unit | есть | `max_loan_by_dscr(300 000, 50 000, 0.24, 12) = 2 009 314.00` |
| `test_max_loan_is_maximal_for_card_example` | unit | есть | +1 ₽ к сумме уже нарушает DSCR |
| `test_dscr_holds_after_all_roundings` | unit | есть | `dscr_after ≥ min_dscr` после округлений |
| `scenario 3 › asks 5.3 mln → counteroffer 2 009 314 ₽ with reasons → accepts → issued (C7)` | e2e | заготовка | — |
| баллы и грейд персоны 3 (87, B); платёж 189 999.92 и improvements «3 593 645 ₽ на 24 мес» | unit | план: D5 | — |
| персона 3 через конвейер до контроффера | API | план: L4 | — |
| e2e сценария 3 | e2e | план: C10, S6 | обе задачи называют сценарий 3: нужно договориться, кто пишет (раздел 9) |

---

### Сценарий 4. Производство: грейд C → ручное рассмотрение → запрос документа → одобрение
- **Цель:** показать работу банка в той же заявке и запрос информации; подготовку и подпись делают разные люди.
- **Доказывает:** F4 (этапы банка и модель решения), F6 (запрос уточнения), F7 (проверки во вкладке банка), F8 (грейд C → сотрудник), F9 (запрос информации, одобрение сотрудником), F10, F12 (бухгалтер готовит, директор подписывает, данные не вводятся заново).
- **Персона:** 4 `furniture_maker`: signatory `demo_furniture_maker`, preparer `demo_accountant`, банк `demo_bank`. ООО, 144 мес, `cfads` 1 800 000, `debt_service` 1 000 000, отчётности нет (`debt`, `ebitda` = null), тренд 0.97, концентрация 0.40, БКИ: текущей просрочки нет, прошлая 10 дн.
- **Предусловия:** засеян черновик, `created_by = demo_accountant`: `capex`, `investment_loan_basic`, `requested_amount = "8000000.00"`, `term_months = 36`, `collateral_description` «Фрезерный станок с ЧПУ по договору поставки (демо)». Загружены `bank_statement`, `tax_return`, `contract`, `invoice`; `financial_report` **не** загружен.
- **Переходы:** 1 → 2 → 5 (грейд C) → 8 → загрузка документа → 10 → 7 → 11 → 13 → 14.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | preparer | вход `demo_accountant` → `/app/applications/:id` · `GET /api/applications/{id}` | `draft`; `available_actions = [edit, upload_document]`: кнопки «Отправить» у бухгалтера нет |
| 2 | preparer | попытка отправить · `POST /api/applications/{id}/submit` | 403; статус остаётся `draft` |
| 3 | signatory | вход `demo_furniture_maker` → та же заявка · `POST …/submit` с `Idempotency-Key` | `submitted`; уведомление «Заявка отправлена» получает бухгалтер (действовал директор) |
| 4 | система | конвейер | `processing`; проверки `ok` (БКИ `ok`: прошлая просрочка 10 дн.); **65, грейд C** |
| 5 | система | П5 `needs_review` | `manual_review` (переход 5); `Decision.outcome = manual_review`, `grade = C`. Reasons (заготовка для сотрудника): `score_total` 65 / 75 → ✗; `bki_history` 10 / 30 → ✓; `max_loan_by_dscr` 11 290 503 / 8 000 000 → ✓; `dscr_after` 1.3722 / 1.25 → ✓; `debt_to_ebitda` null — «отчётности нет». Заготовка условий: 8 000 000 ₽, 23.5 %, 36 мес, платёж 311 766.44. Уведомление «Заявку смотрит сотрудник». У signatory `available_actions = [cancel]` |
| 6 | bank_manager | вход `demo_bank` → `/bank`, фильтр «Ручное рассмотрение», грейд C · `GET /api/bank/applications?status=manual_review&grade=C` | заявка в очереди |
| 7 | bank_manager | `/bank/applications/:id`, вкладки «Проверки», «Скоринг», «Документы», «Журнал» · `GET /api/bank/applications/{id}` | `application.available_actions = [assign, approve, counteroffer, request_info, decline]`; разложение скоринга по 7 факторам (10+18+7+10+7+8+5 = 65); 4 документа |
| 8 | bank_manager | «Взять себе» · `POST /api/bank/applications/{id}/assign` (`assignBankApplication`), `{version}` | статус не меняется; `version + 1`; `assignee` — сотрудник; событие `assigned` |
| 9 | bank_manager | «Запросить документ» · `POST /api/bank/applications/{id}/request-info` (`requestInfoBankApplication`): `{version, message: "Загрузите бухгалтерскую отчётность за последний год — по ней оценим долговую нагрузку", document_kinds: ["financial_report"]}` | `info_requested` (переход 8); `InfoRequest.origin = officer`; событие `info_requested`; уведомление «Банк просит документ» |
| 10 | preparer | `/app/applications/:id` · `GET /api/applications/{id}` | `open_info_requests` — один запрос, `origin = officer`, с текстом и `document_kinds = [financial_report]`; `available_actions = [upload_document, respond_info]` |
| 11 | preparer | загрузить PDF · `POST /api/applications/{id}/documents` (`uploadApplicationDocument`), `kind = financial_report` | 201; событие `document_uploaded` |
| 12 | preparer | «Ответить» · `POST /api/applications/{id}/info-requests/{request_id}/respond` (`respondInfoRequest`), `{message}` | `manual_review` (переход 10); событие `info_responded`; повторный ответ на тот же запрос → 404 |
| 13 | bank_manager | карточка: новый документ во вкладке «Документы» · `GET /api/bank/applications/{id}/documents/{document_id}` (`downloadBankApplicationDocument`) | 200, `Content-Disposition: attachment` |
| 14 | bank_manager | «Одобрить» · `POST /api/bank/applications/{id}/approve` (`approveBankApplication`), `{version}` | `offer` (переход 7); `Decision`: `decided_by = officer`, `is_preliminary = false`, `grade = C`, `policy_version = "officer"`; оффер **`amount = "8000000.00"`, `rate` = 0.235 (23.5 %, `rate_for` по грейду C), `term_months = 36`, `monthly_payment = "311766.44"`**, `is_counteroffer = false`. Уведомление «Готово предложение» |
| 15 | preparer | та же заявка | `available_actions = []`: принять оффер может только подписант |
| 16–20 | signatory, система | блок «Подписание и выдача» | `issued`; переплата 3 223 592.05 |

**Итог:** `issued`, инвест-кредит 8 000 000 ₽ под 23.5 % на 36 мес. Грейд C (65), решение сотрудника после запроса `financial_report`.

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `test_scenario_4_info_request_document_and_approval` (`backend/apps/applications/tests/test_api_bank.py`) | API | есть частично | шаги 9–14: фабрика сразу создаёт заявку в `manual_review` (конвейер и грейд C не проверяет); запрошен и загружен `contract`, а не `financial_report`; `approve` даёт фабричные условия, а не 8 000 000 ₽ / 23.5 %; подписание не проверяет. Расчёт из данных персоны — план: D5, L4 |
| `test_preparer_cannot_submit` (`test_api_client.py`) | API | есть | шаг 2 |
| `test_card_matches_contract` | API | есть | `available_actions` банка в `manual_review` (шаг 7) |
| `test_assign_and_stale_version` | API | есть | шаг 8 и 409 при устаревшей `version` |
| `test_upload_is_allowed_when_the_bank_asked_for_documents` (`backend/apps/documents/tests/test_security.py`) | API | есть | шаг 11 |
| `test_approve_creates_offer_on_requested_terms` | API | есть частично | одобрение на запрошенных условиях, `decided_by = officer`, `is_preliminary = false`; сумма и продукт фабричные; ставку `rate_for` по грейду C не проверяет |
| `test_available_actions` (случаи `info_requested`/preparer, `manual_review`/signatory и bank, `offer`/preparer) | unit | есть | шаги 5, 10, 15 |
| `scenario 4 › grade C → manual review; bank requests a document (B4, B5)` | e2e | заготовка | — |
| `scenario 4 › client uploads the document and responds; bank approves (C6, B5)` | e2e | заготовка | — |
| баллы и грейд персоны 4 (65, C), заготовка 11 290 503 / 1.3722, ставка C 23.5 % | unit | план: D5 | — |
| персона 4 через конвейер до `manual_review` | API | план: L4 | — |
| e2e сценария 4 целиком | e2e | план: S6 (клиентская часть — критерий C6, банковская — критерий B4) | — |

---

### Сценарий 5. Зависимый поставщик: отказ с «что улучшить»
- **Цель:** показать, что отказ объяснён в цифрах и подсказывает, что сделать.
- **Доказывает:** F8 (грейд E по балльной карте), F9 (отказ), F11 (понятные причины).
- **Персона:** 5 `dependent_supplier`, вход `demo_dependent_supplier`. ООО, 48 мес, `cfads` 330 000, `debt_service` 300 000, `debt` 16 800 000, `ebitda` 4 000 000, `cash` 0, тренд 0.80, концентрация 0.80.
- **Предусловия:** засеян черновик `working_capital`, `working_capital_loan_basic`, `requested_amount = "3000000.00"`, `term_months = 12`; документы `bank_statement` и `tax_return`.
- **Переходы:** 1 → 2 → 6.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | signatory | вход → `/app/applications/:id` · `POST …/submit` с `Idempotency-Key` | `submitted` |
| 2 | система | конвейер | `processing`; проверки `ok`; **47, грейд E** |
| 3 | система | П4 `auto_decline` | `declined` (переход 6); `Decision.outcome = declined`, `decided_by = auto`, `is_preliminary = true`, `grade = E`. Reasons: `score_total` 47 / 75 → ✗; `dscr` 1.1 / 1.25 → ✗; `debt_to_ebitda` 4.2 / 3.5 → ✗; `revenue_trend` 0.8 / 0.9 → ✗; `counterparty_concentration` 0.8 / 0.5 → ✗. Событие `decision`; уведомление «Отказ: …»; `available_actions = []` |
| 4 | signatory | `/app/applications/:id` · `GET /api/applications/{id}/decision` (`getApplicationDecision`) | `improvements` — ровно 4 пункта в таком порядке: «Снизьте текущие платежи по долгам или увеличьте свободный денежный поток» (−21); «Снизьте долг до 3,5 годовой прибыли» (−11); «Восстановите выручку хотя бы до уровня прошлого года» (−11); «Снизьте долю крупнейшего покупателя до 50% и меньше» (−10). Экран называет это предварительной оценкой и показывает «что улучшить» |

**Итог:** `declined` автоматически (П4), грейд E (47), 4 пункта «что улучшить».

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `test_decline_requires_improvements_and_reaches_the_client` (`test_api_bank.py`) | API | есть частично | отказ **сотрудника** (`manual_review → declined`, переход 9) и то, что клиент видит `improvements` через `/decision`. Авто-отказ по грейду E (переход 6) не проверяет; текст `improvements` задаёт сам тест |
| `test_decision_is_404_until_there_is_one` | API | есть | `/decision` до решения отдаёт 404 |
| `scenario 5 › decline shows reasons and what to improve (C6)` | e2e | заготовка | — |
| баллы персоны 5 (47, E) и порядок `improvements` | unit | план: D5 | — |
| персона 5 через конвейер до `declined` | API | план: L4 | — |

---

### Сценарий 6. Компания в ликвидации: стоп-фактор, мгновенный отказ
- **Цель:** заведомо невозможную заявку отсечь сразу, без скоринга и без сотрудника.
- **Доказывает:** F6 и F7 (статус из ЕГРЮЛ), F9 (отказ), O4 (симулятор ЕГРЮЛ).
- **Персона:** 6 `liquidating_company`, вход `demo_liquidating_company`. ООО, `registry_status = liquidating`.
- **Предусловия:** засеян черновик `cash_gap`, `overdraft_basic`, `requested_amount = "500000.00"`, `term_months = 6`.
- **Переходы:** 1 → 2 → 3.

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | signatory | вход → `/app/applications/:id` · `POST …/submit` с `Idempotency-Key` | `submitted` |
| 2 | система | `pipeline.start` → validation: стоп-фактор С1 | `processing` → `declined` (переход 3, `stop_factor`); `Decision.outcome = declined`, `grade = null`; `Score` не создаётся; проверки конвейер не запрашивает. Reason: `registry_status` null → ✗ «По данным ЕГРЮЛ компания в процессе ликвидации — кредит оформить нельзя». `improvements = []`. Уведомление «Отказ: …»; `available_actions = []` |
| 3 | signatory | `GET /api/applications/{id}/decision` | то же решение; экран говорит прямо: кредит компании в ликвидации невозможен |

**Итог:** `declined` (П1, С1) без грейда.

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `scenario 6 › instant decline with the stop factor (L4, C6)` | e2e | заготовка | — |
| С1 → `declined`, `grade = null`, без `Score` и `Check` | API | план: L4 (критерий готовности L4: «персоны 1 и 6») | — |

---

### Сценарий 7. Сбой БКИ: ручное рассмотрение с пометкой
- **Цель:** показать устойчивость: недоступный источник отправляет заявку к сотруднику, а не в отказ.
- **Доказывает:** F7 (обогащение через симуляторы), O4 (симулятор со сбоем по флагу), F9 (ручное рассмотрение), критерий 05 (отказоустойчивость).
- **Персона:** 7 `bki_outage`, вход `demo_bki_outage`. Данные как у персоны 1.
- **Предусловия:** `DEMO_MODE=1`; у персоны нет заявки (`_seed: false`); все флаги `failing = false`.
- **Переходы:** 1 → 2 → 5 (источник `unavailable`).

| № | Кто | Действие | Ожидаемый результат |
|---|---|---|---|
| 1 | bank_manager | `/bank/demo` · `GET /api/demo/failures` (`getDemoFailures`) | все четыре флага `false` |
| 2 | bank_manager | включить «БКИ не отвечает» · `PUT /api/demo/failures` (`setDemoFailures`): `{egrul: false, transparent_business: false, bki: true, bank_account: false}` | 200, флаги применены |
| 3 | signatory | вход `demo_bki_outage`; заявка как в сценарии 1, шаги 2–5: `cash_gap`, `overdraft_basic`, 900 000 ₽, 12 мес → submit | `submitted` |
| 4 | система | конвейер: enrichment | `Check(bki).status = unavailable`, `summary` «Источник не ответил (демо)», `data = {}`; остальные `ok`. Скоринг идёт дальше: БКИ даёт нейтральные 10 баллов → **82, грейд B** |
| 5 | система | П3 `needs_review` | `manual_review` (переход 5); `Decision.outcome = manual_review`; `source_unavailable = true`. Reasons: `source_bki` null → ✗ «БКИ сейчас не отвечает — заявку проверит сотрудник банка. Это не отказ»; `score_total` 82 / 75 → ✓; `overdraft_limit` 900 000 → ✓. Заготовка: 900 000 ₽, 23 % (B), 12 мес. Уведомление «Заявку смотрит сотрудник» |
| 6 | bank_manager | `/bank` → карточка · `GET /api/bank/applications`, `GET /api/bank/applications/{id}` | в очереди у заявки `source_unavailable = true`; во вкладке «Проверки» БКИ помечен `unavailable`; доступны `[assign, approve, counteroffer, request_info, decline]` |
| 7 | bank_manager | выключить сбой · `PUT /api/demo/failures` с `bki: false` (или `POST /api/demo/reset`) | флаги снова `false` |

**Итог:** `manual_review` с `source_unavailable = true`, не отказ. Дальше заявку ведёт сотрудник, как в сценарии 4.

| Тест | Уровень | Статус | Что не проверяет |
|---|---|---|---|
| `scenario 7 › demo panel turns BKI off → application lands in manual review with a note (B7, L4)` | e2e | заготовка | — |
| сбой включается флагом, симулятор отвечает `unavailable` | API | план: S1 (критерий: «сбой включается флагом») | — |
| конвейер: `unavailable` → П3 `manual_review`, `source_unavailable = true` | API | план: L4 (критерий: «сценарий сбоя») | — |
| `/api/demo/failures` и демо-панель | API, e2e | план: L5/B7 (критерий B7: «сценарий 7 показывается в два клика») | — |
| баллы персоны 7 (82, B; БКИ `unavailable` → 10) | unit | план: D5 | — |
