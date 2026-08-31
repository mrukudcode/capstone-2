import os
import httpx
from dotenv import load_dotenv

load_dotenv()

client_id = os.environ["WHO_ICD_CLIENT_ID"]
client_secret = os.environ["WHO_ICD_CLIENT_SECRET"]

# 1. Get OAuth token
token_response = httpx.post(
    "https://icdaccessmanagement.who.int/connect/token",
    data={
        "grant_type": "client_credentials",
        "scope": "icdapi_access",
    },
    auth=(client_id, client_secret),
)

print("TOKEN STATUS:", token_response.status_code)

if token_response.status_code != 200:
    print(token_response.text)
    raise SystemExit

token = token_response.json()["access_token"]

# 2. Test WHO ICD API
headers = {
    "Authorization": f"Bearer {token}",
    "API-Version": "v2",
    "Accept": "application/json",
    "Accept-Language": "en",
}

url = "https://id.who.int/icd/entity"

response = httpx.get(
    url,
    headers=headers,
)

print("API STATUS:", response.status_code)
print("RESPONSE:")

# Don't print enormous responses
print(response.text[:2000])