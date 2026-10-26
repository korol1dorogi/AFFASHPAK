# Команде

Онбординг — [START_HERE.md](../START_HERE.md), правила для ИИ-агентов — [AGENTS.md](../AGENTS.md), задачи — [docs/tasks.md](tasks.md).

- Фронт с горячей перезагрузкой: `cd frontend && npm ci && npm run dev` → http://localhost:5173 (API — бэкенд на `127.0.0.1:8000`).
- Фронт без бэкенда, на моке контракта: `docker compose --profile mock up -d mock` → http://localhost:4010, затем в `frontend/`: `npm run dev:mock`.
- Клиент API из контракта: в `frontend/`: `npm run gen:api`. Миграции: `docker compose run --rm backend python manage.py migrate`.
- После правок кода воркера: `docker compose restart worker` (Celery не перезагружается сам).
- Стенд — [docker-compose.prod.yml](../docker-compose.prod.yml) + Caddy (HTTPS), [docs/deploy.md](deploy.md); деплоит CI после мержа в main; если GitHub Actions не запускается (так было 26.10 из-за лимита оплаты) — вручную `ssh root@<ip> alfa-deploy`.
