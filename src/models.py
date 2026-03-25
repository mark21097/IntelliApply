"""Pipeline data types for IntelliApply."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobDescription:
    """Parsed job posting data."""

    raw_text: str
    title: str = ""
    company: str = ""
    required_skills: list[str] = field(default_factory=list)
    url: str | None = None


@dataclass
class RecruiterContact:
    """A recruiter's contact information extracted from a job page."""

    email: str
    name: str | None = None
    source_url: str | None = None


@dataclass
class TailoringPlan:
    """LLM-generated instructions for editing the resume."""

    summary_replacement: str | None = None
    bullet_replacements: list[tuple[str, str]] = field(default_factory=list)
    skills_to_emphasize: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Final result returned after the full pipeline completes."""

    tailored_resume_path: str
    recruiter_message_path: str | None
    recruiter_contacts: list[RecruiterContact]
    tailoring_plan: TailoringPlan
