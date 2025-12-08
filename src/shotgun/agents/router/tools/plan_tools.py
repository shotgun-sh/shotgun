"""Plan management tools for the Router Agent.

These tools allow the router to create, read, and modify execution plans.
Plans are stored in .shotgun/execution_plan.json.
"""

import uuid

from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps
from shotgun.agents.router.models import ExecutionPlan, ExecutionStep
from shotgun.agents.router.plan_storage import delete_plan, load_plan, save_plan
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def _generate_step_id() -> str:
    """Generate a unique step ID."""
    return str(uuid.uuid4())[:8]


def _format_plan_for_display(plan: ExecutionPlan) -> str:
    """Format a plan for display to the LLM."""
    lines = [f"## Execution Plan: {plan.goal}", ""]

    for i, step in enumerate(plan.steps):
        status = "[x]" if step.done else "[ ]"
        current = " ◀" if i == plan.current_step_index and not step.done else ""
        lines.append(f"{status} **{step.title}**{current}")
        lines.append(f"    ID: {step.id}")
        if step.affects_files:
            lines.append(f"    Files: {', '.join(step.affects_files)}")

    lines.append("")
    completed = sum(1 for s in plan.steps if s.done)
    lines.append(f"Progress: {completed}/{len(plan.steps)} steps complete")

    return "\n".join(lines)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Creating plan",
    key_arg="goal",
)
async def create_plan(
    ctx: RunContext[AgentDeps],
    goal: str,
    steps: list[dict[str, str | list[str]]],
) -> str:
    """Create a new execution plan.

    Creates a new plan with the given goal and steps. Any existing plan
    will be overwritten.

    Args:
        goal: High-level goal from user request (e.g., "Implement OAuth authentication")
        steps: List of step definitions, each with:
            - title: Short title shown to user (e.g., "Research OAuth patterns")
            - objective: Detailed goal for sub-agent (hidden from user)
            - success_criteria: Optional list of completion checklist items
            - affects_files: Optional list of files this step will modify

    Returns:
        Confirmation message with plan summary
    """
    logger.debug("Creating plan with goal: %s", goal)

    execution_steps = []
    for step_def in steps:
        step_id = step_def.get("id")
        step = ExecutionStep(
            id=str(step_id) if step_id else _generate_step_id(),
            title=str(step_def.get("title", "Untitled step")),
            objective=str(step_def.get("objective", "")),
            success_criteria=[str(c) for c in step_def.get("success_criteria", []) or []],
            affects_files=[str(f) for f in step_def.get("affects_files", []) or []],
            done=False,
        )
        execution_steps.append(step)

    plan = ExecutionPlan(
        goal=goal,
        steps=execution_steps,
        current_step_index=0,
    )

    await save_plan(plan)
    logger.info("Created execution plan with %d steps", len(execution_steps))

    return f"Created plan: {goal}\n\n{_format_plan_for_display(plan)}"


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Getting plan",
    key_arg="",
)
async def get_plan(ctx: RunContext[AgentDeps]) -> str:
    """Get the current execution plan.

    Returns:
        Formatted plan summary, or message if no plan exists
    """
    logger.debug("Getting current plan")

    plan = await load_plan()
    if plan is None:
        return "No execution plan exists. Use create_plan to create one."

    return _format_plan_for_display(plan)


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Completing step",
    key_arg="step_id",
)
async def mark_step_done(ctx: RunContext[AgentDeps], step_id: str) -> str:
    """Mark a step as completed.

    Args:
        step_id: The ID of the step to mark as done

    Returns:
        Confirmation message or error if step not found
    """
    logger.debug("Marking step done: %s", step_id)

    plan = await load_plan()
    if plan is None:
        return "No execution plan exists."

    for i, step in enumerate(plan.steps):
        if step.id == step_id:
            step.done = True
            # Advance current step index if this was the current step
            if i == plan.current_step_index and i < len(plan.steps) - 1:
                plan.current_step_index = i + 1
            await save_plan(plan)
            logger.info("Marked step '%s' as done", step.title)
            return f"Marked step '{step.title}' as complete."

    return f"Step with ID '{step_id}' not found."


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Adding step",
    key_arg="title",
)
async def add_step(
    ctx: RunContext[AgentDeps],
    step: dict[str, str | list[str]],
    after_step_id: str | None = None,
) -> str:
    """Add a new step to the plan.

    Args:
        step: Step definition with title, objective, etc.
        after_step_id: Insert after this step ID, or at end if None

    Returns:
        Confirmation message with new step ID
    """
    logger.debug("Adding step after: %s", after_step_id)

    plan = await load_plan()
    if plan is None:
        return "No execution plan exists. Use create_plan first."

    step_id = step.get("id")
    new_step = ExecutionStep(
        id=str(step_id) if step_id else _generate_step_id(),
        title=str(step.get("title", "Untitled step")),
        objective=str(step.get("objective", "")),
        success_criteria=[str(c) for c in step.get("success_criteria", []) or []],
        affects_files=[str(f) for f in step.get("affects_files", []) or []],
        done=False,
    )

    if after_step_id is None:
        plan.steps.append(new_step)
        position = "at end"
    else:
        insert_index = None
        for i, s in enumerate(plan.steps):
            if s.id == after_step_id:
                insert_index = i + 1
                break

        if insert_index is None:
            return f"Step with ID '{after_step_id}' not found."

        plan.steps.insert(insert_index, new_step)
        position = f"after step '{after_step_id}'"

    await save_plan(plan)
    logger.info("Added step '%s' %s", new_step.title, position)

    return f"Added step '{new_step.title}' (ID: {new_step.id}) {position}."


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Removing step",
    key_arg="step_id",
)
async def remove_step(ctx: RunContext[AgentDeps], step_id: str) -> str:
    """Remove a step from the plan.

    Args:
        step_id: The ID of the step to remove

    Returns:
        Confirmation message or error if step not found
    """
    logger.debug("Removing step: %s", step_id)

    plan = await load_plan()
    if plan is None:
        return "No execution plan exists."

    for i, step in enumerate(plan.steps):
        if step.id == step_id:
            removed_title = step.title
            plan.steps.pop(i)

            # Adjust current step index if needed
            if plan.current_step_index >= len(plan.steps):
                plan.current_step_index = max(0, len(plan.steps) - 1)
            elif i < plan.current_step_index:
                plan.current_step_index -= 1

            await save_plan(plan)
            logger.info("Removed step '%s'", removed_title)
            return f"Removed step '{removed_title}'."

    return f"Step with ID '{step_id}' not found."


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Updating step",
    key_arg="step_id",
)
async def update_step(
    ctx: RunContext[AgentDeps],
    step_id: str,
    updates: dict[str, str | list[str] | bool],
) -> str:
    """Update fields of an existing step.

    Args:
        step_id: The ID of the step to update
        updates: Dictionary of fields to update (title, objective, success_criteria, affects_files, done)

    Returns:
        Confirmation message or error if step not found
    """
    logger.debug("Updating step: %s", step_id)

    plan = await load_plan()
    if plan is None:
        return "No execution plan exists."

    for step in plan.steps:
        if step.id == step_id:
            if "title" in updates:
                step.title = str(updates["title"])
            if "objective" in updates:
                step.objective = str(updates["objective"])
            if "success_criteria" in updates:
                criteria = updates["success_criteria"]
                step.success_criteria = [str(c) for c in criteria] if isinstance(criteria, list) else []
            if "affects_files" in updates:
                files = updates["affects_files"]
                step.affects_files = [str(f) for f in files] if isinstance(files, list) else []
            if "done" in updates:
                step.done = bool(updates["done"])

            await save_plan(plan)
            logger.info("Updated step '%s'", step.title)
            return f"Updated step '{step.title}'."

    return f"Step with ID '{step_id}' not found."


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Reordering steps",
    key_arg="",
)
async def reorder_steps(ctx: RunContext[AgentDeps], step_ids: list[str]) -> str:
    """Reorder steps in the plan.

    Args:
        step_ids: List of step IDs in the desired order

    Returns:
        Confirmation message or error if step IDs don't match
    """
    logger.debug("Reordering steps: %s", step_ids)

    plan = await load_plan()
    if plan is None:
        return "No execution plan exists."

    # Validate that all step IDs are present
    existing_ids = {step.id for step in plan.steps}
    provided_ids = set(step_ids)

    if existing_ids != provided_ids:
        missing = existing_ids - provided_ids
        extra = provided_ids - existing_ids
        errors = []
        if missing:
            errors.append(f"Missing IDs: {missing}")
        if extra:
            errors.append(f"Unknown IDs: {extra}")
        return f"Step ID mismatch. {' '.join(errors)}"

    # Create new order
    id_to_step = {step.id: step for step in plan.steps}
    plan.steps = [id_to_step[sid] for sid in step_ids]

    # Reset current step index to first incomplete step
    plan.current_step_index = 0
    for i, step in enumerate(plan.steps):
        if not step.done:
            plan.current_step_index = i
            break

    await save_plan(plan)
    logger.info("Reordered steps")

    return f"Reordered steps. New order:\n{_format_plan_for_display(plan)}"


@register_tool(
    category=ToolCategory.ARTIFACT_MANAGEMENT,
    display_text="Clearing plan",
    key_arg="",
)
async def clear_plan(ctx: RunContext[AgentDeps]) -> str:
    """Delete the current execution plan.

    Returns:
        Confirmation message
    """
    logger.debug("Clearing plan")

    deleted = await delete_plan()
    if deleted:
        return "Execution plan deleted."
    return "No execution plan to delete."
