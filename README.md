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
4. Deploy: `deploy/scripts/deploy.sh`. It pulls fresh base images (security updates), builds,
   migrates (running the safety checks), restarts and waits for the health check. If the new
   version does not come up healthy it starts the previous one again by itself. Only commits
   on `main` can be deployed; to go back on purpose, run `deploy/scripts/deploy.sh <older-sha>`.
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

## Going live

**Settings → System status** in the app shows a checklist of these steps and ticks them off.
All settings below go in `deploy/.env` on the server; run `deploy/scripts/deploy.sh` after
changing it.

1. **Real SMS for student logins.** Register a sender ID and an OTP template on the DLT
   portal, add the template in MSG91, then set `SMS_BACKEND=core.sms.Msg91SMSBackend`,
   `MSG91_AUTH_KEY` and `MSG91_OTP_TEMPLATE_ID` (and `MSG91_CODE_VARIABLE` if the template's
   variable is not `otp`). Optional reminder templates: `MSG91_TEMPLATE_<KIND>`, see
   `deploy/.env.example`.
2. **Production mode.** Delete `SMS_CONSOLE_ALLOWED`, set `ENVIRONMENT=production`. The
   deploy stops with a clear message if anything production needs is missing.
3. **Backups.** Give the backup its own settings file (only `DATABASE_URL`, `BACKUP_*` and the
   `S3_*`/`AWS_*` keys, not shared with the web app) and an S3 key that can upload but not
   delete, with old backups removed by a lifecycle rule on the bucket. Encrypt dumps before
   they leave the server if the storage provider is not fully trusted. Dumps already leave out
   sessions, login codes and authenticator secrets. Add the nightly cron line from
   [Deploying](#deploying), and once a month prove a restore with `pg_restore_check.sh`.
4. **Error alerts.** Create a free project on sentry.io and set `SENTRY_DSN`: every server
   error then reaches you by email with the details needed to fix it.
5. **Uptime monitor.** On a free service such as UptimeRobot or Better Stack, watch
   `https://<your-domain>/api/health/` every 5 minutes with alerts to your phone. It answers
   `200` only when the app, the database and Redis all work, and these services also warn
   before the HTTPS certificate expires.
6. **Your own domain (optional).** Point its DNS at the server, set `SERVER_NAME`, and run
   `deploy/scripts/init-letsencrypt.sh` once.
7. **Online payments (optional).** See [Online payments](#online-payments-razorpay).

Then open **System status**: every service should say Working and every job On time.

**Load test.** On a development machine, `uv run python manage.py seed_demo --students 400`
makes a made-up library and `uv run python manage.py loadtest --url http://127.0.0.1:8017`
sends realistic traffic to a running server (both refuse to run on staging or production).
With 3 Gunicorn workers, as in production, 30 students and 3 admins at once got answers in
4–80 ms (typical), and 100 students and 5 admins at once — far beyond a library's
busiest hour — 349 requests a second with no errors.

## Online payments (Razorpay)

Students can renew their membership (same seat and timing) and clear dues from their portal
by UPI, card or net banking. They pay on Razorpay's own page, so no card or UPI details touch
this server and no Razorpay script runs on the site. A payment is recorded, with a normal
receipt, only after Razorpay confirms it: by a signed webhook, by the app asking Razorpay when
the student comes back, and by a job every 10 minutes in case a webhook is lost. If something
changed while the student was paying (the seat was given away, the membership was cancelled,
the desk had already renewed, or more was paid than was due), the money is still recorded and
**Payments → Online payments** says what to sort out; the overview's "To do today" shows it
too. A payment that does not match what was asked for (a different amount) is never recorded
on its own; it waits there as "Paid, needs checking". If a student's payment never came back to
the site, the app finds it before letting them pay again.

**Try it in test mode first** (no KYC, no real money):

1. Sign up at razorpay.com. In the dashboard, switch to **Test Mode**, then **Account &
   Settings → API Keys → Generate Test Key**.
2. Make up a long random webhook secret (for example `openssl rand -hex 32`).
3. **Account & Settings → Webhooks → Add New Webhook**: URL
   `https://<your-domain>/api/payments/razorpay/webhook/`, that secret, and the events
   `payment_link.paid`, `payment_link.expired` and `payment_link.cancelled`.
4. On the server, add `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET`
   to `deploy/.env`, plus `RAZORPAY_TEST_MOBILES` with the mobile number of a test student
   you admit for the purpose (your own number). With test keys only those numbers can pay
   online, so real students never get a receipt or a renewal for test money. Then run
   `deploy/scripts/deploy.sh`.
5. In the app: **Settings → Library → Students can pay online**. Sign in as the test student
   and pay with the test UPI ID `success@razorpay` (or `failure@razorpay` to see a failed
   payment). Afterwards, void the test receipt and cancel the test renewal.

**Going live:** finish Razorpay's KYC (a business or individual account with a bank account),
generate the **live** keys in Live Mode, add the same webhook again in Live Mode (webhooks are
set up separately for each mode), and replace the three values in `deploy/.env`. Set your
business name and logo in Razorpay: students see them on the payment page. With
`ENVIRONMENT=production` the deploy refuses test keys.

Good to know: Razorpay keeps its fee (about 2%; UPI is often free) when it pays the money into
your bank, usually two working days later, so receipts show what the student paid, not what
reached the bank. Refunds are made in the Razorpay dashboard; then the owner voids the payment
in the app with the reason. Students' names and mobile numbers go to Razorpay to fill in its
payment page.

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

**Phase 3 — ledger and analytics:**

- **Expenses**: rent, bills, salaries and other money paid out, plus income that is not a
  fee, by category (categories are managed in Settings). Staff record entries and see only
  their own; the Super Admin sees, edits and voids all of them.
- **Cash book**: the end-of-day count of the cash drawer. Each closing covers every day
  since the previous one, shows what should be there and records any difference.
- **Ledger** (Super Admin): money in and out, day by day, replacing the Excel Balance
  Sheet. **Import old Balance Sheet** brings in its daily collections as past income; days
  already covered by imported payments are not counted twice, and re-importing a newer copy
  adds only new days.
- **Analytics** (Super Admin): key numbers against the previous period, income and expenses
  over time, seat occupancy by shift with the free slots to sell, renewals and retention,
  members by shift, plan and gender, and dues by age. Every table exports to Excel or CSV.

**Phase 4 — automation:**

- **Reminders** (menu, with a counter): every hour from 8 AM to 8 PM the app lists who to
  remind: memberships ending in 3 days or today, fees still unpaid (repeating weekly), and
  the first students waiting when a seat in their shift is free. The front desk taps
  **WhatsApp** to open the chat with the message already written (free, from their own
  phone), or marks a call. Reminders close themselves when the student renews or pays.
- **Automatic SMS** for any reminder kind with a DLT-approved MSG91 template
  (`MSG91_TEMPLATE_<KIND>` in `deploy/.env`); the rest stay on the list for WhatsApp.
- **Settings → Reminders and automation**: when reminders are made, the message wording
  (any language), automatic SMS, and an optional nightly rule that marks students as left
  after a chosen number of days without a membership.
- **Waiting list**: shows the seats free in each person's shift for the next 30 days; giving
  someone a seat takes them off the list, and a returning student becomes current again.
- **Nightly**: uploaded import files and the rows read from them (Aadhaar numbers
  included) are deleted once the 7-day undo window has passed; expired sessions are
  cleared. Notices can be copied with WhatsApp formatting for the library's group.

## Still to do

- **Turn on MSG91**: a DLT-registered sender ID and OTP template, then the MSG91 settings
  in `deploy/.env`. Until then the server runs as staging and login codes go to the server log.
- **Backups** to object storage (deliberately left for later).
- **Razorpay keys**: online payments are built but stay off until the Razorpay keys and
  webhook are set up (see [Online payments](#online-payments-razorpay)).
- The public enquiry form (with lead analytics), when wanted.
