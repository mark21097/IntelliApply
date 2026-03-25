"""Web scraping module: job description parsing and recruiter email extraction.

Uses requests + BeautifulSoup for static HTML pages. For JavaScript-rendered
pages (Greenhouse, Lever, Workday), use the Puppeteer MCP instead.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.models import JobDescription, RecruiterContact

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ScraperError(Exception):
    """Base class for scraper errors."""


class ScraperTimeoutError(ScraperError):
    """Raised when an HTTP request times out."""


class ScraperHTTPError(ScraperError):
    """Raised when an HTTP response indicates an error status."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Addresses that are system/administrative and not recruiters
_NOISE_EMAIL_PREFIXES: set[str] = {
    "noreply",
    "no-reply",
    "support",
    "info",
    "help",
    "contact",
    "admin",
    "hello",
    "careers",
    "jobs",
    "hiring",
    "notifications",
    "donotreply",
}

# Known skills vocabulary for naive extraction
_SKILLS_VOCAB: list[str] = [
    "Python",
    "SQL",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "C#",
    "Go",
    "Rust",
    "R",
    "PyTorch",
    "TensorFlow",
    "scikit-learn",
    "NumPy",
    "pandas",
    "Spark",
    "Hadoop",
    "Kubernetes",
    "Docker",
    "AWS",
    "GCP",
    "Azure",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "Git",
    "Linux",
    "REST",
    "GraphQL",
    "React",
    "Node.js",
    "FastAPI",
    "Flask",
    "Django",
    "NLP",
    "LLM",
    "machine learning",
    "deep learning",
    "computer vision",
    "data structures",
    "algorithms",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_job_description(url: str, timeout: int = 15) -> JobDescription:
    """Fetch and parse a job description from a URL.

    Args:
        url: URL of the job posting.
        timeout: HTTP request timeout in seconds.

    Returns:
        A populated JobDescription dataclass.

    Raises:
        ScraperTimeoutError: If the request times out.
        ScraperHTTPError: If the server returns an error status code.
        ScraperError: For any other fetch/parse failure.
    """
    html = _fetch_html(url, timeout)
    soup = BeautifulSoup(html, "lxml")

    title, company = _parse_job_metadata(soup, url)
    raw_text = _extract_body_text(soup)
    skills = _extract_skills(raw_text)

    return JobDescription(
        raw_text=raw_text,
        title=title,
        company=company,
        required_skills=skills,
        url=url,
    )


def scrape_recruiter_emails(
    url: str,
    domain_allowlist: list[str] | None = None,
    timeout: int = 15,
) -> list[RecruiterContact]:
    """Scrape recruiter email addresses from a URL.

    Args:
        url: URL to scrape for recruiter contact information.
        domain_allowlist: If provided, only return emails whose domain is in
            this list (e.g., ["company.com"]).
        timeout: HTTP request timeout in seconds.

    Returns:
        A deduplicated list of RecruiterContact objects. Returns an empty list
        (rather than raising) if the page cannot be reached, to keep the
        pipeline non-fatal on email scraping failures.
    """
    try:
        html = _fetch_html(url, timeout)
    except ScraperError:
        return []

    contacts = _extract_emails_from_html(html, source_url=url)

    if domain_allowlist:
        allowed = {d.lower() for d in domain_allowlist}
        contacts = [
            c for c in contacts if _email_domain(c.email).lower() in allowed
        ]

    return contacts


def load_job_from_file(path: str) -> JobDescription:
    """Load a job description from a plain-text file.

    Args:
        path: Path to the .txt file containing the job description.

    Returns:
        A JobDescription with raw_text populated and skills extracted.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Job description file not found: {path}")
    raw_text = file_path.read_text(encoding="utf-8")
    return JobDescription(
        raw_text=raw_text,
        required_skills=_extract_skills(raw_text),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fetch_html(url: str, timeout: int) -> str:
    """Perform an HTTP GET and return the response body as text.

    Raises:
        ScraperTimeoutError: On connection/read timeout.
        ScraperHTTPError: On 4xx/5xx responses.
        ScraperError: On other request failures.
    """
    try:
        response = requests.get(url, headers=_DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout as exc:
        raise ScraperTimeoutError(f"Request timed out after {timeout}s: {url}") from exc
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise ScraperHTTPError(f"HTTP {status} for {url}") from exc
    except requests.exceptions.RequestException as exc:
        raise ScraperError(f"Failed to fetch {url}: {exc}") from exc


def _parse_job_metadata(soup: BeautifulSoup, url: str) -> tuple[str, str]:
    """Extract job title and company name from common job board HTML patterns.

    Tries platform-specific selectors (Greenhouse, Lever) then falls back to
    generic <h1> and <title> tags.

    Args:
        soup: Parsed BeautifulSoup object.
        url: Original URL (used for fallback company extraction).

    Returns:
        A (title, company) tuple; either field may be an empty string.
    """
    title = ""
    company = ""

    # Greenhouse
    if soup.select_one(".app-title"):
        title = soup.select_one(".app-title").get_text(strip=True)  # type: ignore[union-attr]
    if soup.select_one(".company-name"):
        company = soup.select_one(".company-name").get_text(strip=True)  # type: ignore[union-attr]

    # Lever
    if not title and soup.select_one(".posting-headline h2"):
        title = soup.select_one(".posting-headline h2").get_text(strip=True)  # type: ignore[union-attr]
    if not company and soup.select_one(".main-header-logo img"):
        el = soup.select_one(".main-header-logo img")
        company = el.get("alt", "") if el else ""  # type: ignore[union-attr]

    # Generic fallback
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        tag = soup.find("title")
        if tag:
            title = tag.get_text(strip=True)

    # Derive company from hostname if still unknown
    if not company:
        hostname = urlparse(url).hostname or ""
        # Strip www. and common job board hosts
        noise = {"greenhouse.io", "lever.co", "myworkdayjobs.com", "linkedin.com"}
        if hostname not in noise:
            parts = hostname.replace("www.", "").split(".")
            company = parts[0].capitalize() if parts else ""

    return title, company


def _extract_body_text(soup: BeautifulSoup) -> str:
    """Return the visible body text, stripping scripts and styles."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    body = soup.find("body")
    if body:
        return body.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


def _extract_skills(text: str) -> list[str]:
    """Return known tech skills found in text (case-insensitive match)."""
    found: list[str] = []
    text_lower = text.lower()
    for skill in _SKILLS_VOCAB:
        if skill.lower() in text_lower and skill not in found:
            found.append(skill)
    return found


def _extract_emails_from_html(html: str, source_url: str) -> list[RecruiterContact]:
    """Extract unique, non-noise email addresses from raw HTML.

    Searches both mailto: href attributes and inline email patterns in text.

    Args:
        html: Raw HTML content.
        source_url: The URL the HTML was fetched from (attached to contacts).

    Returns:
        Deduplicated list of RecruiterContact objects.
    """
    soup = BeautifulSoup(html, "lxml")
    emails: dict[str, RecruiterContact] = {}

    # 1. Extract from mailto: links (may include display name)
    for a_tag in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
        href: str = a_tag.get("href", "")
        email = href[len("mailto:"):].split("?")[0].strip().lower()
        if email and _is_valid_recruiter_email(email):
            name = a_tag.get_text(strip=True) or None
            if email not in emails:
                emails[email] = RecruiterContact(
                    email=email, name=name, source_url=source_url
                )

    # 2. Regex scan of the full text for any email-like patterns
    text = soup.get_text()
    for match in re.finditer(
        r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b", text
    ):
        email = match.group(0).lower()
        if email and _is_valid_recruiter_email(email) and email not in emails:
            emails[email] = RecruiterContact(email=email, source_url=source_url)

    return list(emails.values())


def _is_valid_recruiter_email(email: str) -> bool:
    """Return True if the email looks like a real recruiter address."""
    prefix = email.split("@")[0].lower()
    return prefix not in _NOISE_EMAIL_PREFIXES


def _email_domain(email: str) -> str:
    """Return the domain part of an email address."""
    parts = email.split("@")
    return parts[1] if len(parts) == 2 else ""
