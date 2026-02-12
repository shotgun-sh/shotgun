"""FileRead agent factory - lightweight agent for searching and reading files.

This agent is designed for finding and reading files (including PDFs and images)
without the overhead of full codebase understanding tools.
"""

from functools import partial

from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage

from shotgun.agents.config import ProviderType, get_provider_model
from shotgun.agents.models import (
    AgentDeps,
    AgentResponse,
    AgentRuntimeOptions,
    AgentType,
    ShotgunAgent,
)
from shotgun.logging_config import get_logger
from shotgun.prompts import PromptLoader
from shotgun.sdk.services import get_codebase_service
from shotgun.utils import ensure_shotgun_directory_exists

from .common import (
    EventStreamHandler,
    add_system_status_message,
    run_agent,
)
from .conversation.history import token_limit_compactor
from .tools import directory_lister, file_read, read_file
from .tools.file_read_tools import multimodal_file_read

logger = get_logger(__name__)

# Prompt loader instance
prompt_loader = PromptLoader()


def _build_file_read_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Build system prompt for FileRead agent."""
    template = prompt_loader.load_template("agents/file_read.j2")
    return template.render(
        interactive_mode=ctx.deps.interactive_mode,
        mode="file_read",
    )


async def create_file_read_agent(
    agent_runtime_options: AgentRuntimeOptions,
    provider: ProviderType | None = None,
) -> tuple[ShotgunAgent, AgentDeps]:
    """Create a lightweight file reading agent.

    This agent has minimal tools focused on file discovery and reading:
    - directory_lister: List directory contents
    - file_read: Read text files (from codebase tools)
    - read_file: Read files by path
    - multimodal_file_read: Read PDFs/images with BinaryContent

    Args:
        agent_runtime_options: Agent runtime options
        provider: Optional provider override

    Returns:
        Tuple of (Configured agent, Agent dependencies)
    """
    logger.debug("Initializing FileRead agent")
    ensure_shotgun_directory_exists()

    # Get configured model
    model_config = await get_provider_model(provider)
    logger.debug(
        "FileRead agent using %s model: %s",
        model_config.provider.value.upper(),
        model_config.name,
    )

    # Create minimal dependencies (no heavy codebase analysis)
    codebase_service = get_codebase_service()

    deps = AgentDeps(
        **agent_runtime_options.model_dump(),
        llm_model=model_config,
        codebase_service=codebase_service,
        system_prompt_fn=partial(_build_file_read_system_prompt),
        agent_mode=AgentType.FILE_READ,
    )

    # History processor for context management
    async def history_processor(messages: list[ModelMessage]) -> list[ModelMessage]:
        class ProcessorContext:
            def __init__(self, deps: AgentDeps):
                self.deps = deps
                self.usage = None

        ctx = ProcessorContext(deps)
        return await token_limit_compactor(ctx, messages)

    # Create agent with structured output
    model = model_config.model_instance
    agent: ShotgunAgent = Agent(
        model,
        output_type=AgentResponse,
        deps_type=AgentDeps,
        instrument=True,
        history_processors=[history_processor],
        retries=3,
    )

    # Register only file reading tools (no write tools, no codebase query tools)
    agent.tool(read_file)  # Basic file read
    agent.tool(file_read)  # Codebase file read with CWD fallback
    agent.tool(directory_lister)  # List directories
    agent.tool(multimodal_file_read)  # PDF/image reading with BinaryContent

    logger.debug("FileRead agent created with minimal tools")
    return agent, deps


def create_file_read_usage_limits() -> UsageLimits:
    """Create conservative usage limits for FileRead agent.

    FileRead should be quick - if it can't find the file in a few turns,
    it should give up.
    """
    return UsageLimits(
        request_limit=10,  # Max 10 API calls
        request_tokens_limit=50_000,  # 50k input tokens
        response_tokens_limit=8_000,  # 8k output tokens
        total_tokens_limit=60_000,  # 60k total
    )


async def run_file_read_agent(
    agent: ShotgunAgent,
    prompt: str,
    deps: AgentDeps,
    message_history: list[ModelMessage] | None = None,
    event_stream_handler: EventStreamHandler | None = None,
) -> AgentRunResult[AgentResponse]:
    """Run the FileRead agent to search for and read files.

    Args:
        agent: The configured FileRead agent
        prompt: The file search prompt (e.g., "find the user stories PDF")
        deps: Agent dependencies
        message_history: Optional message history
        event_stream_handler: Optional callback for streaming events

    Returns:
        AgentRunResult with response and files_found
    """
    logger.debug("FileRead agent searching: %s", prompt)

    message_history = await add_system_status_message(deps, message_history)

    try:
        usage_limits = create_file_read_usage_limits()

        result = await run_agent(
            agent=agent,
            prompt=prompt,
            deps=deps,
            message_history=message_history,
            usage_limits=usage_limits,
            event_stream_handler=event_stream_handler,
        )

        logger.debug("FileRead agent completed successfully")
        return result

    except Exception as e:
        logger.error("FileRead agent failed: %s", str(e))
        raise
