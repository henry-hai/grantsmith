"""Tests for the drafting logic.

The LLM call is mocked, so these tests run without any API key or network.
"""

import pytest

from src import grant_writer
from src.docx_export import write_docx


def test_split_questions_basic():
    text = (
        "# Application\n\n"
        "Please answer each question.\n\n"
        "1. What is your mission?\n"
        "2. Who do you serve?\n"
        "3. How do you measure success?\n"
    )
    questions = grant_writer.split_questions(text)
    assert questions == [
        "What is your mission?",
        "Who do you serve?",
        "How do you measure success?",
    ]


def test_split_questions_multiline():
    text = (
        "1. Describe your mission and history.\n"
        "   What need do you address?\n"
        "2. Describe the program.\n"
    )
    questions = grant_writer.split_questions(text)
    assert questions[0] == "Describe your mission and history. What need do you address?"
    assert questions[1] == "Describe the program."


def test_split_questions_ignores_header_and_empty():
    assert grant_writer.split_questions("Just some intro text, no numbers.") == []


def test_load_org_facts(tmp_path):
    facts = tmp_path / "org.md"
    facts.write_text("Our mission is to help.", encoding="utf-8")
    assert grant_writer.load_org_facts(str(facts)) == "Our mission is to help."


def test_load_org_facts_missing(tmp_path):
    with pytest.raises(grant_writer.InputError):
        grant_writer.load_org_facts(str(tmp_path / "nope.md"))


def test_load_examples_reads_markdown(tmp_path):
    (tmp_path / "a.md").write_text("First proposal.", encoding="utf-8")
    (tmp_path / "b.md").write_text("Second proposal.", encoding="utf-8")
    combined = grant_writer.load_examples(str(tmp_path))
    assert "First proposal." in combined
    assert "Second proposal." in combined


def test_load_examples_skips_unsupported(tmp_path, capsys):
    (tmp_path / "a.md").write_text("Good proposal.", encoding="utf-8")
    (tmp_path / "notes.csv").write_text("x,y,z", encoding="utf-8")
    combined = grant_writer.load_examples(str(tmp_path))
    assert "Good proposal." in combined
    assert "Skipping unsupported example file: notes.csv" in capsys.readouterr().out


def test_load_examples_empty_directory(tmp_path):
    with pytest.raises(grant_writer.InputError):
        grant_writer.load_examples(str(tmp_path))


def test_draft_section_uses_mocked_llm(monkeypatch):
    captured = {}

    def fake_generate(system, user):
        captured["system"] = system
        captured["user"] = user
        return "A polished section."

    monkeypatch.setattr(grant_writer, "generate", fake_generate)

    result = grant_writer.draft_section(
        question="What is your mission?",
        org_facts="We serve youth.",
        examples="Example proposal text.",
    )
    assert result == "A polished section."
    assert "What is your mission?" in captured["user"]
    assert "We serve youth." in captured["user"]
    assert "Example proposal text." in captured["user"]


def test_write_docx_creates_file(tmp_path):
    out = tmp_path / "nested" / "draft.docx"
    sections = [
        ("What is your mission?", "We help youth.\n\nWe do it well."),
        ("Who do you serve?", "Bay Area students."),
    ]
    write_docx(sections, str(out), title="Draft")
    assert out.is_file()
    assert out.stat().st_size > 0