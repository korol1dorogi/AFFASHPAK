# Деплой стенда на VPS

Сервер настраивает лид; дальше каждый мерж в main с зелёным CI выкатывается сам (docs/decisions.md D11). Схема: наружу смотрит только Caddy (80/443, HTTPS автоматически). Он раздаёт собранный фронт, проксирует `/api` и админку на gunicorn, раздаёт статику админки. У `db` и `backend` портов наружу нет: Docker обходит UFW, поэтому публиковать что-то, кроме Caddy, нельзя.

Секреты живут только в `/srv/alfa-cabinet/.env` на сервере (права 600). В репозиторий, чат и CI они не попадают.

## 1. Сервер (один раз)
Ubuntu 24.04, 2 vCPU / 4 GB RAM / 30 GB — с запасом.

```sh
# под root
adduser deploy && usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/ && chown -R deploy:deploy /home/deploy/.ssh
# SSH: только ключи, без root
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh
# Файрвол: Docker его обходит, поэтому это вторая линия; первая — нет `ports:` у db/backend
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw enable
apt update && apt install -y unattended-upgrades git
```

Docker — по официальной инструкции для Ubuntu (docs.docker.com/engine/install/ubuntu), затем `usermod -aG docker deploy`.

## 2. Код (один раз)
Репозиторий приватный: на сервере нужен **deploy key только на чтение**.
```sh
# под deploy
ssh-keygen -t ed25519 -f ~/.ssh/alfa_deploy -N "" -C "alfa-vps-deploy"
cat ~/.ssh/alfa_deploy.pub   # → GitHub: репозиторий → Settings → Deploy keys → Add (без write access)
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/alfa_deploy
  IdentitiesOnly yes
EOF
sudo mkdir -p /srv/alfa-cabinet && sudo chown deploy:deploy /srv/alfa-cabinet
git clone git@github.com:korol1dorogi/AFFASHPAK.git /srv/alfa-cabinet
```

## 3. Адрес
- Есть домен — A-запись на IP сервера.
- Домена нет — `DOMAIN=<ip-через-дефисы>.sslip.io` (например, `203-0-113-10.sslip.io`): сертификат Let's Encrypt выпустится и на него.

## 4. Секреты (один раз)
```sh
cd /srv/alfa-cabinet
cp deploy/.env.prod.example .env && chmod 600 .env
python3 -c "import secrets; print('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(64))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('DJANGO_ADMIN_URL=office-' + secrets.token_hex(6) + '/')"
nano .env   # вписать DOMAIN и три значения выше
```
- `LLM_PROVIDER=mock`, пока организаторы не ответят, можно ли отправлять данные кейса во внешние LLM (D8). Потом — **отдельный** ключ для стенда с жёстким месячным лимитом бюджета в кабинете провайдера.
- `DEMO_MODE` (по умолчанию `1` в docker-compose.prod.yml): при каждом старте бэкенд досоздаёт синтетические демо-персоны (`manage.py seed_demo`, существующее не трогает), работают быстрый вход за персону и `/api/demo/*`. `DEMO_MODE=0` в `.env` выключает и то и другое.
- Лимиты входа (`docker-compose.prod.yml`, меняются в `.env`): `THROTTLE_LOGIN=10/min` — вход по паролю и регистрация, строго, против подбора пароля; `THROTTLE_DEMO_LOGIN=120/min` — быстрый вход за демо-персону, отдельный счётчик, чтобы жюри с одного IP переключалось между персонами без 429; `THROTTLE_ANON=300/min` — остальные анонимные запросы (страница входа на каждое переключение делает 3–4 запроса). Значения по умолчанию в коде — `THROTTLE_DEFAULTS` в `config/settings.py`.
- Данные кейса: `sudo mkdir -p /srv/alfa-case-data && sudo chown deploy:deploy /srv/alfa-case-data`, загрузить туда по `scp`. Путь — в `CASE_DATA_DIR`; бэкенд видит его только на чтение.

