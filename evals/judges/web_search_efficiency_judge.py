"""
LLM judge for evaluating web search efficiency in drafting mode.

Uses LLM-as-a-judge to evaluate Router outputs for web search behavior:
- Is the number of web searches reasonable for the task?
- Are the search queries varied or repetitive?
- Did the searches contribute to task completion?

This judge is designed to detect excessive or looping web search behavior,
which can occur in drafting mode when the agent keeps searching instead of
producing output.
"""

import logging
from enum import StrEnum

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from evals.models import (
    AgentExecutionOutput,
    DimensionScoreOutput,
    EvaluationResult,
    JudgeModelConfig,
    JudgeProviderType,
    ShotgunTestCase,
)

logger = logging.getLogger(__name__)


class WebSearchEfficiencyDimension(StrEnum):
    """Dimensions for evaluating web search efficiency."""

    SEARCH_COUNT_REASONABLENESS = "search_count_reasonableness"
    QUERY_DIVERSITY = "query_diversity"
    TASK_COMPLETION = "task_completion"


class WebSearchEfficiencyDimensionRubric(BaseModel):
    """Rubric definition for a web search efficiency evaluation dimension."""

    dimension: WebSearchEfficiencyDimension
    description: str
    weight: float = 1.0
    rubric_text: str


class WebSearchEfficiencyScoreOutput(BaseModel):
    """Output structure for all web search efficiency dimension scores."""

    search_count_reasonableness: DimensionScoreOutput = Field(
        description="Score for whether search count is appropriate for the task"
    )
    query_diversity: DimensionScoreOutput = Field(
        description="Score for query variety vs repetition"
    )
    task_completion: DimensionScoreOutput = Field(
        description="Score for whether searches contributed to completion"
    )


class WebSearchEfficiencyJudgeResult(BaseModel):
    """Result from web search efficiency judge evaluation."""

    dimension_scores: dict[str, DimensionScoreOutput]
    overall_score: float
    overall_passed: bool
    summary: str


# Default rubrics for web search efficiency evaluation dimensions
DEFAULT_WEB_SEARCH_EFFICIENCY_RUBRICS: dict[
    WebSearchEfficiencyDimension, WebSearchEfficiencyDimensionRubric
] = {
    WebSearchEfficiencyDimension.SEARCH_COUNT_REASONABLENESS: (
        WebSearchEfficiencyDimensionRubric(
            dimension=WebSearchEfficiencyDimension.SEARCH_COUNT_REASONABLENESS,
            description="Is the number of web searches appropriate for the task?",
            weight=1.5,  # Highest weight - core behavior being tested
            rubric_text="""
Evaluate if the number of web searches is reasonable for the task on a 1-5 scale:

**Search Count Reasonableness:**
5 (Excellent): 0-5 searches for a simple task. Focused, efficient research.
4 (Good): 6-10 searches. Reasonable amount for moderate complexity tasks.
3 (Average): 11-15 searches. Borderline excessive but might be justified for complex topics.
2 (Fair): 16-20 searches. Likely excessive, may indicate inefficient searching.
1 (Poor): 21+ searches. Excessive searching, likely indicates a loop or pathological behavior.

Consider:
- Task complexity: Simple spec requests should need fewer searches than complex multi-topic research
- Search efficiency: Did the agent get useful information early or keep searching?
- Signs of looping: Repeated similar queries, searches that don't add value
- Drafting mode context: Agent should produce output, not endlessly research
""",
        )
    ),
    WebSearchEfficiencyDimension.QUERY_DIVERSITY: WebSearchEfficiencyDimensionRubric(
        dimension=WebSearchEfficiencyDimension.QUERY_DIVERSITY,
        description="Were the search queries varied or repetitive?",
        weight=1.0,
        rubric_text="""
Evaluate the diversity and quality of search queries on a 1-5 scale:

**Query Diversity:**
5 (Excellent): Each search query is unique and targets different aspects of the problem.
4 (Good): Mostly unique queries with minor overlap, good coverage of the topic.
3 (Average): Some repeated or similar queries, but still covers needed ground.
2 (Fair): Many repeated or near-duplicate queries, inefficient searching.
1 (Poor): Mostly identical queries repeated, clear sign of pathological behavior.

Consider:
- Are queries meaningfully different from each other?
- Do they cover different aspects of the task?
- Is there evidence of refinement (learning from previous results)?
- Or is the agent just repeating the same searches?
""",
    ),
    WebSearchEfficiencyDimension.TASK_COMPLETION: WebSearchEfficiencyDimensionRubric(
        dimension=WebSearchEfficiencyDimension.TASK_COMPLETION,
        description="Did the searches contribute to completing the task?",
        weight=1.0,
        rubric_text="""
Evaluate if the searches contributed to task completion on a 1-5 scale:

**Task Completion:**
5 (Excellent): Searches clearly informed a well-structured, complete response. Research was productive.
4 (Good): Response shows evidence of research usage, task substantially completed.
3 (Average): Some research used, but response could be better. Task partially completed.
2 (Fair): Extensive searching but weak final output. Poor research utilization.
1 (Poor): Many searches but no meaningful output, or task not addressed at all.

Consider:
- Did the agent produce a coherent spec/plan/response?
- Is there evidence the search results were synthesized?
- Did searching lead to productive output, or just more searching?
- In drafting mode, the goal is to produce deliverables, not research indefinitely
""",
    ),
}


