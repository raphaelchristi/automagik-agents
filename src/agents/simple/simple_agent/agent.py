"""SimpleAgent implementation.

This module provides the SimpleAgent implementation, which is a basic
agent that follows PydanticAI conventions for multimodal support.
"""
import logging
import asyncio
import traceback
import re
from typing import Dict, List, Any, Optional, Callable, Union, TypeVar, Tuple, Set
from functools import partial
import json
import os
import uuid

# Import constants
from src.constants import (
    DEFAULT_MODEL, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, DEFAULT_RETRIES
)

# Import dependencies
from src.agents.models.base_agent import BaseAgent
from src.agents.models.dependencies import SimpleAgentDependencies
from src.agents.models.response import AgentResponse
from src.memory.message_history import MessageHistory

# Import tools
from src.tools.common_tools.web_tools import (
    web_search_tool, webscrape_tool
)
from src.tools.common_tools.image_tools import (
    process_image_url_tool, process_image_binary_tool
)
from src.tools.common_tools.audio_tools import (
    process_audio_url_tool, process_audio_binary_tool
)
from src.tools.common_tools.document_tools import (
    process_document_url_tool, process_document_binary_tool
)
from src.tools.common_tools.date_tools import (
    get_current_date_tool, get_current_time_tool, format_date_tool
)
from src.tools.common_tools.memory_tools import (
    get_memory_tool, store_memory_tool, list_memories_tool
)

# Import PydanticAI types with correct import structure
try:
    # Core PydanticAI classes
    from pydantic_ai import Agent as PydanticAgent
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits
    
    # Tool-related imports
    from pydantic_ai.tools import Tool as PydanticTool
    from pydantic_ai.tools import RunContext
    
    # Message and content imports
    from pydantic_ai import (
        ImageUrl, AudioUrl, DocumentUrl, BinaryContent
    )
    from pydantic_ai.messages import ModelMessage
    
    PYDANTIC_AI_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"PydanticAI import error: {str(e)}")
    # Create placeholder types for better error handling
    class PydanticAgent:
        pass
    class ModelMessage:
        pass
    class PydanticTool:
        pass
    class RunContext:
        pass
    class ModelSettings:
        pass
    class UsageLimits:
        pass
    class ImageUrl:
        pass
    class AudioUrl:
        pass
    class DocumentUrl:
        pass
    class BinaryContent:
        pass
    PYDANTIC_AI_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)
T = TypeVar('T')  # Generic type for callable return values

