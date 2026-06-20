import requests
import base64
from PIL import Image
from io import BytesIO


consumer_key = '30NLycZ4xwakrs0dJTDPiyi1ZCq6Hp0PN1qODmxBJl5x5WUT'
consumer_secret = 'qFIqKwXwp0m78XV4UYDk1RYSW5BxcYGbCf8EXuwtbD3R0zZSJrWFJ5eCiN2Mhrjm'

auth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'

response = requests.get(auth_url,auth=(consumer_key, consumer_secret))
access_token = response.json().get('access_token')
if response.status_code == 200: 
    print(f'Access Token: {access_token}')


#generate QR code

qr_url = 'https://sandbox.safaricom.co.ke/mpesa/qrcode/v1/generate'
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

payload = {
    "MerchantName": "KiarieStr",
    "RefNo": "KiarieStr-001",
    "Amount": "100",
    "TrxCode": "SM",
    "CPI": "727951049",
    "Size": "300"
}

qr_response = requests.post(qr_url, json=payload, headers=headers)
data = qr_response.json()

print(data)

#Save QR code image

qr_base64 = data.get('QRCode')

qr_image = base64.b64decode(qr_base64)


print('QR code image saved as qrcode.png')

with open("mpesa_qr.png", "wb") as f:
    f.write(qr_image)

img = Image.open(BytesIO(qr_image))
img.show()