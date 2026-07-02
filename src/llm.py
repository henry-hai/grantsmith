"""Provider-agnostic LLM client.

Exposes a single generate(system, user) function that routes to OpenAI or
Anthropic based on the LLM_PROVIDER environment variable. Switching providers
requires no code changes, only environment variables:

    LLM_PROVIDER=openai|anthropic
    LLM_MODEL=<model id for that provider>
"""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOKENS = 2048


class LLMError(Exception):
    """Raised when the LLM call fails or is misconfigured."""


def generate(system: str, user: str) -> str:
    """Send one system and user prompt pair to the configured provider."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    model = os.getenv("LLM_MODEL", DEFAULT_MODEL).strip()

    if provider == "openai":
        return _generate_openai(system, user, model)
    if provider == "anthropic":
        return _generate_anthropic(system, user, model)
    raise LLMError(
        f"Unknown LLM_PROVIDER '{provider}'. Set it to 'openai' or 'anthropic'."
    )


def _generate_openai(system: str, user: str, model: str) -> str:
    import openai

    if not os.getenv("OPENAI_API_KEY"):
        raise LLMError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = openai.OpenAI()
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except openai.OpenAIError as exc:
        raise LLMError(f"OpenAI request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise LLMError("OpenAI returned an empty response.")
    return text.strip()


def _generate_anthropic(system: str, user: str, model: str) -> str:
    import anthropic

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise LLMError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as exc:
        raise LLMError(f"Anthropic request failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise LLMError("Anthropic declined to answer this prompt.")

    text = "\n\n".join(
        block.text for block in response.content if block.type == "text"
    )
    if not text:
        raise LLMError("Anthropic returned an empty response.")
    return text.strip()