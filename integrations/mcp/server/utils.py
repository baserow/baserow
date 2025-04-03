import os
from requests import request

BASEROW_DATABASE_TOKEN = os.getenv('BASEROW_DATABASE_TOKEN')
BASEROW_BASE_URL = os.getenv('BASEROW_BASE_URL', 'https://api.baserow.io')

headers = {
    "Authorization": f"Token {BASEROW_DATABASE_TOKEN}",
    "Content-Type": "application/json"
}

def make_request(method, url, **kwargs):
    url = f"{BASEROW_BASE_URL}{url}"
    response = request(
        method,
        url,
        headers=headers,
        **kwargs
    )
    response.raise_for_status()
    return response.json()
