"""Tests for sponsor context loading.

Network access is mocked, so these tests never make a real HTTP request.
"""

import requests

from src import grant_writer, prompts, sponsor


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


def test_fetch_page_extracts_visible_text(monkeypatch):
    html = (
        "<html><head><style>.x{color:red}</style>"
        "<script>var secret = 1</script></head>"
        "<body><nav>Menu</nav><h1>Giving</h1>"
        "<p>We fund youth creativity and arts access.</p>"
        "<footer>Copyright</footer></body></html>"
    )
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(html))

    text = sponsor._fetch_page_text("https://sponsor.example/giving")
    assert "We fund youth creativity and arts access." in text
    assert "var secret" not in text
    assert "color:red" not in text


def test_fetch_page_handles_network_error(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise requests.RequestException("connection refused")

    monkeypatch.setattr(requests, "get", boom)

    text = sponsor._fetch_page_text("https://sponsor.example/down")
    assert text == ""
    assert "Could not fetch sponsor page" in capsys.readouterr().err


def test_load_sponsor_context_hybrid(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sponsor,
        "_fetch_page_text",
        lambda url: "Adobe funds creativity and digital skills.",
    )
    notes = tmp_path / "adobe.md"
    notes.write_text(
        "We met their program officer at a spring event.", encoding="utf-8"
    )

    context = sponsor.load_sponsor_context(
        urls=["https://adobe.example/giving"],
        sponsor_file=str(notes),
    )
    assert "Adobe funds creativity and digital skills." in context
    assert "We met their program officer at a spring event." in context


def test_load_sponsor_context_empty_when_no_sources():
    assert sponsor.load_sponsor_context() == ""


def test_load_sponsor_context_missing_file_raises(tmp_path):
    import pytest

    with pytest.raises(grant_writer.InputError):
        sponsor.load_sponsor_context(sponsor_file=str(tmp_path / "nope.md"))


def test_build_user_prompt_includes_sponsor_when_present():
    with_sponsor = prompts.build_user_prompt(
        org_facts="We serve youth.",
        examples="Example proposal.",
        question="What is your mission?",
        sponsor_context="Adobe funds youth creativity.",
    )
    assert "<sponsor_context>" in with_sponsor
    assert "Adobe funds youth creativity." in with_sponsor


def test_build_user_prompt_omits_sponsor_when_empty():
    without_sponsor = prompts.build_user_prompt(
        org_facts="We serve youth.",
        examples="Example proposal.",
        question="What is your mission?",
    )
    assert "<sponsor_context>" not in without_sponsor


def test_draft_section_passes_sponsor_context(monkeypatch):
    captured = {}

    def fake_generate(system, user):
        captured["user"] = user
        return "Tailored section."

    monkeypatch.setattr(grant_writer, "generate", fake_generate)

    grant_writer.draft_section(
        question="What is your mission?",
        org_facts="We serve youth.",
        examples="Example proposal.",
        sponsor_context="Apple funds education equity.",
    )
    assert "Apple funds education equity." in captured["user"]
