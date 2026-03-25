"""CLI entry point for the IntelliApply pipeline.

Orchestrates job description fetching, resume tailoring via Gemini, and
recruiter email scraping + message generation. All business logic lives in
the imported modules; this file only handles argument parsing and sequencing.

Usage:
    python -m src.main --job-url <URL> --resume <PATH> [options]
    python -m src.main --job-text-file <PATH> --resume <PATH> [options]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from src import document_editor, llm_client, scraper
from src.llm_client import LLMAPIError
from src.models import PipelineResult, TailoringPlan


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate CLI arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed argparse.Namespace.
    """
    parser = argparse.ArgumentParser(
        prog="intelliapply",
        description=(
            "Tailor your resume and generate a recruiter outreach message "
            "using Google Gemini (free tier)."
        ),
    )

    # Job description source (mutually exclusive)
    job_group = parser.add_mutually_exclusive_group(required=True)
    job_group.add_argument(
        "--job-url",
        metavar="URL",
        help="URL of the job posting to scrape.",
    )
    job_group.add_argument(
        "--job-text-file",
        metavar="PATH",
        help="Path to a plain-text file containing the job description.",
    )

    # Required
    parser.add_argument(
        "--resume",
        required=True,
        metavar="PATH",
        help="Path to your base resume (.docx).",
    )

    # Outputs (with sensible defaults)
    parser.add_argument(
        "--output-resume",
        default="data/output/tailored_resume.docx",
        metavar="PATH",
        help="Output path for the tailored resume. (default: data/output/tailored_resume.docx)",
    )
    parser.add_argument(
        "--output-message",
        default="data/output/recruiter_message.txt",
        metavar="PATH",
        help="Output path for the recruiter message. (default: data/output/recruiter_message.txt)",
    )

    # LLM options
    parser.add_argument(
        "--model",
        default=llm_client.DEFAULT_MODEL,
        metavar="NAME",
        help=f"Gemini model name. (default: {llm_client.DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        metavar="FLOAT",
        help="LLM sampling temperature 0.0–1.0. (default: 0.3)",
    )

    # Scraping options
    parser.add_argument(
        "--scraping-domains",
        default="",
        metavar="DOMAINS",
        help="Comma-separated domain allowlist for email scraping (e.g. company.com).",
    )

    # Misc
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a backup of the original resume before editing.",
    )

    return parser.parse_args(argv)


def run_pipeline(args: argparse.Namespace) -> PipelineResult:
    """Execute the full IntelliApply pipeline.

    Args:
        args: Parsed CLI arguments from parse_args().

    Returns:
        A PipelineResult summarising all outputs.
    """
    load_dotenv()

    # --- Configure Gemini ---
    print("[1/6] Configuring Gemini model...")
    try:
        model = llm_client.configure_gemini(model_name=args.model)
    except LLMAPIError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Fetch job description ---
    print("[2/6] Loading job description...")
    if args.job_url:
        try:
            job = scraper.fetch_job_description(args.job_url)
            print(f"      Title:   {job.title or '(unknown)'}")
            print(f"      Company: {job.company or '(unknown)'}")
        except scraper.ScraperError as exc:
            print(f"ERROR: Could not fetch job description: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        job = scraper.load_job_from_file(args.job_text_file)
        print(f"      Loaded {len(job.raw_text)} characters from {args.job_text_file}")

    # --- Scrape recruiter emails (non-fatal) ---
    print("[3/6] Scraping recruiter contacts...")
    source_url = args.job_url or ""
    domain_allowlist = (
        [d.strip() for d in args.scraping_domains.split(",") if d.strip()]
        if args.scraping_domains
        else None
    )
    contacts = scraper.scrape_recruiter_emails(source_url, domain_allowlist)
    if contacts:
        for c in contacts:
            print(f"      Found: {c.email}" + (f" ({c.name})" if c.name else ""))
    else:
        print("      No recruiter emails found (continuing without).")
    primary_recruiter = contacts[0] if contacts else None

    # --- Extract resume text for LLM ---
    print("[4/6] Analysing resume...")
    try:
        resume_text = document_editor.extract_resume_text(args.resume)
    except (FileNotFoundError, document_editor.DocumentEditError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Generate tailoring plan ---
    print("[5/6] Generating tailoring plan with Gemini...")
    try:
        plan: TailoringPlan = llm_client.generate_tailoring_plan(
            resume_text=resume_text,
            job=job,
            model=model,
            temperature=args.temperature,
        )
    except LLMAPIError as exc:
        print(f"ERROR: Gemini API failed: {exc}", file=sys.stderr)
        sys.exit(1)

    bullets_count = len(plan.bullet_replacements)
    print(f"      Bullets to replace: {bullets_count}")
    print(f"      Summary update:     {'yes' if plan.summary_replacement else 'no'}")

    # --- Apply tailoring to .docx ---
    print("[6/6] Editing resume and generating message...")
    try:
        tailored_path = document_editor.apply_tailoring_plan(
            resume_path=args.resume,
            plan=plan,
            output_path=args.output_resume,
            backup=not args.no_backup,
        )
    except (FileNotFoundError, document_editor.DocumentEditError) as exc:
        print(f"ERROR: Could not edit resume: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Generate recruiter message ---
    message_path: str | None = None
    try:
        message = llm_client.generate_recruiter_message(
            resume_text=resume_text,
            job=job,
            recruiter=primary_recruiter,
            model=model,
            temperature=args.temperature,
        )
        msg_out = Path(args.output_message)
        msg_out.parent.mkdir(parents=True, exist_ok=True)
        msg_out.write_text(message, encoding="utf-8")
        message_path = str(msg_out)
    except LLMAPIError as exc:
        print(f"WARNING: Could not generate recruiter message: {exc}", file=sys.stderr)

    # --- Summary ---
    print("\n" + "=" * 50)
    print("  IntelliApply complete!")
    print("=" * 50)
    print(f"  Tailored resume : {tailored_path}")
    if message_path:
        print(f"  Recruiter message: {message_path}")
    if primary_recruiter:
        print(f"  Primary contact : {primary_recruiter.email}")
    print("=" * 50)

    return PipelineResult(
        tailored_resume_path=tailored_path,
        recruiter_message_path=message_path,
        recruiter_contacts=contacts,
        tailoring_plan=plan,
    )


def main() -> None:
    """Entry point for the IntelliApply CLI."""
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