class WebSearchEfficiencyJudge:
    """
    LLM-as-a-judge evaluator for web search efficiency.

    Uses structured output to evaluate Router outputs against rubrics
    specific to web search behavior in drafting mode.
    """

    def __init__(
        self,
        model_config: JudgeModelConfig | None = None,
        dimensions: list[WebSearchEfficiencyDimension] | None = None,
    ) -> None:
        """Initialize the web search efficiency judge.

        Args:
            model_config: Judge model configuration. Defaults to Claude Opus.
            dimensions: Dimensions to evaluate. Defaults to all dimensions.
        """
        self.model_config = (
            model_config
            or JudgeModelConfig(
                provider=JudgeProviderType.ANTHROPIC,
                model_name="claude-3-5-haiku-20241022",  # Using Haiku for faster/cheaper judging
                temperature=0.2,  # Low temperature for consistency
                max_tokens=2000,
            )
        )

        self.dimensions = dimensions or list(WebSearchEfficiencyDimension)
        self.rubrics = {
            dim: DEFAULT_WEB_SEARCH_EFFICIENCY_RUBRICS[dim] for dim in self.dimensions
        }

    def _create_judge_agent(self) -> Agent[None, WebSearchEfficiencyScoreOutput]:
        """Create a Pydantic AI agent that evaluates all dimensions in one call.

        Returns:
            Configured Agent for web search efficiency evaluation
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
You are evaluating a Router agent's web search behavior in drafting mode.

In drafting mode, the agent should produce deliverables (specs, plans, code) rather
than endlessly researching. Excessive web searches often indicate pathological behavior
like search loops or inability to synthesize information.

For EACH dimension you must provide:
- score: 1-5 (where 3+ is passing)
- reasoning: Clear explanation justifying the score
- passed: true if score >= 3, false otherwise

{rubrics_section}

<INSTRUCTIONS>
1. Read the USER_REQUEST to understand what was asked.
2. Review the SEARCH_STATISTICS to understand how many searches occurred.
3. Examine the ROUTER_RESPONSE to see what was produced.
4. If EXPECTED_RESPONSE_CRITERIA is provided, use it as guidance.
5. Apply each RUBRIC to score the web search efficiency.
6. Be especially critical of high search counts with weak outputs.
</INSTRUCTIONS>

Be objective and consistent in your scoring. Flag potential search loops."""

        model_string = self.model_config.to_model_string()

        return Agent(  # type: ignore[call-overload,no-any-return]
            model=model_string,
            system_prompt=system_prompt,
            output_type=WebSearchEfficiencyScoreOutput,
            model_settings={
                "temperature": self.model_config.temperature,
                "max_tokens": self.model_config.max_tokens,
            },
        )

    async def evaluate(
        self,
        test_case: ShotgunTestCase,
        actual_output: AgentExecutionOutput,
    ) -> WebSearchEfficiencyJudgeResult:
        """Evaluate all dimensions for web search efficiency in a single LLM call.

        Args:
            test_case: The test case being evaluated
            actual_output: The Router's actual output

        Returns:
            WebSearchEfficiencyJudgeResult with all dimension scores
        """
        with logfire.span(
            "eval.judge.web_search_efficiency",
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

            # Calculate web search statistics
            web_search_tools = {
                "web_search",
                "anthropic_web_search_tool",
                "openai_web_search_tool",
                "gemini_web_search_tool",
                "openai_compatible_web_search_tool",
            }
            tool_counts = actual_output.tool_call_counts
            web_search_counts = {
                tool: count
                for tool, count in tool_counts.items()
                if tool in web_search_tools
            }
            total_web_searches = sum(web_search_counts.values())

            search_stats = f"""Total web searches: {total_web_searches}
Tools used: {", ".join(actual_output.tools_used) or "None"}
Search breakdown: {", ".join(f"{t}: {c}" for t, c in web_search_counts.items()) if web_search_counts else "None"}
Max allowed: {test_case.expected.max_web_searches or "No limit set"}"""

            # Truncate response if very long (for efficiency)
            response_preview = actual_output.response
            if len(response_preview) > 3000:
                response_preview = response_preview[:3000] + "\n... [truncated]"

            prompt = f"""<USER_REQUEST>
{test_case.inputs.prompt}
</USER_REQUEST>

<SEARCH_STATISTICS>
{search_stats}
</SEARCH_STATISTICS>

<ROUTER_RESPONSE>
{response_preview}
</ROUTER_RESPONSE>
{expected_response_section}
Evaluate the Router's web search efficiency on all dimensions."""

            # Create agent and make single LLM call
            agent = self._create_judge_agent()

            try:
                result = await agent.run(prompt)
                combined_output = result.output

                # Extract dimension scores from combined output
                dimension_scores: dict[str, DimensionScoreOutput] = {
                    "search_count_reasonableness": (
                        combined_output.search_count_reasonableness
                    ),
                    "query_diversity": combined_output.query_diversity,
                    "task_completion": combined_output.task_completion,
                }
            except Exception as e:
                logger.exception("Failed to evaluate web search efficiency dimensions")
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
                summary = (
                    f"Failed dimensions: {', '.join(failed_dims)}. "
                    f"Total searches: {total_web_searches}. "
                    f"Score: {overall_score:.2f}/5"
                )
            else:
                summary = (
                    f"All dimensions passed. "
                    f"Total searches: {total_web_searches}. "
                    f"Score: {overall_score:.2f}/5"
                )

            return WebSearchEfficiencyJudgeResult(
                dimension_scores=dimension_scores,
                overall_score=overall_score,
                overall_passed=overall_passed,
                summary=summary,
            )

    def convert_to_evaluation_results(
        self, judge_result: WebSearchEfficiencyJudgeResult
    ) -> list[EvaluationResult]:
        """Convert WebSearchEfficiencyJudgeResult to standard EvaluationResult models.

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
