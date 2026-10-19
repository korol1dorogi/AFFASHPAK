# Домен: термины, сущности, статусы

> v1 по плану лида (L1). Сверка с текстом кейса — после его получения. Имена сущностей и полей в коде, контракте и UI — только отсюда и из [data-model.md](data-model.md).

- Сущности и поля — [data-model.md](data-model.md)
- Статусы, переходы, роли — [state-machine.md](state-machine.md)
- Формулы и примеры — [knowledge/credit.md](knowledge/credit.md), код — `backend/apps/credit_math/`
- Контракт — [openapi.yaml](openapi.yaml)

## Глоссарий
| Русский термин | Имя в коде |
|---|---|
| компания (ИП или ООО) | company (бывш. business) |
| сотрудник компании, роль: директор / бухгалтер | membership: director / accountant |
| сотрудник банка | bank_manager |
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
| сумма отгрузки (по УПД) | invoice_amount |
| кредит на пополнение оборотных средств (КПО) | working_capital_loan |
| инвестиционный кредит | investment_loan |
| лизинг | leasing |
| тип потребности | need_type |
| стоп-фактор | stop_factor |
| обоснование (причина) | reason |
| что улучшить | improvements |
| проверка внешнего источника | check (egrul, transparent_business, bki, bank_account) |
| ЕГРЮЛ / ЕГРИП | egrul |
| «Прозрачный бизнес» (ФНС) | transparent_business |
| бюро кредитных историй | bki |
| скоринг, грейд | score, grade (A–E) |
| предварительная оценка (автоматическое решение) | decision с decided_by=auto |
| ручное рассмотрение | manual_review |
| запрос информации | info_request |
| предложение / контрпредложение | offer / counteroffer (offer.is_counteroffer) |
| подписание кодом | signature |
| выдача | disbursement |
| журнал (аудит) | application_event |
| уведомление | notification |
| PD, LGD, EAD, EL, CCF | pd, lgd, ead, expected_loss, ccf |
| концентрация на плательщике | counterparty_concentration |
| ковенант | covenant |

## Типы потребности (need_type)
| need_type | Ситуация | Основной продукт |
|---|---|---|
| cash_gap | кассовый разрыв до 30–60 дней | overdraft |
| receivable_delay | отгрузили, покупатель платит позже | factoring |
| working_capital | закупка, сезон | working_capital_loan |
| capex | оборудование, транспорт, недвижимость | investment_loan / leasing |

## Правила языка в интерфейсе
- Клиенту — «предварительная оценка» и «предложение», не «решение банка», пока не подписан договор.
- У каждого статуса и каждой причины — «что это значит» и «что дальше» (тексты — D8).
- Деньги — с пробелами и ₽ (`2 009 314 ₽`), ставки — в процентах (`24%`), в API — строки-десятичные в долях (`"0.24"`).
