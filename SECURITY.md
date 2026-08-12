# Security Policy

Shop-Seed handles payments, personal data, and courier credentials. We take
security seriously and ask that you report vulnerabilities responsibly.

## Supported Versions

| Version | Branch | Supported |
|---|---|---|
| latest | `main` | ✅ |
| integration | `testing` | ✅ (CI-gated) |
| older | any other | ❌ |

We support the latest commit on `main`. The `testing` branch is the integration
branch where changes are validated before reaching `main`.

## Reporting a Vulnerability

**Do not open a public issue** for a security vulnerability. Instead, email the
maintainers directly:

- amitkumarkh01012006@gmail.com
- mrtechhackontime999@gmail.com

Please include:

1. A description of the vulnerability and its impact.
2. The affected component(s) and version/commit.
3. Step-by-step reproduction steps (or a minimal PoC).
4. Any suggested mitigation, if you have one.

You can expect an acknowledgement within **48 hours** and a status update
within **5 business days**. We will keep you informed as we work on a fix and
will credit you for the report (unless you prefer to stay anonymous).

## What to report

Anything that could compromise the confidentiality, integrity, or availability
of the platform, including but not limited to:

- Authentication or session issues
- Payment capture/refund or webhook-verification flaws
- Injection (SQL, template, command) or stored/reflected XSS
- CSRF bypasses or insecure access-control checks
- Information disclosure (e.g. protected media such as KYC documents)
- Cryptographic or secrets-handling issues (field encryption, signatures)
- Misconfigurations that expose data or credentials

## Safe harbour

We will not pursue legal action against researchers who:

- Act in good faith and with reasonable care,
- Avoid privacy violations, destruction of data, and interruption of service,
- Report the issue to us first and give us a reasonable time to respond,
- Do not exploit a vulnerability beyond what is necessary to demonstrate it.

## Security-relevant areas

For anyone contributing or auditing the codebase, the highest-risk surfaces are:

- `payments/` — Razorpay callbacks, webhook HMAC verification, capture/refund paths
- `accounts/security.py` — authentication, sessions, rate limiting
- `core/security.py` / `core/middleware.py` — CSP, headers, sanitizers
- `core/encrypted_fields.py` and `FIELD_ENCRYPTION_KEY` handling
- `order/access.py` — order/guest access control and signed tokens
- Upload handling and the `|richtext|` sanitizer (stored XSS)
- Protected media folders (`protected/`, `seller_documents/`)

When changing these areas, add security-focused tests and reference them in
your pull request.
