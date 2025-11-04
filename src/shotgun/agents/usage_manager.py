import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import TypeAlias

import aiofiles
import aiofiles.os
from genai_prices import calc_price
from pydantic import BaseModel, Field
from pydantic_ai import RunUsage

from shotgun.agents.config.models import ProviderType
from shotgun.utils import get_shotgun_home

logger = getLogger(__name__)
ModelName: TypeAlias = str


@dataclass(frozen=True)
class UsageSummaryEntry:
    model_name: ModelName
    provider: ProviderType
    usage: RunUsage


class UsageLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    model_name: ModelName
    usage: RunUsage
    provider: ProviderType


class SessionUsage(BaseModel):
    usage: RunUsage
    log: list[UsageLogEntry]


class UsageState(BaseModel):
    usage: dict[ModelName, RunUsage] = Field(default_factory=dict)
    model_providers: dict[ModelName, ProviderType] = Field(default_factory=dict)
    usage_log: list[UsageLogEntry] = Field(default_factory=list)


class SessionUsageManager:
    def __init__(self) -> None:
        self.usage: defaultdict[ModelName, RunUsage] = defaultdict(RunUsage)
        self._model_providers: dict[ModelName, ProviderType] = {}
        self._usage_log: list[UsageLogEntry] = []
        self._usage_path: Path = get_shotgun_home() / "usage.json"
        # Note: restore_usage_state needs to be called asynchronously after init
        # Caller should use: manager = SessionUsageManager(); await manager.restore_usage_state()

    async def add_usage(
        self, usage: RunUsage, *, model_name: ModelName, provider: ProviderType
    ) -> None:
        self.usage[model_name] += usage
        self._model_providers[model_name] = provider
        self._usage_log.append(
            UsageLogEntry(model_name=model_name, usage=usage, provider=provider)
        )
        await self.persist_usage_state()

    def get_usage_report(self) -> dict[ModelName, RunUsage]:
        return self.usage.copy()

    def get_usage_breakdown(self) -> list[UsageSummaryEntry]:
        breakdown: list[UsageSummaryEntry] = []
        for model_name, usage in self.usage.items():
            provider = self._model_providers.get(model_name)
            if provider is None:
                continue
            breakdown.append(
                UsageSummaryEntry(model_name=model_name, provider=provider, usage=usage)
            )
        breakdown.sort(key=lambda entry: entry.model_name.lower())
        return breakdown

    def build_usage_hint(self) -> str | None:
        return format_usage_hint(self.get_usage_breakdown())

    async def persist_usage_state(self) -> None:
        state = UsageState(
            usage=dict(self.usage.items()),
            model_providers=self._model_providers.copy(),
            usage_log=self._usage_log.copy(),
        )

        try:
            await aiofiles.os.makedirs(self._usage_path.parent, exist_ok=True)
            json_content = json.dumps(state.model_dump(mode="json"), indent=2)
            async with aiofiles.open(self._usage_path, "w", encoding="utf-8") as f:
                await f.write(json_content)
            logger.debug("Usage state persisted to %s", self._usage_path)
        except Exception as exc:
            logger.error(
                "Failed to persist usage state to %s: %s", self._usage_path, exc
            )

    async def restore_usage_state(self) -> None:
        if not await aiofiles.os.path.exists(self._usage_path):
            logger.debug("No usage state file found at %s", self._usage_path)
            return

        try:
            async with aiofiles.open(self._usage_path, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            state = UsageState.model_validate(data)
        except Exception as exc:
            logger.error(
                "Failed to restore usage state from %s: %s", self._usage_path, exc
            )
            return

        self.usage = defaultdict(RunUsage)
        for model_name, usage in state.usage.items():
            self.usage[model_name] = usage

        self._model_providers = state.model_providers.copy()
        self._usage_log = state.usage_log.copy()


def format_usage_hint(breakdown: list[UsageSummaryEntry]) -> str | None:
    if not breakdown:
        return None

    lines = ["# Token usage by model"]

    for entry in breakdown:
        usage = entry.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        cached_tokens = usage.cache_read_tokens

        cost = calc_price(usage=usage, model_ref=entry.model_name)
        input_line = f"* Input: {input_tokens:,}"
        if cached_tokens > 0:
            input_line += f" (+ {cached_tokens:,} cached)"
        input_line += " tokens"
        section = f"""
### {entry.model_name}

{input_line}
* Output: {output_tokens:,} tokens
* Total: {input_tokens + output_tokens:,} tokens
* Cost: ${cost.total_price:,.2f}
""".strip()
        lines.append(section)

    return "\n\n".join(lines)


_usage_manager = None


def get_session_usage_manager() -> SessionUsageManager:
    global _usage_manager
    if _usage_manager is None:
        _usage_manager = SessionUsageManager()
    return _usage_manager
