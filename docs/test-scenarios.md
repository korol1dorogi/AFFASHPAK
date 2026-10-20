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
- **Ожидаемый результат**: статус; `available_actions` текущего пользователя; деньги — строки-десятичные, как их отдаёт API (`"900000.00"`, ставка `"0.20"` = 20 %); ключевые `reasons` в формате `metric: value / threshold → ✓ или ✗`; событие журнала (`ApplicationEvent.kind`); уведомление клиенту (`Notification.title` из [state-machine.md](state-machine.md#переходы)).
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
