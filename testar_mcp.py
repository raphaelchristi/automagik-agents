from dotenv import load_dotenv
load_dotenv()

import requests
import json
import os

# Obter API key
api_key = os.environ.get("AM_API_KEY")
print(f"API Key presente: {bool(api_key)}")

# Definir a mensagem
mensagem = "Olá, por favor me diga a data atual"
print(f"Mensagem: {mensagem}")

# Preparar o payload
payload = {
    "message_content": mensagem,
    "user_id": 1,
    "session_origin": "cli",
    "use_mcp": True
}

# Preparar os headers
headers = {
    "Content-Type": "application/json",
    "x-api-key": api_key
}

# Fazer a requisição
print("Enviando requisição...")
response = requests.post(
    "http://0.0.0.0:8881/api/v1/agent/mcp/run",
    json=payload,
    headers=headers,
    timeout=30
)

# Exibir o resultado
print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nResposta do agente:")
    print("-" * 50)
    print(result.get("message", "Sem resposta"))
    print("-" * 50)
else:
    print(f"Erro: {response.text}")