## 5. Первый запуск
```sh
cd /srv/alfa-cabinet
docker compose up -d --build        # COMPOSE_FILE из .env указывает на docker-compose.prod.yml
docker compose ps                   # все healthy
docker compose run --rm backend python manage.py createsuperuser   # учётка лида в бэк-офисе
```
Проверка: `https://$DOMAIN/` — кабинет, `https://$DOMAIN/api/health` — `{"status":"ok",...}`, `https://$DOMAIN/$DJANGO_ADMIN_URL` — бэк-офис.

## 6. Автодеплой после мержа (D11)
Мерж в `main` → CI (backend, frontend, e2e, gitleaks) → при зелёном — джоба `deploy` заходит на сервер по SSH и запускает `/usr/local/bin/alfa-deploy` ([deploy/alfa-deploy.sh](../deploy/alfa-deploy.sh)): `git fetch` → **дамп БД** → `reset` на `origin/main` → `docker compose up -d --build --wait` → проверка `/api/health`. Журнал — `/var/log/alfa-deploy.log`.
- **Бэкап перед каждым деплоем:** `/var/backups/alfa-cabinet/predeploy-<время>-<коммит>.sql.gz`, хранятся последние 10. Дамп не снялся — деплой не начинается.
- **Откат:** не поднялось — возврат на предыдущий коммит. Если между коммитами менялись миграции (`*/migrations/*`), перед этим `backend` и `worker` останавливаются и база восстанавливается из дампа этого деплоя: старый код не работает на новой схеме. Записи, сделанные за минуты неудачного деплоя, при этом теряются.
- **Скрипт обновляет себя сам:** после каждого запуска установленная копия сверяется с `deploy/alfa-deploy.sh` из репозитория и при расхождении заменяется (следующий запуск — уже новой версией).

Ключ CI в `authorized_keys` ограничен: `restrict,command="/usr/local/bin/alfa-deploy"`. С ним нельзя получить шелл, выполнить другую команду или пробросить порты — только выкатить последний `main`.

Настройка (один раз):
```sh
# на сервере
install -m 755 deploy/alfa-deploy.sh /usr/local/bin/alfa-deploy
# ключ CI (пара генерируется у лида, приватная часть — только в GitHub Secrets)
echo 'restrict,command="/usr/local/bin/alfa-deploy" ssh-ed25519 AAAA... github-actions-deploy-alfa' >> ~/.ssh/authorized_keys
```
- Ключ CI — **секрет окружения `production`, не репозитория**: так его получает только джоба `deploy` и только из `main`, а не любой workflow любой ветки.
  1. GitHub → Settings → Environments → New environment `production`.
  2. Deployment branches and tags → Selected branches → правило `main`.
  3. В окружении `production` → Environment secrets → Add secret `DEPLOY_SSH_KEY` — содержимое приватного ключа CI целиком.
  4. Settings → Secrets and variables → Actions → **удалить** repository secret `DEPLOY_SSH_KEY` (иначе он по-прежнему доступен всем workflow).
  Джоба `deploy` в `.github/workflows/ci.yml` уже объявляет `environment: production`; пока секрет не перенесён, она берёт старый репозиторный — деплой не ломается.
- GitHub → Settings → Deploy keys → публичный ключ сервера для чтения репозитория (раздел 2, без write access).
- IP и ключ хоста сервера записаны в `.github/workflows/ci.yml` (джоба `deploy`); при смене сервера — обновить там.
- Скрипт в репозитории поменялся — переустанавливать не нужно: он обновит установленную копию сам при следующем деплое. Один раз руками — только если на сервере стоит версия старше этой (без самообновления): командой выше.

Вручную (то же самое): `ssh root@<ip> alfa-deploy`, или на сервере `alfa-deploy`.

