import json
import os
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "literature.txt"

# We cap at 30 abstracts and 300 chars each. The literature agent's job is
# thematic synthesis, not exhaustive review — a representative sample produces
# equally useful theme clusters while keeping the prompt small enough to avoid
# context-window pressure and reduce latency/cost.
MAX_ABSTRACTS = 30
MAX_ABSTRACT_CHARS = 300
MAX_TOTAL_CHARS = 180_000


def run_literature_agent(abstracts: list) -> dict:
    """
    Categorize a list of paper abstracts into endometriosis research themes.

    Args:
        abstracts: List of dicts with keys: title, abstract, year, authors.

    Returns:
        Parsed JSON dict with a "themes" key, or an error dict on failure.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_message = _build_user_message(abstracts)
    return _call_with_retry(system_prompt, user_message)


def _build_user_message(abstracts: list) -> str:
    truncated = []
    total_chars = 0
    for paper in abstracts[:MAX_ABSTRACTS]:
        abstract_text = (paper.get("abstract") or "")[:MAX_ABSTRACT_CHARS]
        entry = {
            "title": paper.get("title", ""),
            "abstract": abstract_text,
            "year": paper.get("year", ""),
            "authors": paper.get("authors", [])[:5],  # cap author list
        }
        serialized = json.dumps(entry)
        if total_chars + len(serialized) > MAX_TOTAL_CHARS:
            break
        truncated.append(entry)
        total_chars += len(serialized)

    return (
        f"Below are {len(truncated)} endometriosis paper abstracts. "
        "Analyze them and return the theme landscape as JSON.\n\n"
        + json.dumps(truncated, indent=2)
    )


def _call_with_retry(system_prompt: str, user_message: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    for attempt in range(2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            if attempt == 0:
                print(f"[LiteratureAgent] JSON parse failed (attempt 1): {e}. Retrying...")
                continue
            print(f"[LiteratureAgent] JSON parse failed after retry: {e}")
            return {"error": "Failed to parse JSON response", "raw": raw}
