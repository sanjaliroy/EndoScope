import json
import os
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "gap_analyzer.txt"


def run_gap_agent(theme_landscape: dict) -> dict:
    """
    Identify the 3 most impactful underresearched gaps from the theme landscape.

    Args:
        theme_landscape: Dict produced by run_literature_agent, containing a "themes" key.

    Returns:
        Parsed JSON dict with a "gaps" key, or an error dict on failure.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_message = (
        "Below is the current endometriosis research landscape organized by theme. "
        "Identify the 3 most impactful underresearched gaps and return them as JSON.\n\n"
        + json.dumps(theme_landscape, indent=2)
    )
    return _call_with_retry(system_prompt, user_message)


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
                print(f"[GapAgent] JSON parse failed (attempt 1): {e}. Retrying...")
                continue
            print(f"[GapAgent] JSON parse failed after retry: {e}")
            return {"error": "Failed to parse JSON response", "raw": raw}
