"""Tests verifying that evals.models re-exports work correctly."""

from __future__ import annotations


def test_import_qa_case() -> None:
    """Verify QACase can be imported from evals.models."""
    from evals.models import QACase

    assert QACase is not None


def test_import_agent_tool_case() -> None:
    """Verify AgentToolCase can be imported from evals.models."""
    from evals.models import AgentToolCase

    assert AgentToolCase is not None


def test_import_metric_name() -> None:
    """Verify MetricName can be imported from evals.models."""
    from evals.models import MetricName

    assert MetricName is not None


def test_import_case_eval_result() -> None:
    """Verify CaseEvalResult can be imported from evals.models."""
    from evals.models import CaseEvalResult

    assert CaseEvalResult is not None


def test_import_all_enums() -> None:
    """Verify all enum types can be imported from evals.models."""
    from evals.models import (
        ClarifyingQuestionPolicy,
        Difficulty,
        QADomain,
        ScenarioType,
        SourceType,
    )

    assert Difficulty.EASY == "easy"
    assert QADomain.CODE == "code"
    assert ScenarioType.BUGFIX == "bugfix"
    assert SourceType.HAND_AUTHORED == "hand_authored"
    assert ClarifyingQuestionPolicy.MUST_ASK == "must_ask"


def test_import_all_case_models() -> None:
    """Verify all case-related models can be imported from evals.models."""
    from evals.models import (
        AgentToolCase,
        AgentToolCaseMetadata,
        FileChangeExpectation,
        QACase,
        QACaseMetadata,
        QAExpectation,
        ToolUsageExpectation,
    )

    assert QAExpectation is not None
    assert QACaseMetadata is not None
    assert QACase is not None
    assert FileChangeExpectation is not None
    assert ToolUsageExpectation is not None
    assert AgentToolCaseMetadata is not None
    assert AgentToolCase is not None


def test_import_all_metric_models() -> None:
    """Verify all metric-related models can be imported from evals.models."""
    from evals.models import CaseEvalResult, MetricName, MetricValue

    assert MetricName is not None
    assert MetricValue is not None
    assert CaseEvalResult is not None


def test_import_all_judge_outputs() -> None:
    """Verify all judge output models can be imported from evals.models."""
    from evals.models import (
        FileChangeJudgeOutput,
        FileChangeJudgeScores,
        QAJudgeOutput,
        QAJudgeScores,
        ScoreScale,
        ToolUseJudgeOutput,
        ToolUseJudgeScores,
    )

    assert ScoreScale is not None
    assert QAJudgeScores is not None
    assert QAJudgeOutput is not None
    assert ToolUseJudgeScores is not None
    assert ToolUseJudgeOutput is not None
    assert FileChangeJudgeScores is not None
    assert FileChangeJudgeOutput is not None


def test_qa_case_instantiation() -> None:
    """Verify QACase can be instantiated with valid data."""
    from evals.models import QACase, QAExpectation

    case = QACase(
        case_id="test-001",
        question="Which agent edits plan.md?",
        expectation=QAExpectation(
            reference_answer="The Plan agent edits plan.md.",
        ),
    )
    assert case.case_id == "test-001"
    assert case.question == "Which agent edits plan.md?"


def test_agent_tool_case_instantiation() -> None:
    """Verify AgentToolCase can be instantiated with valid data."""
    from evals.models import AgentToolCase, FileChangeExpectation

    case = AgentToolCase(
        case_id="agent-001",
        task_description="Add a new section to specification.md",
        environment_id="shotgun_mvp",
        file_change_expectations=[
            FileChangeExpectation(
                path=".shotgun/specification.md",
                must_change=True,
            )
        ],
    )
    assert case.case_id == "agent-001"
    assert case.environment_id == "shotgun_mvp"


def test_metric_value_instantiation() -> None:
    """Verify MetricValue can be instantiated with valid data."""
    from evals.models import MetricName, MetricValue

    metric = MetricValue(
        name=MetricName.QA_ACCURACY,
        numeric_value=0.95,
        boolean_value=True,
    )
    assert metric.name == MetricName.QA_ACCURACY
    assert metric.numeric_value == 0.95


def test_case_eval_result_instantiation() -> None:
    """Verify CaseEvalResult can be instantiated with valid data."""
    from evals.models import CaseEvalResult, MetricName, MetricValue

    result = CaseEvalResult(
        case_id="test-001",
        dataset_id="core_qa",
        metrics={
            MetricName.QA_ACCURACY: MetricValue(
                name=MetricName.QA_ACCURACY,
                numeric_value=1.0,
            )
        },
    )
    assert result.case_id == "test-001"
    assert MetricName.QA_ACCURACY in result.metrics
