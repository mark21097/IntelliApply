"""Tests for src/llm_client.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.llm_client import (
    DEFAULT_MODEL,
    LLMAPIError,
    LLMParseError,
    _parse_tailoring_plan,
    configure_gemini,
    generate_recruiter_message,
    generate_tailoring_plan,
)
from src.models import JobDescription, RecruiterContact, TailoringPlan


# ---------------------------------------------------------------------------
# configure_gemini
# ---------------------------------------------------------------------------


def test_configure_gemini_raises_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("VISION_LLM_API_KEY", raising=False)
    with pytest.raises(LLMAPIError, match="No Gemini API key"):
        configure_gemini()


def test_configure_gemini_accepts_vision_llm_api_key_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("VISION_LLM_API_KEY", "test-key-alias")
    with patch("src.llm_client.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        client = configure_gemini()
    assert client is not None


# ---------------------------------------------------------------------------
# _parse_tailoring_plan
# ---------------------------------------------------------------------------

VALID_JSON = """{
  "summary_replacement": "Motivated ML engineer targeting Summer 2026.",
  "bullet_replacements": [
    ["Built pipeline processing 500K rows/day", "Built PyTorch data pipeline processing 500K rows/day with 99.9% uptime"]
  ],
  "skills_to_emphasize": ["Python", "PyTorch", "SQL"]
}"""

JSON_WITH_FENCES = "```json\n" + VALID_JSON + "\n```"
JSON_NULL_SUMMARY = VALID_JSON.replace(
    '"summary_replacement": "Motivated ML engineer targeting Summer 2026."',
    '"summary_replacement": null',
)


def test_parse_tailoring_plan_valid_json() -> None:
    plan = _parse_tailoring_plan(VALID_JSON)
    assert isinstance(plan, TailoringPlan)
    assert plan.summary_replacement == "Motivated ML engineer targeting Summer 2026."
    assert len(plan.bullet_replacements) == 1
    assert plan.bullet_replacements[0][0] == "Built pipeline processing 500K rows/day"
    assert "Python" in plan.skills_to_emphasize


def test_parse_tailoring_plan_strips_markdown_fences() -> None:
    plan = _parse_tailoring_plan(JSON_WITH_FENCES)
    assert plan.summary_replacement is not None


def test_parse_tailoring_plan_null_summary_becomes_none() -> None:
    plan = _parse_tailoring_plan(JSON_NULL_SUMMARY)
    assert plan.summary_replacement is None


def test_parse_tailoring_plan_raises_on_invalid_json() -> None:
    with pytest.raises(LLMParseError):
        _parse_tailoring_plan("this is not json at all")


def test_parse_tailoring_plan_raises_on_non_object() -> None:
    with pytest.raises(LLMParseError):
        _parse_tailoring_plan('["list", "not", "object"]')


def test_parse_tailoring_plan_tolerates_missing_keys() -> None:
    """Missing optional keys should produce empty defaults, not raise."""
    plan = _parse_tailoring_plan("{}")
    assert plan.summary_replacement is None
    assert plan.bullet_replacements == []
    assert plan.skills_to_emphasize == []


# ---------------------------------------------------------------------------
# generate_tailoring_plan (Gemini mocked)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_model() -> MagicMock:
    """Return a mock genai.Client whose models.generate_content returns valid JSON."""
    client = MagicMock()
    response = MagicMock()
    response.text = VALID_JSON
    client.models.generate_content.return_value = response
    client.model_name = DEFAULT_MODEL
    return client


@pytest.fixture()
def sample_job() -> JobDescription:
    return JobDescription(
        raw_text="Looking for a Python and PyTorch ML intern for Summer 2026.",
        title="ML Engineering Intern",
        company="NeuralCore AI",
        required_skills=["Python", "PyTorch", "SQL"],
    )


def test_generate_tailoring_plan_returns_plan(
    mock_model: MagicMock, sample_job: JobDescription
) -> None:
    plan = generate_tailoring_plan(
        resume_text="Built pipeline processing 500K rows/day with Python.",
        job=sample_job,
        model=mock_model,
    )
    assert isinstance(plan, TailoringPlan)
    assert "Python" in plan.skills_to_emphasize


def test_generate_tailoring_plan_retries_on_bad_json(
    sample_job: JobDescription,
) -> None:
    """First call returns bad JSON; second call returns valid JSON."""
    client = MagicMock()
    bad_response = MagicMock()
    bad_response.text = "Sorry, here is the JSON: oops not really json"
    good_response = MagicMock()
    good_response.text = VALID_JSON
    client.models.generate_content.side_effect = [bad_response, good_response]
    client.model_name = DEFAULT_MODEL

    plan = generate_tailoring_plan(
        resume_text="Some resume text.",
        job=sample_job,
        model=client,
    )
    assert isinstance(plan, TailoringPlan)
    assert client.models.generate_content.call_count == 2


def test_generate_tailoring_plan_raises_after_two_bad_responses(
    sample_job: JobDescription,
) -> None:
    client = MagicMock()
    bad = MagicMock()
    bad.text = "still not json"
    client.models.generate_content.return_value = bad
    client.model_name = DEFAULT_MODEL

    with pytest.raises(LLMParseError):
        generate_tailoring_plan("resume", sample_job, model=client)


# ---------------------------------------------------------------------------
# generate_recruiter_message (Gemini mocked)
# ---------------------------------------------------------------------------


def test_generate_recruiter_message_returns_string(
    mock_model: MagicMock, sample_job: JobDescription
) -> None:
    mock_model.models.generate_content.return_value.text = (
        "Hi, I am excited about the ML Engineering Intern role at NeuralCore AI. "
        "My Python and PyTorch skills align well with your needs. "
        "I recently built a CNN achieving 94% accuracy. "
        "I would love to connect for a brief conversation."
    )
    msg = generate_recruiter_message(
        resume_text="Python, PyTorch, ML pipeline experience.",
        job=sample_job,
        model=mock_model,
    )
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_generate_recruiter_message_personalizes_with_recruiter_name(
    sample_job: JobDescription,
) -> None:
    """Verify the recruiter's name appears in the prompt sent to the model."""
    client = MagicMock()
    response = MagicMock()
    response.text = "Hi Jane, ..."
    client.models.generate_content.return_value = response
    client.model_name = DEFAULT_MODEL

    recruiter = RecruiterContact(email="jane@neuralcore.ai", name="Jane")
    generate_recruiter_message(
        "resume text", sample_job, recruiter=recruiter, model=client
    )

    call_args = client.models.generate_content.call_args
    # New SDK uses keyword args: contents=prompt
    prompt_sent = call_args.kwargs.get("contents", "")
    assert "Hi Jane," in prompt_sent
