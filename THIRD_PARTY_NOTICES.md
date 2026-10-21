# Third-party notices

Сторонние компоненты, которые использует «Оборот». Версии закреплены (`backend/requirements*.txt`, `*/package-lock.json`, образы — в `Dockerfile` и `docker-compose*.yml`). Лицензии взяты из метаданных установленных пакетов (21.10.2026). Полные тексты лицензий лежат в самих пакетах (`node_modules/<пакет>/LICENSE`, `site-packages/<пакет>.dist-info/`) и по ссылкам SPDX: https://spdx.org/licenses/.

Ничего из списка не изменялось. Код решения — команды хакатона «Альфа-Будущее».

## ИИ-модель

| Компонент | Как используется | Лицензия |
|---|---|---|
| Mock-провайдер (`apps/assistant/llm`) | по умолчанию: детерминированные ответы без сети и ключа | собственный код |
| LLM с открытыми весами через OpenAI-совместимый API или Ollama | опционально (`LLM_PROVIDER=openai`, профиль `llm`); основной сценарий работает без неё | лицензия выбранной модели: модель и её лицензия вписываются сюда при выборе (D8) |
| `openai` (Python SDK) 3.35.1 | клиент OpenAI-совместимого API (к модели с открытыми весами, не к сервисам OpenAI) | Apache-2.0 |

## Бэкенд (Python 3.12)

| Пакет | Версия | Лицензия |
|---|---|---|
| Django | 6.1.2 | BSD-3-Clause |
| djangorestframework | 3.18.3 | BSD-3-Clause |
| psycopg (binary) | 3.3.6 | LGPL-3.0-only — используется как библиотека без изменений, динамически |
| gunicorn | 26.2.0 | MIT |
| celery | 5.5.3 | BSD-3-Clause |
| openai | 3.35.1 | Apache-2.0 |

Только разработка и тесты: pytest 9.1.1 (MIT), pytest-django 4.14.0 (BSD-3-Clause), ruff 0.17.1 (MIT), openapi-core 0.23.1 (BSD-3-Clause).

## Фронтенд (собирается в статические файлы)

| Пакет | Версия | Лицензия |
|---|---|---|
| react, react-dom | 19.3.1 | MIT |
| react-router | 8.5.0 | MIT |
| @tanstack/react-query | 5.104.5 | MIT |
| react-hook-form | 7.90.0 | MIT |
| @hookform/resolvers | 5.9.2 | MIT |
| zod | 4.6.7 | MIT |
| openapi-fetch | 0.17.0 | MIT |
| @radix-ui/react-checkbox, -dialog, -dropdown-menu, -label, -progress, -radio-group, -select, -separator, -slot, -tabs, -tooltip | 1.2.0–2.4.1 | MIT |
| sonner | 2.0.8 | MIT |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| clsx | 2.1.1 | MIT |
| tailwind-merge | 3.7.0 | MIT |
| lucide-react (иконки) | 1.59.0 | ISC |

### Шрифты

| Шрифт | Пакет | Лицензия |
|---|---|---|
| Golos Text | @fontsource/golos-text 5.3.0 | SIL Open Font License 1.1 |
| Manrope | @fontsource-variable/manrope 5.3.0 | SIL Open Font License 1.1 |

Шрифты подключены локальными файлами, без внешних CDN.

Только сборка и тесты: vite 8.3.4 (MIT), @vitejs/plugin-react 6.1.2 (MIT), tailwindcss и @tailwindcss/vite 4.3.3 (MIT), tw-animate-css 1.4.0 (MIT), typescript 5.9.3 (Apache-2.0), @biomejs/biome 2.5.15 (MIT OR Apache-2.0), vitest 5.0.5 (MIT), jsdom 30.1.3 (MIT), @testing-library/dom 10.4.2, /react 16.3.3, /jest-dom 7.0.1 (MIT), openapi-typescript 7.13.0 (MIT), @types/* (MIT).

## Тесты и коллекция запросов

| Пакет | Версия | Лицензия |
|---|---|---|
| @playwright/test | 1.64.1 | Apache-2.0 |
| newman | 6.2.1 | Apache-2.0 |

## Образы и сервисы Docker

| Образ | Версия | Лицензия ПО |
|---|---|---|
| python (slim) | 3.12.15 | PSF-2.0 (Python); Debian — свободные лицензии пакетов |
| postgres | 18.6 | PostgreSQL License |
| node (slim, только сборка фронта) | 24.22.0 | MIT (Node.js) |
| caddy (alpine) | 2.11.7 | Apache-2.0 |
| stoplight/prism (мок контракта, профиль `mock`) | 5.15.10 | Apache-2.0 |

## Данные

Все данные синтетические: генератор команды (`backend/apps/demo_data`), помечены «демо». Внешние источники (ЕГРЮЛ/ЕГРИП, «Прозрачный бизнес», БКИ, выписка, подписание, выдача) — симуляторы. Логотипы, шрифты и цвета Альфа-Банка не используются.
