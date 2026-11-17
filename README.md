# Wimi / TiBoutik Backend API

Production-grade, secure, and maintainable RESTful API backend built with **Django 5.1** and **Django REST Framework 3.15**, purpose-built for the **TiBoutik** hyperlocal marketplace application.

---

## Table of Contents
1. [Architecture & Features](#architecture--features)
2. [Tech Stack](#tech-stack)
3. [Project Directory Layout](#project-directory-layout)
4. [API Endpoints & Contracts](#api-endpoints--contracts)
5. [Local Development Setup](#local-development-setup)
6. [Running Automated Tests](#running-automated-tests)
7. [API Documentation (OpenAPI 3.0)](#api-documentation-openapi-30)
8. [Production Deployment Checklist](#production-deployment-checklist)

---

## Architecture & Features

- **Domain-Driven Design**: Organized into focused Django apps (`users`, `authentication`, `core`, `notifications`).
- **Custom User Model**: Built on `AbstractBaseUser` with UUID primary keys, normalized email and phone numbers, and explicit verification tracking (`is_verified`, `is_active`, `terms_accepted`).
- **End-to-End Registration & Verification Lifecycle**:
  - Full account validation matching frontend rules (min 3 chars name, valid email, min 8 digits phone, min 8 chars password, terms acceptance).
  - Cryptographically secure 4-digit OTP issued to email with 10-minute expiry window.
  - Brute-force protection: strict 5-attempt limit per OTP code; code is permanently burned on the 5th failed attempt.
  - 60-second resend cooldown enforced on the server to match the client countdown timer (`58s`).
  - Automatic activation & JWT credential issuance upon successful OTP verification.
- **Dual-Mode Sign In**: Seamlessly authenticates via either **Email** or **Phone Number** with password.
- **Password Recovery & Reset**:
  - Verification code sent to email or SMS.
  - Constant-time OTP comparison (`hmac.compare_digest`).
  - Single-use, time-limited cryptographic reset token issued upon OTP verification.
  - Revocation of active refresh tokens upon password reset.
- **Security & Privacy**:
  - Anti-enumeration defense for signups and password recovery.
  - Token blacklisting on logout and password change (`rest_framework_simplejwt.token_blacklist`).
  - Tiered rate-limiting / throttling (Burst, Sustained, Signup, OTP Verify, OTP Resend, Login, Password Reset).
  - Consistent JSON error response structure.
  - Zero plaintext secrets or OTP codes logged.
- **Extensible Notifications**:
  - Clean separation between business logic and delivery channels.
  - Console backend for local development, easily swappable for SMTP, SendGrid, Amazon SES, or Twilio via environment variables.

---

## Tech Stack

| Component | Technology | Version |
| :--- | :--- | :--- |
| **Language** | Python | 3.12+ |
| **Framework** | Django | 5.1.x |
| **API Toolkit** | Django REST Framework | 3.15.x |
| **Authentication** | djangorestframework-simplejwt | 5.3.x |
| **API Schema** | drf-spectacular (OpenAPI 3.0) | 0.28.x |
| **Database** | PostgreSQL (local SQLite fallback) | 16+ |
| **Test Suite** | pytest + pytest-django + factory-boy | Latest |
| **WSGI Server** | Gunicorn | 23.0+ |

---

## Project Directory Layout

```
backend/
├── .env.example              # Template environment configuration
├── .env                      # Local environment settings
├── .gitignore                # Git exclusions for Python & Django
├── pyproject.toml            # Modern Python project configuration
├── requirements.txt          # Pinned project dependencies
├── pytest.ini                # Pytest configuration file
├── manage.py                 # Django command-line runner
├── config/
│   ├── asgi.py               # ASGI gateway
│   ├── wsgi.py               # WSGI production gateway
│   ├── urls.py               # Root URL routing & API docs
│   └── settings/
│       ├── base.py           # Shared settings & security policies
│       ├── local.py          # Local development overrides
│       ├── test.py           # In-memory test environment settings
│       └── production.py     # Hardened HTTPS & header settings
├── apps/
│   ├── core/                 # Exceptions, throttling, renderers, utils
│   ├── users/                # Custom User model, manager, serializers
│   ├── authentication/       # OTP, AuthService, signup/login/reset views
│   └── notifications/        # Email & SMS notification adapters
└── tests/                    # Comprehensive unit and integration test suite
```

---

## API Endpoints & Contracts

All endpoints are versioned under `/api/v1/` (with a legacy alias for `/api/auth/login`).

### Authentication & Account
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/signup/` | Initial registration (creates inactive account & dispatches 4-digit OTP) | No |
| `POST` | `/api/v1/auth/signup/verify/` | Verify 4-digit OTP, activate account, and return JWT tokens | No |
| `POST` | `/api/v1/auth/signup/resend-otp/` | Resend verification OTP (enforces 60s cooldown) | No |
| `POST` | `/api/v1/auth/login/` | Sign in with email or phone + password | No |
| `POST` | `/api/v1/auth/logout/` | Revoke/blacklist refresh token | Yes (Bearer) |
| `POST` | `/api/v1/auth/token/refresh/` | Renew short-lived access token | No |
| `POST` | `/api/v1/auth/forgot-password/request/` | Request 4-digit reset OTP for email or phone | No |
| `POST` | `/api/v1/auth/forgot-password/verify/` | Verify recovery OTP & receive one-time `reset_token` | No |
| `POST` | `/api/v1/auth/forgot-password/reset/` | Set new password with one-time `reset_token` | No |
| `POST` | `/api/v1/auth/change-password/` | Change password with current password verification | Yes (Bearer) |
| `GET` | `/api/v1/auth/me/` | Retrieve current user profile | Yes (Bearer) |
| `PATCH`| `/api/v1/auth/me/` | Update profile (`full_name`, `phone`, `avatar`) | Yes (Bearer) |

### System & Health
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health/` | Service health & database readiness probe |
| `GET` | `/api/v1/schema/` | OpenAPI 3.0 JSON/YAML specification |
| `GET` | `/api/v1/docs/` | Interactive Swagger UI documentation |
| `GET` | `/api/v1/redoc/` | Interactive ReDoc API documentation |

---

## Local Development Setup

### 1. Prerequisites
- Python 3.12+
- PostgreSQL (or use default local SQLite)
- `uv` (recommended) or standard `python3 -m venv`

### 2. Installation
```bash
cd backend

# Create virtual environment
uv venv .venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Ensure `DATABASE_URL` points to your PostgreSQL instance:
```bash
DATABASE_URL=postgres://localhost:5432/wimi_db
```

### 4. Database Migrations
```bash
python manage.py migrate
```

### 5. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 6. Start the Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```
API will be running at `http://localhost:8000/api/v1/`.

## Makefile Commands

A complete `Makefile` is provided in the repository root for streamlined local development and CI/CD operations:

```bash
make help               # Display interactive command menu
make install            # Install Python dependencies
make run                # Start Django dev server on port 8000
make migrate            # Apply database migrations
make makemigrations     # Generate new database migrations
make test               # Run pytest test suite (43 passed)
make test-cov           # Run pytest with coverage report
make check              # Run Django system checks
make schema             # Generate OpenAPI 3.0 schema.yml
make validate-schema    # Validate OpenAPI schema
make validate-postman   # Validate postman.json syntax
make superuser          # Create Django administrator
make shell              # Open interactive Django shell
make clean              # Clean pycache and test artifacts
```

---

## Postman API Collection

A pre-configured Postman v2.1.0 collection is located at [`postman.json`](./postman.json).

### Features:
- **Environment Variables**: Uses `{{baseUrl}}` (defaults to `http://localhost:8000/api/v1`).
- **Automated Token Chaining**: Test scripts automatically extract and update `{{accessToken}}`, `{{refreshToken}}`, and `{{resetToken}}` collection variables upon successful login, signup OTP verification, and merchant onboarding.
- **Grouped by Domain**:
  1. `01. System & Health`: Health check, OpenAPI schema, Swagger UI, ReDoc.
  2. `02. Customer Authentication Flow`: Signup, Verify OTP, Resend OTP.
  3. `03. Merchant Registration Flow`: Register merchant and store.
  4. `04. Session & Token Management`: Email login, Phone login, Token refresh, Logout/blacklist.
  5. `05. Password Recovery Flow`: Request OTP, Verify OTP, Reset Password.
  6. `06. User Profile & Account`: Me profile, Update profile, Change password.

---

## Running Automated Tests

Run the full automated test suite (43 tests across customer signup, OTP, merchant onboarding, recovery, and security):

```bash
# Run using make
make test

# Or using pytest directly
pytest

# Run with test coverage report
make test-cov
```

Current test pass rate is **100%** (43/43 tests passing).

---

## API Documentation (OpenAPI 3.0)

When the server is running, visit:
- **Swagger UI**: [http://localhost:8000/api/v1/docs/](http://localhost:8000/api/v1/docs/)
- **ReDoc**: [http://localhost:8000/api/v1/redoc/](http://localhost:8000/api/v1/redoc/)
- **OpenAPI Schema**: [http://localhost:8000/api/v1/schema/](http://localhost:8000/api/v1/schema/)

---

## Production Deployment Checklist

1. **Environment Variables**:
   - Set `DJANGO_SETTINGS_MODULE=config.settings.production`.
   - Set a strong, cryptographically generated `DJANGO_SECRET_KEY` (50+ random characters).
   - Set `DJANGO_DEBUG=False`.
   - Set explicit `DJANGO_ALLOWED_HOSTS` (e.g. `api.tiboutik.com`).
   - Set explicit `CORS_ALLOWED_ORIGINS` (e.g. `https://tiboutik.com`).
2. **Database**:
   - Point `DATABASE_URL` to managed PostgreSQL (e.g. AWS RDS, DigitalOcean, Supabase).
   - Ensure SSL mode is enabled (`sslmode=require`).
3. **Static and Media Files**:
   - Run `python manage.py collectstatic --noinput`.
   - For user avatars, configure S3 or Cloudflare R2 storage backend via `django-storages`.
4. **Notifications Provider**:
   - Configure live email via SendGrid, Amazon SES, or Postmark (`django-anymail`).
   - Configure live SMS via Twilio in `apps/notifications/sms.py`.
5. **Security Validation**:
   - Run deployment check:
     ```bash
     python manage.py check --deploy --settings=config.settings.production
     ```
   - Ensure HTTPS reverse proxy (Nginx / Caddy / Cloudflare) is enforcing TLS 1.3 with HSTS headers.
6. **Process Management**:
   - Run using Gunicorn with Uvicorn/gevent workers:
     ```bash
     gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 60
     ```
