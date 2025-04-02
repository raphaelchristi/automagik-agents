"""McpAgentAgent implementation with PydanticAI.

This module provides a McpAgentAgent class that uses PydanticAI for LLM integration
and inherits common functionality from AutomagikAgent.
"""
import logging
import traceback
from typing import Dict, Any, Optional, Union, List

from pydantic_ai import Agent
from src.agents.models.automagik_agent import AutomagikAgent
from src.agents.models.dependencies import AutomagikAgentsDependencies
from src.agents.models.response import AgentResponse
from src.agents.models.mcp_server import MCPServerWrapper, MCPStdioServer
from src.memory.message_history import MessageHistory
from src.tools.mcp.python_runner import run_python_code

# Import Playwright MCP tools
from src.tools.mcp.browser_tools import (
    initialize_browser_tools,
    shutdown_browser_tools,
    get_browser_server_url
)

# Import only necessary utilities
from src.agents.common.message_parser import (
    extract_tool_calls, 
    extract_tool_outputs,
    extract_all_messages
)
from src.agents.common.dependencies_helper import (
    parse_model_settings,
    create_model_settings,
    create_usage_limits,
    get_model_name,
    add_system_message_to_history
)

logger = logging.getLogger(__name__)

class McpAgentAgent(AutomagikAgent):
    """McpAgentAgent implementation using PydanticAI.
    
    This agent provides a basic implementation that follows the PydanticAI
    conventions for multimodal support and tool calling.
    """
    
    def __init__(self, config: Dict[str, str]) -> None:
        """Initialize the McpAgentAgent.
        
        Args:
            config: Dictionary with configuration options
        """
        from src.agents.simple.mcp_agent_agent.prompts.prompt import AGENT_PROMPT
        
        # Initialize the base agent
        super().__init__(config, AGENT_PROMPT)
        
        # PydanticAI-specific agent instance
        self._agent_instance: Optional[Agent] = None
        
        # Configure dependencies
        self.dependencies = AutomagikAgentsDependencies(
            model_name=get_model_name(config),
            model_settings=parse_model_settings(config)
        )
        
        # Set agent_id if available
        if self.db_id:
            self.dependencies.set_agent_id(self.db_id)
        
        # Set usage limits if specified in config
        usage_limits = create_usage_limits(config)
        if usage_limits:
            self.dependencies.set_usage_limits(usage_limits)
        
        # Register default tools
        self.tool_registry.register_default_tools(self.context)
        
        # MCP servers for advanced capabilities
        self._mcp_servers: List[MCPServerWrapper] = []
        
        # Enable MCP by default for this agent
        self.use_mcp = config.get("use_mcp", "true").lower() in ["true", "1", "yes"]
        
        # Flag para controlar o uso do Playwright MCP
        self.use_playwright_mcp = config.get("use_playwright_mcp", "false").lower() in ["true", "1", "yes"]
        
        if self.use_mcp:
            self._initialize_mcp_servers()
        
        logger.info("McpAgentAgent initialized successfully")
    
    def _initialize_mcp_servers(self) -> None:
        """Initialize MCP servers for the agent."""
        # Create Stdio MCP server for basic functionality
        stdio_server = MCPStdioServer(name=f"McpAgentAgent-{self.db_id or 'default'}")
        
        # Register MCP tools with clearer names and detailed descriptions
        stdio_server.register_tool(
            "pyexec", 
            run_python_code, 
            "Executa código Python e retorna o resultado. Use esta ferramenta SEMPRE que precisar executar código Python."
        )
        
        # Add more tools as needed
        
        # Store server
        self._mcp_servers.append(stdio_server)
        logger.info(f"Initialized MCP server with {len(stdio_server.get_registered_tools())} tools")
        
        # Inicializar o Playwright MCP se habilitado
        if self.use_playwright_mcp:
            try:
                # Inicializa as ferramentas do navegador e obtém a configuração
                browser_tools_config = initialize_browser_tools()
                if browser_tools_config:
                    logger.info(f"Initialized Playwright MCP with {len(browser_tools_config)} browser tools")
                    
                    # Obter a URL do servidor Playwright MCP
                    browser_server_url = get_browser_server_url()
                    if browser_server_url:
                        logger.info(f"Playwright MCP server URL: {browser_server_url}")
                else:
                    logger.warning("Failed to initialize Playwright MCP tools")
            except Exception as e:
                logger.error(f"Error initializing Playwright MCP: {str(e)}")
    
    async def _initialize_pydantic_agent(self) -> None:
        """Initialize the underlying PydanticAI agent."""
        if self._agent_instance is not None:
            return
            
        # Get model configuration
        model_name = self.dependencies.model_name
        model_settings = create_model_settings(self.dependencies.model_settings)
        
        # Convert tools to PydanticAI format
        tools = self.tool_registry.convert_to_pydantic_tools()
        logger.info(f"Prepared {len(tools)} tools for PydanticAI agent")
        
        # Prepare MCP servers if enabled
        mcp_server_instances = []
        if self.use_mcp and self._mcp_servers:
            # Adicionar os servidores MCP
            for server in self._mcp_servers:
                mcp_server_instances.append(server.server)
            
            logger.info(f"Added {len(mcp_server_instances)} MCP servers")
            
            # Adiciona a URL do servidor Playwright MCP se estiver habilitado
            if self.use_playwright_mcp:
                browser_server_url = get_browser_server_url()
                if browser_server_url:
                    # Configuração para o MCP externo (Playwright)
                    mcp_server_config = {
                        "playwright": {
                            "url": browser_server_url
                        }
                    }
                    logger.info(f"Added Playwright MCP server configuration: {mcp_server_config}")
                    # Note: A URL do servidor será usada pelo cliente MCP do PydanticAI
                    
        try:
            # Create agent instance with MCP servers if enabled
            self._agent_instance = Agent(
                model=model_name,
                system_prompt=self.system_prompt,
                tools=tools,
                model_settings=model_settings,
                deps_type=AutomagikAgentsDependencies,
                mcp_servers=mcp_server_instances if self.use_mcp else None
            )
            
            # Registrar ferramentas MCP diretamente como PydanticAI tools
            if self.use_mcp and self._agent_instance:
                self._register_mcp_tools_directly()
            
            logger.info(f"Initialized agent with model: {model_name}, {len(tools)} tools, " +
                      f"and {len(mcp_server_instances) if self.use_mcp else 0} MCP servers")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise
            
    def _register_mcp_tools_directly(self) -> None:
        """Registra as ferramentas MCP diretamente no agente PydanticAI.
        
        Esta abordagem garante que as ferramentas MCP sejam expostas 
        explicitamente ao modelo, mesmo quando fornecidas via servidor MCP.
        """
        if not self._agent_instance:
            logger.warning("Cannot register MCP tools directly: PydanticAI agent not initialized")
            return
        
        # Importar RunContext para anotação de tipo
        from pydantic_ai import RunContext
        
        # Registrar ferramentas essenciais
        
        # 1. Python execution
        @self._agent_instance.tool(name="execute_python")
        async def execute_python(context: RunContext, code: str):
            """Executa código Python e retorna o resultado.
            
            Args:
                context: Contexto de execução
                code: Código Python para executar
            """
            result = await run_python_code(code=code)
            return {
                "output": result.get('output', ''),
                "error": result.get('error', ''),
                "success": result.get('success', False)
            }
        
        # 2. Datetime tools
        @self._agent_instance.tool(name="get_current_datetime")
        async def get_current_datetime(context: RunContext):
            """Obtém a data e hora atual."""
            from src.tools.mcp.datetime_tools import get_current_datetime
            return await get_current_datetime()
        
        # 3. Filesystem tools - read file
        @self._agent_instance.tool(name="read_file")
        async def read_file(context: RunContext, path: str):
            """Lê o conteúdo de um arquivo.
            
            Args:
                context: Contexto de execução
                path: Caminho do arquivo a ser lido
            """
            from src.tools.mcp.filesystem_tools import read_file
            return await read_file(path=path)
        
        # 4. Filesystem tools - write file
        @self._agent_instance.tool(name="write_file")
        async def write_file(context: RunContext, path: str, content: str):
            """Escreve conteúdo em um arquivo.
            
            Args:
                context: Contexto de execução
                path: Caminho do arquivo a ser escrito
                content: Conteúdo a ser escrito no arquivo
            """
            from src.tools.mcp.filesystem_tools import write_file
            return await write_file(path=path, content=content)
        
        # 5. Playwright browser tools (se habilitado)
        if self.use_playwright_mcp:
            # Estas ferramentas são implementadas pelo servidor Playwright MCP,
            # então não precisamos implementá-las aqui. O servidor MCP cuida disso.
            logger.info("Playwright MCP browser tools will be provided through the MCP server")
            
        logger.info("Registered MCP tools directly as PydanticAI tools")
        
    async def run(self, input_text: str, *, multimodal_content=None, system_message=None, message_history_obj: Optional[MessageHistory] = None,
                 channel_payload: Optional[Dict] = None,
                 message_limit: Optional[int] = 20) -> AgentResponse:
        """Run the agent with the given input.
        
        Args:
            input_text: Text input for the agent
            multimodal_content: Optional multimodal content
            system_message: Optional system message for this run (ignored in favor of template)
            message_history_obj: Optional MessageHistory instance for DB storage
            
        Returns:
            AgentResponse object with result and metadata
        """
        try:
            # Ensure memory variables are initialized
            if self.db_id:
                await self.initialize_memory_variables(getattr(self.dependencies, 'user_id', None))
                    
            # Initialize the agent
            await self._initialize_pydantic_agent()
            
            # Get message history in PydanticAI format
            pydantic_message_history = []
            if message_history_obj:
                pydantic_message_history = message_history_obj.get_formatted_pydantic_messages(limit=message_limit)
            
            # Prepare user input (handle multimodal content)
            user_input = input_text
            if multimodal_content:
                if hasattr(self.dependencies, 'configure_for_multimodal'):
                    self.dependencies.configure_for_multimodal(True)
                user_input = {"text": input_text, "multimodal_content": multimodal_content}
            
            # Get filled system prompt
            filled_system_prompt = await self.get_filled_system_prompt(
                user_id=getattr(self.dependencies, 'user_id', None)
            )
            
            # Add system prompt to message history
            if filled_system_prompt:
                pydantic_message_history = add_system_message_to_history(
                    filled_system_prompt, pydantic_message_history
                )
            
            # Activate any feature flags from channel payload
            if channel_payload and isinstance(channel_payload, dict):
                if channel_payload.get("use_playwright_mcp"):
                    self.use_playwright_mcp = True
                    logger.info("Enabling Playwright MCP for this run")
            
            # Execute agent
            response = await self._agent_instance.run(
                user_input,
                message_history=pydantic_message_history or None
            )
            
            if response is None:
                return AgentResponse(
                    text="Nenhuma resposta recebida do modelo",
                    success=False
                )
                
            # Extract message and tool calls
            message = response.message
            tool_calls = extract_tool_calls(response)
            tool_outputs = extract_tool_outputs(response)
            
            # Create agent response
            agent_response = AgentResponse(
                text=message,
                success=True,
                tool_calls=tool_calls,
                tool_outputs=tool_outputs
            )
            
            # Add session ID if available
            if hasattr(response, 'session_id'):
                agent_response.session_id = response.session_id
                
            return agent_response
            
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}\n{traceback.format_exc()}")
            return AgentResponse(
                text=f"Erro ao processar a mensagem: {str(e)}",
                success=False,
                error_message=str(e)
            )
    
    async def shutdown(self):
        """Clean up resources when shutting down the agent."""
        # Shutdown Playwright MCP if it was initialized
        if self.use_playwright_mcp:
            try:
                shutdown_result = shutdown_browser_tools()
                if shutdown_result:
                    logger.info("Playwright MCP server shutdown successfully")
                else:
                    logger.warning("Failed to shutdown Playwright MCP server")
            except Exception as e:
                logger.error(f"Error shutting down Playwright MCP: {str(e)}")
        
        # Call parent shutdown method
        await super().shutdown() 