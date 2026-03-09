import json
import re
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from agents.citation_verifier import verify_citations
from agents.experiment import run_experiment_agent
from agents.funding import run_funding_agent
from agents.gap_analyzer import run_gap_agent
from agents.literature import run_literature_agent
from utils.pubmed import fetch_pubmed_abstracts

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EndoScope",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FUNDING_PATH = Path(__file__).parent / "data" / "funding_sources.json"
DEMO_PATH = Path(__file__).parent / "data" / "demo_results.json"
PUBMED_QUERY = (
    "endometriosis[MeSH] AND (diagnosis OR pathophysiology OR treatment "
    "OR biomarker OR pain OR genetics OR disparities OR quality of life)"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Base */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0e0e14;
        color: #e2e2f0;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    [data-testid="stSidebar"] { background-color: #13131f; }

    /* Header */
    .endo-header {
        padding: 2rem 0 1rem 0;
        border-bottom: 1px solid #2a2a40;
        margin-bottom: 2rem;
    }
    .endo-title {
        font-size: 2.4rem;
        font-weight: 700;
        color: #c084fc;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .endo-subtitle {
        font-size: 1rem;
        color: #8b8ba8;
        margin-top: 0.25rem;
    }

    /* Section headers */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #c084fc;
        border-left: 3px solid #c084fc;
        padding-left: 0.75rem;
        margin: 2rem 0 1rem 0;
    }

    /* Gap card */
    .gap-card {
        background: #16162a;
        border: 1px solid #2e2e50;
        border-left: 4px solid #c084fc;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
    }
    .gap-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #e2e2f0;
        margin-bottom: 0.4rem;
    }
    .urgency-badge {
        display: inline-block;
        background: #2d1b4e;
        color: #c084fc;
        border: 1px solid #7c3aed;
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 0.78rem;
        font-weight: 600;
    }

    /* Proposal section labels */
    .prop-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #7c6fcd;
        text-transform: uppercase;
        margin-bottom: 0.2rem;
        margin-top: 1rem;
    }
    .prop-value {
        font-size: 0.93rem;
        color: #cccce0;
        line-height: 1.6;
    }

    /* Funding card */
    .funding-card {
        background: #13131f;
        border: 1px solid #2e2e50;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .funder-name {
        font-size: 0.98rem;
        font-weight: 600;
        color: #e2e2f0;
        margin-bottom: 0.3rem;
    }
    .funder-meta {
        font-size: 0.8rem;
        color: #6b6b8a;
        margin-bottom: 0.5rem;
    }

    /* Progress bar override */
    .score-bar-bg {
        background: #1e1e35;
        border-radius: 4px;
        height: 6px;
        width: 100%;
        margin-bottom: 0.75rem;
    }
    .score-bar-fill {
        height: 6px;
        border-radius: 4px;
        background: linear-gradient(90deg, #7c3aed, #c084fc);
    }

    /* Expander */
    [data-testid="stExpander"] {
        background: #13131f;
        border: 1px solid #2e2e50 !important;
        border-radius: 8px !important;
    }

    /* Button */
    .stButton > button {
        background: linear-gradient(135deg, #7c3aed, #9d5cf5);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-weight: 600;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
        transition: opacity 0.15s;
    }
    .stButton > button:hover { opacity: 0.88; }

    /* Divider */
    hr { border-color: #2a2a40; }

    /* Citations */
    .citations-section { margin-top: 1.5rem; }
    .citations-header {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #7c6fcd;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }
    .citation-item {
        font-size: 0.82rem;
        line-height: 1.6;
        padding: 0.3rem 0;
        border-bottom: 1px solid #1e1e35;
        display: flex;
        gap: 0.5rem;
        align-items: baseline;
    }
    .citation-num { color: #5a5a7a; min-width: 1.4rem; font-size: 0.75rem; }
    .citation-type-a { color: #e2e2f0; }
    .citation-type-b { color: #c084fc; font-style: italic; }
    .citation-check { color: #4ade80; font-size: 0.75rem; margin-left: 4px; }
    .citation-unverified { color: #6b6b8a; font-size: 0.75rem; margin-left: 4px; }
    .verified-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #0d2b1a;
        border: 1px solid #166534;
        color: #4ade80;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 0.75rem;
    }

    /* Live / demo indicator badge */
    .result-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.04em;
    }
    .result-badge.live {
        background: #0d2b1a;
        color: #4ade80;
        border: 1px solid #166534;
    }
    .result-badge.demo {
        background: #1e1b2e;
        color: #a78bfa;
        border: 1px solid #5b21b6;
    }
    .badge-dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        display: inline-block;
    }

    /* Status text */
    .status-msg {
        color: #8b8ba8;
        font-size: 0.88rem;
        font-style: italic;
    }

    /* Budget table */
    .budget-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.87rem;
        margin-top: 0.5rem;
    }
    .budget-table th {
        text-align: left;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #7c6fcd;
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid #2e2e50;
    }
    .budget-table td {
        padding: 0.55rem 0.75rem;
        color: #cccce0;
        border-bottom: 1px solid #1e1e35;
        vertical-align: top;
        line-height: 1.5;
    }
    .budget-table tr:hover td { background: #16162a; }
    .budget-table .cat-cell {
        font-weight: 600;
        color: #e2e2f0;
        white-space: nowrap;
        width: 18%;
    }
    .budget-table .calc-cell {
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        color: #9d9dc0;
        width: 38%;
    }
    .budget-table .amt-cell {
        text-align: right;
        font-weight: 600;
        white-space: nowrap;
        width: 12%;
    }
    .budget-table tr.subtotal td {
        border-top: 1px solid #3a3a60;
        color: #c084fc;
        font-weight: 600;
    }
    .budget-table tr.grandtotal td {
        border-top: 2px solid #7c3aed;
        color: #ffffff;
        font-weight: 700;
        font-size: 0.92rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_funding_sources() -> list:
    with open(FUNDING_PATH) as f:
        return json.load(f)["funding_sources"]


def save_demo_results(results: dict):
    DEMO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEMO_PATH, "w") as f:
        json.dump(results, f, indent=2)


def load_demo_results() -> Optional[dict]:
    if not DEMO_PATH.exists():
        return None
    try:
        with open(DEMO_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def funding_url_map(sources: list) -> dict:
    """Return {name: url} lookup from funding sources list."""
    return {s["name"]: s.get("url", "") for s in sources}


def maturity_color(score: int) -> str:
    colors = {1: "#ef4444", 2: "#f97316", 3: "#eab308", 4: "#84cc16", 5: "#22c55e"}
    return colors.get(score, "#8b8ba8")


def render_progress_bar(score: int, max_score: int = 10) -> str:
    pct = int((score / max_score) * 100)
    return (
        f'<div class="score-bar-bg">'
        f'<div class="score-bar-fill" style="width:{pct}%"></div>'
        f"</div>"
    )


def render_field(label: str, value) -> str:
    if isinstance(value, (int, float)):
        display = str(value)
    else:
        display = value or "—"
    return (
        f'<p class="prop-label">{label}</p>'
        f'<p class="prop-value">{display}</p>'
    )


def escape_dollars(text: str) -> str:
    """Prevent Streamlit from interpreting $...$ as LaTeX math."""
    return text.replace("$", r"\$")


# Matches {{cite pmid="..." label="..."}} or {{cite url="..." label="..."}}
# Attribute order is flexible.
_CITE_RE = re.compile(r"\{\{cite\s+([^}]+)\}\}")

_PILL_STYLE = (
    "display:inline-block;"
    "background-color:#3d1f6e;"
    "color:#c084fc;"
    "font-size:0.75rem;"
    "padding:2px 8px;"
    "border-radius:999px;"
    "text-decoration:none;"
    "margin-left:4px;"
    "border:1px solid #7c3aed;"
    "white-space:nowrap;"
)


def render_inline_citations(text: str) -> str:
    """Replace {{cite ...}} markers with clickable HTML pill badges."""
    def _replace(match: re.Match) -> str:
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1)))
        pmid = attrs.get("pmid", "").strip()
        url = attrs.get("url", "").strip()
        label = attrs.get("label", "ref")
        href = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (url or "#")
        return f'<a href="{href}" target="_blank" style="{_PILL_STYLE}">{label} ↗</a>'

    return _CITE_RE.sub(_replace, text)


def render_budget_table(budget_breakdown: list):
    SUBTOTAL_CATS = {"Total Direct Costs", "Total Indirect Costs"}
    GRANDTOTAL_CAT = "Grand Total"

    rows_html = ""
    for item in budget_breakdown:
        cat = item.get("category", "")
        desc = item.get("description", "")
        calc = item.get("calculation", "")
        amt = item.get("amount_usd", 0)
        amt_str = f"${amt:,}" if isinstance(amt, (int, float)) else str(amt)

        if cat == GRANDTOTAL_CAT:
            row_class = "grandtotal"
        elif cat in SUBTOTAL_CATS:
            row_class = "subtotal"
        else:
            row_class = ""

        rows_html += (
            f'<tr class="{row_class}">'
            f'<td class="cat-cell">{cat}</td>'
            f'<td>{desc}</td>'
            f'<td class="calc-cell">{calc}</td>'
            f'<td class="amt-cell">{amt_str}</td>'
            f"</tr>"
        )

    st.markdown(
        '<p class="prop-label" style="margin-top:1.5rem;">Budget Breakdown</p>'
        '<table class="budget-table">'
        "<thead><tr>"
        "<th>Category</th><th>Description</th><th>How We Got There</th><th style='text-align:right'>Amount</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )


def render_citations(citations: list, citations_verified: bool):
    if not citations:
        return

    rows_html = ""
    verified_type_a_count = 0
    for idx, c in enumerate(citations, 1):
        ctype = c.get("type", "B").upper()
        org = c.get("authors_or_org", "")
        title = c.get("title_or_report", "")
        year = c.get("year", "")
        pmid = c.get("pmid")
        claim = c.get("claim", "")
        verified = c.get("verified", False)

        if ctype == "A":
            verified_type_a_count += 1 if verified else 0
            ref_text = f"{org} ({year}). {title}."
            if pmid:
                ref_text += f" PMID: {pmid}."
            check = '<span class="citation-check">✓</span>' if verified else ""
            rows_html += (
                f'<div class="citation-item">'
                f'<span class="citation-num">[{idx}]</span>'
                f'<span class="citation-type-a">{ref_text}{check}'
                f'<br><span style="font-size:0.75rem;color:#5a5a7a;">Supports: {claim}</span>'
                f"</span></div>"
            )
        else:
            ref_text = f"{org} ({year}). {title}."
            check = (
                '<span class="citation-check">✓</span>'
                if verified
                else '<span class="citation-unverified">○</span>'
            )
            rows_html += (
                f'<div class="citation-item">'
                f'<span class="citation-num">[{idx}]</span>'
                f'<span class="citation-type-b">{ref_text}{check}'
                f'<br><span style="font-size:0.75rem;color:#7a6a9a;">Supports: {claim}</span>'
                f"</span></div>"
            )

    badge = ""
    if citations_verified and verified_type_a_count > 0:
        badge = (
            f'<div class="verified-badge">'
            f"✓ {verified_type_a_count} citation{'s' if verified_type_a_count != 1 else ''} "
            f"verified against PubMed</div>"
        )

    st.markdown(
        '<div class="citations-section">'
        '<div class="citations-header">References</div>'
        + rows_html
        + badge
        + "</div>",
        unsafe_allow_html=True,
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(funding_sources: list) -> dict:
    progress = st.progress(0)
    status = st.empty()

    def update(msg: str, pct: int):
        status.markdown(f'<p class="status-msg">{msg}</p>', unsafe_allow_html=True)
        progress.progress(pct)

    # 1. Fetch abstracts
    update("Fetching literature from PubMed…", 5)
    abstracts = fetch_pubmed_abstracts(PUBMED_QUERY, max_results=80)

    # 2. Literature analysis
    update(f"Analyzing {len(abstracts)} abstracts across research themes…", 20)
    theme_landscape = run_literature_agent(abstracts)

    # 3. Gap analysis
    update("Identifying underresearched gaps…", 50)
    gaps_result = run_gap_agent(theme_landscape)

    # 4. Experiment proposals (one per gap) — pass abstracts for citation grounding
    gaps = gaps_result.get("gaps", [])
    proposals = []
    for i, gap in enumerate(gaps):
        pct = 55 + i * 8
        update(f"Designing experiment for gap {i + 1} of {len(gaps)}: {gap.get('gap_title', '')}…", pct)
        proposal = run_experiment_agent(gap, abstracts=abstracts)
        proposals.append(proposal)

    # 5. Verify citations against PubMed and institutional URLs
    update("Verifying citations against PubMed…", 78)
    proposals = verify_citations(proposals)

    # 6. Funding matches (one per proposal)
    funding_matches = []
    for i, proposal in enumerate(proposals):
        pct = 83 + i * 5
        update(f"Matching funding sources for proposal {i + 1}…", pct)
        matches = run_funding_agent(proposal, funding_sources)
        funding_matches.append(matches)

    update("Analysis complete.", 100)
    progress.empty()
    status.empty()

    return {
        "abstracts": abstracts,
        "theme_landscape": theme_landscape,
        "gaps": gaps,
        "proposals": proposals,
        "funding_matches": funding_matches,
    }


# ── Render: Literature Landscape ─────────────────────────────────────────────

def render_literature_section(theme_landscape: dict):
    st.markdown('<div class="section-header">Literature Landscape</div>', unsafe_allow_html=True)

    themes = theme_landscape.get("themes", [])
    if not themes:
        st.warning("No theme data available.")
        return

    # Horizontal bar chart colored by research_maturity
    theme_names = [t["theme_name"].replace("_", " ").title() for t in themes]
    paper_counts = [t["paper_count"] for t in themes]
    maturity_scores = [t.get("research_maturity", 3) for t in themes]
    bar_colors = [maturity_color(m) for m in maturity_scores]

    fig = go.Figure(
        go.Bar(
            x=paper_counts,
            y=theme_names,
            orientation="h",
            marker=dict(color=bar_colors, line=dict(width=0)),
            hovertemplate="<b>%{y}</b><br>Papers: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor="#0e0e14",
        plot_bgcolor="#0e0e14",
        font=dict(color="#e2e2f0", family="Inter, sans-serif"),
        xaxis=dict(
            title="Paper Count",
            gridcolor="#1e1e35",
            tickfont=dict(color="#8b8ba8"),
        ),
        yaxis=dict(tickfont=dict(color="#cccce0"), autorange="reversed"),
        margin=dict(l=10, r=30, t=30, b=40),
        height=max(280, len(themes) * 42),
        showlegend=False,
    )

    # Maturity legend annotation
    legend_html = "".join(
        f'<span style="display:inline-flex;align-items:center;margin-right:12px;">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{maturity_color(s)};'
        f'display:inline-block;margin-right:4px;"></span>'
        f'<span style="font-size:0.75rem;color:#8b8ba8;">{label}</span></span>'
        for s, label in [(1, "Very early"), (3, "Active"), (5, "Established")]
    )
    st.markdown(
        f'<p style="font-size:0.78rem;color:#6b6b8a;margin-bottom:4px;">'
        f"Bar color = Research Maturity &nbsp;|&nbsp; {legend_html}</p>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Key findings per theme
    st.markdown(
        '<p style="font-size:0.9rem;color:#8b8ba8;margin:0.5rem 0 1rem 0;">'
        "Expand a theme to see key findings and notable gaps.</p>",
        unsafe_allow_html=True,
    )
    for theme in sorted(themes, key=lambda t: t.get("research_maturity", 0)):
        label = theme["theme_name"].replace("_", " ").title()
        maturity = theme.get("research_maturity", 0)
        color = maturity_color(maturity)
        with st.expander(f"{label}  —  maturity {maturity}/5", expanded=False):
            findings = theme.get("key_findings", [])
            if findings:
                st.markdown("**Key Findings**")
                for f in findings:
                    st.markdown(f"- {f}")
            gap_text = theme.get("notable_gaps", "")
            if gap_text:
                st.markdown(
                    f'<p style="margin-top:0.75rem;padding:0.75rem;background:#1a1a2e;'
                    f'border-left:3px solid {color};border-radius:4px;font-size:0.88rem;'
                    f'color:#cccce0;">⚠️ <strong>Notable Gap:</strong> {gap_text}</p>',
                    unsafe_allow_html=True,
                )


# ── Render: Gaps & Proposals ──────────────────────────────────────────────────

def render_gaps_section(gaps: list, proposals: list, funding_matches: list, url_map: dict):
    st.markdown(
        '<div class="section-header">Research Gaps &amp; Experiment Proposals</div>',
        unsafe_allow_html=True,
    )

    for i, (gap, proposal, matches) in enumerate(zip(gaps, proposals, funding_matches)):
        urgency = gap.get("urgency_score", 0)
        urgency_color = "#ef4444" if urgency >= 8 else "#f97316" if urgency >= 6 else "#eab308"

        st.markdown(
            f'<div class="gap-card">'
            f'<div class="gap-title">Gap {i + 1}: {gap.get("gap_title", "Untitled")}</div>'
            f'<span class="urgency-badge" style="border-color:{urgency_color};color:{urgency_color};'
            f'background:rgba(0,0,0,0.3);">Urgency {urgency}/10</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        with st.expander("Why this gap matters & experiment design", expanded=(i == 0)):
            col1, col2 = st.columns([1, 1], gap="large")

            with col1:
                st.markdown("**About the Gap**")
                st.markdown(
                    render_field("Clinical Importance", gap.get("clinical_importance")),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_field("Why Neglected", gap.get("why_neglected")),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_field("What Changes If Addressed", gap.get("what_changes_if_addressed")),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    render_field("Suggested Study Type", gap.get("feasible_study_type")),
                    unsafe_allow_html=True,
                )

            with col2:
                p = proposal.get("proposal", proposal)
                st.markdown("**Experiment Proposal**")
                for field, label in [
                    ("research_question", "Research Question"),
                    ("hypothesis", "Hypothesis"),
                    ("study_design", "Study Design"),
                    ("population", "Population"),
                    ("data_collection", "Data Collection"),
                    ("key_variables", "Key Variables"),
                    ("statistical_analysis", "Statistical Analysis"),
                ]:
                    val = p.get(field)
                    if val:
                        st.markdown(
                            render_field(label, render_inline_citations(val)),
                            unsafe_allow_html=True,
                        )

                feasibility = p.get("feasibility_notes")
                if feasibility:
                    st.markdown(
                        render_field("Feasibility Notes", render_inline_citations(feasibility)),
                        unsafe_allow_html=True,
                    )

                impact = p.get("expected_impact")
                if impact:
                    st.markdown(
                        render_field("Expected Impact", render_inline_citations(impact)),
                        unsafe_allow_html=True,
                    )

            # Budget breakdown — full width below the two columns
            budget_breakdown = p.get("budget_breakdown")
            budget = p.get("estimated_budget_usd")
            timeline = p.get("timeline_months")

            if budget or timeline:
                m_col1, m_col2, _ = st.columns([1, 1, 4])
                if budget:
                    m_col1.metric("Grand Total", f"${budget:,}")
                if timeline:
                    m_col2.metric("Timeline", f"{timeline} months")

            if budget_breakdown:
                render_budget_table(budget_breakdown)

            # Citations reference list
            citations = p.get("citations", [])
            citations_verified = p.get("citations_verified", False)
            if citations:
                st.markdown("<hr style='border-color:#1e1e35;margin:1.5rem 0 0.5rem 0;'>", unsafe_allow_html=True)
                render_citations(citations, citations_verified)

        # Funding matches for this proposal
        render_funding_cards(matches, url_map, gap_index=i)
        st.markdown("<hr>", unsafe_allow_html=True)


# ── Render: Funding ───────────────────────────────────────────────────────────

def render_funding_cards(matches_result: dict, url_map: dict, gap_index: int):
    match_list = matches_result.get("matches", [])[:3]
    if not match_list:
        st.caption("No funding matches available.")
        return

    st.markdown(
        '<p style="font-size:0.85rem;font-weight:600;color:#7c6fcd;'
        'letter-spacing:0.06em;text-transform:uppercase;margin:0.5rem 0 0.75rem 0;">'
        "Top Funding Matches</p>",
        unsafe_allow_html=True,
    )

    cols = st.columns(len(match_list), gap="small")
    for col, match in zip(cols, match_list):
        name = match.get("funder_name", "Unknown Funder")
        score = match.get("relevance_score", 0)
        why = match.get("why_it_fits", "")
        concerns = match.get("potential_concerns", "")
        tips = match.get("application_tips", "")
        url = url_map.get(name, "")

        with col:
            st.markdown(
                f'<div class="funding-card">'
                f'<div class="funder-name">{name}</div>'
                f'<div class="funder-meta">Relevance: {score}/10</div>'
                + render_progress_bar(score, 10)
                + f"</div>",
                unsafe_allow_html=True,
            )
            with st.expander("Details", expanded=False):
                if why:
                    st.markdown(f"**Why it fits**\n\n{escape_dollars(why)}")
                if concerns:
                    st.markdown(
                        f'<p style="font-size:0.85rem;padding:0.6rem;background:#1e1010;'
                        f'border-left:3px solid #f97316;border-radius:4px;color:#f0c4a0;">'
                        f"⚠️ {concerns}</p>",
                        unsafe_allow_html=True,
                    )
                if tips:
                    st.markdown(f"**Application Tips**\n\n{escape_dollars(tips)}")
                if url:
                    st.markdown(f"[View Funder Website ↗]({url})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    funding_sources = load_funding_sources()
    url_map = funding_url_map(funding_sources)

    # Header
    st.markdown(
        '<div class="endo-header">'
        '<p class="endo-title">🔬 EndoScope</p>'
        '<p class="endo-subtitle">An AI scientist surfacing research gaps in endometriosis</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    # Controls row: Run button | Demo Mode toggle | status badge
    col_btn, col_toggle, col_badge = st.columns([1, 1, 4])

    with col_btn:
        run_clicked = st.button("Run Analysis", use_container_width=True)

    with col_toggle:
        demo_mode = st.toggle(
            "Demo Mode",
            value=not DEMO_PATH.exists() is False,  # default ON if demo file exists
            help="When ON, loads results from data/demo_results.json instead of calling APIs.",
        )

    # In demo mode with no saved file yet, warn the user
    if demo_mode and not DEMO_PATH.exists():
        st.warning(
            "Demo Mode is ON but no saved results found at `data/demo_results.json`. "
            "Run the analysis once with Demo Mode OFF to generate them.",
            icon="⚠️",
        )

    # Handle Run button
    if run_clicked:
        if demo_mode:
            results = load_demo_results()
            if results is None:
                st.error("No demo results file found. Turn off Demo Mode to run the live pipeline.")
                st.stop()
            st.session_state["results"] = results
            st.session_state["results_source"] = "demo"
        else:
            with st.spinner(""):
                results = run_pipeline(funding_sources)
            save_demo_results(results)
            st.session_state["results"] = results
            st.session_state["results_source"] = "live"
        st.rerun()

    # Status badge
    with col_badge:
        source = st.session_state.get("results_source")
        if source == "live":
            n = len(st.session_state["results"].get("abstracts", []))
            st.markdown(
                f'<div style="padding-top:0.5rem;">'
                f'<span class="result-badge live">'
                f'<span class="badge-dot" style="background:#4ade80;"></span>'
                f'Live — {n} abstracts analyzed</span></div>',
                unsafe_allow_html=True,
            )
        elif source == "demo":
            st.markdown(
                '<div style="padding-top:0.5rem;">'
                '<span class="result-badge demo">'
                '<span class="badge-dot" style="background:#a78bfa;"></span>'
                'Demo — loaded from saved results</span></div>',
                unsafe_allow_html=True,
            )

    # Display
    if "results" in st.session_state:
        results = st.session_state["results"]
        render_literature_section(results["theme_landscape"])
        st.markdown('<div style="height:1.5rem;"></div>', unsafe_allow_html=True)
        render_gaps_section(
            results["gaps"],
            results["proposals"],
            results["funding_matches"],
            url_map,
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:5rem 0;color:#3a3a5c;">'
            "<p style='font-size:3rem;'>🧬</p>"
            "<p style='font-size:1.1rem;'>Click <strong>Run Analysis</strong> to fetch the latest "
            "endometriosis literature and surface actionable research gaps.</p>"
            "<p style='font-size:0.85rem;margin-top:0.5rem;'>Queries PubMed · Powered by Claude</p>"
            "</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
