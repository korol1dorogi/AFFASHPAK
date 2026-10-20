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
