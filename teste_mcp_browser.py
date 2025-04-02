#!/usr/bin/env python3
"""
Script para testar o agente MCP com as ferramentas de navegador do Playwright.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import requests
import json
import os
import sys
import time
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_browser_automation():
    """Testa a automação de navegador com o Playwright MCP."""
    api_key = os.environ.get("AM_API_KEY")
    if not api_key:
        logger.error("Erro: API key não encontrada no arquivo .env")
        sys.exit(1)
    
    logger.info("API Key: %s...", api_key[:4])
    
    # Preparar payload para navegação em uma página
    payload = {
        "message_content": "Por favor, navegue para https://www.example.com e me diga o título da página.",
        "user_id": 1,
        "session_origin": "cli",
        "use_mcp": True,
        "use_playwright_mcp": True  # Ativa o Playwright MCP para esta solicitação
    }
    
    # Preparar headers
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    
    # Fazer a requisição
    logger.info("Enviando requisição para navegação web...")
    
    try:
        response = requests.post(
            "http://0.0.0.0:8881/api/v1/agent/mcp/run",
            json=payload,
            headers=headers,
            timeout=60  # Timeout maior para operações de navegador
        )
        
        logger.info("Status: %d", response.status_code)
        
        if response.status_code == 200:
            result = response.json()
            logger.info("\nResposta do agente:")
            logger.info("=" * 50)
            logger.info(result.get("message", "Sem resposta"))
            logger.info("=" * 50)
            
            # Exibir chamadas de ferramentas
            if "tool_calls" in result and result["tool_calls"]:
                logger.info("\nChamadas de ferramentas:")
                for i, call in enumerate(result["tool_calls"]):
                    logger.info("%d. %s - Args: %s", i+1, call.get('tool_name'), call.get('args'))
            
            # Exibir resultados das ferramentas
            if "tool_outputs" in result and result["tool_outputs"]:
                logger.info("\nResultados das ferramentas:")
                for i, output in enumerate(result["tool_outputs"]):
                    logger.info("%d. %s:", i+1, output.get('tool_name'))
                    output_content = output.get('content', {})
                    if isinstance(output_content, dict):
                        for key, value in output_content.items():
                            if key == 'result' and isinstance(value, str) and len(value) > 100:
                                # Truncar resultados longos
                                logger.info("  %s: %s... (truncado)", key, value[:100])
                            else:
                                logger.info("  %s: %s", key, value)
                    else:
                        logger.info("  %s", output_content)
        else:
            logger.error("Erro: %s", response.text)
            
    except requests.exceptions.ReadTimeout:
        logger.error("Erro: Timeout ao aguardar resposta")
    except requests.exceptions.ConnectionError:
        logger.error("Erro: Não foi possível conectar ao servidor")
    except Exception as e:
        logger.error("Erro: %s", str(e))

if __name__ == "__main__":
    asyncio.run(test_browser_automation()) 