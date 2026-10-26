# Проверки перед релизом (REL1)

CI на GitHub не работает, поэтому всё, что он делает, прогнано вручную. Каждая найденная проблема исправлена минимально, отдельным коммитом в ветке `REL1-final-checks`. Тесты не подгонялись, проверки не отключались.

- **База:** `main` на `fd2532c` (Merge #109), 26.10.2026.
- **Окружение:** WSL2 (около 3,5 ГБ памяти) и Docker Desktop. Отдельный git worktree с `cp .env.example .env` — как в CI. Отдельный compose-проект `-p rel1` с собственными томами, поэтому база чистая. Все контейнерные команды ниже запускались с `-p rel1`.

## Итог

| Проверка | Команда | Итог |
|---|---|---|
| Запуск из чистого клона | `cp .env.example .env && docker compose up -d --build --wait db backend` | ❌ → ✅ исправлено (1) |
| ruff | `docker compose run --rm backend sh -c "ruff check . && ruff format --check ."` | ✅ |
| pytest | `docker compose run --rm backend pytest` | ✅ 2318 passed |
| pytest -m slow | `docker compose run --rm backend pytest -m slow` | ✅ 2 passed |
| Eval ассистента на mock | `migrate && seed_demo --force && assistant_eval` (`LLM_PROVIDER=mock`) | ✅ 62 из 62 сценариев |
| check --deploy, боевые настройки | `DJANGO_DEBUG=0 DJANGO_SECRET_KEY=<случайный> DJANGO_ALLOWED_HOSTS=cabinet.example.com python manage.py check --deploy --fail-level WARNING` | ✅ |
| Миграции совпадают с моделями | `python manage.py makemigrations --check --dry-run` | ✅ |
| Фронт: зависимости | `npm ci` в `frontend/` | ✅ |
| Фронт: biome | `npm run lint` | ❌ → ✅ исправлено (2) |
| Фронт: типы | `npm run typecheck` | ✅ |
| Фронт: vitest | `npm test` | ✅ 382 passed |
| Фронт: сборка | `npm run build` | ✅ |
| Клиент API = контракт | `npm run gen:api && git diff --exit-code -- src/api/` | ✅ |
| e2e на чистой базе | `npx playwright test` в `e2e/` | ❌ → ✅ исправлено (3), см. «e2e» |
| Коллекция запросов | `npm ci && npm test` в `postman/` (newman) | ❌ → ✅ исправлено (4) |
| gitleaks по всей истории | `gitleaks git . --redact --verbose --exit-code 1` (8.30.1, sha256 сверен) | ✅ |
| Ссылки в README и docs/ | скрипт: файл существует, якорь совпадает с заголовком по правилам GitHub | ❌ → ✅ исправлено (5) |
| «На ревью» у слитых задач в docs/tasks.md | статусы против смерженных PR | ❌ → ✅ исправлено (6) |
| THIRD_PARTY_NOTICES | все зависимости, образы и модели против файла | ❌ → ✅ исправлено (7) |
| Выписки других банков в assumptions.md (DOC6) | строка «Выписки из других банков» | ✅ есть |
| README без устаревших команд | каждая команда, npm-скрипт, сервис compose и скрипт | ✅ команды живые; одно устаревшее число исправлено (8) |

## Что было красным и как исправлено

1. **`cp .env.example .env && docker compose up` не запускался.** Контейнер `init` падал: `ValueError: invalid literal for int() with base 10: ''` в `DEMO_QUEUE_SIZE = env_int("DEMO_QUEUE_SIZE", 0)`. В `.env.example` стоит `DEMO_QUEUE_SIZE=` с комментарием «empty — 30», а `env_int` пустую строку не принимала. Это именно та команда, которой стенд запустит жюри.
   - Фикс: `env_int` трактует пустое значение как значение по умолчанию.
   - Тест: `apps/core/tests/test_settings_env.py` — падал до фикса.
   - Коммит `REL1: an empty integer variable in .env means its default`.
2. **biome: 2 ошибки `organizeImports`** в `CreditConclusion.tsx` и `ScoringTab.tsx`. Безопасный автофикс: меняется только порядок строк импорта.
3. **e2e.** Подробно — ниже. Две правки ожиданий, ни одно утверждение не изменено:
   - сценарий 4 — `test.slow()`;
   - сценарий 8 — 15 с на первое ожидание после отправки.
4. **newman: `grade C waits for an officer` — `expected 'processing' to deeply equal 'manual_review'`.** Конвейер теперь выполняется в worker (OPS4), а коллекция читала результат сразу после submit. Запросы «Manual review» и «Automatic offer» теперь повторяются каждые 0,5 с (не больше 20 раз), пока заявка в `submitted` или `processing`. Утверждения те же.
5. **Битая ссылка:** `docs/plan.md` → `tasks.md#финальный-спринт-2226-10`. GitHub делает из «22–26.10» якорь `222610`. Ссылка исправлена.
6. **`docs/tasks.md`:** пять карточек стояли «на ревью», хотя их PR уже в main: AI12-fix (#89, #90), XP7 (#105), UX4 и UX6 (#106), UX7 (#102). Поменяны только слова статуса.
7. **THIRD_PARTY_NOTICES** не перечислял три компонента:
   - Python-пакет `redis` 5.2.1 — MIT, по метаданным пакета;
   - образ `redis:7.4.2-alpine` — RSALv2 или SSPLv1;
   - образ `swaggerapi/swagger-ui:v5.17.14` — Apache-2.0.

   Модели (Qwen3.6, Qwen3.8, gpt-oss) и сервисы (Cloud.ru, Groq) уже были в файле.
8. **README:** «Качество ассистента: 52 сценария» → 62. В `backend/apps/assistant/scenarios/` 33 сценария клиента, 12 банка и 17 атак; eval прогоняет 62 из 62.

## e2e

| Прогон | Результат |
|---|---|
| Dev-сервер Vite, свежая база, до правок | 25 passed, 1 failed: сценарий 4, лимит теста 30 с при ожидании кода подписи |
| Сценарий 4 отдельно, 3 раза | 3 passed, 22–25 с каждый — у самого лимита |
| Dev-сервер, после `test.slow()` | 25 passed, 1 failed: сценарий 8 не увидел «Банк предлагает другой продукт» за 5 с. История уже показывала оффер, а шапка заявки ещё «Отправлена»: worker закончил, а следующий опрос (раз в 3 с) не успел |
| Сценарий 8 отдельно, 5 раз | 5 passed |
| Dev-сервер, после обеих правок, 2 прогона | по 25 passed и 1 failed, каждый раз другой тест: вход сотрудника банка не уложился в 30 с; «Заявка не найдена» не показалась за 5 с |
| **Собранное приложение через Caddy** (`docker compose up --wait`, `E2E_BASE_URL=http://127.0.0.1:8080`), 2 прогона подряд | **26 passed, 26 passed** (1,9 и 1,8 мин) |

**Вывод.** Две правки ожиданий закрывают системные причины, которые сработают и в CI:
- сценарий 4 сам по себе идёт около 25 с;
- конвейер асинхронный, а экран опрашивает сервер раз в 3 с.

Остальные падения на dev-сервере каждый раз приходились на разные тесты. Это нехватка памяти машины: dev-сервер Vite, Chromium и стек с worker в 3,5 ГБ. Против собранного приложения — того, что запускает жюри, — набор стабильно зелёный. Ещё 10 мест в e2e ждут результат конвейера стандартными 5 с; сейчас они проходят, но на медленной машине это тот же риск, что и в сценарии 8.

## Выдержки из вывода

```text
ruff check:          All checks passed!
ruff format --check: 278 files already formatted
pytest:              2318 passed, 2 deselected in 228.72s (0:03:48)
pytest -m slow:      2 passed, 2318 deselected in 356.20s (0:05:56)

assistant_eval, Провайдер: mock
| Набор           | Сценарии | Ходы     | Верные инструменты | Цифры из инструментов | Запрещённое | p50, с | p95, с | Срабатывания guards | Ответы заглушки |
| Клиент          | 33 из 33 | 36 из 36 | 100 % | 100 % | 0 | 0.0 | 0.0 | 0 | 0 |
| Сотрудник банка | 12 из 12 | 12 из 12 | 100 % | 100 % | 0 | 0.0 | 0.1 | 0 | 0 |
| Атаки           | 17 из 17 | 17 из 17 | 100 % | 100 % | 0 | 0.0 | 0.0 | 6 | 0 |
| Всего           | 62 из 62 | 65 из 65 | 100 % | 100 % | 0 | 0.0 | 0.0 | 6 | 0 |

check --deploy:      System check identified no issues (1 silenced).
makemigrations:      No changes detected

frontend lint:       Checked 142 files. No fixes applied.
frontend typecheck:  ok
vitest:              Test Files 33 passed (33) · Tests 382 passed (382)
build:               ✓ built in 2.52s
gen:api:             src/api/ без изменений

e2e (собранное приложение): 26 passed (1.9m) · 26 passed (1.8m)

newman:              requests 63 · test-scripts 126 · assertions 61, failed 0
gitleaks:            381 commits scanned · no leaks found
links:               408 relative links in 45 files, 0 broken
```

## Замечено, но не исправлялось (вне задачи или нужно решение лида)

- **Лицензия Redis 7.4.** RSALv2/SSPLv1 — source-available, не OSI-открытая лицензия. Кейс (O2) требует, чтобы проверяемая версия не зависела от закрытых лицензий. Закрытой эту лицензию не назовёшь, но и открытой тоже. Если это важно для оценки, есть открытые замены с тем же протоколом: Valkey (BSD-3-Clause) или Redis 7.2 (BSD-3-Clause). Это смена зависимости — решает лид.
- **`docs/assistant.md`:** в двух местах «52 сценария (25 + 11 + 16)», а их уже 62 (33 + 12 + 17). Ниже в том же файле 62 упоминается.
- **Имя проекта compose одно — `alfa-cabinet`.** Любая копия репозитория без `-p` подхватывает том базы основного стека. README это уже описывает («Новая копия репозитория показывает старые заявки»).
- **Аудит зависимостей** (job `audit`: pip-audit, npm audit) не прогонялся — его не было в списке задачи. Он и в CI не блокирующий.
- **Сборка образа `web` в этом окружении** упала на credential helper Docker Desktop в WSL (`error getting credentials`). Собиралось с временным `DOCKER_CONFIG` без helper. К репозиторию это не относится.
