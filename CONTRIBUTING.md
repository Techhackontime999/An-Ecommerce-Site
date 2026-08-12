# Contributing to Shop-Seed

Thank you for wanting to contribute to Shop-Seed! This document explains how the
repository is organised, the workflow we use, and how to get a change reviewed
and merged.

Please also read our [Code of Conduct](./CODE_OF_CONDUCT.md). By participating
you agree to follow it.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [What can I work on?](#what-can-i-work-on)
- [Setting up a development environment](#setting-up-a-development-environment)
- [Development workflow](#development-workflow)
  - [1. Branch from a clean base](#1-branch-from-a-clean-base)
  - [2. Make small, focused commits](#2-make-small-focused-commits)
  - [3. Run the checks](#3-run-the-checks)
  - [4. Open a pull request](#4-open-a-pull-request)
- [Branch model](#branch-model)
- [Commit conventions](#commit-conventions)
- [Testing](#testing)
- [Code style](#code-style)
- [Security](#security)
- [Reporting issues](#reporting-issues)

## Code of Conduct

Be respectful and constructive. Harassment, trolling, and personal attacks are
not tolerated. See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## What can I work on?

- **Bugs** — open an issue first describing the bug, then link the PR to it.
- **Features** — open a discussion/issue before starting large features so the
  approach can be agreed on first.
- **Documentation** — typos, clarifications and new guides are always welcome.
- **Tests** — improving coverage of the existing 407-test suite is valuable.

If you are unsure where to start, look for open issues labelled `good first
issue`.

## Setting up a development environment

Follow the [Local Development](./README.md#local-development) section of the
README. The short version:

```sh
git clone https://github.com/Techhackontime999/An-Ecommerce-Site.git
cd An-Ecommerce-Site

python3 -m venv env
source env/bin/activate          # Windows: env\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # adjust as needed (DJANGO_ENV=local is the default)
python manage.py migrate
python manage.py create_default_groups
python manage.py createsuperuser
python manage.py runserver
```

Optional demo data:

```sh
python manage.py seed_all --preset medium
```

## Development workflow

### 1. Branch from a clean base

Work on a descriptive feature branch, not directly on `main`/`testing`:

```sh
git checkout main
git pull
git checkout -b fix/cart-quantity-bug
```

Prefix your branch with the kind of change:

- `fix/...` — bug fixes
- `feature/...` — new functionality
- `chore/...` — maintenance, dependencies, tooling
- `docs/...` — documentation only

### 2. Make small, focused commits

Each commit should be one logical change and must leave the codebase in a
working state (tests passing). See [Commit conventions](#commit-conventions).

### 3. Run the checks

Before pushing, make sure everything is green:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run   # no missing migrations
python manage.py test                               # full suite (407 tests)
```

New behaviour should come with tests. When you add or change a model, add the
corresponding migration:

```sh
python manage.py makemigrations <app_label>
```

### 4. Open a pull request

- Target the `testing` branch for review (it is the integration branch that is
  merged into `main` after CI passes).
- Keep PRs small and focused — one logical change per PR.
- Describe what you changed, why, and how it was tested.
- Link any related issue (`Fixes #123`).
- Wait for CI (GitHub Actions on Python 3.12 and 3.13) to go green. A PR is
  only mergeable when the full test suite passes.

## Branch model

```
main      — stable, deployable. Merge only from testing after CI is green.
testing   — integration branch. PRs land here first; CI runs on every push.
feature/* — short-lived branches for individual pieces of work.
```

Backup snapshots (e.g. `testing-backup`) exist as rollback points; do not work
on them.

## Commit conventions

Write clear, imperative commit messages that describe **why** the change is made:

```
Fix six pin to existing 1.16.0 so fresh CI installs succeed
Add newsletter double opt-in, seller payouts/ledger, and a DB-backed async job queue
Pin setuptools<82 so razorpay's pkg_resources import works on fresh installs
```

Prefix when useful: `fix:`, `feat:`, `chore:`, `docs:`, `test:`, `refactor:`.
Keep the first line under ~72 characters and add a body paragraph for anything
non-obvious.

## Testing

- Run the full suite with `python manage.py test` (never `pytest` — CI uses the
  Django test runner).
- Run a subset while iterating:

  ```sh
  python manage.py test order
  python manage.py test order.tests.test_services
  python manage.py test order.tests.test_services.OrderViewTests.test_cancel_refunds_captured_payment
  ```

- Tests that touch the Razorpay gateway or courier APIs must not perform real
  network calls — mock the client. Existing tests use `unittest.mock`; follow
  the same pattern.
- Make sure new tests are hermetic: they must not depend on data created by
  other tests or on environment-specific values.

## Code style

- PEP 8, 4-space indentation, no trailing whitespace.
- No `# type: ignore` unless strictly necessary and commented.
- Django apps are self-contained: keep models, services, views, forms, admin,
  urls and templates inside the app directory.
- Business logic belongs in the app's `services.py` (or similar), not in views.
- Sensitive settings come from the environment (see `.env.example`); never
  hard-code secrets.
- Follow the existing patterns in the file you are editing (imports, naming,
  docstrings). Do not reformat unrelated code.

## Security

This project processes payments and stores personal data. If your change
touches:

- payment capture/refund paths,
- authentication or sessions,
- media uploads or rich text,
- admin functionality,

please think about attack surface and add tests for the security-relevant cases.
For vulnerabilities, follow [SECURITY.md](./SECURITY.md) — do **not** open a
public issue for a live security bug.

## Reporting issues

- **Bugs** — include the exact steps to reproduce, expected vs. actual
  behaviour, the Django/Python versions, and any relevant logs.
- **Questions / ideas** — open a discussion issue so maintainers and
  contributors can weigh in before code is written.

## License and contributions

Shop-Seed is commercially licensed (see [LICENSE](./LICENSE)). Because the
platform is sold to end customers, please note:

- Only open pull requests for **your own original work**; do not paste code
  from third-party projects unless it is compatible with a commercial license.
- By submitting a pull request you agree that your contribution becomes part
  of the commercial Shop-Seed codebase and may be licensed, sold, and
  distributed under the Shop-Seed Commercial License with no separate
  attribution requirement.
