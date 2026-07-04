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
from . import retrieval
from . import sponsor
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
        "--sponsor-url",
        action="append",
        default=None,
        metavar="URL",
        help=(
            "Sponsor web page to fetch for grounding context. Repeat the flag "
            "to include more than one page."
        ),
    )
    parser.add_argument(
        "--sponsor-file",
        default=None,
        help=(
            "File of manual sponsor context (relationship, ask, alignment "
            "notes). Combined with any --sponsor-url pages."
        ),
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
        sponsor_context = sponsor.load_sponsor_context(
            args.sponsor_url, args.sponsor_file
        )
    except grant_writer.InputError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 1

    if sponsor_context:
        print("Loaded sponsor context. Answers will be tailored to the sponsor.")
    else:
        print("No sponsor context provided. Drafting without sponsor tailoring.")

    questions = grant_writer.split_questions(questions_text)
    if not questions:
        print(
            "No questions found. Check that questions are numbered, "
            "for example '1. ...'.",
            file=sys.stderr,
        )
        return 1

    top_k = retrieval.get_top_k()
    index = retrieval.try_build_index(examples, top_k)
    if index is not None:
        print(
            f"Built retrieval index of {len(index.chunks)} example chunk(s). "
            f"Injecting the top {top_k} per question."
        )
    else:
        print("Retrieval unavailable. Using the full example text per question.")

    print(f"Found {len(questions)} question(s). Drafting sections.\n")

    sections = []
    for number, question in enumerate(questions, start=1):
        preview = question if len(question) <= 70 else question[:67] + "..."
        print(f"[{number}/{len(questions)}] Drafting: {preview}")

        examples_for_question = examples
        if index is not None:
            try:
                examples_for_question = "\n\n".join(
                    index.retrieve(question, top_k)
                )
            except retrieval.EmbeddingError as exc:
                print(
                    f"  Could not embed the question ({exc}). Using the full "
                    "example text for the rest of this run.",
                    file=sys.stderr,
                )
                index = None
                examples_for_question = examples

        try:
            answer = grant_writer.draft_section(
                question, org_facts, examples_for_question, sponsor_context
            )
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