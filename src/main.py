"""GrantSmith command line entry point.

Usage:
    python -m src.main \\
        --questions inputs/example_grant_questions.md \\
        --org data/org_facts.md \\
        --examples data/examples \\
        --out outputs/draft.docx
"""

import argparse
import sys

from . import grant_writer
from .docx_export import write_docx
from .llm import LLMError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="grantsmith",
        description="Draft a grant proposal in a nonprofit's voice.",
    )
    parser.add_argument(
        "--questions",
        required=True,
        help="Path to the funder application questions file.",
    )
    parser.add_argument(
        "--org",
        required=True,
        help="Path to the organization facts file.",
    )
    parser.add_argument(
        "--examples",
        required=True,
        help="Path to the directory of example past proposals.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Path for the generated .docx draft.",
    )
    parser.add_argument(
        "--title",
        default="Grant Proposal Draft",
        help="Title placed at the top of the .docx file.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    try:
        org_facts = grant_writer.load_org_facts(args.org)
        examples = grant_writer.load_examples(args.examples)
        questions_text = grant_writer.load_questions(args.questions)
    except grant_writer.InputError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 1

    questions = grant_writer.split_questions(questions_text)
    if not questions:
        print(
            "No questions found. Check that questions are numbered, "
            "for example '1. ...'.",
            file=sys.stderr,
        )
        return 1

    print(f"Found {len(questions)} question(s). Drafting sections.\n")

    sections = []
    for number, question in enumerate(questions, start=1):
        preview = question if len(question) <= 70 else question[:67] + "..."
        print(f"[{number}/{len(questions)}] Drafting: {preview}")
        try:
            answer = grant_writer.draft_section(question, org_facts, examples)
        except LLMError as exc:
            print(f"LLM error while drafting section {number}: {exc}", file=sys.stderr)
            return 2
        sections.append((question, answer))

    try:
        write_docx(sections, args.out, args.title)
    except OSError as exc:
        print(f"Could not write output file: {exc}", file=sys.stderr)
        return 1

    print(f"\nDone. Wrote {len(sections)} section(s) to {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())