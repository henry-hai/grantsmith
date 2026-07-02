# GrantSmith

GrantSmith is an AI grant-writing assistant that runs from the terminal. Give it a funder's application questions and it drafts a full proposal, section by section, in the voice of a specific nonprofit. It uses the nonprofit's past proposals and basic organizational facts as style and content references, and it outputs a formatted .docx file ready for review and editing.

Version 1 was built for ArtHouse Studio, but nothing about the organization is hardcoded. Swap out the data files and GrantSmith writes for any nonprofit.

## How it works

1. Reads a markdown file of funder application questions and splits it into individual questions.
2. For each question, calls an LLM once with a prompt that includes the org facts, the example past proposals as style references, and that single question.
3. Assembles all drafted sections into one .docx file, with each question as a heading and the drafted answer beneath it.

## Setup

Requires Python 3.11 or higher.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and add your API key for whichever provider you are using.

## Usage

```bash
python -m src.main \
  --questions inputs/example_grant_questions.md \
  --org data/org_facts.md \
  --examples data/examples \
  --out outputs/draft.docx
```

Arguments:

| Flag | Description |
| --- | --- |
| `--questions` | Markdown file containing the funder's application questions |
| `--org` | Markdown file with the nonprofit's facts (mission, programs, wins) |
| `--examples` | Directory of past proposals used as style references |
| `--out` | Path for the generated .docx draft |

## Configuring the LLM provider

GrantSmith is provider-agnostic. The provider and model are read from environment variables, and switching providers requires zero code changes.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai` | Which provider to use: `openai` or `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | The model id sent to the provider |
| `OPENAI_API_KEY` | none | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | none | Required when `LLM_PROVIDER=anthropic` |

The default is OpenAI with `gpt-4o-mini` for cheap testing.

### Switching to Claude for delivery

Set two environment variables in `.env` and nothing else:

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=<current Claude Sonnet model id>
```

Copy the current Claude Sonnet model id from [console.anthropic.com](https://console.anthropic.com). No code changes are needed.

## Customizing for another nonprofit

- Replace `data/org_facts.md` with the new organization's mission, programs, people served, and past wins.
- Replace the files in `data/examples/` with two or three of the organization's real past proposals in markdown.
- Point `--questions` at the new funder's application questions.

## Project structure

```
src/
  main.py           CLI entry point
  llm.py            Provider-agnostic LLM client
  prompts.py        All prompt templates
  grant_writer.py   Core drafting logic
  docx_export.py    Writes the assembled draft to .docx
data/
  org_facts.md      Placeholder facts for ArtHouse Studio
  examples/         Placeholder past proposals (style references)
inputs/             Example funder questions for demoing
outputs/            Generated drafts (gitignored)
tests/              Pytest tests with a mocked LLM (no API key needed)
```

## Running tests

Tests mock the LLM call, so they run without an API key:

```bash
pytest
```

## Roadmap

Planned upgrades for v2:

- Real RAG retrieval with embeddings over past proposals, so the most relevant passages are selected per question instead of including all examples in every prompt.
- Direct Google Docs API export, so drafts land in a shared Drive folder instead of a local .docx file.
