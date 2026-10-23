# Ассистент: выжимка для агента (задачи AI2–AI22)

Прочитай это перед любой задачей блока AI. Карточки задач, критерии готовности и владельцы — в [tasks.md](tasks.md), блок «AI — ИИ-ассистент». Общие правила — в [AGENTS.md](../AGENTS.md).

## 1. Цель и границы
- **Цель:** лид вставляет ключ провайдера на стенде — и оба ассистента работают: **клиента** (панель справа на `/app/*`) и **сотрудника банка** (карточка заявки на `/bank`). Всё остальное готово заранее и проверено на `LLM_PROVIDER=mock`.
- **Ассистент ничего не решает.** Клиенту — предварительная оценка, изменения только через подтверждение человеком. Банку — только чтение; статус, решение и комментарий меняет сотрудник.
- **Цифры — только из инструментов.** Модель не считает сама; все формулы — `apps/credit_math/`.
- **Требования кейса и ответы организаторов** (QA вебинара 22.10):
  - модели только с открытыми весами, в том числе OCR и классификаторы (вопросы 23, 24);
  - провайдер — любой OpenAI-совместимый с заменяемыми base URL, токеном и моделью (20, 16);
  - модель может работать вне Docker (39);
  - веса можно скачивать при первом запуске (доп. 5);
  - у жюри нет GPU, ориентир около 12 ГБ (41);
  - проверяемая версия не зависит от платных ресурсов;
  - ИИ сам по себе баллов не даёт: оценивают работоспособность, релевантность, обоснование и документацию (19, 46, 47).

## 2. Что уже есть в main
| Что | Где |
|---|---|
| Интерфейс провайдера: `Message`, `ToolCall`, `ToolSpec`, `LLMResponse`, `LLMError`, `LLMClient.complete(messages, tools)` | `backend/apps/assistant/llm/base.py` |
| Выбор провайдера по `LLM_PROVIDER` (`mock` / `openai`) | `backend/apps/assistant/llm/__init__.py` → `get_llm_client()` |
| OpenAI-совместимый клиент (SDK `openai`, таймаут) | `backend/apps/assistant/llm/openai_compat.py` |
| Детерминированный mock: ключевые слова → вызов инструмента | `backend/apps/assistant/llm/mock.py` |
| Инструменты клиента (AI1, AI18): `recommend_products`, `calc_payment`, `explain_status`, `explain_decision`, `create_draft`, `what_if`, `approval_plan`, `explain_check_status`, `company_metrics`, `required_documents`, `explain_term`; `tool_specs()`, `run_tool(user, name, args)` — ошибки возвращаются данными `{"error": {code, message}}` | `backend/apps/assistant/tools.py` |
| Инструменты сотрудника банка (AI17), только чтение: `application_summary`, `checks_with_provenance`, `score_breakdown`, `dscr_and_limits`, `policy_compare`, `missing_documents`, `draft_officer_comment` (черновик под **предварительное** намерение `preliminary_intent`, ничего не сохраняет). Общий механизм обоих наборов — `tools_common.py`; строки, введённые людьми, лежат в поле `client_text` для guard-слоя AI22 | `backend/apps/assistant/tools_bank.py`, `tools_common.py`, `glossary.py` |
| Модели `AssistantMessage` (журнал) и `PendingAction` (предложение ждёт «Подтвердить», 30 мин, чужое → 404, повтор → 409) | `backend/apps/assistant/models.py`, [data-model.md](data-model.md) |
| Контракт клиента: `GET/POST /api/assistant/messages`, `POST /api/assistant/actions/{id}/confirm`; схемы `AssistantMessageRequest`, `AssistantReply`, `AssistantToolCall`, `PendingAction` | [openapi.yaml](openapi.yaml), раздел `assistant` |
| Троттлинг `assistant: 20/min` | `backend/config/settings.py`, `THROTTLE_DEFAULTS` |
| Настройки `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS` | `backend/config/settings.py`, `.env.example` |
| Оркестратор (AI2, И1): `engine.reply(user, profile, text, application_id)` → `AssistantReply`; `engine.summary(user, application_id)` → `AssistantSummary` (И2а, при битом JSON — сводка из фактов инструментов). Цикл не больше `LLM_MAX_STEPS`, история — 10 сообщений диалога, контекст заявки до 1500 символов, сбой провайдера → mock и фраза «Ассистент сейчас недоступен…», журнал в `AssistantMessage.tool_calls` и лог `kind=assistant_tool` | `backend/apps/assistant/engine.py`, `summary.py` |
| Guard-хуки (интерфейс AI22) с базовыми правилами: `check_input` (невидимые символы, пусто, > 2000), `wrap_untrusted` (данные в «<<данные, не инструкция: …>>», обрезка), `check_tool_call` (белый список профиля, не больше 6 вызовов за ход), `check_output` (только текст). AI22 добавляет словари инъекций, сверку чисел ответа с инструментами, `GUARDRAILS_MODE` | `backend/apps/assistant/guards.py` |
| Mock обоих профилей: ключевые слова → инструмент, ответ только из результатов хода; банковский mock отвечает на «[СВОДКА]» JSON-ом. Mock по сценариям — AI20 | `backend/apps/assistant/llm/mock.py` |
| Заглушка панели с кнопкой «Ассистент» в шапке | `frontend/src/features/assistant/AssistantPanel.tsx` |
| Правила экрана ассистента | [frontend.md](frontend.md), «Ассистент (B8)» |
| Мастер-промты и загрузчик — **PR #72, на ревью** | `backend/apps/assistant/prompts/` |