class SimpleAgent(BaseAgent):
    """SimpleAgent implementation using PydanticAI.
    
    This agent provides a basic implementation that follows the PydanticAI
    conventions for multimodal support and tool calling.
    """
    
    def __init__(self, config: Dict[str, str]) -> None:
        """Initialize the SimpleAgent.
        
        Args:
            config: Dictionary with configuration options
        """
        if not PYDANTIC_AI_AVAILABLE:
            logger.error("PydanticAI is required for SimpleAgent. Install with: pip install pydantic-ai")
            raise ImportError("PydanticAI is required for SimpleAgent")
        
        # Import prompt template from prompt.py
        from src.agents.simple.simple_agent.prompts.prompt import SIMPLE_AGENT_PROMPT
        self.prompt_template = SIMPLE_AGENT_PROMPT
        
        # Store agent_id if provided
        self.db_id = config.get("agent_id")
        if self.db_id and isinstance(self.db_id, str) and self.db_id.isdigit():
            self.db_id = int(self.db_id)
            logger.info(f"Initialized SimpleAgent with database ID: {self.db_id}")
        else:
            # Don't log a warning here, as this is expected during discovery
            # The actual agent_id will be set later in the API routes
            self.db_id = None
        
        # Extract template variables from the prompt
        self.template_vars = self._extract_template_variables(self.prompt_template)
        if self.template_vars:
            logger.info(f"Detected template variables: {', '.join(self.template_vars)}")
            
            # Initialize memory variables if agent ID is available
            if self.db_id:
                try:
                    self._initialize_memory_variables_sync()
                    logger.info(f"Memory variables initialized for agent ID {self.db_id}")
                except Exception as e:
                    logger.error(f"Error initializing memory variables: {str(e)}")
        
        # Create initial system prompt - dynamic parts will be added via decorators
        base_system_prompt = self._create_base_system_prompt()
        
        # Initialize the BaseAgent with proper arguments
        super().__init__(config, base_system_prompt)
        
        # Initialize variables
        self._agent_instance: Optional[PydanticAgent] = None
        self._registered_tools: Dict[str, Callable] = {}
        
        # Create dependencies
        self.dependencies = SimpleAgentDependencies(
            model_name=config.get("model", DEFAULT_MODEL),
            model_settings=self._parse_model_settings(config)
        )
        
        # Set agent ID in dependencies
        if self.db_id:
            self.dependencies.set_agent_id(self.db_id)
        
        # Set usage limits if specified
        if "response_tokens_limit" in config or "request_limit" in config or "total_tokens_limit" in config:
            self._set_usage_limits(config)
        
        # Register default tools
        self._register_default_tools()
    
    def _extract_template_variables(self, template: str) -> List[str]:
        """Extract all template variables from a string.
        
        Args:
            template: Template string with {{variable}} placeholders
            
        Returns:
            List of variable names without braces
        """
        pattern = r'\{\{([a-zA-Z_]+)\}\}'
        matches = re.findall(pattern, template)
        return list(set(matches))  # Remove duplicates
    
    def _initialize_memory_variables_sync(self) -> None:
        """Initialize memory variables in the database.
        
        This ensures all template variables exist in memory with default values.
        Uses direct repository calls to avoid async/await issues.
        """
        if not self.db_id:
            logger.warning("Cannot initialize memory variables: No agent ID available")
            return
            
        try:
            # Import the repository functions for direct database access
            from src.db.repository.memory import get_memory_by_name, create_memory
            from src.db.models import Memory
            
            # Extract all variables except run_id which is handled separately
            memory_vars = [var for var in self.template_vars if var != "run_id"]
            
            for var_name in memory_vars:
                try:
                    # Check if memory already exists with direct repository call
                    existing_memory = get_memory_by_name(var_name, agent_id=self.db_id)
                    
                    # If not found, create it with default value
                    if not existing_memory:
                        logger.info(f"Creating missing memory variable: {var_name}")
                        
                        # Prepare a proper description based on the variable name
                        description = f"Auto-created template variable for SimpleAgent"
                        if var_name == "personal_attributes":
                            description = "Personal attributes and preferences for the agent"
                            content = "None stored yet. You can update this by asking the agent to remember personal details."
                        elif var_name == "technical_knowledge":
                            description = "Technical knowledge and capabilities for the agent"
                            content = "None stored yet. You can update this by asking the agent to remember technical information."
                        elif var_name == "user_preferences":
                            description = "User preferences and settings for the agent"
                            content = "None stored yet. You can update this by asking the agent to remember your preferences."
                        else:
                            content = "None stored yet"
                        
                        # Create the memory directly using repository function
                        memory = Memory(
                            name=var_name,
                            content=content,
                            description=description,
                            agent_id=self.db_id,
                            read_mode="system_prompt",
                            access="read_write"  # Ensure it can be written to
                        )
                        
                        memory_id = create_memory(memory)
                        if memory_id:
                            logger.info(f"Created memory variable: {var_name} with ID: {memory_id}")
                        else:
                            logger.error(f"Failed to create memory variable: {var_name}")
                    else:
                        logger.info(f"Memory variable already exists: {var_name}")
                        
                except Exception as e:
                    logger.error(f"Error initializing memory variable {var_name}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in _initialize_memory_variables_sync: {str(e)}")
    
    def _create_base_system_prompt(self) -> str:
        """Create the base system prompt.
        
        Returns an empty base prompt since we'll completely fill it
        in the dynamic system prompt handler.
        
        Returns:
            Empty string as base prompt
        """
        # Return empty string as we'll fully replace it with the filled template
        # in our dynamic system prompt handler
        return ""

    def _parse_model_settings(self, config: Dict[str, str]) -> Dict[str, Any]:
        """Parse model settings from config.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary with model settings
        """
        settings = {}
        
        # Extract model settings from config
        for key, value in config.items():
            if key.startswith("model_settings."):
                setting_key = key.replace("model_settings.", "")
                settings[setting_key] = value
        
        # Add default settings if not specified
        if "temperature" not in settings and "model_settings.temperature" not in config:
            settings["temperature"] = DEFAULT_TEMPERATURE
        if "max_tokens" not in settings and "model_settings.max_tokens" not in config:
            settings["max_tokens"] = DEFAULT_MAX_TOKENS
            
        return settings
    
    def _set_usage_limits(self, config: Dict[str, str]) -> None:
        """Set usage limits from config.
        
        Args:
            config: Configuration dictionary
        """
        if not PYDANTIC_AI_AVAILABLE:
            return
            
        # Parse limits from config
        response_tokens_limit = config.get("response_tokens_limit")
        request_limit = config.get("request_limit")
        total_tokens_limit = config.get("total_tokens_limit")
        
        # Convert string values to integers
        if response_tokens_limit:
            response_tokens_limit = int(response_tokens_limit)
        if request_limit:
            request_limit = int(request_limit)
        if total_tokens_limit:
            total_tokens_limit = int(total_tokens_limit)
            
        # Create UsageLimits object
        self.dependencies.set_usage_limits(
            response_tokens_limit=response_tokens_limit,
            request_limit=request_limit,
            total_tokens_limit=total_tokens_limit
        )
    
    async def __aenter__(self):
        """Async context manager entry method."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit method."""
        await self.cleanup()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools for this agent."""
        # Web tools
        self.register_tool(web_search_tool)
        self.register_tool(webscrape_tool)
        
        # Image tools
        self.register_tool(process_image_url_tool)
        self.register_tool(process_image_binary_tool)
        
        # Audio tools
        self.register_tool(process_audio_url_tool)
        self.register_tool(process_audio_binary_tool)
        
        # Document tools
        self.register_tool(process_document_url_tool)
        self.register_tool(process_document_binary_tool)
        
        # Date/time tools
        self.register_tool(get_current_date_tool)
        self.register_tool(get_current_time_tool)
        self.register_tool(format_date_tool)
        
        # Memory tools
        self.register_tool(get_memory_tool)
        self.register_tool(store_memory_tool)
        self.register_tool(list_memories_tool)
    
    def register_tool(self, tool_func: Callable) -> None:
        """Register a tool with the agent.
        
        Args:
            tool_func: The tool function to register
        """
        name = getattr(tool_func, "__name__", str(tool_func))
        self._registered_tools[name] = tool_func
    
    async def _initialize_agent(self) -> None:
        """Initialize the underlying PydanticAI agent with dynamic system prompts."""
        if self._agent_instance is not None:
            return
            
        # Get model settings
        model_name = self.dependencies.model_name
        model_settings = self._get_model_settings()
        
        # Get available tools
        tools = []
        for name, func in self._registered_tools.items():
            if hasattr(func, "get_pydantic_tool"):
                # Use the PydanticAI tool definition if available
                tool = func.get_pydantic_tool()
                tools.append(tool)
            elif hasattr(func, "__doc__") and callable(func):
                # Create a basic wrapper for regular functions
                try:
                    doc = func.__doc__ or f"Tool for {name}"
                    # Create a simple PydanticTool
                    tool = PydanticTool(
                        name=name,
                        description=doc,
                        function=func
                    )
                    tools.append(tool)
                except Exception as e:
                    logger.error(f"Error creating tool {name}: {str(e)}")
                    
        # Create the agent
        try:
            self._agent_instance = PydanticAgent(
                model=model_name,
                system_prompt=self.system_prompt,
                tools=tools,
                model_settings=model_settings,
                deps_type=SimpleAgentDependencies
            )
            
            # Register dynamic system prompts
            self._register_system_prompts()
            
            logger.info(f"Initialized agent with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise
    
    def _register_system_prompts(self) -> None:
        """Register dynamic system prompts for template variables."""
        if not self._agent_instance:
            logger.error("Cannot register system prompts: Agent not initialized")
            return
            
        # Register a dynamic prompt handler that will replace all template variables in the prompt
        @self._agent_instance.system_prompt
        async def replace_template_variables(ctx: RunContext[SimpleAgentDependencies]) -> str:
            """Replace all template variables in the system prompt with their values."""
            template_values = {}
            variables_with_errors = []
            
            # Get run_id value
            if self.db_id:
                try:
                    from src.db.repository import increment_agent_run_id, get_agent
                    # First increment
                    increment_success = increment_agent_run_id(self.db_id)
                    if not increment_success:
                        logger.warning(f"Failed to increment run_id for agent {self.db_id}")
                    
                    # Then get updated value
                    agent = get_agent(self.db_id)
                    if agent and hasattr(agent, 'run_id'):
                        template_values["run_id"] = str(agent.run_id)
                        logger.info(f"Using run_id={agent.run_id} for prompt")
                    else:
                        template_values["run_id"] = "1"
                except Exception as e:
                    logger.error(f"Error getting run_id: {str(e)}")
                    template_values["run_id"] = "1"
                    variables_with_errors.append("run_id")
            else:
                template_values["run_id"] = "1"
                logger.warning("No agent ID available - using default run_id=1")
            
            # Get memory variables
            memory_vars = [var for var in self.template_vars if var != "run_id"]
            for var_name in memory_vars:
                try:
                    memory_content = await get_memory_tool(var_name)
                    if memory_content and not memory_content.startswith("Memory with key"):
                        template_values[var_name] = memory_content
                    else:
                        # Try to create memory if it doesn't exist and we have an agent ID
                        if self.db_id:
                            try:
                                from src.db.repository.memory import get_memory_by_name, create_memory
                                from src.db.models import Memory
                                
                                # Create memory with default value
                                memory = Memory(
                                    name=var_name,
                                    content="None stored yet",
                                    description=f"Auto-created template variable for SimpleAgent during runtime",
                                    agent_id=self.db_id,
                                    read_mode="system_prompt"
                                )
                                
                                memory_id = create_memory(memory)
                                if memory_id:
                                    logger.info(f"Created memory variable during runtime: {var_name} with ID: {memory_id}")
                                    template_values[var_name] = "None stored yet"
                                else:
                                    logger.error(f"Failed to create memory variable: {var_name}")
                                    template_values[var_name] = "None stored yet"
                                    variables_with_errors.append(var_name)
                            except Exception as e:
                                logger.error(f"Error creating memory during runtime for {var_name}: {str(e)}")
                                template_values[var_name] = "None stored yet"
                                variables_with_errors.append(var_name)
                        else:
                            template_values[var_name] = "None stored yet"
                            variables_with_errors.append(var_name)
                except Exception as e:
                    logger.error(f"Error getting memory for {var_name}: {str(e)}")
                    template_values[var_name] = "None stored yet"
                    variables_with_errors.append(var_name)
            
            # Log the values we're using
            for name, value in template_values.items():
                display_value = value[:30] + "..." if len(value) > 30 else value
                logger.info(f"Template variable {name} = {display_value}")
            
            if variables_with_errors:
                logger.warning(f"Issues with template variables: {', '.join(variables_with_errors)}")
            
            # Now generate a filled template by replacing each variable
            try:
                prompt_template = self.prompt_template
                for var_name, value in template_values.items():
                    placeholder = f"{{{{{var_name}}}}}"
                    prompt_template = prompt_template.replace(placeholder, value)
                
                # Return the filled template as the system prompt
                return prompt_template
            except Exception as e:
                logger.error(f"Error filling template: {str(e)}")
                # Return the original template as a fallback
                return self.prompt_template
    
    def _get_model_settings(self) -> Optional[ModelSettings]:
        """Get model settings for the PydanticAI agent.
        
        Returns:
            ModelSettings object with model configuration
        """
        if not PYDANTIC_AI_AVAILABLE:
            return None
            
        settings = self.dependencies.model_settings.copy()
        
        # Apply defaults if not specified
        if "temperature" not in settings:
            settings["temperature"] = DEFAULT_TEMPERATURE
        if "max_tokens" not in settings:
            settings["max_tokens"] = DEFAULT_MAX_TOKENS
        
        return ModelSettings(**settings)
    
    async def cleanup(self) -> None:
        """Clean up resources used by the agent."""
        if self.dependencies.http_client:
            await self.dependencies.close_http_client()
    
    def _check_and_ensure_memory_variables(self) -> bool:
        """Check if memory variables are properly initialized and initialize if needed.
        
        Returns:
            True if all memory variables are properly initialized, False otherwise
        """
        if not self.db_id:
            logger.warning("Cannot check memory variables: No agent ID available")
            return False
            
        try:
            from src.db.repository.memory import get_memory_by_name
            
            # Extract all variables except run_id which is handled separately
            memory_vars = [var for var in self.template_vars if var != "run_id"]
            missing_vars = []
            
            for var_name in memory_vars:
                # Check if memory exists
                existing_memory = get_memory_by_name(var_name, agent_id=self.db_id)
                
                if not existing_memory:
                    missing_vars.append(var_name)
            
            # If we found missing variables, try to initialize them
            if missing_vars:
                logger.warning(f"Found {len(missing_vars)} uninitialized memory variables: {', '.join(missing_vars)}")
                self._initialize_memory_variables_sync()
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking memory variables: {str(e)}")
            return False
            
    async def run(self, 
                 input_text: str, 
                 multimodal_content: Optional[Dict[str, Any]] = None,
                 system_message: Optional[str] = None,
                 message_history_obj: Optional['MessageHistory'] = None) -> AgentResponse:
        """Run the agent on the input text.
        
        Args:
            input_text: Text input from the user
            multimodal_content: Optional multimodal content dictionary
            system_message: Optional system message for this run
            message_history_obj: Optional MessageHistory instance for DB storage
            
        Returns:
            AgentResponse object with result and metadata
        """
        # Check and ensure memory variables are initialized if we have an agent ID
        if self.db_id:
            self._check_and_ensure_memory_variables()
            
        # Initialize agent if not done already
        await self._initialize_agent()
        
        # Get or create message history from dependencies
        pydantic_message_history = self.dependencies.get_message_history()
        
        # Check if we need multimodal support
        agent_input = input_text
        if multimodal_content:
            agent_input = self._configure_for_multimodal(input_text, multimodal_content)
        
        # If a system message is provided for this run and we don't have message history,
        # we need to reinitialize the agent with the new system prompt
        if system_message and not pydantic_message_history:
            temp_system_prompt = self.system_prompt
            self.system_prompt = system_message
            self._agent_instance = None  # Force reinitialization
            await self._initialize_agent()
            self.system_prompt = temp_system_prompt  # Restore original
            
            # Also store system prompt in database if we have MessageHistory
            if message_history_obj and system_message:
                message_history_obj.add_system_prompt(system_message, agent_id=getattr(self, "db_id", None))
        
        # If we have a MessageHistory object but no messages in dependencies,
        # check if we should add a system prompt to the database
        if message_history_obj and not pydantic_message_history and hasattr(self, "system_prompt") and self.system_prompt:
            message_history_obj.add_system_prompt(self.system_prompt, agent_id=getattr(self, "db_id", None))
            logger.info(f"Added system prompt from agent to MessageHistory")
        
        # Run the agent
        try:
            # Include usage_limits if available
            usage_limits = self.dependencies.usage_limits if hasattr(self.dependencies, "usage_limits") else None
            
            result = await self._agent_instance.run(
                agent_input,
                message_history=pydantic_message_history,
                usage_limits=usage_limits,
                deps=self.dependencies
            )
            
            # Extract tool calls and outputs safely
            tool_calls = getattr(result, "tool_calls", None)
            tool_outputs = getattr(result, "tool_outputs", None)
            
            # Store assistant response in database if we have a MessageHistory object
            if message_history_obj:
                logger.info(f"Adding assistant response to MessageHistory in the database")
                
                # Extract the response content
                response_content = result.data
                
                # Store in database
                message_history_obj.add_response(
                    content=response_content,
                    tool_calls=tool_calls,
                    tool_outputs=tool_outputs,
                    agent_id=getattr(self, "db_id", None),
                    system_prompt=self.system_prompt if hasattr(self, "system_prompt") else None
                )
            
            # Create response
            return AgentResponse(
                text=result.data,
                success=True,
                tool_calls=tool_calls,
                tool_outputs=tool_outputs,
                raw_message=result.all_messages() if hasattr(result, "all_messages") else None
            )
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}")
            logger.error(traceback.format_exc())
            return AgentResponse(
                text="An error occurred while processing your request.",
                success=False,
                error_message=str(e)
            )
    
    def _configure_for_multimodal(self, input_text: str, multimodal_content: Dict[str, Any]) -> List[Any]:
        """Configure the agent input for multimodal content.
        
        Args:
            input_text: The text input from the user
            multimodal_content: Dictionary of multimodal content
            
        Returns:
            List containing text and multimodal content objects
        """
        if not PYDANTIC_AI_AVAILABLE:
            logger.warning("Multimodal content provided but PydanticAI is not available")
            return input_text
            
        result = [input_text]
        
        # Process different content types
        for content_type, content in multimodal_content.items():
            if content_type == "image":
                if isinstance(content, str) and (content.startswith("http://") or content.startswith("https://")):
                    result.append(ImageUrl(url=content))
                else:
                    result.append(BinaryContent(data=content, media_type="image/jpeg"))
            elif content_type == "audio":
                if isinstance(content, str) and (content.startswith("http://") or content.startswith("https://")):
                    result.append(AudioUrl(url=content))
                else:
                    result.append(BinaryContent(data=content, media_type="audio/mp3"))
            elif content_type == "document":
                if isinstance(content, str) and (content.startswith("http://") or content.startswith("https://")):
                    result.append(DocumentUrl(url=content))
                else:
                    result.append(BinaryContent(data=content, media_type="application/pdf"))
            else:
                logger.warning(f"Unsupported content type: {content_type}")
                
        return result
    
    async def process_message(self, user_message: str, session_id: Optional[str] = None, agent_id: Optional[Union[int, str]] = None, user_id: int = 1, context: Optional[Dict] = None, message_history: Optional['MessageHistory'] = None) -> AgentResponse:
        """Process a user message with this agent.
        
        Args:
            user_message: User message to process
            session_id: Optional session ID
            agent_id: Optional agent ID for database tracking
            user_id: User ID
            context: Optional additional context
            message_history: Optional MessageHistory object
            
        Returns:
            Agent response
        """
        # Set session and user info in dependencies
        if session_id:
            self.dependencies.session_id = session_id
        self.dependencies.user_id = user_id
        
        # If agent_id is provided and different from the current db_id, update it
        agent_id_updated = False
        if agent_id and str(agent_id) != str(getattr(self, "db_id", None)):
            self.db_id = int(agent_id) if isinstance(agent_id, (str, int)) and str(agent_id).isdigit() else agent_id
            self.dependencies.set_agent_id(self.db_id)
            logger.info(f"Updated agent ID to {self.db_id}")
            agent_id_updated = True
            
            # Initialize memory variables if they haven't been initialized yet
            if agent_id_updated and self.template_vars:
                try:
                    self._initialize_memory_variables_sync()
                    logger.info(f"Memory variables initialized for agent ID {self.db_id}")
                except Exception as e:
                    logger.error(f"Error initializing memory variables: {str(e)}")
        
        # Extract multimodal content from context
        multimodal_content = None
        if context and "multimodal_content" in context:
            multimodal_content = context["multimodal_content"]
        
        # If message_history is provided:
        # 1. Store user message in database
        # 2. Extract messages for PydanticAI
        if message_history:
            logger.info(f"Using provided MessageHistory for session {session_id}")
            # Add user message to database
            message_history.add(user_message, agent_id=agent_id, context=context)
            # Get messages to pass to PydanticAI
            self.dependencies.set_message_history(message_history.all_messages())
        else:
            logger.info(f"No MessageHistory provided, will not store messages in database")
        
        # Reinitialize the agent if needed to use updated config
        if agent_id_updated:
            # Force agent to reinitialize with new ID
            self._agent_instance = None
            logger.info(f"Agent will be reinitialized with updated ID {self.db_id}")
        
        logger.info(f"Processing message for agent {self.db_id} with dynamic system prompts")
        
        # Run the agent with the MessageHistory object for database storage
        return await self.run(
            user_message, 
            multimodal_content=multimodal_content,
            message_history_obj=message_history
        )
        
    def register_tools(self):
        """Register tools with the agent.
        
        This method is required by BaseAgent.
        """
        # Tools are registered during initialization
        pass 