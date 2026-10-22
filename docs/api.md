# API

Описание API кабинета «Оборот» (кейс: «описание API», T7). Источник истины — контракт [openapi.yaml](openapi.yaml) (OpenAPI 3.1, contract-first, D2): бэкенд проверяет каждый свой ответ по нему в тестах, фронт генерирует из него клиент (`npm run gen:api`), CI сверяет, что клиент не разошёлся с контрактом.

- **Swagger UI:** `/api/docs` (на стенде и в `docker compose up` → http://localhost:8080/api/docs).
- **Коллекция запросов:** [postman/collection.json](../postman/collection.json) — весь путь клиента и банка, 60 запросов; в CI прогоняется newman.
- **Мок по контракту:** `docker compose --profile mock up -d mock` → http://localhost:4010 (Prism).

## Общие правила

| Что | Как |
|---|---|
| Адрес | один origin с кабинетом: `/api/…`; CORS нет |
| Вход | сессия Django (cookie `sessionid`): `POST /api/auth/login`, `/register` или `/api/demo/login` (стенд) |
| CSRF | любой небезопасный метод (`POST`, `PUT`, `PATCH`, `DELETE`) — с заголовком `X-CSRFToken` = cookie `csrftoken`; cookie выставляет `GET /api/auth/csrf`. Вход и регистрация тоже требуют CSRF |
| Формат | JSON, UTF-8. Деньги, ставки и коэффициенты — **строки-десятичные**: `"900000.00"`, `"0.2400"` (ставка годовая, в долях); float нет |
| Ошибки | всегда `{"error": {"code", "message", "details"?}}`; `message` — по-русски для человека, `details` — ошибки по полям |
| Коды | 400 `invalid` (поля), 401 `not_authenticated` / `invalid_credentials`, 403 `permission_denied` (роль, CSRF), 404 `not_found` (в том числе **чужой объект** — его существование не раскрывается), 409 `invalid_transition` / `version_conflict` / `…_exists`, 413 файл больше 10 МБ, 429 `throttled`, 503 `source_unavailable` / `not_ready` |
| ИНН | 10 или 12 цифр с контрольными цифрами ФНС; неверные — 400 |
| Компания | реквизиты из реестра (`name` и др.) не меняются; `PATCH /api/company` — только `short_name`; что подключено — `integrations` |
| Версия заявки | действия над заявкой передают `version`, которую видел пользователь; заявку уже изменили → 409 `version_conflict`, перечитать |
| Идемпотентность | `POST /api/applications/{id}/submit` — с заголовком `Idempotency-Key` (UUID): повтор с тем же ключом возвращает сохранённый ответ |
| Кнопки | `available_actions` в каждой заявке — что текущий пользователь может сделать сейчас (по статусу и роли); фронт показывает кнопки только по нему |
| Страницы | `page`, `page_size` (≤ 100) → `count`, `page`, `page_size`, `results` |
| Лимиты | вход и регистрация — 10/мин с IP, демо-вход — 120/мин, анонимные — 300/мин на стенде, остальное — 600/мин на пользователя |
| Демо | `/api/demo/*` существует только при `DEMO_MODE=1` (стенд), иначе 404 |

## Роли

| Роль | Кто | Что может |
|---|---|---|
| `client` · `signatory` | собственник, директор | всё по заявкам своей компании: создать, отправить, принять оффер, подписать; сотрудники компании |
| `client` · `preparer` | бухгалтер, финдиректор | готовить черновик, загружать документы, отвечать на запросы банка; **не** отправляет и не подписывает |
| `bank` (`bank_manager`) | сотрудник банка | очередь, карточка, действия: взять в работу, одобрить, иные условия / другой продукт, запросить информацию, отказать, комментарий; дашборд; демо-панель |

Матрица переходов и действий — [state-machine.md](state-machine.md).

## Путь клиента запросами

```http
GET  /api/auth/csrf                                   → cookie csrftoken
POST /api/demo/login            {"persona": "coffee_shop"}            (или /api/auth/login)
POST /api/recommendations       {"need_type": "cash_gap"}             → варианты с суммой и reasons
POST /api/applications          {"need_type", "purpose", "requested_amount", "term_months", "product_code", …}
POST /api/applications/{id}/documents   multipart: kind, file          (PDF/PNG/JPEG, ≤ 10 МБ)
POST /api/applications/{id}/submit      Idempotency-Key: <uuid>        → конвейер решает сразу
GET  /api/applications/{id}                                           → status, decision, offer, available_actions
POST /api/applications/{id}/offer/accept   {"version"}
POST /api/applications/{id}/signature                                 → код на экране (без SMS)
POST /api/applications/{id}/signature/confirm   {"code"}              → signed → issued
```

Банк: `GET /api/bank/applications?status=manual_review` → `GET /api/bank/applications/{id}` → `POST …/assign`, `…/request-info`, `…/approve` с `version`.

## Эндпоинты

Сгенерировано из [openapi.yaml](openapi.yaml): 49 путей, 57 операций. «Вход: нет» — доступно без сессии. Пока не реализованы два пути ассистента (три операции) — помечены ⏳ с номером задачи.

### system
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/health` | Живость API и базы | нет |
| GET | `/api/ready` | Готовность к трафику (база, очередь, симуляторы) | нет |

### auth
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/auth/csrf` | Выставить cookie csrftoken | нет |
| POST | `/api/auth/register` | Регистрация клиента без подтверждения почты; сразу входит | нет |
| POST | `/api/auth/login` | Вход по логину и паролю (сессия) | нет |
| POST | `/api/auth/logout` | Выход | сессия |
| GET | `/api/auth/me` | Текущий пользователь, его сторона и роль | сессия |

### company
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/company/lookup` | Данные из ЕГРЮЛ/ЕГРИП по ИНН (симулятор) — для автозаполнения | сессия |
| GET | `/api/company` | Компания текущего пользователя (404 — ещё не создана) | сессия |
| POST | `/api/company` | Создать компанию по ИНН; реквизиты — из ЕГРЮЛ, создатель становится signatory | сессия |
| PATCH | `/api/company` | Изменить редактируемые поля (реквизиты из реестра не редактируются) | сессия |
| GET | `/api/company/members` | Сотрудники компании и их роли | сессия |
| DELETE | `/api/company/members/{member_id}` | Убрать сотрудника (только signatory; себя убрать нельзя) | сессия |
| GET | `/api/company/invitations` | Приглашения компании, ждущие ответа | сессия |
| POST | `/api/company/invitations` | Пригласить сотрудника по логину (только signatory); ответ одинаков для любого логина | сессия |
| DELETE | `/api/company/invitations/{invitation_id}` | Отозвать приглашение (только signatory) | сессия |
| GET | `/api/invitations` | Приглашения, адресованные текущему пользователю | сессия |
| POST | `/api/invitations/{invitation_id}/accept` | Принять приглашение и войти в компанию | сессия |
| POST | `/api/invitations/{invitation_id}/decline` | Отклонить приглашение | сессия |
| GET | `/api/company/metrics` | Последний финансовый снимок и ключевые метрики с пояснениями | сессия |
| POST | `/api/company/integrations/{source}/connect` | Подключить источник данных (симулятор; данные помечены «демо») | сессия |

### products
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/products` | Каталог кредитных продуктов | нет |
| GET | `/api/products/{code}` | Продукт | нет |
| POST | `/api/recommendations` | Подбор «Что вам нужно?» — продукт, сумма, платёж и причины по данным компании | сессия |
| POST | `/api/calculators/annuity` | Аннуитетный калькулятор с графиком платежей | нет |

### applications
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/applications` | Заявки компании текущего пользователя (новые сверху) | сессия |
| POST | `/api/applications` | Создать черновик (signatory или preparer) | сессия |
| GET | `/api/applications/{id}` | Заявка с офером, открытыми запросами банка и доступными действиями | сессия |
| PATCH | `/api/applications/{id}` | Изменить черновик (только draft; version обязательна — автосохранение) | сессия |
| POST | `/api/applications/{id}/submit` | Отправить (draft → submitted). Идемпотентно по Idempotency-Key | сессия |
| POST | `/api/applications/{id}/cancel` | Отозвать заявку | сессия |
| GET | `/api/applications/{id}/events` | Таймлайн заявки для клиента (без внутренних комментариев банка) | сессия |
| GET | `/api/applications/{id}/decision` | Последнее решение с причинами и «что улучшить» (404 — решения ещё нет) | сессия |
| POST | `/api/applications/{id}/offer/accept` | Принять активный оффер или контроффер (offer → signing; signatory) | сессия |
| POST | `/api/applications/{id}/offer/decline` | Отказаться от оффера (offer → cancelled; signatory) | сессия |
| POST | `/api/applications/{id}/signature` | Получить код подписания — показывается на экране (не SMS); повтор выдаёт новый код | сессия |
| POST | `/api/applications/{id}/signature/confirm` | Подтвердить подписание кодом (signing → signed) | сессия |
| POST | `/api/applications/{id}/info-requests/{request_id}/respond` | Ответить на запрос (info_requested → submitted, если запросила проверка полноты; → manual_review, если сотрудник); документы — заранее через /documents | сессия |
| GET | `/api/applications/{id}/documents` | Документы заявки | сессия |
| POST | `/api/applications/{id}/documents` | Загрузить документ (только draft и info_requested; PDF, JPEG, PNG по сигнатуре; лимит размера) | сессия |
| GET | `/api/applications/{id}/documents/{document_id}` | Скачать документ (всегда attachment, тип — определённый по сигнатуре) | сессия |

### notifications
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/notifications` | Уведомления (только в интерфейсе; фронт опрашивает раз в 15–30 с) | сессия |
| POST | `/api/notifications/{notification_id}/read` | Отметить прочитанным | сессия |
| POST | `/api/notifications/read-all` | Отметить все прочитанными | сессия |

### bank
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/bank/applications` | Очередь банка с фильтрами, сортировкой, пагинацией и счётчиками по статусам | сессия |
| GET | `/api/bank/applications/{id}` | Карточка заявки для сотрудника — заявка, клиент, проверки, скоринг, решения, документы, журнал | сессия |
| POST | `/api/bank/applications/{id}/assign` | Взять заявку себе (статус не меняется) | сессия |
| POST | `/api/bank/applications/{id}/approve` | Одобрить на запрошенных условиях (manual_review → offer) | сессия |
| POST | `/api/bank/applications/{id}/counteroffer` | Иные условия и/или другой продукт (manual_review → offer; is_counteroffer / product_changed) | сессия |
| POST | `/api/bank/applications/{id}/request-info` | Запросить информацию или документ (manual_review → info_requested) | сессия |
| POST | `/api/bank/applications/{id}/decline` | Отказать с причинами и «что улучшить» (manual_review → declined) | сессия |
| POST | `/api/bank/applications/{id}/comments` | Внутренний комментарий в журнал (клиенту не виден) | сессия |
| GET | `/api/bank/applications/{id}/documents/{document_id}` | Скачать документ заявки (сотрудник банка) | сессия |
| GET | `/api/bank/dashboard` | Воронка, время в статусах, доля автоматических решений | сессия |

### assistant
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/assistant/messages` ⏳ S7 | История диалога с ассистентом (журнал вызовов инструментов) | сессия |
| POST | `/api/assistant/messages` ⏳ S7 | Сообщение ассистенту; инструменты работают от имени пользователя | сессия |
| POST | `/api/assistant/actions/{action_id}/confirm` ⏳ S7 | Человек подтверждает действие, предложенное ассистентом | сессия |

### demo
| Метод | Путь | Что делает | Вход |
|---|---|---|---|
| GET | `/api/demo/personas` | Демо-персоны для быстрого входа | нет |
| POST | `/api/demo/login` | Быстрый вход за персону | нет |
| GET | `/api/demo/failures` | Текущие флаги сбоев симуляторов | сессия |
| PUT | `/api/demo/failures` | Включить или выключить сбои симуляторов (сотрудник банка) | сессия |
| POST | `/api/demo/reset` | Сбросить демо-данные к засеянному состоянию (сотрудник банка) | сессия |
