"""
LLM judge for Router agent quality evaluation.

Uses LLM-as-a-judge to evaluate Router outputs against rubrics for:
- Router-specific dimensions: delegation rationale quality, context handling coherence
- Core writing quality dimensions: clarity, relevance

Configured with low temperature for consistent, deterministic evaluation.
Judge model is configurable to avoid same-family bias.
"""

import logging

import logfire
from pydantic_ai import Agent

from evals.models import (
    AgentExecutionOutput,
    DimensionScoreOutput,
    EvaluationResult,
    JudgeModelConfig,
    JudgeProviderType,
    RouterDimension,
    RouterDimensionRubric,
    RouterJudgeResult,
    ShotgunTestCase,
)

logger = logging.getLogger(__name__)


# Default rubrics for Router evaluation dimensions
DEFAULT_RUBRICS: dict[RouterDimension, RouterDimensionRubric] = {
    RouterDimension.DELEGATION_RATIONALE: RouterDimensionRubric(
        dimension=RouterDimension.DELEGATION_RATIONALE,
        description="Quality of Router's reasoning for sub-agent selection",
        weight=1.5,  # Higher weight - core Router responsibility
        rubric_text="""
Evaluate the Router agent's delegation rationale quality on a 1-5 scale:

**Delegation Rationale Quality:**
5 (Excellent): Clear, logical reasoning that perfectly matches request type to sub-agent capabilities. Demonstrates deep understanding of each sub-agent's strengths.
4 (Good): Sound reasoning with correct sub-agent selection. Minor gaps in explaining the choice.
3 (Average): Correct sub-agent chosen but reasoning is superficial or formulaic.
2 (Fair): Questionable sub-agent choice or unclear/missing rationale.
1 (Poor): Wrong sub-agent selected with no meaningful rationale, or completely missed the request intent.

Consider:
- Did Router correctly identify the type of request (research, specification, planning, task execution, export)?
- Is the reasoning for the sub-agent choice explicit and logical?
- Does the rationale demonstrate understanding of sub-agent capabilities?
""",
    ),
    RouterDimension.CONTEXT_HANDLING: RouterDimensionRubric(
        dimension=RouterDimension.CONTEXT_HANDLING,
        description="How well Router prepares and passes context to sub-agents",
        weight=1.0,
        rubric_text="""
Evaluate the Router agent's context handling on a 1-5 scale:

**Context Handling Coherence:**
5 (Excellent): All relevant context from user request is preserved and appropriately formatted for the sub-agent. No information loss.
4 (Good): Key context is preserved with minimal loss. Sub-agent receives what it needs.
3 (Average): Basic context preserved but some nuances may be lost in handoff.
2 (Fair): Important context missing or distorted during delegation.
1 (Poor): Critical context lost, garbled, or irrelevant information passed instead.

Consider:
- Is the user's original intent preserved in the delegation?
- Are relevant details (file paths, specific requirements, constraints) passed through?
- Is context appropriately scoped for the sub-agent's role?
""",
    ),
    RouterDimension.CLARITY: RouterDimensionRubric(
        dimension=RouterDimension.CLARITY,
        description="Clarity of Router's communication to users",
        weight=1.0,
        rubric_text="""
Evaluate the Router agent's communication clarity on a 1-5 scale:

**Clarity:**
5 (Excellent): Crystal clear communication. User understands exactly what's happening and why.
4 (Good): Clear communication with minor room for improvement.
3 (Average): Understandable but could be more explicit about what Router is doing.
2 (Fair): Somewhat confusing. User may not understand the delegation decision.
1 (Poor): Unclear, cryptic, or no communication about what's happening.

Consider:
- If Router communicates with the user, is the message clear?
- Does the user understand which sub-agent is being invoked and why?
- Are any status updates or explanations easy to follow?
""",
    ),
    RouterDimension.RELEVANCE: RouterDimensionRubric(
        dimension=RouterDimension.RELEVANCE,
        description="Relevance of Router's actions to the user's request",
        weight=1.0,
        rubric_text="""
Evaluate the Router agent's relevance to the user's request on a 1-5 scale:

**Relevance:**
5 (Excellent): Router's delegation is perfectly aligned with what the user asked for.
4 (Good): Highly relevant delegation with minor tangents.
3 (Average): Generally relevant but may include unnecessary steps or miss some aspects.
2 (Fair): Partially relevant but misses key aspects of the request.
1 (Poor): Irrelevant delegation that doesn't address the user's actual need.

Consider:
- Does the delegation directly address what the user asked for?
- Are there unnecessary intermediate steps or diversions?
- Would the chosen sub-agent actually help fulfill the user's request?
""",
    ),
}