## 7. Демо-данные
Засев автоматический: при каждом старте бэкенд выполняет `seed_demo` — каталог, 8 персон, сотрудник банка и один раз 30 заявок популяции через конвейер (живая очередь банка). Существующее не трогает.
- Сброс перед показом: демо-панель `/bank/demo` → «Сбросить» (или `POST /api/demo/reset` от сотрудника банка) — удаляются заявки демо-персон и демо-очереди (с уведомлениями и файлами), выключаются сбои, очередь засевается заново. Заявки компаний, которые посетители подключили сами, остаются; кто сбросил — в логе бэкенда (`demo reset by …`).
- Сценарий 7: на демо-панели включить сбой «Бюро кредитных историй», подать заявку персоной `bki_outage`, выключить. Забытый сбой гаснет сам через 15 минут (`FAILURE_TTL` в [backend/apps/integrations/flags.py](../backend/apps/integrations/flags.py)).
- Swagger: `https://<домен>/api/docs`.

## 7а. Ассистент на живой модели (один раз)
По умолчанию ассистент работает на детерминированном mock: без ключа и без сети. Чтобы включить живую модель с открытыми весами, на сервере в `/srv/alfa-cabinet/.env` (ключ — только здесь, не в репозитории и не в CI):

```
LLM_PROVIDER=openai
LLM_BASE_URL=https://foundation-models.api.cloud.ru/v1
LLM_API_KEY=<ключ провайдера>
LLM_MODEL=Qwen/Qwen3.6-35B-A3B
LLM_TIMEOUT_SECONDS=45
LLM_TURN_BUDGET_SECONDS=60
```

Затем `docker compose up -d backend worker` (перечитать `.env`) и проверка: `docker compose exec backend python -m apps.assistant.llm.smoke` — «готово» или что не так.

- Таймауты: gunicorn обрывает запрос через 120 с (`--timeout 120`), поэтому `LLM_TURN_BUDGET_SECONDS` + `LLM_TIMEOUT_SECONDS` < 120 (на модели стенда ответ банка доходит до 30 с). После бюджета новый запрос к модели не начинается — ответ дописывает заглушка с пометкой «упрощённый режим». 24.10 при таймауте модели 90 с медленный ответ оборвался ошибкой 500.
- Провайдер должен пускать IP сервера. Стенд в России: Groq и OpenRouter отвечают ему 403 (с ноутбука тот же ключ работает), поэтому на стенде Cloud.ru Foundation Models — российский, OpenAI-совместимый, `Qwen/Qwen3.6-35B-A3B` на нём бесплатна.
- Список моделей через запятую: модель, упёршаяся в лимит (429) или таймаут, сразу передаёт запрос следующей. На бесплатном тарифе Groq у каждой модели свои 8000 токенов в минуту, а ход ассистента тратит 3–7 тысяч, поэтому три модели ≈ втрое больше ходов в минуту.
- Если не ответила ни одна модель, ассистент отвечает через mock с фразой «Ассистент сейчас недоступен…»; кабинет и заявки работают как обычно.
- Вернуть mock: `LLM_PROVIDER=mock` и тот же перезапуск.

## 8. Обслуживание
- Логи: `docker compose logs -f --tail 100 caddy backend`. Ротация — у каждого контейнера 3 файла по 10 МБ (`x-logging` в docker-compose.prod.yml; проверено 25.10: `docker inspect … LogConfig`).
- Память: на VPS 3 ГБ, поэтому есть swap 2 ГБ (`/swapfile`, в `/etc/fstab`; проверка `swapon --show`).
- После перезагрузки VPS стек поднимается сам (`restart: unless-stopped`; проверено 25.10 — сервер перезагрузился, стек и данные на месте).