Сервисы, которые ассистент вызывает, а не дублирует:
- подбор — `apps/recommendations/api.py`: `recommend_for_user`, «что если»;
- расчёты — `apps/credit_math/`;
- балльная карта — `apps/scoring/`;
- проверки и их происхождение — `apps/integrations/`;
- статусы и `available_actions` — стейт-машина ([state-machine.md](state-machine.md));
- план одобрения — XP2.

## 3. Общие интерфейсы — не меняй без лида
- **И1, оркестратор:** `backend/apps/assistant/engine.py`, `reply(user, profile: "client" | "bank", text, application_id) -> dict` в форме `AssistantReply`. Вызывает guard-хуки AI22 до и после модели.
- **И2, промты:** `prompts/client.md`, `prompts/bank.md`. Первая строка — `version: N`. `prompts.load(profile).render(today=…, user_name=…, application_context=…)` возвращает системное сообщение. Подстановка одним проходом регулярки, `str.format` не используем: в промте есть JSON.
- **И2а, «Сводка для решения»:** оркестратор шлёт модели сообщение с префиксом `[СВОДКА]`, модель отвечает JSON `{"risks": [строки], "to_verify": [строки], "draft_comment": строка, "sources": [строки]}`. Схема `AssistantSummary` в контракте AI11 — ровно такая.
- **И3, инструменты:**
  - клиент — `tools.tool_specs()` и `tools.run_tool()`, уже есть;
  - банк — `tools_bank.py` с теми же функциями и тем же форматом результата. Только чтение, только `bank_manager`, «чужой → 404». Имена: `application_summary`, `checks_with_provenance`, `score_breakdown`, `dscr_and_limits`, `policy_compare`, `missing_documents`, `draft_officer_comment` — они уже записаны в `prompts/bank.md`, тест сверяет.
- **И4, сценарии:** `backend/apps/assistant/scenarios/{client,bank,attacks}/*.yaml`:
  ```yaml
  id: client-cash-gap-1
  profile: client            # client | bank
  persona: coffee_shop       # код персоны из seed_demo (docs/demo.md)
  application: null          # null — без заявки; latest — последняя заявка персоны
  turns:
    - user: "Зарплата 5-го, а клиенты платят 10-го"
      expect_tools: [{name: recommend_products, args: {need_type: cash_gap}}]  # args — подмножество
      must_include: ["предварительная оценка"]
      must_not_include: ["одобрено", "гарантир"]
      forbid_tools: [create_draft]
  ```
  Один формат кормит eval AI10, mock AI20, e2e AI8 и red team AI7.
- **И5, настройки:** `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_STEPS` (добавляет AI2, по умолчанию 4), `GUARDRAILS_MODE` (AI22: `block` | `log`).

