"""
Daraja API client.

IMPORTANT ARCHITECTURE NOTE:
Every function here takes a `merchant` object and uses THAT merchant's own
Daraja credentials (see models.Merchant.get_daraja_credentials /
get_b2c_credentials). We never use a single global shortcode for all
merchants — that would mean customer payments land in OUR account, making
us a custodian of merchant funds. Instead, money always moves directly
between the merchant's own M-Pesa account and their customer.
"""
import base64
import time
from datetime import datetime

import requests

from app.models import Merchant

# In-memory token cache: {merchant_id: (token, expires_at_epoch)}
# Daraja tokens are valid ~3600s. Caching avoids hitting the auth
# endpoint on every single request (faster + avoids rate limits).
# NOTE: for multi-process deployments, replace this with Redis.
_token_cache: dict[int, tuple[str, float]] = {}

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}


def _base_url(environment: str) -> str:
    return BASE_URLS.get(environment, BASE_URLS["sandbox"])


def get_access_token(merchant: Merchant) -> str:
    cached = _token_cache.get(merchant.id)
    if cached and cached[1] > time.time():
        return cached[0]

    creds = merchant.get_daraja_credentials()
    url = f"{_base_url(creds['environment'])}/oauth/v1/generate?grant_type=client_credentials"

    auth = base64.b64encode(
        f"{creds['consumer_key']}:{creds['consumer_secret']}".encode()
    ).decode()

    response = requests.get(url, headers={"Authorization": f"Basic {auth}"}, timeout=15)
    response.raise_for_status()
    data = response.json()

    token = data["access_token"]
    # Refresh a little early (55 min) to avoid edge-of-expiry failures
    _token_cache[merchant.id] = (token, time.time() + 55 * 60)
    return token


def normalize_phone(phone: str) -> str:
    """Normalize to Safaricom's expected 2547XXXXXXXX / 2541XXXXXXXX format."""
    phone = phone.strip().replace(" ", "").replace("+", "")
    if phone.startswith("0") and len(phone) == 10:
        phone = "254" + phone[1:]
    elif phone.startswith("7") or phone.startswith("1"):
        if len(phone) == 9:
            phone = "254" + phone
    if not (phone.startswith("254") and len(phone) == 12 and phone.isdigit()):
        raise ValueError(f"Invalid phone number format: {phone}")
    return phone


def stk_push(merchant: Merchant, phone: str, amount: int, account_reference: str = None):
    creds = merchant.get_daraja_credentials()
    token = get_access_token(merchant)
    phone = normalize_phone(phone)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{creds['shortcode']}{creds['passkey']}{timestamp}".encode()
    ).decode()

    url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    payload = {
        "BusinessShortCode": creds["shortcode"],
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": creds["shortcode"],
        "PhoneNumber": phone,
        "CallBackURL": f"{creds['callback_base_url']}/api/payment/callback/{merchant.id}",
        "AccountReference": account_reference or merchant.business_name[:12],
        "TransactionDesc": "Payment",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)

    print("=" * 60)
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Body:")
    print(response.text)
    print("=" * 60)

    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        raise Exception(f"Server returned non-JSON response:\n{response.text}")


def generate_qr(merchant, amount, account_ref, trx_code="BG"):
    creds = merchant.get_daraja_credentials()
    token = get_access_token(merchant)

    url = "https://api.safaricom.co.ke/mpesa/qrcode/v1/generate"

    payload = {
        "MerchantName": merchant.business_name,
        "RefNo": account_ref,
        "Amount": amount,
        "TrxCode": trx_code,
        "CPI": creds["shortcode"],
        "Size": "300",
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )

    print("Status:", response.status_code)
    print("Headers:", response.headers)
    print("Body:", repr(response.text))

    if not response.ok:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    if not response.text.strip():
        raise Exception("Safaricom returned an empty response.")

    try:
        return response.json()
    except ValueError:
        raise Exception(f"Response was not JSON.\nBody:\n{response.text}")

def b2c_disbursement(merchant: Merchant, phone: str, amount: int, remarks: str = "Disbursement"):

    if not merchant.has_b2c_credentials():
        raise ValueError(
            "Merchant has not configured B2C credentials. "
            "They must have a Safaricom-approved B2C shortcode first."
        )

    daraja_creds = merchant.get_daraja_credentials()
    b2c_creds = merchant.get_b2c_credentials()
    token = get_access_token(merchant)
    phone = normalize_phone(phone)

    url = f"{_base_url(daraja_creds['environment'])}/mpesa/b2c/v3/paymentrequest"
    payload = {
        "OriginatorConversationID": None,  # let Safaricom assign; or generate a UUID
        "InitiatorName": b2c_creds["initiator_name"],
        "SecurityCredential": b2c_creds["security_credential"],
        "CommandID": "BusinessPayment",
        "Amount": amount,
        "PartyA": b2c_creds["shortcode"],
        "PartyB": phone,
        "Remarks": remarks,
        "QueueTimeOutURL": f"{daraja_creds['callback_base_url']}/api/payment/b2c/timeout/{merchant.id}",
        "ResultURL": f"{daraja_creds['callback_base_url']}/api/payment/b2c/result/{merchant.id}",
        "Occasion": "Disbursement",
    }
    # OriginatorConversationID must be a string if provided; drop if None
    payload = {k: v for k, v in payload.items() if v is not None}

    response = requests.post(
        url, json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=60,
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(e)
        print(response.json())
    return response.json()