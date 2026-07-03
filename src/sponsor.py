"""Sponsor context loading for GrantSmith.

Builds a block of grounding context about the sponsor a grant is aimed at, so
drafted answers can be tailored to that sponsor's priorities. Context is
assembled from two optional sources, in any combination:

- One or more sponsor web pages, fetched live and reduced to readable text.
- A manual context file written by the grant writer (relationship history,
  program officer, the specific ask, alignment notes).

Using both together is the hybrid mode: the sponsor's own words from their
site, plus the human context the site does not contain.
"""

import sys
from pathlib import Path

from . import grant_writer

USER_AGENT = "GrantSmith grant-research assistant"
FETCH_TIMEOUT_SECONDS = 20
MAX_CHARS_PER_PAGE = 12000
STRIP_TAGS = ("script", "style", "noscript", "header", "footer", "nav", "form")


def load_sponsor_context(
    urls: list[str] | None = None,
    sponsor_file: str | None = None,
) -> str:
    """Assemble sponsor context from live pages and an optional manual file.

    Returns an empty string when no sources are given or none produce text, in
    which case drafting proceeds without sponsor tailoring.
    """
    chunks = []

    for url in urls or []:
        text = _fetch_page_text(url)
        if text:
            chunks.append(f"Sponsor web page ({url}):\n\n{text}")

    if sponsor_file:
        path = Path(sponsor_file)
        if not path.is_file():
            raise grant_writer.InputError(f"Sponsor file not found: {sponsor_file}")
        manual = grant_writer._read_text_file(path).strip()
        if manual:
            chunks.append(f"Context from the grant writer:\n\n{manual}")

    return "\n\n".join(chunks)


def _fetch_page_text(url: str) -> str:
    """Fetch one page and reduce it to readable text.

    On any network or HTTP error this prints a warning and returns an empty
    string, so a bad sponsor URL never stops a drafting run.
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  Could not fetch sponsor page {url}: {exc}", file=sys.stderr)
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(list(STRIP_TAGS)):
        tag.decompose()

    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned[:MAX_CHARS_PER_PAGE]