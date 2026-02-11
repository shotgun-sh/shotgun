"""Dependency graph computation for parallel stage execution.

This module provides pure-Python dependency graph analysis for stages,
enabling the autopilot to determine which stages can run in parallel.
"""

import logging
from collections import deque
from enum import StrEnum

from pydantic import BaseModel, Field

from shotgun.agents.autopilot.models import Stage, StageStatus

logger = logging.getLogger(__name__)


class ExecutionBatch(BaseModel):
    """A group of stages that can execute in parallel.

    All stages in a batch have their dependencies satisfied and
    can run concurrently.
    """

    level: int = Field(description="Topological level (0 = no dependencies)")
    stage_numbers: list[str] = Field(description="Stage identifiers in this batch")


class ExecutionPlan(BaseModel):
    """Complete execution plan with ordered batches."""

    batches: list[ExecutionBatch] = Field(
        default_factory=list, description="Ordered list of execution batches"
    )

    @property
    def total_batches(self) -> int:
        """Total number of batches."""
        return len(self.batches)

    @property
    def total_stages(self) -> int:
        """Total number of stages across all batches."""
        return sum(len(b.stage_numbers) for b in self.batches)


class DependencyErrorType(StrEnum):
    """Types of dependency validation errors."""

    CYCLE = "cycle"
    MISSING_REF = "missing_ref"


class DependencyError(BaseModel):
    """Error found during dependency validation."""

    error_type: DependencyErrorType = Field(description="Type of dependency error")
    details: str = Field(description="Human-readable error description")


def validate_dependencies(stages: list[Stage]) -> list[DependencyError]:
    """Validate the dependency graph for cycles and missing references.

    Args:
        stages: List of stages to validate.

    Returns:
        List of DependencyError objects. Empty list means valid graph.
    """
    errors: list[DependencyError] = []
    stage_numbers = {s.number for s in stages}

    # Check for missing references
    for stage in stages:
        for dep in stage.depends_on:
            if dep not in stage_numbers:
                errors.append(
                    DependencyError(
                        error_type=DependencyErrorType.MISSING_REF,
                        details=f"Stage {stage.number} depends on Stage {dep}, which does not exist",
                    )
                )

    # Check for cycles using Kahn's algorithm
    # If we can't process all nodes, there's a cycle
    in_degree: dict[str, int] = {s.number: 0 for s in stages}
    adjacency: dict[str, list[str]] = {s.number: [] for s in stages}

    for stage in stages:
        for dep in stage.depends_on:
            if dep in stage_numbers:  # Only count valid refs
                in_degree[stage.number] += 1
                adjacency[dep].append(stage.number)

    queue: deque[str] = deque()
    for number, degree in in_degree.items():
        if degree == 0:
            queue.append(number)

    processed = 0
    while queue:
        node = queue.popleft()
        processed += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if processed < len(stages):
        # Find stages involved in cycles
        cycle_stages = [num for num, deg in in_degree.items() if deg > 0]
        errors.append(
            DependencyError(
                error_type=DependencyErrorType.CYCLE,
                details=f"Dependency cycle detected involving stages: {', '.join(sorted(cycle_stages))}",
            )
        )

    return errors


def compute_execution_batches(
    stages: list[Stage],
    *,
    skip_completed: bool = True,
) -> ExecutionPlan:
    """Compute execution batches using topological sort (Kahn's algorithm).

    Groups stages into levels where all stages in a level can execute
    in parallel because their dependencies are satisfied.

    Args:
        stages: List of stages with dependency information.
        skip_completed: If True, exclude completed/skipped stages from batches.

    Returns:
        ExecutionPlan with ordered batches of parallelizable stages.
    """
    # Filter stages based on status
    if skip_completed:
        active_stages = [
            s
            for s in stages
            if s.status not in (StageStatus.COMPLETED, StageStatus.SKIPPED)
        ]
        completed_numbers = {
            s.number
            for s in stages
            if s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
        }
    else:
        active_stages = list(stages)
        completed_numbers = set()

    if not active_stages:
        return ExecutionPlan(batches=[])

    active_numbers = {s.number for s in active_stages}

    # Build in-degree map (only counting active dependencies)
    in_degree: dict[str, int] = {s.number: 0 for s in active_stages}
    adjacency: dict[str, list[str]] = {s.number: [] for s in active_stages}

    for stage in active_stages:
        for dep in stage.depends_on:
            if dep in completed_numbers:
                # Dependency already satisfied, don't count it
                continue
            if dep in active_numbers:
                in_degree[stage.number] += 1
                adjacency[dep].append(stage.number)

    # BFS level-by-level (Kahn's algorithm with level tracking)
    batches: list[ExecutionBatch] = []
    current_level: list[str] = [num for num, deg in in_degree.items() if deg == 0]
    level = 0

    while current_level:
        batches.append(ExecutionBatch(level=level, stage_numbers=sorted(current_level)))

        next_level: list[str] = []
        for node in current_level:
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_level.append(neighbor)

        current_level = next_level
        level += 1

    logger.info(
        "Computed %d execution batches from %d active stages",
        len(batches),
        len(active_stages),
    )
    for batch in batches:
        logger.info(
            "  Batch level %d: stages %s",
            batch.level,
            batch.stage_numbers,
        )

    return ExecutionPlan(batches=batches)


def get_ready_stages(stages: list[Stage]) -> list[Stage]:
    """Get stages that are ready to execute (all dependencies satisfied).

    A stage is ready if:
    - Its status is PENDING
    - All stages it depends on are COMPLETED

    Args:
        stages: All stages in the plan.

    Returns:
        List of stages ready to execute.
    """
    completed_numbers = {
        s.number
        for s in stages
        if s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
    }

    ready: list[Stage] = []
    for stage in stages:
        if stage.status != StageStatus.PENDING:
            continue
        # Check if all dependencies are satisfied
        if all(dep in completed_numbers for dep in stage.depends_on):
            ready.append(stage)

    return ready
