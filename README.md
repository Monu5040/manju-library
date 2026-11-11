# Manju Library

The website that replaces Manju Library's Excel workbook: an admin panel for the owner and
staff, a portal for students, and an analytics page. The full plan is in
[Manju Library Website — Production Plan](https://claude.ai/artifact/2nUM9ErCBLbcLUgQf9QV6J).

**Stack:** React + TypeScript (Vite) · Django 5.2 LTS + Django REST Framework · PostgreSQL ·
Redis + Celery · Nginx · Docker Compose.

## Run it locally

You need [uv](https://docs.astral.sh/uv/), Node.js 22 and Docker Desktop (running).

```sh
make setup   # first time: install dependencies, create backend/.env
make dev     # start PostgreSQL + Redis, migrate, run Django and React. Ctrl+C stops all.
make seed    # in a second terminal, first time: create local logins
```

Open <http://localhost:5173>.

| Who | Where | How to sign in locally |
| --- | --- | --- |
| Student | /login | Mobile `9000000002`; the 6-digit code appears in the `make dev` log |
| Super Admin | /staff/login | `admin@example.com` / `local-admin-password-123`, then connect an authenticator app |
| Back office (Django admin) | /backoffice/ | Same Super Admin login plus the app code |

Ports busy? `make dev BACKEND_PORT=8001 FRONTEND_PORT=5174`. Running PostgreSQL and Redis
yourself instead of in Docker? Set them in `backend/.env` and use `make dev USE_DOCKER=0`.

Run `make` to see every command. The everyday ones:

| Command | What it does |
| --- | --- |
| `make dev` | Run the whole app |
| `make test` | Backend tests (pytest, on PostgreSQL) and frontend tests (Vitest) |
| `make lint` | Ruff, oxlint and the TypeScript check |
| `make check` | Everything CI runs: lint, tests, production build |
| `make worker` | Background jobs (Celery worker and scheduler) |
| `make docker-build` | Build the production images |

## How it fits together

```
browser ─▶ Nginx ─┬─ /api/, /backoffice/, /static/ ─▶ Django (Gunicorn) ─▶ PostgreSQL
                  │                                        └──▶ Redis ─▶ Celery worker + beat
                  └─ everything else ─▶ React app (static files)
```

- `backend/`: Django project. `accounts` (users, roles, login), `audit` (audit log),
  `core` (health check, encryption, SMS, startup safety checks), `config` (settings, URLs).
- `frontend/`: React app. `src/components/ui` is the design system; tokens live in
  `src/index.css`.
- `deploy/`: production Compose file, Nginx image, backup and deploy scripts.

**Sign-in.** Students get a one-time SMS code: 5-minute expiry, 5 attempts, stored only as an
HMAC, and rate-limited per number and per IP. Staff and the owner use a password (Argon2) and
then an authenticator app; nobody reaches admin data without both. Sessions are httpOnly
cookies, and every login endpoint checks a CSRF token. Every sign-in, failure and sign-out is
written to the audit log.

**Sensitive data.** `core.fields.EncryptedTextField` encrypts values such as Aadhaar with
AES-256-GCM, using keys from `FIELD_ENCRYPTION_KEYS` (several keys allow rotation).

**Safety checks.** In staging and production, Django refuses to migrate or start with:
- no encryption key
- `DEBUG` on
- an SMS backend that doesn't send real messages (staging may opt in with `SMS_CONSOLE_ALLOWED=true`)

## Deploying

One VM with Docker (E2E Networks or any VPS), managed PostgreSQL, and S3-compatible storage
for backups.

1. Point the domain's DNS at the VM. Install Docker and clone this repository, for example to
   `/srv/manju-library`.
2. `cp deploy/.env.example deploy/.env` and fill it in. Generate `SECRET_KEY` and
   `FIELD_ENCRYPTION_KEYS` as the comments say, and keep a copy of the encryption key in a
   password manager: without it, encrypted data cannot be read.
3. First certificate: `deploy/scripts/init-letsencrypt.sh`. Renewals are automatic.
4. Deploy: `deploy/scripts/deploy.sh`. It builds, migrates (running the safety checks), restarts
   and waits for the health check. To roll back, run `deploy/scripts/deploy.sh <older-commit-sha>`.
   Migrations must stay compatible with the previous release.
5. Create the owner's account:
   `docker compose -f deploy/docker-compose.prod.yml exec backend python manage.py createsuperuser`
6. Nightly backup with 30-day retention. Add to the server's crontab:
   `30 2 * * * cd /srv/manju-library/deploy && docker compose -f docker-compose.prod.yml --profile backup run --rm backup >> /var/log/manju-backup.log 2>&1`
7. Once a month, prove the backups restore. Run `pg_restore_check.sh` in the same image, with
   `RESTORE_DATABASE_URL` set to a scratch database (never the live one).

Staging is the same steps on a second VM with `ENVIRONMENT=staging`.

**From GitHub:** CI (`.github/workflows/ci.yml`) runs on every push and pull request: lint,
tests on PostgreSQL, the production settings checklist, both Docker images, the Nginx config,
the Compose file and the shell scripts. Deploys are manual (`Actions → Deploy`); the
workflow file lists the secrets each environment needs. Add required reviewers to the
`production` environment.

## Phase 0 status

Done: repository, local one-command setup, CI, Docker images, HTTPS with renewal, backups,
roles, both sign-in flows, audit log, encryption, safety checks, design system and the
portal and admin shells.

Waiting on decisions or accounts:

- **Domain and VMs** for staging and production.
- **SMS provider** (MSG91 or Gupshup) with a DLT-registered sender ID and template. Then add
  its backend in `core/sms.py`; until then only staging can run, with codes in the server log.
- **Sentry** project (optional): set `SENTRY_DSN`.
- **GitHub repository**, then the deploy secrets above.
