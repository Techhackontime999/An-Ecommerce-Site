# Shop-Seed — Django E-Commerce Platform

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/Django-5.2-green.svg)](https://www.djangoproject.com/)
[![Build](https://github.com/Techhackontime999/An-Ecommerce-Site/actions/workflows/django.yml/badge.svg)](https://github.com/Techhackontime999/An-Ecommerce-Site/actions/workflows/django.yml)

A full-featured, production-ready e-commerce platform built on **Django 5.2**.
Shop-Seed is a complete marketplace: a multi-currency, multi-language storefront
with a seller marketplace, Razorpay payments (cards / UPI / netbanking) plus
cash-on-delivery, logistics with shipment tracking, coupons and deals, a blog,
moderated reviews, newsletter double opt-in, and a durable background job queue
for emails, fulfilment and refunds.

It ships with a one-click **Render blueprint**, a **Heroku-style Procfile**, a
full test suite (407 tests) and a GitHub Actions CI pipeline that runs on
Python 3.12 and 3.13.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Development](#local-development)
  - [Prerequisites](#prerequisites)
  - [Linux / macOS](#linux--macos)
  - [Windows](#windows)
  - [Environment Variables](#environment-variables)
  - [Demo Data](#demo-data)
- [Running Tests](#running-tests)
- [Deployment](#deployment)
  - [Render (one-click)](#render-one-click)
  - [Heroku / generic platforms](#heroku--generic-platforms)
  - [Production environment variables](#production-environment-variables)
- [Production Operations](#production-operations)
  - [Async worker (DB-backed job queue)](#async-worker-db-backed-job-queue)
  - [Scheduled jobs (cron)](#scheduled-jobs-cron)
  - [Refund reconciliation](#refund-reconciliation)
  - [Media storage (S3)](#media-storage-s3)
  - [Monitoring (Sentry)](#monitoring-sentry)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## Features

**Storefront & catalogue**
- Product catalogue with categories, multi-image galleries and rich-text (CKEditor) descriptions
- Product **variants** — separate SKU, price and per-variant stock
- Full-text search, daily deals, product sitemap and `robots.txt`
- Responsive, mobile-first UI with light/dark themes, font/contrast preferences and accent colours

**Buying experience**
- Shopping cart (session-based, works for guests too) and wishlist
- Coupon codes with usage/over-refund protection and per-user targeting
- Guest checkout with session access + signed, expiring email tokens (guests never see a login wall)
- Multiple shipping methods with estimated delivery windows

**Payments (Razorpay + COD)**
- In-page checkout (`checkout.js`) with hosted **Payment Link** fallback
- HMAC-verified browser callbacks and **webhooks** (double-delivery safe and idempotent)
- Cash on Delivery with recorded cash collection on delivery
- **Auto-refunds**: on customer cancellation, insufficient stock, or capture-after-cancel — with a durable retry + reconciliation sweep so funds can never be stranded

**Orders & fulfilment**
- Order status workflow (pending → processing → shipped → delivered / cancelled) with a full audit log
- Tax-inclusive totals (GST), PDF **tax invoices** (ReportLab)
- Cancellation restores stock and refunds captured payments atomically
- Returns/refunds admin with over-refund protection

**Marketplace & sellers**
- Seller registration and admin **verification** flow
- Seller storefronts and listings, configurable marketplace commission
- **Payouts** backed by a ledger (`SellerLedgerEntry`) with a reconciliation command

**Logistics (LMS)**
- Courier registry with pluggable providers (mock, mockexpress, delhivery)
- Shipment creation, AWB labels, **tracking timelines** synced from courier APIs
- NDR (non-delivery report) and returns queues
- Courier API credentials encrypted with Fernet

**Content & community**
- Blog engine: posts, tags, comments, likes, bookmarks, follows, badges/XP and moderation reports
- News ticker, FAQ, About, Services, legal pages, and a customer-facing documentation section
- Moderated product reviews with verified-purchase weighting and a report queue

**Marketing**
- Newsletter with **double opt-in** confirmation
- Coupons, flash deals, and blog post→product linking

**Users & personalization**
- Accounts, customer/seller profiles, password management
- Per-user preferences: theme, language, currency, font size/accent
- In-app **notifications** plus transactional email digests

**Platform & operations**
- Custom admin dashboard with analytics/marketing pages and role-based groups (`customers`, `sellers`, `admins`)
- **DB-backed async job queue** — durable, leased, retried background jobs
- `/healthz` readiness probe, Sentry error tracking, structured console logging

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 · Python 3.12 / 3.13 (`runtime.txt`: 3.13.3) |
| Database | SQLite (dev) · PostgreSQL via `dj-database-url` (prod) |
| Cache / Sessions | LocMem or DatabaseCache (dev) · **Redis** (prod, with DB-session fallback) |
| Payments | Razorpay (order creation, payment links, refunds, webhooks) |
| Media | Local filesystem or **Amazon S3** (`django-storages`) |
| Static files | WhiteNoise (`CompressedManifestStaticFilesStorage`) |
| Async jobs | `jobs` app — DB-backed queue drained by `run_worker` |
| PDF / documents | ReportLab, WeasyPrint, python-docx |
| Emails | SMTP / SES, console fallback in dev |
| Monitoring | Sentry SDK (no-op unless `SENTRY_DSN` is set) |
| Frontend | Django templates · Bootstrap 4 (crispy-forms) · custom CSS/JS |
| i18n | Django internationalisation with locale catalogs (`locale/`) |

---

## Project Structure

```
An-Ecommerce-Site/
├── config/                  # Project settings & URL routing
│   └── settings/
│       ├── __init__.py      # Picks local/production from DJANGO_ENV
│       ├── local.py         # Dev settings (SQLite, console email, DEBUG=True)
│       └── production.py    # Prod settings (Postgres, HTTPS, security headers)
├── core/                    # Healthz, admin URL overrides, security middleware/CSP
├── shop/                    # Product catalogue, categories, variants, search, sitemap
├── cart/                    # Session-based shopping cart
├── wishlist/                # Wishlist
├── order/                   # Orders, status workflow, stock, invoices, cancellations
├── payments/                # Razorpay orders/payment-links/webhooks, refunds, COD
├── coupons/                 # Coupon codes
├── deals/                   # Flash deals on products
├── accounts/                # Users, customer/seller profiles, verification
├── seller/                  # Seller marketplace, listings, commission, payouts/ledger
├── logistics/               # Courier integrations, shipments, tracking, NDR/returns
├── reviews/                 # Moderated product reviews
├── blogs/                   # Blog engine (posts, comments, badges, moderation)
├── newsletter/              # Double opt-in newsletter
├── notifications/           # In-app notifications + transactional emails
├── preferences/             # User theme/language/currency preferences, FX rates
├── jobs/                    # DB-backed async job queue (worker + reconciliation)
├── shipping/                # Shipping methods/addresses/shipments (legacy layer)
├── services/ · about/ · contact/ · faq/ · documentation/ · news/ · legal/
│                           # Content/marketing/static pages
├── locale/                  # Gettext translation catalogs
├── static/                  # Static assets (collected into staticfiles/ in prod)
├── build.sh                 # Render build phase (deps + collectstatic)
├── setup.sh                 # Render pre-deploy: migrate, cache table, superuser
├── render.yaml              # Render Blueprint (web + worker + cron + Postgres)
├── Procfile                 # Heroku-style process definitions
├── .env.example             # Documented environment variable template
└── .github/workflows/django.yml  # CI: checks, migrations check, 407 tests
```

---

## Local Development

### Prerequisites

- Python **3.12** or **3.13**
- `pip` and `virtualenv`/`venv`
- (Optional) PostgreSQL if you want to develop against prod-like DB

### Linux / macOS

```sh
git clone https://github.com/Techhackontime999/An-Ecommerce-Site.git
cd An-Ecommerce-Site

python3 -m venv env
source env/bin/activate

pip install -r requirements.txt

cp .env.example .env          # review & adjust values
python manage.py migrate
python manage.py create_default_groups   # customers / sellers / admins
python manage.py createsuperuser
python manage.py runserver
```

Open http://localhost:8000 — the admin is at http://localhost:8000/admin/.

### Windows

```bat
git clone https://github.com/Techhackontime999/An-Ecommerce-Site.git
cd An-Ecommerce-Site

python -m venv siteenv
siteenv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
python manage.py migrate
python manage.py create_default_groups
python manage.py createsuperuser
python manage.py runserver
```

There is also an interactive installer, `windows_installation.bat`, which performs
the venv/deps/migrations/superuser steps for you.

> **Windows + WSL:** the repository's `env/` directory is a Linux (WSL) virtual
> environment and will not run on a native Windows Python. Create a fresh venv
> as shown above, or activate it from inside WSL (`source env/bin/activate`,
> `start_wsl.sh`).

### Environment Variables

All configuration is read from the environment, with `.env` auto-loaded in
`config/settings/local.py` / `production.py`. Copy `.env.example` to `.env`
and edit it. The most important variables:

| Variable | Purpose | Default (dev) |
|---|---|---|
| `DJANGO_ENV` | `local` or `production` — selects settings module | `local` |
| `SECRET_KEY` | Django secret key | insecure dev default |
| `FIELD_ENCRYPTION_KEY` | Fernet key for encrypted courier credentials (**required in prod**) | dev default |
| `DATABASE_URL` | PostgreSQL URL (prod); leave empty for SQLite | empty |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay API keys | test placeholders |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook signing secret (**required in prod**) | empty |
| `ADMIN_URL` | Obfuscated admin mount path (prod) | `admin/` |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket for persistent media (recommended prod) | empty |
| `SENTRY_DSN` | Error tracking DSN (optional) | empty |
| `EMAIL_HOST*` | SMTP settings; dev falls back to console email | — |

See [`.env.example`](./.env.example) for the complete, commented reference.

### Demo Data

Populate the store with realistic demo data (products, variants, categories,
deals, coupons, orders, reviews, blog posts, news, subscribers):

```sh
python manage.py seed_all --preset medium
# presets: tiny | small | medium | large | full
# individual flags: --users --products --orders --reviews --posts --news ...
```

Seed demo users:
- `admin` / `admin123` (superuser + verified seller)
- `priya.sharma` / `test123` and other customers
- `fashion_hub` / `test123` and other sellers

---

## Running Tests

```sh
python manage.py test                 # full suite (407 tests)
python manage.py test order          # one app
python manage.py test order.tests.test_services.OrderViewTests.test_cancel_refunds_captured_payment   # one test
```

The same checks run in CI (`.github/workflows/django.yml`) on Python 3.12 and
3.13: `manage.py check`, `makemigrations --check --dry-run`, then the full test
suite.

---

## Deployment

### Render (one-click)

The repository includes a [Render Blueprint](./render.yaml) that provisions
everything needed:

- **PostgreSQL** database
- **Web service** (gunicorn, 2 workers) — health check on `/healthz`
- **Background worker** draining the async job queue (`run_worker`)
- **Cron jobs**: refund reconciliation (every 10 min), job re-arming (every 5 min),
  tracking sync (every 30 min), exchange-rate refresh (every 12 h)

To deploy:

1. Push this repository to GitHub.
2. Go to **https://dashboard.render.com/blueprints** → **New Blueprint** → connect the repo.
3. Render auto-detects `render.yaml`. Fill in the `sync: false` values when prompted:
   `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
   `RAZORPAY_WEBHOOK_SECRET`, and the `DJANGO_SUPERUSER_*` variables.
4. Migrations, the cache table and the superuser are created automatically in the
   pre-deploy phase (`setup.sh`).

> **Plans:** the free tier covers **one web service + one PostgreSQL** database.
> The background worker and cron jobs require a paid plan (Starter and above).
> On a purely free deployment, disable the `worker` and `cron` services — the
> web app still works, but transactional emails, fulfilment and refund retries
> will not drain until a worker runs.

### Heroku / generic platforms

A `Procfile` is provided:

```
release: bash setup.sh
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers=2 --access-logfile=-
worker: python manage.py run_worker --poll 5 --limit 25
```

Set the same environment variables as for Render (minus the Render-specific ones)
and add the cron commands via your platform's scheduler.

### Production environment variables

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_ENV` | ✅ | `production` |
| `SECRET_KEY` | ✅ | unique per deployment |
| `FIELD_ENCRYPTION_KEY` | ✅ | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | ✅ | e.g. Render/Supabase PostgreSQL |
| `SITE_URL` | ✅ | your canonical domain, e.g. `https://www.yourstore.com` — used in emails, invoices, payment links, tracking, SEO previews |
| `ALLOWED_HOSTS` | recommended | comma-separated hosts; defaults to `RENDER_EXTERNAL_URL` |
| `CSRF_TRUSTED_ORIGINS` | recommended | comma-separated origins; same as hosts for HTTPS |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | ✅ | Razorpay live keys |
| `RAZORPAY_WEBHOOK_SECRET` | ✅ | set in the Razorpay dashboard, must match |
| `DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD` | optional | auto-creates/updates the superuser on first deploy |
| `AWS_STORAGE_BUCKET_NAME` (+ access key/secret/region) | recommended | persistent media; without it uploads are lost on redeploy |
| `ADMIN_URL` | recommended | random segment, e.g. `x7k2-admin/` |
| `SENTRY_DSN` | optional | error tracking |
| `REDIS_URL` | optional | Redis cache + sessions; otherwise DatabaseCache |

**Branding.** Your store name, tagline, logo letter, support email, copyright
holder and contact email are all editable at runtime — no code changes needed —
under **Platform Studio → Brand & Identity** in the admin. `DEFAULT_FROM_EMAIL`
(preset `Shop-Seed <no-reply@shop-seed.com>`) is overridable via env for a
custom sender. Every Shop-Seed default (name, logo, emails, demo data) can be
replaced to present the platform as your own storefront.

---

## Production Operations

### Async worker (DB-backed job queue)

Transactional emails, fulfilment runs and gateway refunds are enqueued as durable
`jobs.Job` rows instead of blocking the checkout/webhook request path. A worker
drains them with crash-safe leases, exponential backoff and attempt caps:

```sh
python manage.py run_worker --poll 5 --limit 25      # long-lived worker
python manage.py run_worker --once --limit 200       # cron-friendly batch
```

Handlers are idempotent (at-least-once delivery). Jobs that exhaust
`JOB_MAX_ATTEMPTS` are marked `dead` and are reviewable in the admin. A
`reconcile_jobs` run re-arms crashed/stuck jobs even if no worker was alive.

### Scheduled jobs (cron)

- **Tracking sync** — polls courier APIs for in-flight shipments:

  ```sh
  python manage.py sync_tracking_status --limit 100 --min-age-hours 1
  ```

- **Exchange rates** — refresh the cached live FX rates (default every 12 h):

  ```sh
  python manage.py update_currency_rates
  ```

### Refund reconciliation

Auto-refunds (cancellation, insufficient stock, capture-after-cancel) are tried
inline and, on any gateway failure, enqueued as a durable `refund_payment` job.
`reconcile_refunds` sweeps every payment where the gateway took money but it
hasn't been returned yet:

```sh
python manage.py reconcile_refunds --dry-run   # preview first
```

### Media storage (S3)

Render's disk is ephemeral — uploads are lost on every redeploy. Set
`AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and
`AWS_S3_REGION_NAME` to serve media from S3. Protected folders
(`protected/`, `seller_documents/`) are never served from the public media URL —
they require the authenticated `accounts:seller_document` view (enforce the same
rule in your S3 bucket policy).

### Monitoring (Sentry)

Set `SENTRY_DSN` to enable error tracking. Optional: `SENTRY_ENVIRONMENT`,
`SENTRY_TRACES_SAMPLE_RATE`, and `GIT_SHA`/`RENDER_GIT_COMMIT` for release tags.

---

## Security

- HTTPS-only production settings (HSTS preload, secure cookies) behind a proxy
- Content-Security-Policy and Permissions-Policy headers via a custom middleware
- Stored-XSS protection: rich text is sanitized on save
- Field-level encryption (Fernet) for courier API credentials
- Obfuscated admin path (`ADMIN_URL`), rate-limited auth endpoints
- Upload validation (MIME/size limits), oversized-body rejection
- Guest order access via signed, expiring tokens; protected KYC media is never public
- Payment webhooks/callbacks verified by HMAC; captures are idempotent and serialized

See [SECURITY.md](./SECURITY.md) for how to report a vulnerability.

---

## Contributing

Contributions are welcome — bug fixes, features and documentation. Please read
[CONTRIBUTING.md](./CONTRIBUTING.md) first (branch model, commit conventions,
how to run the checks and open a pull request) and follow our
[Code of Conduct](./CODE_OF_CONDUCT.md).

---

## License

Shop-Seed is released under the **Shop-Seed Commercial License** — see the
[LICENSE](./LICENSE) file for the full terms.

In short: a licensed copy may be used, modified, and deployed to operate your
own e-commerce business (any number of your own storefronts). **Redistributing,
reselling, or offering the software itself to third parties — as source code or
as a hosted/SaaS platform — requires a separate written agreement.**

Interested in commercial licensing, white-labeling, or reseller terms? Contact
amitkumarkh01012006@gmail.com.
