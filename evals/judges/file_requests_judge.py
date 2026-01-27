"""
LLM judge for Router agent file_requests evaluation.

Uses LLM-as-a-judge to evaluate Router outputs for file handling scenarios:
- Did the Router correctly use file_requests instead of asking questions?
- Did it avoid delegating to inappropriate agents (like Research)?
- Is the response appropriate for a file loading action?

This judge has different rubrics than RouterQualityJudge because it evaluates
scenarios where the Router should NOT ask clarifying questions.
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


class FileRequestsDimension(StrEnum):
    """Dimensions for evaluating file_requests behavior."""

    FILE_REQUEST_USAGE = "file_request_usage"
    NO_UNNECESSARY_QUESTIONS = "no_unnecessary_questions"
    APPROPRIATE_RESPONSE = "appropriate_response"
    NO_WRONG_DELEGATION = "no_wrong_delegation"


class FileRequestsDimensionRubric(BaseModel):
    """Rubric definition for a file_requests evaluation dimension."""

    dimension: FileRequestsDimension
    description: str
    weight: float = 1.0
    rubric_text: str


class FileRequestsScoreOutput(BaseModel):
    """Output structure for all file_requests dimension scores."""

    file_request_usage: DimensionScoreOutput = Field(
        description="Score for correct file_requests usage"
    )
    no_unnecessary_questions: DimensionScoreOutput = Field(
        description="Score for not asking unnecessary clarifying questions"
    )
    appropriate_response: DimensionScoreOutput = Field(
        description="Score for appropriate response text"
    )
    no_wrong_delegation: DimensionScoreOutput = Field(
        description="Score for not delegating to wrong agents"
    )


class FileRequestsJudgeResult(BaseModel):
    """Result from file_requests judge evaluation."""

    dimension_scores: dict[str, DimensionScoreOutput]
    overall_score: float
    overall_passed: bool
    summary: str


# Default rubrics for file_requests evaluation dimensions
DEFAULT_FILE_REQUESTS_RUBRICS: dict[
    FileRequestsDimension, FileRequestsDimensionRubric
] = {
    FileRequestsDimension.FILE_REQUEST_USAGE: FileRequestsDimensionRubric(
        dimension=FileRequestsDimension.FILE_REQUEST_USAGE,
        description="Did the Router correctly use file_requests to load the binary file?",
        weight=2.0,  # Highest weight - this is the core behavior being tested
        rubric_text="""
Evaluate if the Router correctly used file_requests to load the binary file on a 1-5 scale:

**File Request Usage:**
5 (Excellent): Router immediately used file_requests with the correct file path. No hesitation or unnecessary steps.
4 (Good): Router used file_requests correctly but with minor issues (slight delay or extra explanation).
3 (Average): Router eventually used file_requests but took unnecessary steps first.
2 (Fair): Router attempted to use file_requests but with incorrect path or format.
1 (Poor): Router did not use file_requests at all, or claimed inability to access the file.

Consider:
- Did the Router include the file path in file_requests?
- Was the response immediate rather than asking for more information first?
- Did the Router acknowledge it would load/analyze the file?
""",
    ),
    FileRequestsDimension.NO_UNNECESSARY_QUESTIONS: FileRequestsDimensionRubric(
        dimension=FileRequestsDimension.NO_UNNECESSARY_QUESTIONS,
        description="Did the Router avoid asking unnecessary clarifying questions?",
        weight=1.5,  # High weight - directly related to the test criteria
        rubric_text="""
Evaluate if the Router appropriately avoided asking clarifying questions on a 1-5 scale:

**No Unnecessary Questions:**
5 (Excellent): Router asked zero clarifying questions and proceeded directly to use file_requests.
4 (Good): Router proceeded with file_requests but included a minor, non-blocking question.
3 (Average): Router asked one question but still used file_requests.
2 (Fair): Router asked multiple questions before using file_requests.
1 (Poor): Router asked questions instead of using file_requests, or refused to proceed.

Consider:
- For explicit file paths (like "docs/prd.pdf"), no clarifying questions should be needed
- The user has already specified what file they want to access
- Questions about file content should wait until after the file is loaded
""",
    ),
    FileRequestsDimension.APPROPRIATE_RESPONSE: FileRequestsDimensionRubric(
        dimension=FileRequestsDimension.APPROPRIATE_RESPONSE,
        description="Is the response text appropriate for a file loading action?",
        weight=1.0,
        rubric_text="""
Evaluate if the response text is appropriate for a file loading action on a 1-5 scale:

**Appropriate Response:**
5 (Excellent): Response clearly acknowledges it will load/analyze the file. Professional and concise.
4 (Good): Response is appropriate with minor room for improvement.
3 (Average): Response is acceptable but could be clearer about what will happen.
2 (Fair): Response is confusing or makes incorrect claims about file access.
1 (Poor): Response claims inability to access files, or is completely off-topic.

Consider:
- Does the response acknowledge the file will be loaded?
- Is it clear the Router understands what the user wants?
- Does it avoid claiming inability to read PDFs/images?
""",
    ),
    FileRequestsDimension.NO_WRONG_DELEGATION: FileRequestsDimensionRubric(
        dimension=FileRequestsDimension.NO_WRONG_DELEGATION,
        description="Did the Router avoid delegating to inappropriate agents?",
        weight=1.5,  # High weight - delegating to Research for file access is a key failure mode
        rubric_text="""
