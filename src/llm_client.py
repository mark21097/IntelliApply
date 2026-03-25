"""Google Gemini integration for resume tailoring and message generation.

Uses the official google-genai SDK (replaces the deprecated google-generativeai).
Free tier: https://aistudio.google.com/app/apikey

Set GEMINI_API_KEY (or VISION_LLM_API_KEY) in your .env file.
"""
from __future__ import annotations

import json
import os
import re
import textwrap

from google import genai
from google.genai import types as genai_types

from src.models import JobDescription, RecruiterContact, TailoringPlan

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base class for LLM client errors."""


class LLMAPIError(LLMError):
    """Raised when the Gemini API cannot be configured or returns an error."""


class LLMParseError(LLMError):
    """Raised when the LLM response cannot be parsed into the expected format."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-1.5-flash"

_SYSTEM_INSTRUCTION = textwrap.dedent(
    """\
    You are a professional resume coach specializing in tech internships.
    Your primary focus is Software Engineering, Data Science, and Machine Learning
    roles targeting Summer 2026. Candidates typically have skills in Python, SQL,
    PyTorch, scikit-learn, algorithms, and data structures.
    Always be concise, professional, and action-oriented.
    """
)


def configure_gemini(model_name: str = DEFAULT_MODEL) -> genai.Client:
    """Configure and return a Gemini client.

    Reads GEMINI_API_KEY from the environment (falls back to VISION_LLM_API_KEY
    for backwards compatibility).

    Args:
        model_name: Gemini model identifier to use (stored on the returned client
            via a custom attribute for convenience).

    Returns:
        A configured genai.Client instance with a `model_name` attribute attached.

    Raises:
        LLMAPIError: If no API key is found in the environment.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("VISION_LLM_API_KEY")
    if not api_key:
        raise LLMAPIError(
            "No Gemini API key found. Set GEMINI_API_KEY in your .env file. "
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )
    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1"},
    )
    # Attach the model name so callers don't need to track it separately
    client.model_name = model_name  # type: ignore[attr-defined]
    return client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_tailoring_plan(
    resume_text: str,
    job: JobDescription,
    model: genai.Client | None = None,
    temperature: float = 0.3,
) -> TailoringPlan:
    """Ask Gemini to produce a structured plan for tailoring the resume.

    Sends the resume text and job description to Gemini and expects a JSON
    response. Retries once with a stricter prompt if the first response is
    not valid JSON.

    Args:
        resume_text: Plain text extracted from the candidate's .docx resume.
        job: Parsed job description including title, company, and raw text.
        model: Optional pre-configured genai.Client. If None, configure_gemini()
            is called automatically.
        temperature: Sampling temperature (0.0-1.0).

    Returns:
        A TailoringPlan dataclass with bullet replacements and skill emphasis.

    Raises:
        LLMAPIError: If the API call fails.
        LLMParseError: If the response cannot be parsed as JSON after retry.
    """
    if model is None:
        model = configure_gemini()

    prompt = _build_tailoring_prompt(resume_text, job)
    raw = _call_gemini(model, prompt, temperature)

    try:
        return _parse_tailoring_plan(raw)
    except LLMParseError:
        # Retry with an explicit JSON-only instruction
        strict_prompt = (
            prompt
            + "\n\nIMPORTANT: Your entire response must be valid JSON only. "
            "No prose, no markdown, no code fences. Start with { and end with }."
        )
        raw2 = _call_gemini(model, strict_prompt, temperature=0.0)
        return _parse_tailoring_plan(raw2)


def generate_recruiter_message(
    resume_text: str,
    job: JobDescription,
    recruiter: RecruiterContact | None = None,
    model: genai.Client | None = None,
    temperature: float = 0.5,
) -> str:
    """Generate a personalized cold-outreach email to a recruiter.

    Args:
        resume_text: Plain text of the candidate's resume.
        job: Parsed job description.
        recruiter: Optional recruiter contact (name used to personalize greeting).
        model: Optional pre-configured genai.Client.
        temperature: Sampling temperature.

    Returns:
        A ready-to-send recruiter outreach email as a plain string.

    Raises:
        LLMAPIError: If the API call fails.
    """
    if model is None:
        model = configure_gemini()

    prompt = _build_recruiter_prompt(resume_text, job, recruiter)
    return _call_gemini(model, prompt, temperature)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_tailoring_prompt(resume_text: str, job: JobDescription) -> str:
    return textwrap.dedent(
        f"""\
        ## Task
        Analyze the resume and job description below. Return a JSON object with
        specific edits to tailor the resume for this role.

        ## Job Description
        Title: {job.title}
        Company: {job.company}
        Required Skills: {", ".join(job.required_skills)}

        {job.raw_text}

        ## Current Resume
        {resume_text}

        ## Required JSON Format
        Return ONLY a JSON object with these keys:

        {{
          "summary_replacement": "<new 1-2 sentence summary targeting this role, or null>",
          "bullet_replacements": [
            ["<exact text of existing bullet to replace>", "<improved bullet using job keywords>"]
          ],
          "skills_to_emphasize": ["<skill1>", "<skill2>"]
        }}

        Rules:
        - bullet_replacements must use the EXACT existing bullet text as the first element
        - Improve at most 3 bullets - focus on highest-impact changes
        - Incorporate keywords from the job description naturally
        - Preserve quantified achievements (numbers, percentages)
        - Return valid JSON only, no markdown fences
        """
    )


def _build_recruiter_prompt(
    resume_text: str,
    job: JobDescription,
    recruiter: RecruiterContact | None,
) -> str:
    greeting = f"Hi {recruiter.name}," if recruiter and recruiter.name else "Hi,"
    return textwrap.dedent(
        f"""\
        Write a professional cold-outreach email from a candidate to a recruiter.

        Recruiter greeting: {greeting}
        Role: {job.title}
        Company: {job.company}

        Candidate resume summary:
        {resume_text[:1500]}

        Requirements:
        - Exactly 4 sentences
        - Sentence 1: Express specific interest in the {job.title} role at {job.company}
        - Sentence 2: Highlight 2 relevant technical skills from the resume that match the role
        - Sentence 3: Mention one concrete project or achievement
        - Sentence 4: Clear call-to-action (ask for a brief conversation)
        - Professional but warm tone; no filler phrases like "I hope this email finds you well"
        - Do not include a subject line or signature - return only the email body
        """
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _call_gemini(
    client: genai.Client,
    prompt: str,
    temperature: float,
) -> str:
    """Call the Gemini API and return the text response.

    Raises:
        LLMAPIError: On API failure.
    """
    model_name: str = getattr(client, "model_name", DEFAULT_MODEL)
    # Prepend system instruction directly — v1 API does not support the
    # systemInstruction field (that is a v1beta-only feature).
    full_prompt = f"{_SYSTEM_INSTRUCTION}\n\n{prompt}"
    config = genai_types.GenerateContentConfig(temperature=temperature)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=config,
        )
        return response.text.strip()
    except Exception as exc:
        raise LLMAPIError(f"Gemini API call failed: {exc}") from exc


def _parse_tailoring_plan(raw: str) -> TailoringPlan:
    """Parse a raw LLM response string into a TailoringPlan.

    Strips markdown code fences if present before JSON parsing.

    Raises:
        LLMParseError: If the response is not valid JSON or has wrong schema.
    """
    # Strip ```json ... ``` fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMParseError(
            f"LLM returned non-JSON response: {exc}\n\nRaw:\n{raw}"
        ) from exc

    if not isinstance(data, dict):
        raise LLMParseError(f"Expected a JSON object, got: {type(data)}")

    raw_bullets: list[object] = data.get("bullet_replacements", [])
    bullet_replacements: list[tuple[str, str]] = []
    for item in raw_bullets:
        if isinstance(item, list) and len(item) == 2:
            bullet_replacements.append((str(item[0]), str(item[1])))

    return TailoringPlan(
        summary_replacement=data.get("summary_replacement") or None,
        bullet_replacements=bullet_replacements,
        skills_to_emphasize=[str(s) for s in data.get("skills_to_emphasize", [])],
    )
