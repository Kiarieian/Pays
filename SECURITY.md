# Security Model

## API Key Authentication

Merchants authenticate using API keys sent via the `X-API-Key` header.

- Keys are generated with `sk_live_` prefix + 32 bytes of `secrets.token_urlsafe`
- Only the SHA-256 hash is stored in the database
- The prefix (first 12 characters) is stored in plaintext for fast DB lookup
- Verification uses `secrets.compare_digest` for constant-time comparison
- Keys are shown to the merchant exactly once at creation

## Credential Encryption

Merchant Daraja API credentials (consumer key, secret, passkey) are encrypted at rest using Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).

- The encryption key is stored in `CREDENTIAL_ENCRYPTION_KEY` environment variable
- Never committed to source control
- If compromised, all stored Daraja credentials must be re-entered by merchants

## Tenant Isolation

Every database query is scoped to the authenticated merchant:
- Payments: `WHERE merchant_id = current_merchant.id`
- Disbursements: `WHERE merchant_id = current_merchant.id`
- API logs: `WHERE merchant_id = current_merchant.id`

Cross-merchant access is prevented by the `get_current_merchant` dependency injection.

## Webhook Security

Safaricom callbacks include the merchant ID in the URL path. Callbacks are currently unauthenticated (Safaricom does not provide HMAC signatures for these endpoints). The callback URL is deterministic and includes the merchant ID, making it non-guessable without knowing the exact URL structure.

## Known Limitations

- Callback authentication: No HMAC/signature verification on incoming Safaricom callbacks
- Rate limiting: Not yet implemented
- API key rotation: Not yet implemented (requires merchant re-registration)
- Admin secret: Single shared secret, no per-admin keys
