"""
Módulo para integração do Playwright MCP nas ferramentas MCP do agente.
"""

import os
import json
import subprocess
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class PlaywrightMCPTools:
    """Classe para gerenciar as ferramentas de navegador do Playwright MCP."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Inicializa as ferramentas do Playwright MCP.
        
        Args:
            config_path: Caminho para o arquivo de configuração. Se None, usa o padrão.
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "mcp_playwright_config.json"
        )
        self.config = self._load_config()
        self.process = None
        self.server_url = None
    
    def _load_config(self) -> Dict:
        """Carrega a configuração do arquivo JSON."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar configuração do Playwright MCP: {str(e)}")
            return {"mcpServers": {}, "mcp_tools": [], "mcp_config": {}}
    
    def start_server(self) -> bool:
        """Inicia o servidor Playwright MCP."""
        if not self.config.get("mcpServers", {}).get("playwright"):
            logger.error("Configuração do Playwright MCP ausente")
            return False
        
        try:
            server_config = self.config["mcpServers"]["playwright"]
            cmd = [server_config["command"]] + server_config["args"]
            
            # Adiciona porta específica para facilitar a conexão
            if "--port" not in server_config["args"]:
                cmd.append("--port")
                cmd.append("8931")  # Porta padrão para o Playwright MCP
            
            logger.info(f"Iniciando servidor Playwright MCP: {' '.join(cmd)}")
            
            # Inicia o processo em segundo plano
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Define a URL do servidor para conexão
            self.server_url = "http://localhost:8931/sse"
            
            logger.info(f"Servidor Playwright MCP iniciado com PID {self.process.pid}")
            return True
        except Exception as e:
            logger.error(f"Erro ao iniciar servidor Playwright MCP: {str(e)}")
            return False
    
    def stop_server(self) -> bool:
        """Para o servidor Playwright MCP."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("Servidor Playwright MCP encerrado")
                return True
            except Exception as e:
                logger.error(f"Erro ao encerrar servidor Playwright MCP: {str(e)}")
                try:
                    self.process.kill()
                except:
                    pass
                return False
        return True
    
    def get_tools_config(self) -> Dict:
        """Retorna a configuração das ferramentas para registro no agente MCP."""
        tools_config = {}
        
        # Ferramentas de navegação
        if "browser_navigate" in self.config.get("mcp_tools", []):
            tools_config["browser_navigate"] = {
                "description": "Navega para uma URL específica no navegador",
                "parameters": {
                    "url": {
                        "type": "string",
                        "description": "A URL para navegação"
                    }
                }
            }
        
        # Ferramenta de captura de snapshot
        if "browser_snapshot" in self.config.get("mcp_tools", []):
            tools_config["browser_snapshot"] = {
                "description": "Captura um snapshot de acessibilidade da página atual",
                "parameters": {}
            }
        
        # Ferramenta de clique
        if "browser_click" in self.config.get("mcp_tools", []):
            tools_config["browser_click"] = {
                "description": "Clica em um elemento na página",
                "parameters": {
                    "element": {
                        "type": "string",
                        "description": "Descrição legível do elemento para interação"
                    },
                    "ref": {
                        "type": "string",
                        "description": "Referência exata do elemento do snapshot da página"
                    }
                }
            }
        
        # Ferramenta de digitação
        if "browser_type" in self.config.get("mcp_tools", []):
            tools_config["browser_type"] = {
                "description": "Digita texto em um elemento editável",
                "parameters": {
                    "element": {
                        "type": "string",
                        "description": "Descrição legível do elemento para interação"
                    },
                    "ref": {
                        "type": "string",
                        "description": "Referência exata do elemento do snapshot da página"
                    },
                    "text": {
                        "type": "string",
                        "description": "Texto a ser digitado no elemento"
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "Se deve enviar o texto (pressionar Enter após)"
                    }
                }
            }
        
        # Ferramenta de captura de screenshot
        if "browser_take_screenshot" in self.config.get("mcp_tools", []):
            tools_config["browser_take_screenshot"] = {
                "description": "Captura um screenshot da página",
                "parameters": {
                    "raw": {
                        "type": "string",
                        "description": "Opcionalmente retorna screenshot PNG sem perdas. JPEG por padrão."
                    }
                }
            }
        
        return tools_config
    
    def get_server_url(self) -> Optional[str]:
        """Retorna a URL do servidor para conexão."""
        return self.server_url


# Instância global para uso no agente
playwright_tools = PlaywrightMCPTools()

def initialize_browser_tools() -> Dict:
    """Inicializa as ferramentas de navegador e retorna sua configuração."""
    success = playwright_tools.start_server()
    if success:
        return playwright_tools.get_tools_config()
    return {}

def shutdown_browser_tools() -> bool:
    """Encerra as ferramentas de navegador."""
    return playwright_tools.stop_server()

def get_browser_server_url() -> Optional[str]:
    """Retorna a URL do servidor de navegador."""
    return playwright_tools.get_server_url() 