"""Core drafting logic for GrantSmith.

This module loads the organization facts, the example past proposals, and the
funder questions, then drafts one proposal section per question by calling the
provider-agnostic LLM client.
"""

import os
from pathlib import Path

from . import prompts
from .llm import generate

EXAMPLES_EXTENSIONS = (".md",)
QUESTIONS_EXTENSIONS = (".md",)


class InputError(Exception):
    """Raised when an input file or directory cannot be read."""


def _read_text_file(path: Path) -> str:
    """Extract text from a single supported file.

    Only markdown and plain text are supported here. Support for other file
    types is added by extending this dispatcher.
    """
    suffix = path.suffix.lower()
    if suffix in (".md", ".txt"):
        return path.read_text(encoding="utf-8")
    raise InputError(f"Unsupported file type '{suffix}' for {path}.")


def load_org_facts(path: str) -> str:
    """Load the organization facts file."""
    facts_path = Path(path)
    if not facts_path.is_file():
        raise InputError(f"Org facts file not found: {path}")
    text = _read_text_file(facts_path).strip()
    if not text:
        raise InputError(f"Org facts file is empty: {path}")
    return text


def load_examples(directory: str) -> str:
    """Load and concatenate every supported example proposal in a directory."""
    examples_dir = Path(directory)
    if not examples_dir.is_dir():
        raise InputError(f"Examples directory not found: {directory}")

    chunks = []
    for entry in sorted(examples_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in EXAMPLES_EXTENSIONS:
            print(f"  Skipping unsupported example file: {entry.name}")
            continue
        text = _read_text_file(entry).strip()
        if text:
            chunks.append(f"### Example: {entry.name}\n\n{text}")

    if not chunks:
        raise InputError(f"No usable example proposals found in {directory}")
    return "\n\n".join(chunks)


def load_questions(path: str) -> str:
    """Load the raw text of the funder questions file."""
    questions_path = Path(path)
    if not questions_path.is_file():
        raise InputError(f"Questions file not found: {path}")
    if questions_path.suffix.lower() not in QUESTIONS_EXTENSIONS:
        raise InputError(
            f"Unsupported questions file type '{questions_path.suffix}'."
        )
    text = _read_text_file(questions_path).strip()
    if not text:
        raise InputError(f"Questions file is empty: {path}")
    return text


def split_questions(text: str) -> list[str]:
    """Split raw questions text into a list of individual questions.

    A question begins at a line that starts with a number followed by a period
    or a closing parenthesis, for example '1.' or '2)'. Everything up to the
    next such line belongs to the same question, so multi-line questions are
    preserved. Header lines and instructions before the first numbered item are
    ignored.
    """
    questions = []
    current: list[str] = []

    def flush() -> None:
        if current:
            joined = " ".join(part.strip() for part in current if part.strip())
            if joined:
                questions.append(joined)

    for line in text.splitlines():
        stripped = line.strip()
        if _starts_new_question(stripped):
            flush()
            current = [_strip_leading_number(stripped)]
        elif current:
            current.append(stripped)

    flush()
    return questions


def _starts_new_question(line: str) -> bool:
    """Return True if a line begins a new numbered question."""
    index = 0
    while index < len(line) and line[index].isdigit():
        index += 1
    if index == 0:
        return False
    if index >= len(line) or line[index] not in ".)":
        return False
    rest = line[index + 1:]
    return rest.startswith(" ") or rest == ""


def _strip_leading_number(line: str) -> str:
    """Remove a leading '1.' or '2)' marker from a question line."""
    index = 0
    while index < len(line) and line[index].isdigit():
        index += 1
    if index < len(line) and line[index] in ".)":
        index += 1
    return line[index:].strip()


def draft_section(question: str, org_facts: str, examples: str) -> str:
    """Draft one proposal section answering a single question."""
    user_prompt = prompts.build_user_prompt(org_facts, examples, question)
    return generate(prompts.SYSTEM_PROMPT, user_prompt)