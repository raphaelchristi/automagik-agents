from dotenv import load_dotenv
load_dotenv()

import requests
import json
import os

api_key = os.environ.get("AM_API_KEY")
print(f"API Key: {api_key[:4]}..." if api_key else "API Key não encontrada")

# Solicitação para obter a hora e data
mensagem = "Que horas são agora?"

print(f"Mensagem: {mensagem}")
print("Enviando requisição...")

response = requests.post(
    "http://0.0.0.0:8881/api/v1/agent/mcp/run",
    json={"message_content": mensagem, "user_id": 1, "use_mcp": True},
    headers={"Content-Type": "application/json", "x-api-key": api_key},
    timeout=30
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print("\nResposta do agente:")
    print("-" * 50)
    print(result.get("message", "Sem resposta"))
    print("-" * 50)
    
    # Exibir detalhes das chamadas de ferramentas
    if "tool_calls" in result and result["tool_calls"]:
        print("\nChamadas de ferramentas:")
        for i, call in enumerate(result["tool_calls"]):
            print(f"{i+1}. {call['tool_name']}")
            
    # Exibir os resultados das ferramentas
    if "tool_outputs" in result and result["tool_outputs"]:
        print("\nResultados das ferramentas:")
        for i, output in enumerate(result["tool_outputs"]):
            print(f"{i+1}. {output['tool_name']}: {json.dumps(output['content'], indent=2)}")
else:
    print(f"Erro: {response.text}") 