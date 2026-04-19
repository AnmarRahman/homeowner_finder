import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("LA_DATASET_URL")

print("URL:", url)

response = requests.get(
    url,
    params={"$limit": 1},
    headers={"Accept": "application/json"},
    timeout=30,
)

print("Status:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("First 500 chars:")
print(response.text[:500])