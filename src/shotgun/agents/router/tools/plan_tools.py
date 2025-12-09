"""Plan management tools for the Router agent.

These tools allow the router to create and manage execution plans.
All tools use Pydantic models for inputs and outputs.

IMPORTANT: There is NO get_plan() tool - the plan is shown in the system
status message every turn so the router always has visibility into it.
"""

from pydantic_ai import RunContext

from shotgun.agents.router.models import (
    AddStepInput,
    CreatePlanInput,
    ExecutionPlan,
    ExecutionStep,
    MarkStepDoneInput,
    PendingApproval,
    PendingCheckpoint,
    PlanApprovalStatus,
    RemoveStepInput,
    RouterDeps,
    RouterMode,
    ToolResult,
)
from shotgun.agents.tools.registry import ToolCategory, register_tool
from shotgun.logging_config import get_logger

logger = get_logger(__name__)


def _notify_plan_changed(deps: RouterDeps) -> None:
    """Notify TUI of plan changes via callback if registered.

    This helper is called after any plan modification to update the
    Plan Panel widget in the TUI.

    Args:
        deps: RouterDeps containing the on_plan_changed callback.
    """
    if deps.on_plan_changed:
        deps.on_plan_changed(deps.current_plan)


@register_tool(
    category=ToolCategory.PLANNING,
    display_text="Creating execution plan",
    key_arg="input",
)
async def create_plan(
    ctx: RunContext[RouterDeps], input: CreatePlanInput
) -> ToolResult:
    """Create a new execution plan for the current task.

    This replaces any existing plan. The plan is stored in-memory in RouterDeps,
    NOT in a file. It will be shown in the system status message.

    Args:
        ctx: RunContext with RouterDeps
        input: CreatePlanInput with goal and steps

    Returns:
        ToolResult indicating success or failure
    """
    logger.debug("Creating execution plan with goal: %s", input.goal)

    # Convert step inputs to ExecutionStep objects
    steps = [
        ExecutionStep(
            id=step_input.id,
            title=step_input.title,
            objective=step_input.objective,
            done=False,
        )
        for step_input in input.steps
    ]

    # Create and store the plan
    plan = ExecutionPlan(
        goal=input.goal,
        steps=steps,
        current_step_index=0,
    )

    ctx.deps.current_plan = plan

    # Set pending approval for multi-step plans in Planning mode
    # The TUI will detect this and show the PlanApprovalWidget
    if ctx.deps.router_mode == RouterMode.PLANNING and plan.needs_approval():
        ctx.deps.pending_approval = PendingApproval(plan=plan)
        ctx.deps.approval_status = PlanApprovalStatus.PENDING
        logger.debug(
            "Set pending approval for plan with %d steps",
            len(steps),
        )
    else:
        # Single-step plans or Drafting mode - skip approval
        ctx.deps.approval_status = PlanApprovalStatus.SKIPPED

    logger.info(
        "Created execution plan with %d steps: %s",
        len(steps),
        input.goal,
    )

    _notify_plan_changed(ctx.deps)

    return ToolResult(
        success=True,
        message=f"Created plan with {len(steps)} steps. Goal: {input.goal}",
    )


@register_tool(
    category=ToolCategory.PLANNING,
    display_text="Marking step complete",
    key_arg="input",
)
async def mark_step_done(
    ctx: RunContext[RouterDeps], input: MarkStepDoneInput
) -> ToolResult:
    """Mark a step in the execution plan as complete.

    Args:
        ctx: RunContext with RouterDeps
        input: MarkStepDoneInput with step_id

    Returns:
        ToolResult indicating success or failure
    """
    plan = ctx.deps.current_plan

    if plan is None:
        return ToolResult(
            success=False,
            message="No execution plan exists. Create a plan first.",
        )

    # Find the step by ID
    for _i, step in enumerate(plan.steps):
        if step.id == input.step_id:
            step.done = True
            logger.info("Marked step '%s' as done", input.step_id)

            # Advance current_step_index to next incomplete step
            while (
                plan.current_step_index < len(plan.steps)
                and plan.steps[plan.current_step_index].done
            ):
                plan.current_step_index += 1

            # Set pending checkpoint for Planning mode
            # The TUI will detect this and show the StepCheckpointWidget
            if ctx.deps.router_mode == RouterMode.PLANNING:
                next_step = plan.next_step()
                ctx.deps.pending_checkpoint = PendingCheckpoint(
                    completed_step=step, next_step=next_step
                )
                logger.debug(
                    "Set pending checkpoint: completed='%s', next='%s'",
                    step.title,
                    next_step.title if next_step else None,
                )

            _notify_plan_changed(ctx.deps)

            return ToolResult(
                success=True,
                message=f"Marked step '{step.title}' as complete.",
            )

    return ToolResult(
        success=False,
        message=f"Step with ID '{input.step_id}' not found in plan.",
    )


