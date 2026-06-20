from app.services.payment_service import create_payment
from datetime import datetime
from dotenv import load_dotenv
import requests
import json
import os
import base64

load_dotenv()

shortcode = os.getenv("SHORTCODE")
consumer_key = os.getenv("CONSUMER_KEY")
consumer_secret = os.getenv("CONSUMER_SECRET")


def get_access_token():

    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    auth = base64.b64encode(
        f"{os.getenv('CONSUMER_KEY')}:{os.getenv('CONSUMER_SECRET')}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {auth}"
    }

    response = requests.get(url, headers=headers)

    print(response.status_code)
    print(response.text)

    return response.json()["access_token"]

#SDK configuration
passkey = os.getenv("PASSKEY")
callback_url = os.getenv("CALLBACK_URL")

def stk_push(phone, amount):

    token = get_access_token()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    password = base64.b64encode(
        f"{shortcode}{passkey}{timestamp}".encode()
    ).decode()

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": "KiarieStr",
        "TransactionDesc": "txndesc"
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers
    )
    print(response.status_code)
    print(response.text)

    return response.json()


      

def generate_qr(amount,account_ref):

    token = get_access_token()
    qr_url = "https://sandbox.safaricom.co.ke/mpesa/qrcode/v1/generate"
    headers = {
        "Authorization" : f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        
        "MerchantName": "KiarieStr",
        "RefNo": account_ref,
        "Amount": amount,
        "TrxCode": "BG",
        "CPI": shortcode,
        "Size": "300"
    }

    response = requests.post(
        qr_url, 
        json=payload,
        headers=headers
    )
    print(json.dumps(payload, indent=4))
    print(response.status_code)
    print(response.text)
    return response.json()  
