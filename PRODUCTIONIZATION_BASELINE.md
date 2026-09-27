# Productionization Baseline Report

## Repository State

- **Branch**: main (8 commits, 2 contributors)
- **Python**: 3.14.3
- **Node**: 24.13.1 / npm 11.18.0
- **Docker**: Not available on this machine

## Directory Structure (Working Tree)

```
Pays/
  .env                          # EXISTS ON DISK - contains live secrets
  .gitignore
  Frontend/paymen_system/       # NOTE: misspelled "paymen"
    .env                        # EXISTS ON DISK - contains live API key
    src/
  payment_system/               # git tracks as payment_System (case mismatch)
    app/
      main.py                   # FastAPI app, 404 lines
      models.py                 # SQLAlchemy ORM, 5 tables, 166 lines
      daraja.py                 # Safaricom API client, 198 lines
      callbacks.py              # STK/B2C webhook handlers, 85 lines
      security.py               # Fernet encryption + API key hashing, 65 lines
      database.py               # Engine/session setup, 29 lines
      init_db.py                # create_all script, 6 lines
      services/
        payment_service.py      # CRUD layer, 82 lines
    requirements.txt            # 33 dependencies, all pinned
  README.md                     # Single line: "# Pays"
```

## Git-Tracked Files (HEAD)

- `.env` and `Frontend/paymen_system/.env` tracked in HEAD
- 18 `.pyc` files tracked under `payment_System/app/__pycache__/`
- `KWY.txt` tracked (contains encryption key value)
- `payment_System/app/services/audit_services.py` tracked (deleted in working tree)
- `payment_System/app/services/merchant_service.py` tracked (deleted in working tree)

## Security Findings

### CRITICAL: Secrets in Git History

1. **HEAD commit `.env`**: Contains `CREDENTIAL_ENCRYPTION_KEY` value and `ADMIN_SECRET` value
2. **HEAD commit `KWY.txt`**: Contains `CREDENTIAL_ENCRYPTION_KEY` value in plaintext
3. **Commit 8b71592 `Frontend/paymen_system/.env`**: Contains `VITE_MERCHANT_API_KEY` (placeholder text, not live)
4. **Working tree `.env`**: Contains `CREDENTIAL_ENCRYPTION_KEY` and `ADMIN_SECRET` (different values from committed)
5. **Working tree `Frontend/paymen_system/.env`**: Contains `sk_live_...` API key

### CRITICAL: Generated Files Tracked

- 18 `.pyc` bytecode files tracked in git
- `.vscode/settings.json` tracked

### Active Credential Classes Requiring Rotation

- `CREDENTIAL_ENCRYPTION_KEY` (Fernet key - if this was ever used to encrypt real Daraja credentials, those are compromised)
- `ADMIN_SECRET` (admin activation key)
- Database password in `DATABASE_URL`
- Any `sk_live_` merchant API keys generated while the old encryption key was active

## Backend Architecture

### Entrypoint
- `uvicorn app.main:app` (from `payment_system/` directory)

### Database
- PostgreSQL via `psycopg2-binary` + SQLAlchemy 2.0
- Schema created via `Base.metadata.create_all()` at module import
- No migrations (no Alembic)

### Authentication
- API key in `X-API-Key` header
- Key prefix (12 chars) for DB lookup, SHA-256 hash for verification
- Constant-time comparison via `secrets.compare_digest`

### Payment Flow
1. Merchant calls `/pay` with phone + amount
2. Backend normalizes phone, calls Daraja STK Push
3. Daraja returns `CheckoutRequestID`
4. Payment record created with status "Pending"
5. Daraja sends callback to `/api/payment/callback/{merchant_id}`
6. Callback updates payment status to "SUCCESS" or "FAILED"

### Models (5 tables)
- `merchants` - multi-tenant, BYO Daraja credentials (encrypted)
- `payments` - STK Push / C2B transactions
- `disbursements` - B2C outgoing payments
- `payment_links` - defined but unused
- `api_request_logs` - API usage tracking

## Frontend Architecture

- React 19 + Vite 8
- Manual page routing via state (`page` variable in App.jsx)
- No React Router
- Tailwind CSS via inline className
- API client in `src/Api/api.js`
- Pages: Dashboard, Payments, QRPayment, Transactions, APIIntegration

## Known Issues

1. No tests
2. No Alembic migrations
3. Blocking `requests` calls in FastAPI async context
4. `print()` statements in `daraja.py`
5. `b2c_disbursement` catches HTTP error but continues to `response.json()`
6. In-memory token cache (not multi-process safe)
7. No rate limiting
8. No health check endpoint
9. No structured logging
10. No Docker configuration
11. No CI/CD
12. No README documentation
