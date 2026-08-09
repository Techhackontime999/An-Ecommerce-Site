## License

This project is licensed under a custom license - see the [LICENSE](./LICENSE) file for details.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
![Django 5.2](https://img.shields.io/badge/Django-5.2-green.svg)
[![Build](https://github.com/Techhackontime999/An-Ecommerce-Site/actions/workflows/django.yml/badge.svg)](https://github.com/Techhackontime999/An-Ecommerce-Site/actions/workflows/django.yml)


# Django E-commerce
Django-ecommerce is an open-source ecommerce platform built on the Django Web Framework.
## Features Included
- Custom Admin dashboard
- Search Functionality
- Shopping Cart
- Order Management
- Coupon system
- Payments Using Razorpay (cards/UPI/netbanking + COD)
- Responsive, mobile-friendly design
- Much more...

## Installation

**1.clone Repository & Install Packages**
```sh
git clone https://github.com/Techhackontime999/An-Ecommerce-Site.git
pip install -r requirements.txt
```
**2.Setup Virtualenv**
```sh
virtualenv env
source env/bin/activate
```
**3.Migrate & Start Server**
```sh
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

## Where to find Me
Like Me on [Facebook]()
Or visit My [Website]

## Production operations

### Required environment variables
- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `SECRET_KEY` — Django secret, unique per deployment.
- `FIELD_ENCRYPTION_KEY` — base64 key used to encrypt courier API credentials
  (`logistics` `api_key`/`api_secret`) via Fernet. **The site will not start in
  production without it.** Generate one with:

  ```sh
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

  Set it once and keep it stable — rotating it invalidates stored credentials.
  The dev default is only for `config.settings.local`.
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` / `RAZORPAY_WEBHOOK_SECRET`
- `REDIS_URL` (optional) — when set, the cache uses Redis; otherwise a
  `DatabaseCache` table is used. `setup.sh` runs `createcachetable`, so the
  database-cache table is always present on deploy.
- `AWS_STORAGE_BUCKET_NAME` (+ `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` /
  `AWS_S3_REGION_NAME`) — **recommended for production**. Media (product/blog/
  review images, courier labels) is stored on the server's ephemeral disk
  otherwise and would be lost on every redeploy.

### Scheduled jobs (Render cron / Celery beat)
- **Tracking sync** — poll courier APIs for in-flight shipments and advance the
  timeline:

  ```sh
  python manage.py sync_tracking_status --limit 100 --min-age-hours 1
  ```

  Safe to run every 15–30 minutes; it only touches shipments with a courier AWB
  that aren't terminal and were last tracked at least `--min-age-hours` ago.
- **Exchange rates** — refresh the cached live currency rates:

  ```sh
  python manage.py update_currency_rates
  ```

  Runs on the same schedule as the rate cache TTL (default 12 h).

