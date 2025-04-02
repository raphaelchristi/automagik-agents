#!/usr/bin/env python3
"""
Cliente para o agente MCP
Uso: python mcp_client.py "Sua mensagem aqui"
"""

from dotenv import load_dotenv
load_dotenv()

import requests
import json
import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Cliente para o agente MCP")
    parser.add_argument("mensagem", help="Mensagem para enviar ao agente MCP")
    parser.add_argument("--agente", default="mcp", help="Nome do agente (padrão: mcp)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout em segundos (padrão: 30)")
    parser.add_argument("--sem-mcp", action="store_true", help="Desabilitar MCP")
    args = parser.parse_args()
    
    # Obter a API key do arquivo .env
    api_key = os.environ.get("AM_API_KEY")
    if not api_key:
        print("Erro: API key não encontrada no arquivo .env")
        sys.exit(1)
    
    print(f"API Key: {api_key[:4]}...")
    print(f"Agente: {args.agente}")
    print(f"Mensagem: {args.mensagem}")
    
    # Preparar o payload
    payload = {
        "message_content": args.mensagem,
        "user_id": 1,
        "session_origin": "cli"
    }
    
    # Adicionar flag MCP se necessário
    if not args.sem_mcp:
        payload["use_mcp"] = True
        print("MCP: Habilitado")
    else:
        print("MCP: Desabilitado")
    
    # Preparar os headers
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    
    # Fazer a requisição
    print("\nEnviando requisição...")
    try:
        response = requests.post(
            f"http://0.0.0.0:8881/api/v1/agent/{args.agente}/run",
            json=payload,
            headers=headers,
            timeout=args.timeout
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
                    print(f"{i+1}. {output['tool_name']}:")
                    print(json.dumps(output['content'], indent=2))
        else:
            print(f"Erro: {response.text}")
            
    except requests.exceptions.ReadTimeout:
        print(f"Erro: Timeout após {args.timeout} segundos")
    except requests.exceptions.ConnectionError:
        print(f"Erro: Não foi possível conectar ao servidor: http://0.0.0.0:8881")
    except Exception as e:
        print(f"Erro: {str(e)}")

if __name__ == "__main__":
    main() 