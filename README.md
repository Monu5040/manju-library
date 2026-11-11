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

One VM with Docker (E2E Networks or any VPS), PostgreSQL (managed, or on the VM with
`deploy/docker-compose.db.yml`), and S3-compatible storage for backups. Run the commands below
from the `deploy/` folder; `COMPOSE_FILE` in `deploy/.env` tells `docker compose` which files
to use.

1. Point the domain's DNS at the VM; without a domain, `<ip-with-dashes>.sslip.io` works.
   Install Docker and clone this repository, for example to `/srv/manju-library`.
2. `cp deploy/.env.example deploy/.env` and fill it in. Generate `SECRET_KEY` and
   `FIELD_ENCRYPTION_KEYS` as the comments say, and keep a copy of the encryption key in a
   password manager: without it, encrypted data cannot be read.
3. First certificate: `deploy/scripts/init-letsencrypt.sh`. Renewals are automatic.
4. Deploy: `deploy/scripts/deploy.sh`. It builds, migrates (running the safety checks), restarts
   and waits for the health check. To roll back, run `deploy/scripts/deploy.sh <older-commit-sha>`.
   Migrations must stay compatible with the previous release.
5. Create the owner's account: `docker compose exec backend python manage.py createsuperuser`
6. Nightly backup with 30-day retention. Add to the server's crontab:
   `30 2 * * * cd /srv/manju-library/deploy && docker compose --profile backup run --rm backup >> /var/log/manju-backup.log 2>&1`
7. Once a month, prove the backups restore. Run `pg_restore_check.sh` in the same image, with
   `RESTORE_DATABASE_URL` set to a scratch database (never the live one).

Staging is the same steps on a second VM with `ENVIRONMENT=staging`.

**From GitHub:** CI (`.github/workflows/ci.yml`) runs on every push and pull request: lint,
tests on PostgreSQL, the production settings checklist, both Docker images, the Nginx config,
the Compose file and the shell scripts. Deploys are manual (`Actions → Deploy`); the
workflow file lists the secrets each environment needs. Add required reviewers to the
`production` environment.

## What's built

**Phase 0 — foundation:** one-command local setup, CI, Docker images, HTTPS with renewal,
backups, roles, both sign-in flows, audit log, encryption, safety checks, design system.

**Phase 1 — admin core:**

- Branch model from day one (one branch now), with a per-branch "share seats between
  shifts" setting. Shifts can run past midnight.
- Students with roll numbers, encrypted Aadhaar (checked with its checksum; masked; full
  number for the Super Admin only, logged) and one portal login per mobile number.
- Memberships: seat, shift or custom time, dates, fee, discount, dues, renewals, cancel.
  PostgreSQL itself refuses a double-booked seat.
- Payments with gap-free receipt numbers continuing from 1107, void (never delete),
  printable receipts, totals by payment mode.
- Admin screens: overview, students, admission, student page, seat map, renewals due,
  payments, waiting list, settings, staff accounts, import, my account.
- **Import** (Super Admin, `Import` in the menu): upload the existing Admission Sheet
  (.xlsx, .xls or .csv). The app finds the title row, matches the columns, checks every
  row without saving anything, and lists problems in plain words. Import everything, or
  skip rows with errors and download them as an error file to fix. Undo within 7 days.
- **Export** on the Students and Payments lists (Super Admin, or staff given export
  rights): Excel or CSV of exactly what is filtered on screen.

Staff can admit, renew and take payments; only the Super Admin deletes, voids, cancels,
changes settings, imports or sees full Aadhaar numbers. Every change is in the audit log.

**Phase 2 — student portal** (sign in with mobile number and SMS code):

- Home: seat, timing, plan, days left with a renewal reminder, dues, and the library's
  notices. Siblings who share a mobile number switch between their profiles.
- Payment history with printable receipts, contact details the student can update
  (address, other mobile number), and current fees and timings.
- **Notices** in the admin menu: staff post and edit them, with optional start and end
  dates and pinning; only the Super Admin deletes.
- Real login-code SMS through MSG91 (`SMS_BACKEND=core.sms.Msg91SMSBackend`; settings in
  `deploy/.env.example`). If MSG91 fails, the student is asked to try again in a minute and
  the failure is logged.

## Still to do

- **Turn on MSG91**: a DLT-registered sender ID and OTP template, then the MSG91 settings
  in `deploy/.env`. Until then the server runs as staging and login codes go to the server log.
- **Backups** to object storage (deliberately left for later).
- Next phases: online renewal (Razorpay), analytics, ledger and expenses, WhatsApp/SMS
  reminders.
