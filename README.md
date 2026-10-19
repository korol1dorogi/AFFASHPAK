# Умный кредитный кабинет предпринимателя

Прототип личного кабинета для малого и микробизнеса: от вопроса «зачем бизнесу деньги» до подбора кредитного продукта с суммой и обоснованием, заявки и предварительной оценки. ИИ-ассистент ведёт клиента по этому пути.
Хакатон «Альфа-Будущее» (Альфа-Банк × Changellenge). Репозиторий приватный, решение не публикуем.

**Команде:** начни с [START_HERE.md](START_HERE.md). **Агентам:** правила — [AGENTS.md](AGENTS.md).

## Быстрый старт
Нужны Git, Docker Desktop и Node из [.nvmrc](.nvmrc) (24 LTS). На Windows работай внутри WSL2.

```sh
cp .env.example .env
docker compose up -d --build          # db + backend → http://localhost:8000/api/health

cd frontend && npm ci && npm run dev  # кабинет → http://localhost:5173
```

Фронт без бэка, на моке контракта: `docker compose --profile mock up -d mock`, затем `npm run dev:mock` в frontend/.

## Проверки
| Что | Команда |
|---|---|
| Тесты бэка | `docker compose run --rm backend pytest` |
| Линт бэка | `docker compose run --rm backend sh -c "ruff check --fix . && ruff format ."` |
| Фронт (в frontend/) | `npm run lint && npm run typecheck && npm test` |
| Клиент API из контракта (в frontend/) | `npm run gen:api` |
| e2e (в e2e/, бэк должен быть поднят) | `npm ci && npx playwright install chromium && npx playwright test` |

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) гоняет то же самое, а ещё сверяет сгенерированный клиент с контрактом, запускает gitleaks и `manage.py check --deploy`. Локальные хуки (необязательно): `pipx install pre-commit && pre-commit install`.

## Структура
```
AGENTS.md            правила для всех ИИ-агентов (единый файл)
START_HERE.md        онбординг команды
docs/                знания и контракт
  case.md            кейс и чек-лист F1…Fn       judging.md   критерии → доказательства
  domain.md          термины, модели, статусы    openapi.yaml контракт API (источник истины)
  tasks.md           задачи и владельцы          plan.md      план и роли
  decisions.md       принятые решения            demo.md      персоны и сценарий демо
  pitch.md, redteam.md, submission.md, knowledge/credit.md
data/                SCHEMA.md — схема данных кейса; sample/ — синтетика (демо)
backend/             Django + DRF: config/ — настройки из env; apps/<домен>/
  apps/credit_math/  все кредитные расчёты (Decimal, чистые функции)
  apps/assistant/    ИИ-ассистент: LLM-клиент (mock | OpenAI-совместимый)
frontend/            React + TS + Vite + shadcn/ui: src/features/<фича>/, src/api/ (сгенерировано)
e2e/                 Playwright: journey.spec.ts — сквозной путь клиента
```

## Стенд
Прод-сборка — [docker-compose.prod.yml](docker-compose.prod.yml) + Caddy (HTTPS), инструкция — [docs/deploy.md](docs/deploy.md). Деплоит лид.

## Демо-учётки
Появятся после Фазы 2 (команда `seed_demo`, персоны — [docs/demo.md](docs/demo.md)).

## Данные и секреты
- В `.env` — только локальные значения; в репозиторий попадает лишь [.env.example](.env.example) с заглушками.
- Реальные данные кейса лежат вне репозитория: путь задаётся в `CASE_DATA_DIR` в `.env`, бэкенд видит их только на чтение в `/case-data`.
- ИИ-ассистент по умолчанию работает на `LLM_PROVIDER=mock` — без сети и ключа.
