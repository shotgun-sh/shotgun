"""LLM-based parser for .shotgun/tasks.md files.

Uses a fast sub-agent model (like Haiku) with structured output to parse
tasks.md files more flexibly than regex patterns.
"""

import logging
from pathlib import Path

from pydantic_ai import Agent

from shotgun.agents.autopilot.models import (
    ParsedTasksOutput,
    Stage,
    StageStatus,
    Task,
)
from shotgun.agents.autopilot.tasks_parser import ParsedTasksFile
from shotgun.agents.config import get_provider_model

logger = logging.getLogger(__name__)


PARSER_SYSTEM_PROMPT = """You are a markdown parser that extracts stages and tasks from a tasks.md file.

Your job is to:
1. Find all stages in the document (usually marked with ## Stage N: or ### Stage N: headers)
2. For each stage, extract all tasks (checkbox items like - [ ] or - [x])
3. Return structured data with stages and their tasks

Rules:
- A stage header contains "Stage" followed by a number and a name
- Tasks are checkbox items: - [ ] means incomplete, - [x] or - [X] means complete
- Only extract actual tasks (checkboxes), not other bullet points or text
- Preserve the exact task text after the checkbox
- Stages should be in order by their number
- Ignore any content that isn't a stage header or task checkbox

Be precise and extract all stages and tasks from the document."""


class LLMTasksParser:
    """LLM-based parser for tasks.md files.

    Uses a fast model with structured output for flexible parsing.
    """

    def __init__(self, working_directory: Path | None = None):
        """Initialize the parser.

        Args:
            working_directory: Base directory for resolving relative paths.
        """
        self.working_directory = working_directory or Path.cwd()
        self._agent: Agent[None, ParsedTasksOutput] | None = None

    async def _get_agent(self) -> Agent[None, ParsedTasksOutput]:
        """Get or create the parsing agent.

        Uses a fast sub-agent model for efficient parsing.
        """
        if self._agent is not None:
            return self._agent

        # Get a sub-agent model (cheaper/faster) with API key already configured
        try:
            model_config = await get_provider_model(for_sub_agent=True)
            model_instance = model_config.model_instance
            logger.debug("Using model for LLM parsing: %s", model_config.name)

        except Exception as e:
            logger.exception("Could not get model config for LLM parser")
            raise RuntimeError(f"Failed to initialize LLM parser: {e}") from e

        self._agent = Agent(
            model_instance,
            output_type=ParsedTasksOutput,
            system_prompt=PARSER_SYSTEM_PROMPT,
            retries=2,
        )

        return self._agent

    async def parse(
        self, file_path: str | Path = ".shotgun/tasks.md"
    ) -> ParsedTasksFile:
        """Parse a tasks.md file using the LLM.

        Args:
            file_path: Path to the tasks.md file (relative or absolute).

        Returns:
            ParsedTasksFile with stages and any parse errors.
        """
        # Resolve the file path
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.is_absolute():
            file_path = self.working_directory / file_path

        result = ParsedTasksFile(file_path=str(file_path))

        # Check if file exists
        if not file_path.exists():
            result.parse_errors.append(f"File not found: {file_path}")
            return result

        # Read the file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            result.parse_errors.append(f"Error reading file: {e}")
            return result

        # Parse using LLM
        try:
            result.stages = await self._parse_content(content)
        except Exception as e:
            logger.exception("LLM parsing failed")
            result.parse_errors.append(f"LLM parsing error: {e}")

        return result

    async def _parse_content(self, content: str) -> list[Stage]:
        """Parse content using the LLM.

        Args:
            content: The file content to parse.

        Returns:
            List of parsed Stage objects.
        """
        agent = await self._get_agent()

        # Run the agent with the content
        result = await agent.run(
            f"Parse the following tasks.md file and extract all stages and tasks:\n\n{content}"
        )

        # Convert to Stage objects
        stages: list[Stage] = []
        for parsed_stage in result.output.stages:
            tasks = [
                Task(
                    text=task.text,
                    completed=task.completed,
                    line_number=0,  # LLM doesn't track line numbers
                )
                for task in parsed_stage.tasks
            ]

            stage = Stage(
                number=parsed_stage.number,
                name=parsed_stage.name,
                tasks=tasks,
                status=StageStatus.PENDING,
            )
            stages.append(stage)

        logger.info(
            "LLM parser found %d stages with %d total tasks",
            len(stages),
            sum(len(s.tasks) for s in stages),
        )

        return stages

    async def parse_content(self, content: str) -> ParsedTasksFile:
        """Parse tasks.md content directly (for testing).

        Args:
            content: The markdown content to parse.

        Returns:
            ParsedTasksFile with stages and any parse errors.
        """
        result = ParsedTasksFile(file_path="<string>")

        try:
            result.stages = await self._parse_content(content)
        except Exception as e:
            logger.exception("LLM parsing failed")
            result.parse_errors.append(f"LLM parsing error: {e}")

        return result
