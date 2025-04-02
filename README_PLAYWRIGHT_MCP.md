# Integração do Playwright MCP com o Agente MCP

Este documento descreve como utilizar a integração do [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) com o agente MCP.

## O que é o Playwright MCP?

O Playwright MCP (Model Context Protocol) é um servidor que fornece capacidades de automação de navegador usando o Playwright. Este servidor permite que LLMs interajam com páginas web através de snapshots de acessibilidade estruturados, sem a necessidade de capturas de tela ou modelos ajustados visualmente.

## Características principais

- **Rápido e leve**: Usa a árvore de acessibilidade do Playwright, não entrada baseada em pixels.
- **Amigável para LLMs**: Não são necessários modelos de visão, opera puramente em dados estruturados.
- **Aplicação determinística de ferramentas**: Evita ambiguidades comuns em abordagens baseadas em capturas de tela.

## Configuração

A integração foi configurada no arquivo `mcp_playwright_config.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--port",
        "8931"
      ]
    }
  },
  "mcp_tools": ["browser_navigate", "browser_snapshot", "browser_click", "browser_type", "browser_take_screenshot"],
  "mcp_config": {
    "allow_browser_automation": true
  }
}
```

## Ferramentas disponíveis

As seguintes ferramentas de navegador estão disponíveis para o agente MCP:

- **browser_navigate**: Navega para uma URL específica
- **browser_snapshot**: Captura um snapshot de acessibilidade da página atual
- **browser_click**: Clica em elementos na página
- **browser_type**: Digita texto em elementos editáveis
- **browser_take_screenshot**: Captura um screenshot da página

## Como usar

### 1. Iniciar o servidor Playwright MCP

```bash
./start_playwright_mcp.sh
```

Isso iniciará o servidor Playwright MCP na porta 8931.

### 2. Usar o agente MCP com as ferramentas de navegador

Você pode usar o script de cliente que criamos anteriormente, adicionando o parâmetro `use_playwright_mcp`:

```python
import requests
import json
import os

api_key = os.environ.get("AM_API_KEY")

response = requests.post(
    "http://0.0.0.0:8881/api/v1/agent/mcp/run",
    json={
        "message_content": "Navegue para https://www.example.com e me diga o título da página",
        "user_id": 1,
        "use_mcp": True,
        "use_playwright_mcp": True  # Ativa o Playwright MCP para esta solicitação
    },
    headers={"Content-Type": "application/json", "x-api-key": api_key},
    timeout=60
)

print(response.json()["message"])
```

### 3. Teste com o script de exemplo

```bash
python teste_mcp_browser.py
```

Este script enviará uma solicitação para o agente MCP navegar para uma página web e retornar informações sobre ela.

## Arquitetura da integração

1. O módulo `src/tools/mcp/browser_tools.py` gerencia a integração com o Playwright MCP
2. O agente MCP em `src/agents/simple/mcp_agent_agent/agent.py` foi modificado para suportar o Playwright MCP
3. A configuração em `mcp_agent_config.json` e `mcp_playwright_config.json` controla o comportamento do Playwright MCP

## Limitações e considerações

- O navegador Chrome será iniciado com um perfil novo, localizado em:
  - `%USERPROFILE%\AppData\Local\ms-playwright\mcp-chrome-profile` no Windows
  - `~/Library/Caches/ms-playwright/mcp-chrome-profile` no macOS
  - `~/.cache/ms-playwright/mcp-chrome-profile` no Linux

- Todas as informações de login serão armazenadas nesse perfil. Você pode excluí-lo entre as sessões se desejar limpar o estado offline.

- Para executar o navegador sem interface gráfica (modo headless), modifique o arquivo `mcp_playwright_config.json` adicionando `"--headless"` aos argumentos. 