@register_tool(
    category=ToolCategory.PLANNING,
    display_text="Adding step to plan",
    key_arg="input",
)
async def add_step(ctx: RunContext[RouterDeps], input: AddStepInput) -> ToolResult:
    """Add a new step to the execution plan.

    The step can be inserted after a specific step (by ID) or appended to the end.

    Args:
        ctx: RunContext with RouterDeps
        input: AddStepInput with step details and optional after_step_id

    Returns:
        ToolResult indicating success or failure
    """
    plan = ctx.deps.current_plan

    if plan is None:
        return ToolResult(
            success=False,
            message="No execution plan exists. Create a plan first.",
        )

    # Check for duplicate ID
    existing_ids = {step.id for step in plan.steps}
    if input.step.id in existing_ids:
        return ToolResult(
            success=False,
            message=f"Step with ID '{input.step.id}' already exists in plan.",
        )

    # Create the new step
    new_step = ExecutionStep(
        id=input.step.id,
        title=input.step.title,
        objective=input.step.objective,
        done=False,
    )

    # Insert at the specified position
    if input.after_step_id is None:
        # Append to end
        plan.steps.append(new_step)
        logger.info("Appended step '%s' to end of plan", input.step.id)

        _notify_plan_changed(ctx.deps)

        return ToolResult(
            success=True,
            message=f"Added step '{new_step.title}' at end of plan.",
        )

    # Find the position to insert after
    for i, step in enumerate(plan.steps):
        if step.id == input.after_step_id:
            plan.steps.insert(i + 1, new_step)
            logger.info(
                "Inserted step '%s' after '%s'",
                input.step.id,
                input.after_step_id,
            )

            _notify_plan_changed(ctx.deps)

            return ToolResult(
                success=True,
                message=f"Added step '{new_step.title}' after '{step.title}'.",
            )

    return ToolResult(
        success=False,
        message=f"Step with ID '{input.after_step_id}' not found in plan.",
    )


@register_tool(
    category=ToolCategory.PLANNING,
    display_text="Removing step from plan",
    key_arg="input",
)
async def remove_step(
    ctx: RunContext[RouterDeps], input: RemoveStepInput
) -> ToolResult:
    """Remove a step from the execution plan.

    Args:
        ctx: RunContext with RouterDeps
        input: RemoveStepInput with step_id

    Returns:
        ToolResult indicating success or failure
    """
    plan = ctx.deps.current_plan

    if plan is None:
        return ToolResult(
            success=False,
            message="No execution plan exists. Create a plan first.",
        )

    # Find and remove the step
    for i, step in enumerate(plan.steps):
        if step.id == input.step_id:
            removed_step = plan.steps.pop(i)
            logger.info("Removed step '%s' from plan", input.step_id)

            # Adjust current_step_index if needed
            if plan.current_step_index > i:
                plan.current_step_index -= 1
            elif plan.current_step_index >= len(plan.steps):
                plan.current_step_index = max(0, len(plan.steps) - 1)

            _notify_plan_changed(ctx.deps)

            return ToolResult(
                success=True,
                message=f"Removed step '{removed_step.title}' from plan.",
            )

    return ToolResult(
        success=False,
        message=f"Step with ID '{input.step_id}' not found in plan.",
    )
