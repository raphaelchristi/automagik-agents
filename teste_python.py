from dotenv import load_dotenv
load_dotenv()

import requests
import json
import os

api_key = os.environ.get("AM_API_KEY")
print(f"API Key: {api_key[:4]}..." if api_key else "API Key não encontrada")

# Solicitação para executar código Python
mensagem = """Por favor execute o seguinte código Python:
import math
numeros = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
soma = sum(numeros)
media = soma / len(numeros)
desvio_padrao = math.sqrt(sum((x - media) ** 2 for x in numeros) / len(numeros))
print(f"Soma: {soma}")
print(f"Média: {media}")
print(f"Desvio padrão: {desvio_padrao}")
"""

print(f"Mensagem: {mensagem}")
print("Enviando requisição...")

response = requests.post(
    "http://0.0.0.0:8881/api/v1/agent/mcp/run",
    json={"message_content": mensagem, "user_id": 1, "use_mcp": True},
    headers={"Content-Type": "application/json", "x-api-key": api_key},
    timeout=60  # Aumentando o timeout para 60 segundos
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print("\nResposta do agente:")
    print("-" * 50)
    print(result.get("message", "Sem resposta"))
    print("-" * 50)
    
    # Exibir detalhes da chamada da ferramenta
    if "tool_calls" in result and result["tool_calls"]:
        print("\nChamadas de ferramentas:")
        for i, call in enumerate(result["tool_calls"]):
            print(f"{i+1}. {call['tool_name']}")
else:
    print(f"Erro: {response.text}") 