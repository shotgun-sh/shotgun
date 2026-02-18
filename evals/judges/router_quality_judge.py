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
    AllDimensionsScoreOutput,
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
        description="Quality of Router's clarifying questions - are they high-level and thoughtful?",
        weight=1.5,  # Higher weight - core Router responsibility
        rubric_text="""
Evaluate the quality of the Router's clarifying questions on a 1-5 scale:

**Clarifying Questions Quality:**
5 (Excellent): Questions are high-level, thoughtful, and would genuinely help understand what the user needs. Questions show understanding of the problem space.
4 (Good): Good questions that address important ambiguities. Minor room for improvement.
3 (Average): Reasonable questions but somewhat generic or could be more targeted.
2 (Fair): Questions are too detailed, too many, or miss obvious ambiguities.
1 (Poor): No questions asked when they were clearly needed, or questions are irrelevant/confusing.

Consider:
- Are the questions high-level (strategic) rather than low-level (implementation details)?
- Do the questions help clarify scope, goals, or constraints?
- Are there an appropriate number of questions (2-4 is ideal, not overwhelming)?

IMPORTANT: If the Router asked clarifying questions, that is generally the correct behavior for ambiguous requests. Score based on the quality of those questions, not whether they should have been asked.
""",
    ),
    RouterDimension.CONTEXT_HANDLING: RouterDimensionRubric(
        dimension=RouterDimension.CONTEXT_HANDLING,
        description="How well Router's questions capture the user's intent",
        weight=1.0,
        rubric_text="""
Evaluate how well the Router's questions capture the user's intent on a 1-5 scale:

**Intent Capture:**
5 (Excellent): Questions demonstrate clear understanding of what the user is trying to accomplish. The questions would help refine the request meaningfully.
4 (Good): Questions show good understanding with minor gaps.
3 (Average): Questions are reasonable but may miss some aspects of the user's intent.
2 (Fair): Questions seem to misunderstand what the user wants.
1 (Poor): Questions are completely off-topic or ignore the user's stated goals.

Consider:
- Do the questions relate directly to what the user asked about?
- Would answering these questions help the Router plan appropriate next steps?
- Do the questions show the Router understood the domain/context?

IMPORTANT: Asking clarifying questions is the correct behavior before taking action on complex requests. Evaluate the questions themselves, not whether delegation happened.
""",
    ),
    RouterDimension.CLARITY: RouterDimensionRubric(
        dimension=RouterDimension.CLARITY,
        description="Clarity of Router's communication and questions",
        weight=1.0,
        rubric_text="""
Evaluate the Router's communication clarity on a 1-5 scale:

**Clarity:**
5 (Excellent): Questions and any response text are crystal clear. User knows exactly what information is being requested and why.
4 (Good): Clear communication with minor room for improvement.
3 (Average): Understandable but questions could be more specific or better phrased.
2 (Fair): Somewhat confusing. User may not understand what's being asked.
1 (Poor): Unclear, cryptic, or confusing questions/response.

Consider:
- Are the clarifying questions easy to understand?
- Is it clear what kind of answer is expected for each question?
- Is the overall response well-structured and professional?
""",
    ),
    RouterDimension.RELEVANCE: RouterDimensionRubric(
        dimension=RouterDimension.RELEVANCE,
        description="Relevance of Router's questions to the user's request",
        weight=1.0,
        rubric_text="""
Evaluate the relevance of the Router's questions to the user's request on a 1-5 scale:

**Relevance:**
5 (Excellent): Every question directly relates to understanding or fulfilling the user's request. No irrelevant tangents.
4 (Good): Highly relevant questions with minor tangents.
3 (Average): Generally relevant but some questions may not be necessary.
2 (Fair): Some questions miss the point of what the user asked.
1 (Poor): Questions are irrelevant or don't help clarify the user's actual request.

Consider:
- Does each question help clarify something about the user's specific request?
- Are there questions that seem off-topic or unnecessary?
- Would these questions help the Router do what the user actually wants?
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
            model_name="claude-opus-4-6",
            temperature=0.2,  # Low temperature for consistency
            max_tokens=2000,
        )

        self.dimensions = dimensions or list(RouterDimension)
        self.rubrics = {dim: DEFAULT_RUBRICS[dim] for dim in self.dimensions}

    def _create_combined_judge_agent(self) -> Agent[None, AllDimensionsScoreOutput]:
        """Create a Pydantic AI agent that evaluates all dimensions in one call.

        Returns:
            Configured Agent for combined dimension evaluation
        """
        # Build rubrics section with all dimensions
        rubrics_section = ""
        for dimension in self.dimensions:
            rubric = self.rubrics[dimension]
            tag_name = f"{dimension.value.upper()}_RUBRIC"
            rubrics_section += f"""
<{tag_name}>
{rubric.rubric_text}
</{tag_name}>
"""

        system_prompt = f"""You are an expert evaluator for AI agent systems.
Evaluate the Router agent's performance on ALL of the following dimensions.

For EACH dimension you must provide:
- score: 1-5 (where 3+ is passing)
- reasoning: Clear explanation justifying the score
- passed: true if score >= 3, false otherwise

{rubrics_section}

<INSTRUCTIONS>
1. Read the USER_REQUEST and the ROUTER_RESPONSE carefully.
2. If EXPECTED_RESPONSE_CRITERIA is provided, use it as guidance for what a good response looks like.
3. Apply each RUBRIC to score the Router's performance on that dimension.
4. Provide clear, specific reasoning for each score.
5. Evaluate each dimension independently.
</INSTRUCTIONS>

Be objective and consistent in your scoring."""

        model_string = self.model_config.to_model_string()

        return Agent(  # type: ignore[call-overload,no-any-return]
            model=model_string,
            system_prompt=system_prompt,
            output_type=AllDimensionsScoreOutput,
            model_settings={
                "temperature": self.model_config.temperature,
                "max_tokens": self.model_config.max_tokens,
            },
        )

    def _format_message_history(self, test_case: ShotgunTestCase) -> str:
        """Format message history for the judge prompt.

        Args:
            test_case: Test case containing message history

        Returns:
            Formatted string representation of the conversation history
        """
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        if not test_case.inputs.message_history:
            return ""

        lines = []
        for msg in test_case.inputs.message_history:
            if isinstance(msg, ModelRequest):
                for req_part in msg.parts:
                    if isinstance(req_part, UserPromptPart):
                        lines.append(f"USER: {req_part.content}")
                    elif isinstance(req_part, ToolReturnPart):
                        # Skip tool returns in the display
                        pass
            elif isinstance(msg, ModelResponse):
                for resp_part in msg.parts:
                    if isinstance(resp_part, TextPart):
                        lines.append(f"ROUTER: {resp_part.content}")
                    elif isinstance(resp_part, ToolCallPart):
                        if resp_part.tool_name == "final_result":
                            args = resp_part.args
                            if isinstance(args, dict):
                                if args.get("response"):
                                    lines.append(f"ROUTER: {args['response']}")
                                if args.get("clarifying_questions"):
                                    questions = args["clarifying_questions"]
                                    lines.append(
                                        f"ROUTER QUESTIONS: {', '.join(questions)}"
                                    )

        if not lines:
            return ""

        return "\n".join(lines)

    async def evaluate(
        self,
        test_case: ShotgunTestCase,
        actual_output: AgentExecutionOutput,
    ) -> RouterJudgeResult:
        """Evaluate all dimensions for a Router output in a single LLM call.

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
            # Build the evaluation prompt
            expected_response_section = ""
            if test_case.expected.expected_response:
                expected_response_section = f"""
<EXPECTED_RESPONSE_CRITERIA>
{test_case.expected.expected_response}
</EXPECTED_RESPONSE_CRITERIA>
"""

            # Include conversation history if available
            conversation_history = self._format_message_history(test_case)
            conversation_section = ""
            if conversation_history:
                conversation_section = f"""
<CONVERSATION_HISTORY>
{conversation_history}
</CONVERSATION_HISTORY>
"""

            clarifying_questions = (
                ", ".join(actual_output.clarifying_questions)
                if actual_output.clarifying_questions
                else "None"
            )

            prompt = f"""
{conversation_section}<USER_REQUEST>
{test_case.inputs.prompt}
</USER_REQUEST>

<ROUTER_RESPONSE>
{actual_output.response}
</ROUTER_RESPONSE>

<ROUTER_ACTIONS>
Tools used: {", ".join(actual_output.tools_used) or "None"}
Delegated to: {actual_output.delegated_sub_agent or "None"}
Clarifying questions: {clarifying_questions}
</ROUTER_ACTIONS>
{expected_response_section}
Evaluate the Router's performance on all dimensions."""

            # Create combined agent and make single LLM call
            agent = self._create_combined_judge_agent()

            try:
                result = await agent.run(prompt)
                combined_output = result.output

                # Extract dimension scores from combined output
                dimension_scores: dict[str, DimensionScoreOutput] = {
                    "delegation_rationale": combined_output.delegation_rationale,
                    "context_handling": combined_output.context_handling,
                    "clarity": combined_output.clarity,
                    "relevance": combined_output.relevance,
                }
            except Exception as e:
                logger.exception("Failed to evaluate dimensions")
                # Provide failing scores on error
                dimension_scores = {
                    dim.value: DimensionScoreOutput(
                        score=1,
                        reasoning=f"Evaluation failed: {e!s}",
                        passed=False,
                    )
                    for dim in self.dimensions
                }

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
