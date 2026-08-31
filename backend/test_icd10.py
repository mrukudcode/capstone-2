import os
import httpx
from dotenv import load_dotenv

load_dotenv()

client_id = os.environ["WHO_ICD_CLIENT_ID"]
client_secret = os.environ["WHO_ICD_CLIENT_SECRET"]

# Get token
token_response = httpx.post(
    "https://icdaccessmanagement.who.int/connect/token",
    data={
        "grant_type": "client_credentials",
        "scope": "icdapi_access",
    },
    auth=(client_id, client_secret),
)

token_response.raise_for_status()

token = token_response.json()["access_token"]

headers = {
    "Authorization": f"Bearer {token}",
    "API-Version": "v2",
    "Accept": "application/json",
    "Accept-Language": "en",
}

url = "https://id.who.int/icd/release/10/2019/IV"

response = httpx.get(
    url,
    headers=headers,
)

print("STATUS:", response.status_code)
print(response.text[:10000])