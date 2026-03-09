import json
import os
import re
from pathlib import Path
from typing import Optional

import anthropic

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 6000  # budget_breakdown adds significant JSON; needs extra headroom
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "experiment.txt"


def run_experiment_agent(gap: dict, abstracts: Optional[list] = None) -> dict:
    """
    Design a rigorous experiment proposal for a single research gap.

    Args:
        gap: A single gap dict with keys such as gap_title, clinical_importance,
             why_neglected, what_changes_if_addressed, feasible_study_type, urgency_score.
        abstracts: Optional list of PubMed abstracts (with pmid, title, year, authors)
                   to use as the citation pool for Type A references.

    Returns:
        Parsed JSON dict with a "proposal" key, or an error dict on failure.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    user_message = (
        "Below is an underresearched gap in endometriosis research. "
        "Design a rigorous, fundable experiment proposal and return it as JSON.\n\n"
        "## Research Gap\n"
        + json.dumps(gap, indent=2)
        + _build_abstracts_block(abstracts)
    )
    return _call_with_retry(system_prompt, user_message)


def _build_abstracts_block(abstracts: Optional[list]) -> str:
    """Return a condensed reference block for citation grounding, or empty string."""
    if not abstracts:
        return ""
    # Include only the fields needed for citation: pmid, title, year, first author
    refs = []
    for a in abstracts:
        pmid = a.get("pmid", "")
        title = a.get("title", "")
        year = a.get("year", "")
        authors = a.get("authors", [])
        first_author = f"{authors[0]} et al." if authors else "Unknown"
        if pmid and title:
            refs.append({"pmid": pmid, "title": title, "year": year, "first_author": first_author})
    if not refs:
        return ""
    return (
        "\n\n## Reference Abstracts (Type A citations must come only from this list)\n"
        + json.dumps(refs, indent=2)
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
        raw = response.content[0].text.strip() if response.content else ""
        print(f"[ExperimentAgent] Raw response (attempt {attempt + 1}):\n{raw}\n")

        if not raw:
            if attempt == 0:
                print("[ExperimentAgent] Empty response (attempt 1). Retrying...")
                continue
            print("[ExperimentAgent] Empty response after retry.")
            return {"error": "Empty response from Claude", "raw": ""}

        cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            if attempt == 0:
                print(f"[ExperimentAgent] JSON parse failed (attempt 1): {e}. Retrying...")
                continue
            print(f"[ExperimentAgent] JSON parse failed after retry: {e}")
            return {"error": "Failed to parse JSON response", "raw": raw}
