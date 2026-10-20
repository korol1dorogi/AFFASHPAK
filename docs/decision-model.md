# Модель решения (D4)

> v1 · `model_version = "scorecard-2026.10-v1"` · `policy_version = "2026.10-v1"`. Закрывает F4, F8, F9, O6 ([case.md](case.md)).
> Скоринг ≠ решение (F8): балльная карта (`apps/scoring`, D5) даёт грейд — уровень риска заёмщика; правила решения (L4) поверх грейда учитывают продукт, сумму, срок, внешние проверки и политику. Все расчёты — функции `backend/apps/credit_math/` ([knowledge/credit.md](knowledge/credit.md)); новых формул здесь нет. Продукты и их `params` — [products.md](products.md) (D3). Клиенту любой автоматический исход — «предварительная оценка», не «решение банка».

Обозначения: «для D5» — функции нет, её пишет D5 по описанию. «Предложение лиду» — правка вне docs/decision-model.md, в этом документе не сделана. Пороги — параметры (раздел 6), числа в тексте — их значения в v1.

## 1. Конвейер решения
`submitted` → `processing` → **validation → enrichment → scoring → decision** → `record_auto_decision(...)` ([state-machine.md](state-machine.md#конвейер-l4), переходы 3–6).

| Шаг | Вход (поля [data-model.md](data-model.md)) | Что делает | Выход |
|---|---|---|---|
| validation | `Application`: `need_type`, `purpose`, `product`, `requested_amount`, `term_months`, `invoice_amount`, `collateral_description`; `Company`: `legal_form`, `inn`, `registered_at`, `registry_status`; `Document.kind` заявки; `Product`: `term_min_months`, `term_max_months`, `amount_min`, `required_documents`, `kind` | стоп-факторы по анкете (раздел 2, С1); полнота и корректность (раздел 3) | стоп → `declined`; пробелы → `info_requested`; иначе дальше |
| enrichment | `Company.inn` | параллельно, с таймаутами: `Check` по `egrul`, `transparent_business`, `bki`, `bank_account`; счёт даёт `FinancialSnapshot` (`source = simulator`); стоп-факторы по проверкам (С2–С5) | `Check.status` ∈ `ok`/`warning`/`failed`/`unavailable`; последний по `period` снимок |
| scoring | `FinancialSnapshot`: `cfads`, `debt_service`, `debt`, `ebitda`, `cash`, `revenue_trend`, `counterparty_concentration`; `Check(bki).data`, `Check(transparent_business).data`, `Check.status`; `Company.registered_at`, `Application.submitted_at` | балльная карта (раздел 4) | `Score`: `grade`, `total`, `factors[name, value, points, message]`, `model_version` |
| decision | `Score.grade`, `Score.factors`; `Product`: `rate_min`, `rate_max`, `amount_min`, `amount_max`, `term_*_months`, `requirements`, `collateral_required`, `is_revolving`, `params`; `Application`; `FinancialSnapshot`: `cleaned_credit_turnover`, `cfads`, `debt_service`, `receivables`, `inventory`, `payables`; `Check.status` | правила решения (раздел 5), суммы — `credit_math` | аргументы `record_auto_decision`: `outcome`, `grade`, `policy_version`, `reasons`, `improvements`, `offer {product, amount, term_months, rate}`, `info_request {message, fields, document_kinds}`, `source_unavailable` |

- Стоп-фактор и неполные данные дают решение до скоринга: `Decision.grade = null`, `Score` не создаётся.
- Источник `unavailable` не останавливает конвейер: скоринг считается с нейтральными баллами по этому источнику, решение — `manual_review` (сценарий 7).
- Ответ клиента на `InfoRequest(origin=validation)` → `submitted` → конвейер целиком заново (переход 10a).

**Ключи `Check.data`, которые читает модель** (в data-model.md и openapi.yaml не описаны — **предложение лиду** зафиксировать их в контракте симуляторов S1):

| `source` | Ключ | Тип | Смысл |
|---|---|---|---|
| `egrul` | `registry_status` | `active` \| `liquidating` \| `liquidated` | статус в реестре; дублирует `Company.registry_status` на момент проверки |
| `bki` | `current_overdue_days` | int | текущая просрочка, дней (0 — нет) |
| `bki` | `past_overdue_max_days` | int | самая длинная закрытая просрочка за 36 мес, дней (0 — не было) |
| `transparent_business` | `mass_address` | bool | массовый адрес регистрации |
| `transparent_business` | `mass_director` | bool | массовый руководитель |
| `transparent_business` | `tax_arrears` | Money | налоговая задолженность, ₽ (0 — нет) |

`egrul` со `status = failed` — компания не найдена в реестре.

## 2. Стоп-факторы
Сразу `declined`, `grade = null`, скоринг не запускается. Проверяются раньше всего остального, в т. ч. раньше полноты и недоступности источников: если компания в ликвидации, уточнения и ручное рассмотрение ничего не изменят.

| # | Признак | Источник | Шаг | Порог (параметр) | `improvements` |
|---|---|---|---|---|---|
| С1 | компания ликвидируется или ликвидирована (персона 6) | `Company.registry_status`, затем `Check(egrul).data.registry_status` | validation, повторно enrichment | `registry_status` ∈ `liquidating`, `liquidated` | — (кредит компании в ликвидации невозможен) |
| С2 | компания не найдена в ЕГРЮЛ/ЕГРИП | `Check(egrul).status = failed` | enrichment | — | «Проверьте ИНН компании» |
| С3 | EBITDA ≤ 0 | `FinancialSnapshot.ebitda` (не `null`) | enrichment | `ebitda ≤ 0` — `debt_to_ebitda` возвращает None с пометкой «стоп-фактор» | «Подайте заявку, когда бизнес выйдет на операционную прибыль» |
| С4 | текущая просрочка в БКИ больше 30 дней | `Check(bki).data.current_overdue_days` | enrichment | `stop_current_overdue_days` = 30 | «Погасите текущую просрочку и подайте заявку снова» |
| С5 | бизнесу меньше 6 мес | `Company.registered_at` → `Application.submitted_at` | validation | `stop_min_business_age_months` = 6 (минимум `min_business_age_months` по каталогу) | «Вернитесь, когда бизнесу будет 6 месяцев: с даты регистрации прошло N мес» |

`ebitda = null` (у ИП нет отчётности) — не стоп-фактор: метрика просто не считается (раздел 4). Требования конкретного продукта (возраст 12 мес у КПО, правовая форма, залог) — не стоп-факторы, а фильтр продукта (раздел 5, П6).

## 3. Проверка полноты и корректности (F6)
Шаг validation. Все найденные пробелы собираются в **один** `InfoRequest(origin=validation)`: `fields` — имена полей API, `document_kinds` — недостающие `DocumentKind`. Исход `info_requested`, `grade = null`.

| Что считается неполным или некорректным | `fields` | `document_kinds` | Текст для клиента |
|---|---|---|---|
| нет `need_type` | `need_type` | — | «Укажите, на что нужны деньги» |
| `purpose` пустая или короче 10 символов | `purpose` | — | «Опишите цель подробнее: на что именно пойдут деньги» |
| не выбран продукт | `product_code` | — | «Выберите продукт или воспользуйтесь подбором» |
| `requested_amount` пустая, ≤ 0 или меньше `amount_min` продукта | `requested_amount` | — | «Минимальная сумма по продукту — {amount_min} ₽» |
| `term_months` пустой или вне `term_min_months`…`term_max_months` | `term_months` | — | «Срок по продукту — от {min} до {max} мес» |
| факторинг без `invoice_amount` | `invoice_amount` | — | «Укажите сумму отгрузки по документу» |
| нет документа из `Product.required_documents` | — | недостающие виды | «Загрузите: {список документов}» |
| `Company.registered_at` пустая | `registered_at` | — | «Не удалось определить дату регистрации компании» |

- `requested_amount` больше `amount_max` — не пробел: решение ограничит сумму (контрпредложение, раздел 5, П7).
- Пустой `collateral_description` у продукта с `collateral_required` — не пробел, а повод предложить продукт без залога (раздел 5, П6).
- Обязательные документы есть у факторинга (`contract`, `shipment_document`), КПО (`bank_statement`, `tax_return`), инвест-кредита и лизинга ([products.md](products.md)). Чтобы автосценарии 2 и 3 не останавливались на проверке полноты, seed персон 2 и 3 загружает эти документы заранее — **предложение для S2/seed_demo**.

## 4. Балльная карта (скоринг, F8)
Прозрачная балльная карта без ML (O6): каждый фактор даёт баллы по шкале, сумма (0–100) → грейд. Скоринг оценивает **заёмщика**, а не заявку: в факторах нет запрошенной суммы и срока, поэтому одна и та же компания получает один грейд для любого продукта, а условия разные (кейс: «одинаковая оценка риска может давать разные условия для разных продуктов»). Сумма и срок проверяются в правилах решения (раздел 5).

### Факторы
Интервалы: `[a; b)` — a включительно, b нет. «Порог» — граница, по которой `ScoreFactor` и `Reason` получают `passed` (раздел 7).

| Фактор (`name`) | Источник | Функция | Шкала → баллы | Порог `passed` | Метрика не считается (None) | Макс. |
|---|---|---|---|---|---|---|
| `business_age_months` | `Company.registered_at`, `Application.submitted_at` | **для D5**: `business_age_months(registered_at, on_date) -> int` — полных месяцев между датами, в `apps/scoring` (не денежная формула) | ≥ 36 → 10 · [24; 36) → 7 · [12; 24) → 4 · [6; 12) → 1 · < 6 — стоп-фактор С5 | ≥ 12 | дата пустая — пробел полноты (раздел 3), до скоринга не доходит | 10 |
| `dscr` | `FinancialSnapshot.cfads`, `.debt_service` | `dscr(cfads, debt_service)` — по **текущим** долгам, без нового кредита | ≥ 2.0 → 25 · [1.5; 2.0) → 18 · [1.25; 1.5) → 10 · [1.0; 1.25) → 4 · < 1.0 → 0 | ≥ `min_dscr` 1.25 | `debt_service = 0` и `cfads > 0` (долга нет) → **25**, «Долгов нет — нагрузки нет»; `cfads` или `debt_service` = `null` → **12**, ключевая метрика пропущена | 25 |
| `debt_to_ebitda` | `.debt`, `.ebitda`, `.cash` | `debt_to_ebitda(debt, ebitda, cash)` | ≤ 2.0 → 15 · (2.0; 3.5] → 10 · (3.5; 5.0] → 4 · > 5.0 → 0 | ≤ `max_debt_to_ebitda` 3.5 | `ebitda` или `debt` = `null` (нет отчётности, обычно ИП) → **7**, «Отчётности нет — долговую нагрузку оценили по счёту»; `ebitda ≤ 0` — стоп-фактор С3 | 15 |
| `revenue_trend` | `.revenue_trend` (считает S2/адаптер счёта функцией `revenue_trend`, год к году) | `revenue_trend` | ≥ 1.0 → 15 · [0.9; 1.0) → 10 · [0.8; 0.9) → 4 · < 0.8 → 0 | ≥ 0.9 | `null` → **7**, ключевая метрика пропущена | 15 |
| `counterparty_concentration` | `.counterparty_concentration` (функцией `counterparty_concentration`) | `counterparty_concentration` | ≤ 0.3 → 10 · (0.3; 0.5] → 7 · (0.5; 0.7] → 3 · > 0.7 → 0 | ≤ 0.5 | `null` → **5**, ключевая метрика пропущена | 10 |
| `bki_history` | `Check(bki).data`: `current_overdue_days`, `past_overdue_max_days` | — (сравнение с порогами) | текущей нет, прошлой нет → 20 · прошлая ≤ 30 дн. → 8 · прошлая > 30 дн. → 3 · текущая 1–30 дн. → 0 · текущая > 30 — стоп-фактор С4 | текущей нет и прошлая ≤ 30 дн. | `Check.status = unavailable` → **10**, «БКИ не ответило — историю проверит сотрудник» | 20 |
| `transparent_business` | `Check(transparent_business).data`: `mass_address`, `mass_director`, `tax_arrears` | — | флагов нет → 5 · один из `mass_address`/`mass_director` → 2 · `tax_arrears > 0` или оба флага → 0 | флагов нет | `unavailable` → **2** | 5 |
| **Итого** | | | | | | **100** |

- Нейтральные баллы для None — около середины шкалы: «не знаем» не равно ни «хорошо», ни «плохо» (AGENTS.md: None и причина, не 0). `ScoreFactor.value = null`, `message` — текст `Metric.note` из `credit_math`.
- Почему DSCR без нового платежа: сумма — параметр заявки, а не риск заёмщика. Посилен ли **этот** кредит, проверяет правило П7 через `max_loan_by_dscr` (персона 3: грейд B, но сумма урезана до 2 009 314 ₽).
- Доля `cash` в `debt_to_ebitda` — по формуле функции (долг за вычетом денег).
- **Пропущенные ключевые метрики**: `dscr` (данных нет; «долга нет» — не пропуск), `revenue_trend`, `counterparty_concentration`. Две и больше пропущены → авторешения нет, `manual_review` (П5). `debt_to_ebitda` в этот счёт не входит: у ИП отчётности обычно нет, это норма.

### Грейд
| Грейд | Сумма баллов | Смысл | Доля ставки (раздел 5) |
|---|---|---|---|
| A | ≥ 90 | низкий риск | 0.2 |
| B | [75; 90) | умеренный риск | 0.4 |
| C | [60; 75) | повышенный риск, нужен сотрудник | 0.6 |
| D | [50; 60) | высокий риск, нужен сотрудник | 0.8 |
| E | < 50 | риск неприемлем | — (оффера нет) |

`Score.total` — целое; `Score.model_version = "scorecard-2026.10-v1"`. Любая правка шкал или порогов грейда — новая `model_version`; старые `Score` не пересчитываются.

## 5. Правила решения поверх грейда
Правила проверяются **по порядку, первое сработавшее определяет исход**. Каждое проверенное правило добавляет свои `reasons` (раздел 7), даже если не сработало: клиент и сотрудник видят, что прошло, а что нет.

| # | Условие | `outcome` | Статус (переход) | Что ещё |
|---|---|---|---|---|
| П1 | любой стоп-фактор С1–С5 | `declined` | `declined` (3) | `grade = null`; `improvements` из таблицы раздела 2 |
| П2 | есть пробелы полноты (раздел 3) | `info_requested` | `info_requested` (4a) | `info_request {message, fields, document_kinds}`, `grade = null` |
| П3 | хотя бы один `Check.status = unavailable` | `manual_review` | `manual_review` (5) | `source_unavailable = true`; при **любом** грейде, включая E: на неполных данных не отказываем (сценарий 7) |
| П4 | грейд E | `declined` | `declined` (6) | `improvements` — все факторы с `passed = false`, по убыванию потерянных баллов |
| П5 | грейд C или D; **или** пропущены ≥ 2 ключевые метрики (раздел 4); **или** невозобновляемый продукт и `debt_to_ebitda` > `max_debt_to_ebitda` | `manual_review` | `manual_review` (5) | в `reasons` — допустимая сумма по П7, ставка по грейду: заготовка решения для сотрудника |
| П6 | продукт заявки не проходит своё требование: `requirements.legal_forms`, `requirements.min_business_age_months`, или `collateral_required` при пустом `collateral_description` | `alternative_product`, если подходит продукт из `alternatives`; иначе `declined` | `offer` (4) / `declined` (6) | альтернатива должна пройти свои требования и П7 с суммой ≥ её `amount_min`; срок — `term_months`, прижатый к её диапазону; сумма — min(запрошенная, допустимая для альтернативы) |
| П7 | допустимая сумма (таблица ниже) < `requested_amount` | `counteroffer`, если допустимая ≥ `amount_min`; иначе `manual_review` | `offer` (4) / `manual_review` (5) | `offer.amount` = допустимая, срок — как в заявке; `improvements` — как получить запрошенное |
| П8 | всё прошло | `offer` | `offer` (4) | `offer.amount = requested_amount` |

**Альтернативы** (`alternatives`, политика): `investment_loan` → `leasing` (нет залога — лизингу он не нужен); `leasing` → `investment_loan` (только если залог описан); `working_capital_loan` → `overdraft` (бизнесу 6–11 мес: КПО требует 12, овердрафт — 6). Факторинг и овердрафт без альтернатив. Если сработали и П6, и уменьшение суммы, исход `alternative_product`, а `Offer.is_counteroffer` и `Offer.product_changed` оба `true` (их считает `create_offer`).

### Допустимая сумма (П6, П7)
Ставка и срок — те, что пойдут в оффер: ставка по грейду (ниже), срок из заявки.

| `Product.kind` | Допустимая сумма | Функции `credit_math` | Нельзя посчитать |
|---|---|---|---|
| `overdraft` | min(лимит, `amount_max`) | `overdraft_limit(cleaned_credit_turnover, alpha)` | `cleaned_credit_turnover = null` → `manual_review` |
| `factoring` | min(аванс, `amount_max`) | `factoring_advance(invoice_amount, beta)` | `invoice_amount` проверен в validation |
| `working_capital_loan` | min(потребность, по DSCR, `amount_max`) | `working_capital_need(receivables, inventory, payables)`, `max_loan_by_dscr(cfads, debt_service, rate, term_months, min_dscr)` | остатки `null` → ограничивает только DSCR, в `reasons` пометка; `max_loan_by_dscr` = None → `manual_review` |
| `investment_loan`, `leasing` | min(по DSCR, `amount_max`) | `max_loan_by_dscr(...)` | None → `manual_review` |

- Для невозобновляемых в `reasons` добавляется DSCR с новым платежом: `dscr(cfads, debt_service + annuity_payment(amount, rate, term_months))` ≥ `min_dscr` — `max_loan_by_dscr` это гарантирует, reason показывает клиенту итог.
- **Для D5**: `working_capital_need` принимает только числа; нужна обёртка, возвращающая `Metric.unavailable(...)`, если любой из остатков `null`.
- **Для D5**: комиссия факторинга `invoice_amount × commission` (персона 2: 25 000 ₽) — функции нет; добавить в `credit_math` (`factoring_commission(invoice_amount, commission)`, `round_money`), показывается отдельной строкой в `reasons` оффера.

### Ставка по грейду
`rate = round_ratio(rate_min + (rate_max − rate_min) × rate_share[grade])`, `rate_share` — политика: A 0.2 · B 0.4 · C 0.6 · D 0.8 · E 1.0 (E — только если оффер делает сотрудник после П3). Одинаковый грейд — разные ставки у разных продуктов (F8).

| Продукт | A | B | C | D |
|---|---|---|---|---|
| `overdraft_basic` (20–32%) | 22.4% | 24.8% | 27.2% | 29.6% |
| `factoring_basic` (20–30%) | 22% | 24% | 26% | 28% |
| `working_capital_loan_basic` (20–30%) | 22% | **24%** | 26% | 28% |
| `investment_loan_basic` (19–28%) | 20.8% | 22.6% | **24.4%** | 26.2% |
| `leasing_basic` (20–30%) | 22% | 24% | 26% | 28% |

**Предложение лиду**: `rate_for` в `backend/apps/applications/offers.py` (L2) сейчас линейный A→`rate_min`, E→`rate_max` (КПО B = 22.5%); заменить на эту сетку — иначе контроффер персоны 3 не совпадёт с 2 009 314 ₽ при 24%. Сотрудник при `approve` получает ту же ставку по грейду.

`Decision.policy_version = "2026.10-v1"`. Любая правка правил, порогов политики или сетки — новая `policy_version`.

## 6. Пороги: где живут
Все пороги — данные, а не константы в коде. Две группы:

| Группа | Где | Параметры v1 |
|---|---|---|
| Условия продукта (D3) | `Product`: поля и `params`, `requirements`, `required_documents` (фикстура `backend/apps/products/fixtures/products.json`) | `alpha` 0.3, `tranche_days` 60, `beta` 0.9, `commission` 0.005, `min_dscr` 1.25, `max_debt_to_ebitda` 3.5; `rate_min`/`rate_max`, `term_*_months`, `amount_min`/`amount_max`; `min_business_age_months`, `legal_forms`; `collateral_required` |
| Политика модели | версионированный конфиг в `apps/scoring` (D5: словарь/JSON по ключу `policy_version` и `model_version`; модели БД не нужны) | шкалы и баллы факторов (раздел 4), нейтральные баллы для None, пороги `passed`; пороги грейдов 90/75/60/50; `rate_share`; `stop_current_overdue_days` 30, `stop_min_business_age_months` 6; `max_missing_key_metrics` 1; `alternatives`; `purpose_min_length` 10; концентрация (0.3/0.5/0.7) и тренд (1.0/0.9/0.8) — общая политика, не условие продукта ([products.md](products.md), «Вне каталога») |

Пороги `dscr` в карте и `min_dscr` продукта — разные вещи: карта меряет текущую нагрузку заёмщика (общая шкала), `min_dscr` — требование продукта к сумме нового кредита (П7). В v1 порог `passed` фактора `dscr` берётся из `min_dscr` продукта заявки (1.25 у всех).

## 7. reasons и improvements
`Reason`: `metric`, `value` (DecimalString | null), `threshold` (DecimalString | null), `passed`, `message` ([openapi.yaml](openapi.yaml), схема `Reason`). Нечисловые признаки (статус реестра, флаги) — `value = null`, суть в `message`. Метрика не посчитана — `value = null`, `passed = false`, `message` = `Metric.note` (так работают `check_at_least`/`check_at_most`), кроме случаев «долга нет», где `passed = true`.

Клиенту всё — «предварительная оценка». «Что это значит» — в `message`, «что улучшить» — в `Decision.improvements` (для отказа и контроффера). Тексты — основа для D8, D8 может их переформулировать, не меняя смысла.

| `metric` | `value` | `threshold` | `message` при passed / fail («что это значит») | «Что улучшить» (fail) |
|---|---|---|---|---|
| `registry_status` | null | null | — / «По данным ЕГРЮЛ компания в процессе ликвидации — кредит оформить нельзя» | — |
| `egrul_found` | null | null | «Компания найдена в реестре» / «Компанию не нашли в ЕГРЮЛ/ЕГРИП» | «Проверьте ИНН компании» |
| `ebitda` | EBITDA | 0 | — / «Операционная прибыль за год ≤ 0: бизнесу нечем обслуживать долг» | «Подайте заявку, когда бизнес выйдет на прибыль» |
| `bki_current_overdue_days` | дни | 30 | — / «Сейчас есть просрочка по кредиту больше 30 дней» | «Погасите текущую просрочку» |
| `business_age_months` | мес | 12 (или `min_business_age_months` продукта) | «Бизнесу N мес — достаточно» / «Бизнесу N мес, а продукт требует от M» | «Вернитесь через {M − N} мес или выберите {альтернативу}» |
| `score_total` | сумма баллов | нижняя граница грейда | «Предварительная оценка риска: грейд B (87 из 100)» | — |
| `dscr` | DSCR | 1.25 | «На каждый рубль платежей по долгам приходится {x} ₽ свободных денег» / «Свободных денег на платежи по долгам мало: {x} ₽ на рубль при норме 1,25» | «Снизьте текущие платежи по долгам или увеличьте свободный денежный поток» |
| `debt_to_ebitda` | x | 3.5 | «Долги — {x} годовых прибыли, норма до 3,5» / «Долги — {x} годовых прибыли, это больше нормы 3,5» | «Снизьте долг до 3,5 годовой прибыли (EBITDA)» |
| `revenue_trend` | x | 0.9 | «Выручка за 3 мес — {±%} к тем же месяцам прошлого года» / «Выручка упала на {%} к прошлому году» | «Восстановите выручку хотя бы до уровня прошлого года» |
| `counterparty_concentration` | доля | 0.5 | «Крупнейший покупатель приносит {%} поступлений» / «{%} денег приходит от одного покупателя: если он уйдёт, бизнес останется без выручки» | «Снизьте долю крупнейшего покупателя до 50% и меньше» |
| `bki_history` | дни прошлой просрочки | 30 | «Кредитная история без серьёзных просрочек» / «В кредитной истории была просрочка {N} дней» | «Подтвердите, что просрочка погашена; новых просрочек не допускайте» |
| `transparent_business` | null | null | «Признаков риска в ФНС нет» / «ФНС: {массовый адрес / массовый руководитель / налоговый долг N ₽}» | «Погасите налоговый долг» / «Подтвердите фактический адрес» |
| `source_{egrul\|transparent_business\|bki\|bank_account}` | null | null | — / «{Источник} сейчас не отвечает — заявку проверит сотрудник банка. Это не отказ» | — |
| `missing_key_metrics` | число пропущенных | 1 | — / «Не хватает данных по счёту для автоматической оценки — заявку посмотрит сотрудник» | — |
| `overdraft_limit` | лимит | `requested_amount` | «Лимит — 30% среднемесячных поступлений: {x} ₽» / «По оборотам доступно {x} ₽ — меньше запрошенного» | «Лимит вырастет вместе с поступлениями на счёт» |
| `factoring_advance` | аванс | `requested_amount` | «Сразу — 90% суммы отгрузки: {x} ₽» / «Под эту отгрузку доступно {x} ₽» | — |
| `factoring_commission` | комиссия | null | «Разовая комиссия — {x} ₽ (0,5% отгрузки)» | — |
| `working_capital_need` | потребность | `requested_amount` | «В дебиторке и запасах за вычетом кредиторки заморожено {x} ₽ — больше бизнесу не нужно» / «Потребность в оборотных средствах — {x} ₽, меньше запрошенного» | — |
| `max_loan_by_dscr` | P_max | `requested_amount` | «Платёж посилен: допустимо до {x} ₽» / «Чтобы платежи не съели запас 25%, сумма ограничена {x} ₽ на {n} мес при {r}%» | «При сроке {term_max} мес допустимо {max_loan_by_dscr на term_max} ₽» · «Снизьте текущие платежи по долгам» |
| `dscr_after` | DSCR с новым платежом | `min_dscr` | «С новым платежом {p} ₽/мес запас покрытия — {x}» / — | — |
| `amount_max` | `amount_max` | `requested_amount` | — / «Максимальная сумма по продукту — {x} ₽» | — |
| `product_requirements` | null | null | — / «{Продукт} требует {залог / возраст / правовую форму}; подходит {альтернатива}» | — |

`improvements` отказа по грейду E — тексты «что улучшить» всех факторов с `passed = false`, по убыванию потерянных баллов (максимум фактора минус полученные), при равенстве — в порядке таблицы раздела 4.
