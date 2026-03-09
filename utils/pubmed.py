import time
import requests
import xml.etree.ElementTree as ET

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 20  # NCBI recommends fetching in batches


def fetch_pubmed_abstracts(query: str, max_results: int = 80) -> list[dict]:
    """
    Search PubMed and return abstracts for the top max_results papers.

    Args:
        query: PubMed search query string.
        max_results: Maximum number of papers to retrieve (default 80).

    Returns:
        List of dicts with keys: title, abstract, year, authors.
    """
    pmids = _search_pubmed(query, max_results)
    if not pmids:
        return []

    results = []
    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i : i + BATCH_SIZE]
        records = _fetch_records(batch)
        results.extend(records)
        if i + BATCH_SIZE < len(pmids):
            time.sleep(0.34)  # stay under 3 requests/sec for unauthenticated users

    return results


def _search_pubmed(query: str, max_results: int) -> list[str]:
    """Return a list of PubMed IDs for the query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    try:
        response = requests.get(ESEARCH_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except requests.RequestException as e:
        print(f"[PubMed] Search error: {e}")
        return []
    except ValueError as e:
        print(f"[PubMed] JSON parse error: {e}")
        return []


def _fetch_records(pmids: list[str]) -> list[dict]:
    """Fetch and parse article records for a batch of PubMed IDs."""
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    try:
        response = requests.get(EFETCH_URL, params=params, timeout=30)
        response.raise_for_status()
        return _parse_xml(response.text)
    except requests.RequestException as e:
        print(f"[PubMed] Fetch error for IDs {pmids}: {e}")
        return []


def _parse_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML response into a list of article dicts."""
    records = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"[PubMed] XML parse error: {e}")
        return records

    for article in root.findall(".//PubmedArticle"):
        records.append({
            "pmid": _extract_pmid(article),
            "title": _extract_title(article),
            "abstract": _extract_abstract(article),
            "year": _extract_year(article),
            "authors": _extract_authors(article),
        })

    return records


def _extract_pmid(article: ET.Element) -> str:
    el = article.find(".//PMID")
    return el.text.strip() if el is not None and el.text else ""


def _extract_title(article: ET.Element) -> str:
    el = article.find(".//ArticleTitle")
    if el is None:
        return ""
    # Concatenate all text including sub-elements (e.g. italics)
    return "".join(el.itertext()).strip()


def _extract_abstract(article: ET.Element) -> str:
    texts = []
    for el in article.findall(".//AbstractText"):
        label = el.get("Label")
        text = "".join(el.itertext()).strip()
        if text:
            texts.append(f"{label}: {text}" if label else text)
    return " ".join(texts)


def _extract_year(article: ET.Element) -> str:
    # Prefer PubDate year; fall back to MedlineDate
    for tag in ("PubDate/Year", "ArticleDate/Year", "PubDate/MedlineDate"):
        el = article.find(f".//{tag}")
        if el is not None and el.text:
            return el.text[:4]
    return ""


def _extract_authors(article: ET.Element) -> list[str]:
    authors = []
    for author in article.findall(".//Author"):
        last = author.findtext("LastName", "")
        initials = author.findtext("Initials", "")
        name = f"{last} {initials}".strip()
        if name:
            authors.append(name)
    return authors
