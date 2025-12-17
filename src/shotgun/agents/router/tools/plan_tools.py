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
from shotgun.posthog_telemetry import track_event

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
        # Plan is NOT executing yet - user must approve first
        ctx.deps.is_executing = False
        logger.debug(
            "Set pending approval for plan with %d steps",
            len(steps),
        )
    else:
        # Single-step plans or Drafting mode - skip approval and start executing
        ctx.deps.approval_status = PlanApprovalStatus.SKIPPED
        ctx.deps.is_executing = True
        logger.debug("Plan approved automatically, is_executing=True")

    logger.info(
        "Created execution plan with %d steps: %s",
        len(steps),
        input.goal,
    )

    # Track plan creation metric
    track_event(
        "plan_created",
        {
            "step_count": len(steps),
            "goal_preview": input.goal[:100],
            "requires_approval": plan.needs_approval(),
            "router_mode": ctx.deps.router_mode.value,
        },
    )

    _notify_plan_changed(ctx.deps)

    # Return different message based on whether approval is needed
    if ctx.deps.pending_approval is not None:
        return ToolResult(
            success=True,
            message=f"Created plan with {len(steps)} steps. Goal: {input.goal}\n\n"
            "IMPORTANT: This plan requires user approval before execution. "
            "You MUST call final_result NOW to present this plan to the user. "
            "Do NOT attempt to delegate or execute any steps yet.",
        )

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
    for step_index, step in enumerate(plan.steps):
        if step.id == input.step_id:
            step.done = True
            logger.info("Marked step '%s' as done", input.step_id)

            # Track step completion metric
            completed_count = sum(1 for s in plan.steps if s.done)
            track_event(
                "plan_step_completed",
                {
                    "step_position": step_index + 1,  # 1-indexed for human readability
                    "total_steps": len(plan.steps),
                    "steps_remaining": len(plan.steps) - completed_count,
                },
            )

            # Advance current_step_index to next incomplete step
            while (
                plan.current_step_index < len(plan.steps)
                and plan.steps[plan.current_step_index].done
            ):
                plan.current_step_index += 1

            # Check if plan is complete
            if plan.is_complete():
                ctx.deps.is_executing = False
                logger.debug("Plan complete, is_executing=False")

                # Track plan completion metric
                track_event(
                    "plan_completed",
                    {
                        "step_count": len(plan.steps),
                    },
                )

                # Set pending completion for Drafting mode
                # The TUI will detect this and show the completion message
                if ctx.deps.router_mode == RouterMode.DRAFTING:
                    ctx.deps.pending_completion = True
                    logger.debug("Set pending_completion=True for drafting mode")
            # Set pending checkpoint for Planning mode
            # The TUI will detect this and show the StepCheckpointWidget
            elif ctx.deps.router_mode == RouterMode.PLANNING:
                # Use current_step() since the while loop above already advanced
                # current_step_index to the next incomplete step
                next_step = plan.current_step()
                ctx.deps.pending_checkpoint = PendingCheckpoint(
                    completed_step=step, next_step=next_step
                )
                logger.debug(
                    "Set pending checkpoint: completed='%s', next='%s'",
                    step.title,
                    next_step.title if next_step else None,
                )

            _notify_plan_changed(ctx.deps)

            # Return different messages based on mode and plan state
            if plan.is_complete():
                return ToolResult(
                    success=True,
                    message=f"Marked step '{step.title}' as complete.\n\n"
                    "All plan steps are now complete. You may return your final response.",
                )
            elif ctx.deps.router_mode == RouterMode.DRAFTING:
                next_step = plan.current_step()
                return ToolResult(
                    success=True,
                    message=f"Marked step '{step.title}' as complete.\n\n"
                    f"NEXT STEP: {next_step.title if next_step else 'None'}\n"
                    "IMPORTANT: Do NOT call final_result. "
                    "Immediately delegate the next step.",
                )
            else:
                # Planning mode - checkpoint will be shown
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

        # Track step added metric
        track_event(
            "plan_step_added",
            {
                "new_step_count": len(plan.steps),
                "position": len(plan.steps),  # Appended at end
            },
        )

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

            # Track step added metric
            track_event(
                "plan_step_added",
                {
                    "new_step_count": len(plan.steps),
                    "position": i + 2,  # 1-indexed, inserted after position i+1
                },
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

            # Track step removed metric
            track_event(
                "plan_step_removed",
                {
                    "new_step_count": len(plan.steps),
                },
            )

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
