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
Мерж в `main` → CI (backend, frontend, e2e, gitleaks) → при зелёном — джоба `deploy` заходит на сервер по SSH и запускает `/usr/local/bin/alfa-deploy` ([deploy/alfa-deploy.sh](../deploy/alfa-deploy.sh)): `git fetch` → `reset` на `origin/main` → `docker compose up -d --build --wait` → проверка `/api/health`. Не поднялось — откат на предыдущий коммит (миграции БД не откатываются: ломающие миграции делаем в два шага). Журнал — `/var/log/alfa-deploy.log`.

Ключ CI в `authorized_keys` ограничен: `restrict,command="/usr/local/bin/alfa-deploy"`. С ним нельзя получить шелл, выполнить другую команду или пробросить порты — только выкатить последний `main`.

Настройка (один раз):
```sh
# на сервере
install -m 755 deploy/alfa-deploy.sh /usr/local/bin/alfa-deploy
# ключ CI (пара генерируется у лида, приватная часть — только в GitHub Secrets)
echo 'restrict,command="/usr/local/bin/alfa-deploy" ssh-ed25519 AAAA... github-actions-deploy-alfa' >> ~/.ssh/authorized_keys
```
- GitHub → Settings → Secrets and variables → Actions → New repository secret `DEPLOY_SSH_KEY` — содержимое приватного ключа CI целиком.
- GitHub → Settings → Deploy keys → публичный ключ сервера для чтения репозитория (раздел 2, без write access).
- IP и ключ хоста сервера записаны в `.github/workflows/ci.yml` (джоба `deploy`); при смене сервера — обновить там.
- Скрипт в репозитории поменялся → переустановить его на сервере командой выше (CI запускает установленную копию).

Вручную (то же самое): `ssh root@<ip> alfa-deploy`, или на сервере `alfa-deploy`.

## 7. Демо-данные
После Фазы 2: `docker compose run --rm backend python manage.py seed_demo` (персоны из docs/demo.md) и команда сброса демо-данных перед показом.

## 8. Обслуживание
- Логи: `docker compose logs -f --tail 100 caddy backend`
- Бэкап БД: `docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > ~/backup-$(date +%F-%H%M).sql.gz`
- После хакатона (docs/submission.md): ротировать LLM-ключ, удалить данные кейса с сервера.
