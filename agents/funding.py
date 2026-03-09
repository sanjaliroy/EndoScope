import json
import os
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "funding.txt"


def run_funding_agent(proposal: dict, funding_sources: list) -> dict:
    """
    Match an experiment proposal to the top 5 most relevant funding sources.

    Args:
        proposal: Dict produced by run_experiment_agent, containing a "proposal" key.
        funding_sources: List of funding source dicts from funding_sources.json.

    Returns:
        Parsed JSON dict with a "matches" key, or an error dict on failure.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_message = (
        "Below is an endometriosis experiment proposal followed by a list of available "
        "funding sources. Return the top 5 funding matches ranked by fit as JSON.\n\n"
        "## Experiment Proposal\n"
        + json.dumps(proposal, indent=2)
        + "\n\n## Funding Sources\n"
        + json.dumps(funding_sources, indent=2)
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
                print(f"[FundingAgent] JSON parse failed (attempt 1): {e}. Retrying...")
                continue
            print(f"[FundingAgent] JSON parse failed after retry: {e}")
            return {"error": "Failed to parse JSON response", "raw": raw}
