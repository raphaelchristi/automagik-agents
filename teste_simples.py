from dotenv import load_dotenv
load_dotenv()

import requests
import json
import os

api_key = os.environ.get("AM_API_KEY")
print(f"API Key: {api_key[:4]}..." if api_key else "API Key não encontrada")

response = requests.post(
    "http://0.0.0.0:8881/api/v1/agent/mcp/run",
    json={"message_content": "Olá, me diga a data atual", "user_id": 1, "use_mcp": True},
    headers={"Content-Type": "application/json", "x-api-key": api_key},
    timeout=30
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"Resposta: {result.get('message', 'Sem resposta')}")
else:
    print(f"Erro: {response.text}") 