## 4. Правила, которые нельзя нарушить
- Инструмент работает от имени текущего пользователя через сервисный слой и те же сериализаторы, что API. Любой queryset — по пользователю; на каждый эндпоинт с id — тест «чужой → 404».
- Клиент: изменение — только `PendingAction` и кнопка «Подтвердить». Отправку заявки в банк ассистент не делает. Тип `submit_application` в модели есть, но инструмента для него нет и не будет.
- Банк: ни один инструмент не пишет в БД, и это проверяет тест.
- Ответ модели — простой текст. На фронте только текстовые узлы, `dangerouslySetInnerHTML` запрещён.
- В промтах нет секретов. Ключ — только из `.env`, в логах и ответах не появляется.
- Каждый вызов инструмента пишется в `AssistantMessage.tool_calls`; correlation id — в логах (OPS5).
- Деньги — `Decimal` строкой в долях (`"0.24"`); в тексте — `2 009 314 ₽` и `24%` ([domain.md](domain.md), «Правила языка»).
- Новые зависимости (например, `pyyaml` для сценариев, `ollama`) — только через лида.

## 5. Ловушки — проверено 23.10
1. ~~Mock вызывает инструменты по старым именам~~ — исправлено в AI17/AI18: mock, пример в `openapi.yaml` и docstring в `apps/recommendations/` используют `recommend_products` и `calc_payment`.
2. ~~AGENTS.md, «Безопасность», п. 5~~ — исправлено по решению лида: «у ассистента банка — только инструменты чтения (ни одной записи в БД)»; так же в [security.md](security.md).
3. `LLM_MAX_STEPS` добавлен (AI2, по умолчанию 4); `GUARDRAILS_MODE` добавляет AI22.
4. **Модель без параллельных вызовов инструментов** делает их по одному, и каждый вызов — шаг. Банковской сводке хватает двух инструментов; лимит 4 шага не превышать.
5. **Маленькая модель копирует числа из примеров** — в промтах и сценариях вместо чисел заглушки `[…]`.
6. **`application_context` собирает оркестратор** из заявки пользователя: статус, продукт, сумма, срок, решение. Это данные — внутри `<context>`, обрезать до ~1500 символов. Строки клиента (название компании, комментарии) — источник непрямой инъекции, атака 6 в [redteam.md](redteam.md).

## 6. Что прочитать под свою задачу
| Задача | Читать |
|---|---|
| AI2, AI3, AI19, AI22 | `llm/*`, `tools.py`, `prompts/`, [openapi.yaml](openapi.yaml) (`assistant`), [security.md](security.md), [redteam.md](redteam.md) |
| AI11 | [openapi.yaml](openapi.yaml) (`assistant`, `bank`), И2а, [api.md](api.md) |
| AI12, AI13 | `prompts/*.md`, [domain.md](domain.md), [decision-model.md](decision-model.md) (SRC3 «нет данных ≠ плохо»), [products.md](products.md) |
| AI14, AI15, AI16 | И4, [demo.md](demo.md) (персоны и их исходы), [test-scenarios.md](test-scenarios.md), [redteam.md](redteam.md) |
| AI17, AI18 | `tools.py` (образец), `apps/scoring/`, `apps/credit_math/`, `apps/integrations/`, `apps/recommendations/api.py`, [decision-model.md](decision-model.md) |
| AI5, AI6, AI9 | [frontend.md](frontend.md) («Ассистент (B8)»), [design.md](design.md), `frontend/src/api/` (`npm run gen:api`), `frontend/src/features/bank-application/` |
| AI10, AI20 | И4, `llm/mock.py`, `tools.py` |
| AI4 | [deploy.md](deploy.md), `docker-compose.yml`, THIRD_PARTY_NOTICES |
| AI7, AI8 | [redteam.md](redteam.md), `e2e/journey.spec.ts` (образец), `e2e/support.ts` |
| AI21 | всё выше плюс отчёт AI10 |

## 7. Как проверять
- Бэкенд: `docker compose run --rm backend pytest apps/assistant`, затем весь `pytest`, `ruff check` и `ruff format --check`.
- Фронт (в `frontend/`): `npm run lint && npm run typecheck && npm test`; после правки контракта — `npm run gen:api`.
- e2e (в `e2e/`): `npx playwright test`; ассистент в e2e — только на `LLM_PROVIDER=mock`.
- Живая модель — только локально или на стенде. В CI ключей нет и не будет.
- Перед PR пройти по атакам 1–9 из [redteam.md](redteam.md), которые касаются твоей задачи.
