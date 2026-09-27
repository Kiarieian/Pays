"""
Daraja API client.

Every function takes a `merchant` object and uses THAT merchant's own
Daraja credentials (see models.Merchant.get_daraja_credentials /
get_b2c_credentials). Money always moves directly between the merchant's
own M-Pesa account and their customer.
"""
import base64
import logging
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import get_settings
from app.models import Merchant

logger = logging.getLogger("daraja.client")

settings = get_settings()

# In-memory token cache: {merchant_id: (token, expires_at_epoch)}
_token_cache: dict[int, tuple[str, float]] = {}

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}

# Timeout tuples: (connect_timeout, read_timeout)
CONNECT_TIMEOUT = settings.daraja.connect_timeout
READ_TIMEOUT = settings.daraja.read_timeout


def _base_url(environment: str) -> str:
    return BASE_URLS.get(environment, BASE_URLS["sandbox"])


def _get_http_session() -> requests.Session:
    """Create a requests session with retry logic for transient errors."""
    session = requests.Session()
    retry = Retry(
        total=0,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_http = _get_http_session()


def get_access_token(merchant: Merchant) -> str:
    """Get OAuth access token, using cache where possible."""
    cached = _token_cache.get(merchant.id)
    if cached and cached[1] > time.time():
        return cached[0]

    creds = merchant.get_daraja_credentials()
    url = f"{_base_url(creds['environment'])}/oauth/v1/generate?grant_type=client_credentials"

    auth = base64.b64encode(
        f"{creds['consumer_key']}:{creds['consumer_secret']}".encode()
    ).decode()

    try:
        response = _http.get(
            url,
            headers={"Authorization": f"Basic {auth}"},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        response.raise_for_status()
        logger.info(
             "Daraja OAuth succeeded for merchant=%s status=%s",
             merchant.id,
             response.status_code,
        )
    except requests.exceptions.Timeout:
        logger.error("Daraja OAuth timeout for merchant %s", merchant.id)
        raise
    except requests.exceptions.ConnectionError:
        logger.exception("Daraja OAuth connection error for merchant %s",merchant.id)
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(
            "Daraja OAuth HTTP %s for merchant %s: %s",
            e.response.status_code, merchant.id, e.response.text[:200],
        )
        raise

    data = response.json()
    token = data.get("access_token")
    logger.info("Daraja OAuth token obtained for merchant %s", merchant.id)
    if not token:
        logger.error("Daraja OAuth response missing access_token for merchant %s", merchant.id)
        raise ValueError("Daraja OAuth response missing access_token")
        

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


def stk_push(
    merchant: Merchant,
    phone: str,
    amount: int,
    account_reference: str | None = None,
) -> dict:
    """Initiate an STK Push (Lipa Na M-Pesa Online) request."""
    creds = merchant.get_daraja_credentials()
    token = get_access_token(merchant)
    phone = normalize_phone(phone)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{creds['shortcode']}{creds['passkey']}{timestamp}".encode()
    ).decode()

    url = f"{_base_url(creds['environment'])}/mpesa/stkpush/v1/processrequest"
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
        "AccountReference": account_reference or "Payment",
        "TransactionDesc": f"Payment of KSh {amount}",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = _http.post(url, json=payload, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except requests.exceptions.Timeout:
        logger.error("STK Push timeout for merchant %s, phone %s", merchant.id, phone)
        raise
    except requests.exceptions.ConnectionError:
        logger.error("STK Push connection error for merchant %s", merchant.id)
        raise

    logger.info(
        "STK Push merchant=%s phone=%s amount=%s status=%s",
        merchant.id, phone, amount, response.status_code,
    )

    if not response.ok:
        logger.error(
            "STK Push HTTP %s for merchant %s: %s",
            response.status_code, merchant.id, response.text[:500],
        )
        response.raise_for_status()
        

    try:
        return response.json()
    except ValueError:
        logger.error(
            "STK Push non-JSON response for merchant %s: %s",
            merchant.id, response.text[:500],
        )
        raise Exception("Daraja returned non-JSON response for STK Push")


def generate_qr(
    merchant: Merchant,
    amount: int,
    account_ref: str,
    trx_code: str = "BG",
) -> dict:
    """Generate an M-Pesa QR code."""
    creds = merchant.get_daraja_credentials()
    token = get_access_token(merchant)

    url = f"{_base_url(creds['environment'])}/mpesa/qrcode/v1/generate"

    payload = {
        "MerchantName": merchant.business_name,
        "RefNo": account_ref,
        "Amount": amount,
        "TrxCode": trx_code,
        "CPI": creds["shortcode"],
        "Size": "300",
    }

    try:
        response = _http.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.exceptions.Timeout:
        logger.error("QR generation timeout for merchant %s", merchant.id)
        raise
    except requests.exceptions.ConnectionError:
        logger.error("QR generation connection error for merchant %s", merchant.id)
        raise

    logger.info(
        "QR generation merchant=%s amount=%s status=%s",
        merchant.id, amount, response.status_code,
    )

    if not response.ok:
        logger.error(
            "QR generation HTTP %s for merchant %s: %s",
            response.status_code, merchant.id, response.text[:500],
        )
        raise Exception(f"Daraja QR HTTP {response.status_code}: {response.text[:200]}")

    if not response.text.strip():
        raise Exception("Safaricom returned an empty QR response")

    try:
        return response.json()
    except ValueError:
        raise Exception("Safaricom QR response was not JSON")


def b2c_disbursement(
    merchant: Merchant,
    phone: str,
    amount: int,
    remarks: str = "Disbursement",
) -> dict:
    """Initiate a B2C disbursement (merchant -> customer payment)."""
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

    try:
        response = _http.post(
            url, json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.exceptions.Timeout:
        logger.error("B2C disbursement timeout for merchant %s", merchant.id)
        raise
    except requests.exceptions.ConnectionError:
        logger.error("B2C disbursement connection error for merchant %s", merchant.id)
        raise

    logger.info(
        "B2C disbursement merchant=%s phone=%s amount=%s status=%s",
        merchant.id, phone, amount, response.status_code,
    )

    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        logger.error(
            "B2C disbursement non-JSON response for merchant %s: %s",
            merchant.id, response.text[:500],
        )
        raise Exception("Daraja returned non-JSON response for B2C disbursement")