class RouterQualityJudge:
    """
    LLM-as-a-judge evaluator for Router agent quality.

    Uses structured output to evaluate Router outputs against rubrics.
    Configured with low temperature for consistent, deterministic evaluation.
    """

    def __init__(
        self,
        model_config: JudgeModelConfig | None = None,
        dimensions: list[RouterDimension] | None = None,
    ) -> None:
        """Initialize the Router quality judge.

        Args:
            model_config: Judge model configuration. Defaults to Claude Sonnet.
            dimensions: Dimensions to evaluate. Defaults to all dimensions.
        """
        self.model_config = model_config or JudgeModelConfig(
            provider=JudgeProviderType.ANTHROPIC,
            model_name="claude-sonnet-4-20250514",
            temperature=0.2,  # Low temperature for consistency
            max_tokens=2000,
        )

        self.dimensions = dimensions or list(RouterDimension)
        self.rubrics = {dim: DEFAULT_RUBRICS[dim] for dim in self.dimensions}

    def _create_judge_agent(
        self, dimension: RouterDimension
    ) -> Agent[None, DimensionScoreOutput]:
        """Create a Pydantic AI agent for a specific dimension evaluation.

        Args:
            dimension: The dimension to create a judge for

        Returns:
            Configured Agent for dimension evaluation
        """
        rubric = self.rubrics[dimension]

        system_prompt = f"""You are an expert evaluator for AI agent systems.
Your task is to evaluate a Router agent's performance on the "{dimension.value}" dimension.

{rubric.rubric_text}

Instructions:
1. Read the user's original request and the Router's response/actions carefully.
2. Apply the rubric to score the Router's performance on a 1-5 scale.
3. Provide clear reasoning for your score.
4. A score of 3 or higher indicates a passing evaluation.

Be objective and consistent in your scoring. Focus only on the {dimension.value} dimension."""

        model_string = self.model_config.to_model_string()

        # Use type: ignore because the model string is dynamically constructed
        # from configuration, so mypy can't verify it matches the literal types
        return Agent(  # type: ignore[call-overload,no-any-return]
            model=model_string,
            system_prompt=system_prompt,
            output_type=DimensionScoreOutput,
            model_settings={
                "temperature": self.model_config.temperature,
                "max_tokens": self.model_config.max_tokens,
            },
        )

    async def evaluate_dimension(
        self,
        dimension: RouterDimension,
        test_case: ShotgunTestCase,
        actual_output: AgentExecutionOutput,
    ) -> DimensionScoreOutput:
        """Evaluate a single dimension using LLM judge.

        Args:
            dimension: The dimension to evaluate
            test_case: The test case being evaluated
            actual_output: The Router's actual output

        Returns:
            DimensionScoreOutput with score, reasoning, and pass status
        """
        agent = self._create_judge_agent(dimension)

        # Construct the evaluation prompt
        prompt = f"""
**User Request:**
{test_case.inputs.prompt}

**Router Response:**
{actual_output.response}

**Router Actions:**
- Tools used: {", ".join(actual_output.tools_used) or "None"}
- Delegated to: {actual_output.delegated_sub_agent or "None"}
- Clarifying questions: {", ".join(actual_output.clarifying_questions) if actual_output.clarifying_questions else "None"}

Please evaluate the Router's performance on the "{dimension.value}" dimension."""

        with logfire.span(
            "eval.judge.dimension",
            dimension=dimension.value,
            test_case_name=test_case.name,
        ):
            result = await agent.run(prompt)
            return result.output

    async def evaluate(
        self,
        test_case: ShotgunTestCase,
        actual_output: AgentExecutionOutput,
    ) -> RouterJudgeResult:
        """Evaluate all dimensions for a Router output.

        Args:
            test_case: The test case being evaluated
            actual_output: The Router's actual output

        Returns:
            RouterJudgeResult with all dimension scores and overall assessment
        """
        with logfire.span(
            "eval.judge.router_quality",
            test_case_name=test_case.name,
            dimensions=[d.value for d in self.dimensions],
        ):
            dimension_scores: dict[str, DimensionScoreOutput] = {}

            for dimension in self.dimensions:
                try:
                    score = await self.evaluate_dimension(
                        dimension, test_case, actual_output
                    )
                    dimension_scores[dimension.value] = score
                except Exception as e:
                    logger.exception(f"Failed to evaluate dimension {dimension.value}")
                    # Provide a failing score on error
                    dimension_scores[dimension.value] = DimensionScoreOutput(
                        score=1,
                        reasoning=f"Evaluation failed: {e!s}",
                        passed=False,
                    )

            # Calculate weighted average
            total_weight = sum(self.rubrics[dim].weight for dim in self.dimensions)
            weighted_sum = sum(
                dimension_scores[dim.value].score * self.rubrics[dim].weight
                for dim in self.dimensions
            )
            overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

            # Overall pass requires all dimensions to pass and average >= 3
            overall_passed = (
                all(ds.passed for ds in dimension_scores.values())
                and overall_score >= 3.0
            )

            # Generate summary
            failed_dims = [
                dim.value
                for dim in self.dimensions
                if not dimension_scores[dim.value].passed
            ]
            if failed_dims:
                summary = f"Failed dimensions: {', '.join(failed_dims)}. Overall score: {overall_score:.2f}/5"
            else:
                summary = f"All dimensions passed. Overall score: {overall_score:.2f}/5"

            return RouterJudgeResult(
                dimension_scores=dimension_scores,
                overall_score=overall_score,
                overall_passed=overall_passed,
                summary=summary,
            )

    def convert_to_evaluation_results(
        self, judge_result: RouterJudgeResult
    ) -> list[EvaluationResult]:
        """Convert RouterJudgeResult to standard EvaluationResult models.

        Args:
            judge_result: Result from the judge evaluation

        Returns:
            List of EvaluationResult, one per dimension plus one overall
        """
        results: list[EvaluationResult] = []

        # Add per-dimension results
        for dim_name, dim_score in judge_result.dimension_scores.items():
            results.append(
                EvaluationResult(
                    evaluator_name=f"judge.{dim_name}",
                    passed=dim_score.passed,
                    score=float(dim_score.score),
                    reasoning=dim_score.reasoning,
                    dimension=dim_name,
                )
            )

        # Add overall result
        results.append(
            EvaluationResult(
                evaluator_name="judge.overall",
                passed=judge_result.overall_passed,
                score=judge_result.overall_score,
                reasoning=judge_result.summary,
                dimension="overall",
            )
        )

        return results
