# Нагрузочные сценарии k6 (OPS6)

k6 — в Docker (`grafana/k6:1.3.0`), на хост не ставится. Сеть хоста, адрес стека — `BASE_URL`
(локально — порт `web`, `WEB_PORT`, по умолчанию 8080). Результаты и выводы — [docs/perf.md](../../docs/perf.md).

| Файл | Что делает |
|---|---|
| `reset.js` | `/api/ready` и сброс демо-данных (`POST /api/demo/reset`); с `-e SKIP_RESET=1` — только `/api/ready` |
| `match.js` | 50 VU за 9 клиентских персон: `POST /api/recommendations`, как `/app/match`, пауза 1–3 с |
| `queue.js` | 50 VU за сотрудника банка: очередь с фильтрами и страницами + карточка заявки. `PROFILE=realistic` (по умолчанию) — как фронт: очередь раз в 15 ± 2 с, карточка каждый третий проход и 5–10 с на ней. `PROFILE=stress` — пауза 1–3 с; 429 — ожидаемая защита: метрика `throttled_429`, в `http_req_failed` не входит |
| `stats.sh` | CPU и память контейнеров во время прогона (`docker stats`) и пик по каждому |

Профиль нагрузки у всех: разгон 30 с → 2 мин держим 50 VU → спад 15 с. Пороги: `http_req_failed` < 1 %,
p95 ответов 200 < 800 мс (подбор) и < 500 мс (очередь, карточка).

## Запуск

Из корня репозитория, стек поднят (`docker compose up -d --wait`):

```bash
# перед каждым прогоном — сброс демо-данных
docker run --rm --network host -v "$PWD/scripts/k6:/scripts:ro" -e BASE_URL=http://localhost:8080 grafana/k6:1.3.0 run /scripts/reset.js

# подбор
docker run --rm --network host -v "$PWD/scripts/k6:/scripts:ro" -e BASE_URL=http://localhost:8080 grafana/k6:1.3.0 run /scripts/match.js

# очередь банка в темпе фронта
docker run --rm --network host -v "$PWD/scripts/k6:/scripts:ro" -e BASE_URL=http://localhost:8080 grafana/k6:1.3.0 run /scripts/queue.js

# очередь банка, stress: где срабатывает троттлинг
docker run --rm --network host -v "$PWD/scripts/k6:/scripts:ro" -e BASE_URL=http://localhost:8080 -e PROFILE=stress grafana/k6:1.3.0 run /scripts/queue.js

# после — стек жив
docker run --rm --network host -v "$PWD/scripts/k6:/scripts:ro" -e BASE_URL=http://localhost:8080 -e SKIP_RESET=1 grafana/k6:1.3.0 run /scripts/reset.js
```

Ресурсы контейнеров — во втором терминале на время прогона:
`scripts/k6/stats.sh record stats.csv`, после Ctrl-C — `scripts/k6/stats.sh peak stats.csv`.

Демо-эндпоинты есть только при `DEMO_MODE=1`. У банка одна демо-персона, поэтому все 50 VU делят один лимит `user`
(600/мин на пользователя). В realistic это ~230 запросов в минуту, под лимитом; в stress лимит срабатывает
(docs/perf.md).
