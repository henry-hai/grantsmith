# GrantSmith

GrantSmith is an AI grant-writing assistant that runs from the terminal. Give it a funder's application questions and it drafts a full proposal, section by section, in the voice of a specific nonprofit. It uses the nonprofit's past proposals and basic organizational facts as style and content references, and it outputs a formatted .docx file ready for review and editing.

Version 1 was built for ArtHouse Studio, but nothing about the organization is hardcoded. Swap out the data files and GrantSmith writes for any nonprofit.

## How it works

1. Reads a funder application questions file and splits it into individual questions.
2. For each question, retrieves the most relevant passages from the example proposals (see Retrieval below) and calls an LLM once with a prompt that includes the org facts, those retrieved passages as style references, and that single question.
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
| `--questions` | Funder's application questions as a .md, .pdf, or .docx file |
| `--org` | Markdown file with the nonprofit's facts (mission, programs, wins) |
| `--examples` | Directory of past proposals used as style references |
| `--out` | Path for the generated .docx draft |

Drop past proposals into `data/examples` as .md, .pdf, or .docx. GrantSmith extracts the text from each file. Files with any other extension are skipped with a warning rather than stopping the run. The `--questions` file may also be a .md, .pdf, or .docx file.

## Retrieval over past proposals

GrantSmith does not stuff every example proposal into every prompt. Instead it uses retrieval (RAG) so each question is answered against only the most relevant example passages.

On each run GrantSmith reads the example proposals, splits their text into overlapping chunks, and embeds each chunk with an OpenAI embedding model. For every question it embeds the question, ranks the chunks by cosine similarity, and injects only the top matches into the prompt. Vectors are held in memory with numpy for the duration of the run. There is no external vector database and nothing is persisted to disk.

Embeddings use OpenAI, so `OPENAI_API_KEY` is required whenever retrieval is active, even if drafting itself uses Anthropic.

Retrieval is controlled by these environment variables, all optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model used for chunks and questions |
| `RAG_TOP_K` | `5` | Number of example chunks injected per question |
| `CHUNK_SIZE` | `1000` | Target chunk size in characters |
| `CHUNK_OVERLAP` | `200` | Overlap between consecutive chunks in characters |

Graceful fallback: if there are fewer example chunks than `RAG_TOP_K`, or embeddings cannot be produced (for example a missing key or an API error), GrantSmith prints a clear warning and falls back to using the full example text for that run rather than stopping.

## Tailoring to a specific sponsor

GrantSmith can ground its answers in the sponsor a grant is aimed at, so the draft speaks to that sponsor's priorities instead of reading as generic. Sponsor context comes from two optional sources that can be used alone or together.

| Flag | Description |
| --- | --- |
| `--sponsor-url` | A sponsor web page to fetch and read for grounding context. Repeat the flag to include more than one page. |
| `--sponsor-file` | A file of manual sponsor context you write: relationship history, program officer, the specific ask, alignment notes. Use `data/sponsors/example_sponsor.md` as a starting template. |

Three ways to use it:

- **Scrape only.** Pass one or more `--sponsor-url` pages. GrantSmith fetches each page, reduces it to readable text, and feeds it into the drafting prompt.
- **Manual only.** Pass a `--sponsor-file` you have written by hand.
- **Hybrid.** Pass both. The sponsor's own words from their site are combined with the human context the site does not contain.

Example, tailoring an application toward Adobe:

```bash
python -m src.main \
  --questions inputs/example_grant_questions.md \
  --org data/org_facts.md \
  --examples data/examples \
  --sponsor-url https://www.adobe.com/corporate-responsibility.html \
  --sponsor-file data/sponsors/adobe.md \
  --out outputs/adobe_draft.docx
```

If a sponsor page cannot be fetched, GrantSmith prints a warning and continues with whatever other context is available, rather than stopping the run. GrantSmith will not invent facts about the sponsor. It uses only the sponsor context you provide.

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
- Replace the files in `data/examples/` with two or three of the organization's real past proposals as .md, .pdf, or .docx.
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

- Direct Google Docs API export, so drafts land in a shared Drive folder instead of a local .docx file.

Already implemented: RAG retrieval with embeddings over past proposals, so the most relevant passages are selected per question instead of including all examples in every prompt. See "Retrieval over past proposals" above.
