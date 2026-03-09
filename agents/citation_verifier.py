import time
import xml.etree.ElementTree as ET
from typing import Optional

import requests

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Stable root-domain homepages for Type B institutional citations.
# Values are the canonical fallback URL used when a deep link fails.
ORG_URLS = {
    "who": "https://www.who.int",
    "world health organization": "https://www.who.int",
    "nih": "https://www.nih.gov",
    "national institutes of health": "https://www.nih.gov",
    "nih reporter": "https://reporter.nih.gov",
    "cdc": "https://www.cdc.gov",
    "centers for disease control": "https://www.cdc.gov",
    "werf": "https://werf.co",
    "world endometriosis research foundation": "https://werf.co",
    "endofound": "https://www.endofound.org",
    "endometriosis foundation of america": "https://www.endofound.org",
    "acog": "https://www.acog.org",
    "american college of obstetricians and gynecologists": "https://www.acog.org",
    "nature women's health": "https://www.nature.com/nwom",
    "pcori": "https://www.pcori.org",
    "asrm": "https://www.asrm.org",
    "american society for reproductive medicine": "https://www.asrm.org",
    "eshre": "https://www.eshre.eu",
    "nimhd": "https://www.nimhd.nih.gov",
    "national institute on minority health and health disparities": "https://www.nimhd.nih.gov",
    "ahrq": "https://www.ahrq.gov",
    "agency for healthcare research and quality": "https://www.ahrq.gov",
}


def verify_citations(proposals: list) -> list:
    """
    Verify all citations in a list of experiment proposals.

    Type A: Fetch PMID from PubMed efetch. Remove if PMID doesn't exist or
            title doesn't roughly match (prevents hallucinated references).
    Type B: HEAD-request the organization's URL. Remove if unreachable.

    Adds 'citations_verified' (bool) and 'verified_count' (int) to each proposal.
    """
    verified_proposals = []
    for proposal in proposals:
        p = proposal.get("proposal", proposal)
        raw_citations = p.get("citations", [])

        clean = []
        for citation in raw_citations:
            ctype = citation.get("type", "").upper()
            if ctype == "A":
                result = _verify_type_a(citation)
            elif ctype == "B":
                result = _verify_type_b(citation)
            else:
                result = None  # unknown type — drop it

            if result is not None:
                clean.append(result)

            time.sleep(0.35)  # respect NCBI rate limit across the loop

        # Write clean citations back; store verification metadata
        key = "proposal" if "proposal" in proposal else None
        target = proposal["proposal"] if key else proposal
        target["citations"] = clean
        target["citations_verified"] = True
        target["verified_count"] = sum(1 for c in clean if c.get("verified"))

        verified_proposals.append(proposal)

    return verified_proposals


# ── Type A: PubMed PMID verification ─────────────────────────────────────────

def _verify_type_a(citation: dict) -> Optional[dict]:
    """
    Fetch the paper by PMID and check that the title roughly matches.
    Returns the citation dict with verified=True, or None to drop it.
    """
    pmid = str(citation.get("pmid") or "").strip()
    if not pmid:
        print(f"[CitationVerifier] Type A citation missing PMID — dropping: {citation.get('title_or_report', '')[:60]}")
        return None

    try:
        response = requests.get(
            EFETCH_URL,
            params={"db": "pubmed", "id": pmid, "retmode": "xml"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[CitationVerifier] PubMed fetch failed for PMID {pmid}: {e} — dropping")
        return None

    fetched_title = _parse_title_from_xml(response.text)
    if not fetched_title:
        print(f"[CitationVerifier] PMID {pmid} not found in PubMed — dropping")
        return None

    if not _titles_match(fetched_title, citation.get("title_or_report", "")):
        print(
            f"[CitationVerifier] Title mismatch for PMID {pmid}:\n"
            f"  Fetched : {fetched_title[:80]}\n"
            f"  Claimed : {citation.get('title_or_report', '')[:80]}\n"
            f"  — dropping"
        )
        return None

    # Canonicalize title to the authoritative PubMed version
    verified = dict(citation)
    verified["title_or_report"] = fetched_title
    verified["verified"] = True
    print(f"[CitationVerifier] PMID {pmid} verified ✓")
    return verified


def _parse_title_from_xml(xml_text: str) -> str:
    try:
        root = ET.fromstring(xml_text)
        el = root.find(".//ArticleTitle")
        if el is None:
            return ""
        return "".join(el.itertext()).strip()
    except ET.ParseError:
        return ""


def _titles_match(fetched: str, claimed: str) -> bool:
    """
    Return True if the two titles share enough keywords to be considered the same paper.
    Threshold: at least 4 significant words (>3 chars) from the fetched title appear in
    the claimed title (case-insensitive). Handles minor subtitle or punctuation differences.
    """
    def keywords(text: str) -> set:
        return {w.lower().strip(".,;:()[]") for w in text.split() if len(w) > 3}

    fetched_kw = keywords(fetched)
    claimed_kw = keywords(claimed)
    if not fetched_kw:
        return False
    overlap = fetched_kw & claimed_kw
    return len(overlap) >= min(4, len(fetched_kw))


# ── Type B: Institutional URL verification ────────────────────────────────────

def _verify_type_b(citation: dict) -> Optional[dict]:
    """
    Verify that the cited organization's URL is reachable via HEAD request.
    Returns the citation dict with verified=True, or None to drop it.
    """
    org = (citation.get("authors_or_org") or "").strip()
    url = ORG_URLS.get(org.lower())

    if not url:
        # Unknown org — keep it but mark as unverified rather than dropping,
        # since failure to find a URL doesn't mean the org doesn't exist.
        print(f"[CitationVerifier] No URL mapping for org '{org}' — keeping unverified")
        verified = dict(citation)
        verified["verified"] = False
        return verified

    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        if 200 <= resp.status_code <= 399:
            verified = dict(citation)
            verified["url"] = url
            verified["verified"] = True
            print(f"[CitationVerifier] Type B org '{org}' reachable at {url} ✓")
            return verified
        else:
            print(f"[CitationVerifier] Type B org '{org}' returned HTTP {resp.status_code} — using root domain {url}")
            verified = dict(citation)
            verified["url"] = url
            verified["verified"] = False
            return verified
    except requests.RequestException as e:
        print(f"[CitationVerifier] Type B URL check failed for '{org}' ({url}): {e} — using root domain {url}")
        verified = dict(citation)
        verified["url"] = url
        verified["verified"] = False
        return verified
