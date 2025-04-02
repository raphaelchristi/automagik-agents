#!/bin/bash
# Script para iniciar o servidor Playwright MCP

echo "Iniciando servidor Playwright MCP..."

# Verifica se o pacote está instalado
if ! npm list -g @playwright/mcp &> /dev/null; then
    echo "Instalando @playwright/mcp globalmente..."
    npm install -g @playwright/mcp
fi

# Inicia o servidor na porta 8931
npx @playwright/mcp@latest --port 8931

echo "Servidor Playwright MCP encerrado" 