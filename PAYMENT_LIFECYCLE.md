# Payment Lifecycle

## STK Push Payment Flow

```
Merchant                    Safaricom                   Customer
   |                           |                           |
   |--- POST /pay ------------>|                           |
   |                           |--- STK Push Prompt ------>|
   |<-- 200 {checkout_id} ----|                           |
   |                           |                           |
   |                           |<-- Enter PIN / Cancel ----|
   |                           |                           |
   |--- callback POST -------->|                           |
   |   (merchant_id, result)   |                           |
   |                           |                           |
   | Payment status updated    |                           |
```

## Payment States

```
PENDING ──> SUCCESS    (callback with ResultCode=0)
PENDING ──> FAILED     (callback with ResultCode!=0)
PENDING ──> TIMEOUT    (no callback within timeout window)
```

### Terminal States

Once a payment reaches SUCCESS, FAILED, or TIMEOUT, it cannot transition to any other state. This prevents:
- Accidental overwrites of successful payments
- Status manipulation after callback receipt
- Duplicate state changes from late callbacks

## Disbursement (B2C) Flow

```
Merchant                    Safaricom                   Customer
   |                           |                           |
   |--- POST /disburse ------->|                           |
   |<-- 200 {conversation_id}--|                           |
   |                           |                           |
   |                           |--- B2C Payment --------->|
   |                           |                           |
   |--- result callback ------>|                           |
   |--- timeout callback ----->|  (if queued too long)     |
   |                           |                           |
   | Disbursement status       |                           |
   | updated                   |                           |
```

## Disbursement States

```
PENDING ──> SUCCESS    (result callback with ResultCode=0)
PENDING ──> FAILED     (result callback with ResultCode!=0)
PENDING ──> TIMEOUT    (timeout callback received)
```

## Idempotency

Both payment and disbursement creation support idempotency keys:

```json
{
  "phone": "254712345678",
  "amount": 100,
  "idempotency_key": "unique-order-123"
}
```

If the same `idempotency_key` is sent twice for the same merchant, the second request returns the existing payment/disbursement instead of creating a duplicate.

## Duplicate Callback Safety

Safaricom may send the same callback multiple times. The state machine ensures that:
- A payment already in SUCCESS state ignores duplicate success callbacks
- A payment already in FAILED state ignores duplicate failure callbacks
- The callback handler always returns `ResultCode: 0` to Safaricom regardless of internal state

## Timeout Handling

If no callback is received within the timeout window:
- STK Push: The payment remains in PENDING state until manually resolved or a timeout mechanism is implemented
- B2C Disbursement: Safaricom sends a timeout callback which transitions the disbursement to TIMEOUT state