### Бэкапы и восстановление (OPS7)
| Что | Команда на сервере |
|---|---|
| Ежедневный дамп | сам: `/etc/cron.d/alfa-cabinet-backup` — в 03:30 `alfa-deploy backup daily` → `/var/backups/alfa-cabinet/daily-<время>-<коммит>.sql.gz`, хранятся последние 10 |
| Дамп руками (перед демо) | `alfa-deploy backup` → `manual-…sql.gz` |
| Перед каждым деплоем | сам: `predeploy-…sql.gz`; деплой без дампа не начинается (раздел 6) |
| Проверить, что дамп восстанавливается | `alfa-deploy verify-backup` — свежий дамп разворачивается во временном контейнере PostgreSQL той же версии и сверяется с живой базой по числу строк в каждой таблице; живая база не трогается. Для конкретного файла — `alfa-deploy verify-backup <файл>` |
| Восстановить | `alfa-deploy restore /var/backups/alfa-cabinet/<файл>.sql.gz` — одна команда: дамп текущей базы (`prerestore-…`), остановка backend и worker, восстановление, подъём стека, проверка `/api/health`. Не получилось — в логе команда для отката на `prerestore-…` |

Дамп снят с `--clean --if-exists`: он сам удаляет и пересоздаёт таблицы. Журнал всех операций — `/var/log/alfa-deploy.log`.

### Внешний мониторинг (OPS1)
UptimeRobot (бесплатно): монитор типа Keyword на `https://194-67-92-122.sslip.io/api/ready`, ключевое слово `"ready"`, интервал 5 минут, оповещение — в Telegram команды и на почту лида. `/api/ready` проверяет базу и миграции, поэтому ловит не только падение Caddy, но и «сайт открывается, а база лежит».

## 9. Если стенд упал (runbook)
Порядок — от быстрого к радикальному. Все команды — на сервере в `/srv/alfa-cabinet`.

| # | Что проверить | Как | Что делать |
|---|---|---|---|
| 1 | Отвечает ли стенд | `curl -s https://<домен>/api/ready` (или оповещение мониторинга) | `{"status":"ready"…}` — стенд жив, проблема в конкретном экране: шаг 3 |
| 2 | Живы ли контейнеры | `docker compose ps` | не `Up … (healthy)` → `docker compose up -d --wait`; после перезагрузки VPS стек поднимается сам — подождать минуту |
| 3 | Что в логах | `docker compose logs --tail 100 backend worker caddy`; по `request_id` из ответа об ошибке — вся история запроса | трассировка — в чат команды; ошибки конвейера заявки — в `worker` |
| 4 | Хватает ли ресурсов | `df -h /`, `free -m`, `dmesg -T \| grep -i -E "killed process\|oom"` | диск забит — `docker system prune -f` (образы), старые дампы в `/var/backups/alfa-cabinet`; OOM — проверить swap (`swapon --show`), перезапустить стек |
| 5 | Сломал последний деплой | `tail -20 /var/log/alfa-deploy.log`, `git log --oneline -5` | неудачный деплой откатывается сам; если откат не помог: `git reset --hard <прошлый коммит> && docker compose up -d --build --wait`, затем исправление в `main` |
| 6 | Испорчены данные | `ls -lt /var/backups/alfa-cabinet \| head` | `alfa-deploy restore <последний подходящий дамп>`; если демо просто «замусорено» — Демо-панель → «Сброс демо-данных» |
| 7 | Ассистент отвечает «упрощённый режим» | `docker compose exec backend python -m apps.assistant.llm.smoke` | «ключ не подходит» / 402 / 403 — ключ или провайдер (раздел 7а); долго думает — норма раз в несколько ответов; совсем нет модели — `LLM_PROVIDER=mock` в `.env` и `docker compose up -d backend worker`: ассистент работает на заглушке |
| 8 | Ничего не помогло | — | `docker compose down && docker compose up -d --build --wait` (данные в томе сохраняются; `down -v` — **никогда**: удалит базу) |

После любого восстановления — сценарий 1 по HTTPS: `BASE_URL=https://<домен> HOST=<домен> python scripts/smoke_scenario_1.py` (с ноутбука) → «scenario 1 passed».