Evaluate if the Router avoided delegating to inappropriate agents on a 1-5 scale:

**No Wrong Delegation:**
5 (Excellent): Router did not delegate to any sub-agent. Used file_requests directly.
4 (Good): Router used file_requests without inappropriate delegation.
3 (Average): Router used file_requests but mentioned potentially delegating later.
2 (Fair): Router delegated to an agent when it should have used file_requests.
1 (Poor): Router delegated file reading to Research or another inappropriate agent.

Consider:
- For direct file access requests, the Router should use file_requests, not delegate
- Delegating to Research agent for PDF reading is incorrect
- The Router has the capability to load files via file_requests
""",
    ),
}


class FileRequestsJudge:
    """
    LLM-as-a-judge evaluator for file_requests behavior.

    Uses structured output to evaluate Router outputs against rubrics
    specific to file handling scenarios.
    """

    def __init__(
        self,
        model_config: JudgeModelConfig | None = None,
        dimensions: list[FileRequestsDimension] | None = None,
    ) -> None:
        """Initialize the file_requests judge.

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

        self.dimensions = dimensions or list(FileRequestsDimension)
        self.rubrics = {
            dim: DEFAULT_FILE_REQUESTS_RUBRICS[dim] for dim in self.dimensions
        }

    def _create_judge_agent(self) -> Agent[None, FileRequestsScoreOutput]:
        """Create a Pydantic AI agent that evaluates all dimensions in one call.

        Returns:
            Configured Agent for file_requests evaluation
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
You are evaluating a Router agent's handling of file requests (PDFs, images, documents).

The Router should use file_requests to load binary files directly, NOT:
- Ask clarifying questions about the file
- Delegate to Research or other agents
- Claim inability to access the file

For EACH dimension you must provide:
- score: 1-5 (where 3+ is passing)
- reasoning: Clear explanation justifying the score
- passed: true if score >= 3, false otherwise

{rubrics_section}

<INSTRUCTIONS>
1. Read the USER_REQUEST and the ROUTER_RESPONSE carefully.
2. Check the ROUTER_ACTIONS to see what the Router actually did.
3. If EXPECTED_RESPONSE_CRITERIA is provided, use it as guidance.
4. Apply each RUBRIC to score the Router's file handling performance.
5. Provide clear, specific reasoning for each score.
</INSTRUCTIONS>

Be objective and consistent in your scoring."""

        model_string = self.model_config.to_model_string()

        return Agent(  # type: ignore[call-overload,no-any-return]
            model=model_string,
            system_prompt=system_prompt,
            output_type=FileRequestsScoreOutput,
            model_settings={
                "temperature": self.model_config.temperature,
                "max_tokens": self.model_config.max_tokens,
            },
        )

    async def evaluate(
        self,
        test_case: ShotgunTestCase,
        actual_output: AgentExecutionOutput,
    ) -> FileRequestsJudgeResult:
        """Evaluate all dimensions for Router file handling in a single LLM call.

        Args:
            test_case: The test case being evaluated
            actual_output: The Router's actual output

        Returns:
            FileRequestsJudgeResult with all dimension scores and overall assessment
        """
        with logfire.span(
            "eval.judge.file_requests",
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

            clarifying_questions = (
                ", ".join(actual_output.clarifying_questions)
                if actual_output.clarifying_questions
                else "None"
            )

            file_requests = (
                ", ".join(actual_output.file_requests)
                if actual_output.file_requests
                else "None"
            )

            prompt = f"""<USER_REQUEST>
{test_case.inputs.prompt}
</USER_REQUEST>

<ROUTER_RESPONSE>
{actual_output.response}
</ROUTER_RESPONSE>

<ROUTER_ACTIONS>
Tools used: {", ".join(actual_output.tools_used) or "None"}
Delegated to: {actual_output.delegated_sub_agent or "None"}
File requests: {file_requests}
Clarifying questions: {clarifying_questions}
</ROUTER_ACTIONS>
{expected_response_section}
Evaluate the Router's file handling performance on all dimensions."""

            # Create agent and make single LLM call
            agent = self._create_judge_agent()

            try:
                result = await agent.run(prompt)
                combined_output = result.output

                # Extract dimension scores from combined output
                dimension_scores: dict[str, DimensionScoreOutput] = {
                    "file_request_usage": combined_output.file_request_usage,
                    "no_unnecessary_questions": combined_output.no_unnecessary_questions,
                    "appropriate_response": combined_output.appropriate_response,
                    "no_wrong_delegation": combined_output.no_wrong_delegation,
                }
            except Exception as e:
                logger.exception("Failed to evaluate file_requests dimensions")
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

            return FileRequestsJudgeResult(
                dimension_scores=dimension_scores,
                overall_score=overall_score,
                overall_passed=overall_passed,
                summary=summary,
            )

    def convert_to_evaluation_results(
        self, judge_result: FileRequestsJudgeResult
    ) -> list[EvaluationResult]:
        """Convert FileRequestsJudgeResult to standard EvaluationResult models.

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
