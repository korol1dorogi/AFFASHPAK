# Деплой стенда на VPS

Делает только лид (docs/decisions.md D11). Схема: наружу смотрит только Caddy (80/443, HTTPS автоматически). Он раздаёт собранный фронт, проксирует `/api` и админку на gunicorn, раздаёт статику админки. У `db` и `backend` портов наружу нет: Docker обходит UFW, поэтому публиковать что-то, кроме Caddy, нельзя.

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
- Данные кейса: `sudo mkdir -p /srv/alfa-case-data && sudo chown deploy:deploy /srv/alfa-case-data`, загрузить туда по `scp`. Путь — в `CASE_DATA_DIR`; бэкенд видит его только на чтение.

## 5. Первый запуск
```sh
cd /srv/alfa-cabinet
docker compose up -d --build        # COMPOSE_FILE из .env указывает на docker-compose.prod.yml
docker compose ps                   # все healthy
docker compose run --rm backend python manage.py createsuperuser   # учётка лида в бэк-офисе
```
Проверка: `https://$DOMAIN/` — кабинет, `https://$DOMAIN/api/health` — `{"status":"ok",...}`, `https://$DOMAIN/$DJANGO_ADMIN_URL` — бэк-офис.

## 6. Обновление (вручную, D11)
```sh
cd /srv/alfa-cabinet && git pull && docker compose up -d --build
```
Миграции и collectstatic выполняются при старте бэкенда.

## 7. Демо-данные
После Фазы 2: `docker compose run --rm backend python manage.py seed_demo` (персоны из docs/demo.md) и команда сброса демо-данных перед показом.

## 8. Обслуживание
- Логи: `docker compose logs -f --tail 100 caddy backend`
- Бэкап БД: `docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > ~/backup-$(date +%F-%H%M).sql.gz`
- После хакатона (docs/submission.md): ротировать LLM-ключ, удалить данные кейса с сервера.
