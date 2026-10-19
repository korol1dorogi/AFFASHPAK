# Домен: термины, модели, статусы

> **ЧЕРНОВИК до кейса.** После кейса лид сверяет и снимает пометку. Имена сущностей и полей в коде, контракте и UI — только отсюда.

## Глоссарий
| Русский термин | Имя в коде |
|---|---|
| выручка | revenue |
| себестоимость | cogs |
| дебиторская задолженность | receivables |
| кредиторская задолженность | payables |
| запасы | inventory |
| финансовый долг | debt |
| денежные средства | cash |
| денежный поток для обслуживания долга | cfads |
| платежи по долгу | debt_service |
| коэффициент покрытия долга | dscr |
| долг / EBITDA | debt_to_ebitda |
| финансовый цикл (оборачиваемость дебиторки, запасов, кредиторки) | ccc (dso, dio, dpo) |
| потребность в оборотных средствах | working_capital_need |
| очищенный кредитовый оборот | cleaned_credit_turnover |
| аннуитетный платёж | annuity_payment |
| лимит | limit |
| транш | tranche |
| овердрафт | overdraft |
| факторинг | factoring |
| кредит на пополнение оборотных средств (КПО) | working_capital_loan |
| инвестиционный кредит | investment_loan |
| лизинг | leasing |
| тип потребности | need_type |
| стоп-фактор | stop_factor |
| обоснование (причина) | reason |
| вероятность дефолта, доля потерь, сумма под риском, ожидаемые потери, коэффициент конверсии | pd, lgd, ead, expected_loss, ccf |
| концентрация на плательщике | counterparty_concentration |
| ковенант | covenant |
| предварительная оценка | preliminary evaluation (Decision с decided_by=auto) |

Формулы и примеры — [knowledge/credit.md](knowledge/credit.md), код — `backend/apps/credit_math/`.

## Типы потребности (need_type)
| need_type | Ситуация | Основной продукт |
|---|---|---|
| cash_gap | кассовый разрыв до 30–60 дней | overdraft |
| receivable_delay | отгрузили, покупатель платит позже | factoring |
| working_capital | закупка, сезон | working_capital_loan |
| capex | оборудование, транспорт, недвижимость | investment_loan / leasing |

## Модели
Деньги — Decimal (2 знака), коэффициенты — Decimal (4 знака); необязательное — null. Владение: всё, что ниже Business, принадлежит его владельцу; каждый queryset фильтруется по текущему пользователю.

### User
Стандартный пользователь Django + роль.
- role: `client` (предприниматель) | `officer` (сотрудник банка, работает через Django admin).

### Business
- owner → User (client)
- legal_form: `ip` | `ooo`
- name, inn, ogrn, okved, registered_at (date), region
- is_demo: bool — синтетические данные

### FinancialSnapshot
Финансовый снимок бизнеса за период.
- business → Business; period; source: `case` | `demo` | `manual`
- cleaned_credit_turnover (среднемесячный), cfads, debt_service, revenue, cogs, ebitda, debt, cash, receivables, inventory, payables — Money | null
- counterparty_concentration, revenue_trend — коэффициент | null

### Product
- code (уникальный), kind: `overdraft` | `factoring` | `working_capital_loan` | `investment_loan` | `leasing`, name
- rate_min, rate_max (годовые, в долях); term_min_months, term_max_months; amount_min, amount_max
- params: alpha, beta, min_dscr, max_debt_to_ebitda, tranche_days… — пороги живут здесь, не в коде
- requirements: min_business_age_months, legal_forms

### Application
- business → Business; need_type; purpose; requested_amount; term_months
- product → Product | null (до выбора)
- status (см. ниже) — read-only в API, меняется только функциями сервисного слоя
- prefill_source: `manual` | `recommendation` | `assistant`
- created_at, submitted_at

### Decision
- application → Application; outcome: `approved` | `declined` | `info_requested`
- approved_amount, rate, term_months, monthly_payment — read-only
- reasons: list[Reason]
- decided_by: `auto` (предварительная оценка) | `officer`
- created_at

### Reason (значение, не таблица)
metric, value (null — нельзя посчитать), threshold, passed, message (текст для клиента).

### Document
- application → Application; kind: `bank_statement` | `financial_report` | `tax_return` | `contract` | `invoice` | `other`
- file (случайное имя), original_name, content_type (по содержимому), size, sha256, uploaded_at

### AssistantMessage — журнал ассистента
- user → User; application → Application | null; role: `user` | `assistant` | `tool`
- content; tool_calls (имя, аргументы, результат); created_at

## Статусы заявки
```
draft ──submit──▶ submitted ──▶ in_review ──▶ approved
  │                  │                    ├─▶ declined
  │                  │                    └─▶ info_requested ──submit──▶ submitted
  └──cancel──▶ cancelled ◀──cancel──┘
```
- Клиент: `submit` (draft | info_requested → submitted), `cancel` (draft | submitted → cancelled).
- Система / сотрудник банка: submitted → in_review → approved | declined | info_requested.
- Переходы — только функциями сервисного слоя (стейт-машина); недопустимый переход → 409.
- В интерфейсе клиента — «предварительная оценка», не «решение банка».
