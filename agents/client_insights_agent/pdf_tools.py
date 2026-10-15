"""PDF tools for the client_insights_agent.

The tender PDF is ~112 pages (~170k characters), too large to hand to the model in
one go. The tools below therefore work in two stages:

1. Load + page-index the PDF once (cached).
2. Per insight category, retrieve only the relevant pages by keyword scoring and
   return those excerpts to the LLM, which does the summarising.

Keyword retrieval is deliberately simple (no vector DB) - the goal of this project is
to exercise the A2A flow, not to build a RAG system.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF = REPO_ROOT / "docs" / "ITPS Road Haulage and Warehousing - Tender Stage.pdf"

# Max characters returned to the LLM per tool call (keeps the context small).
MAX_EXCERPT_CHARS = 9000
# Number of top-scoring pages included per tool call.
TOP_PAGES = 5

# Keyword sets per insight category. Weights are implicit: each occurrence counts 1.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "background": [
        "network rail", "non-departmental", "overview of requirement", "railway infrastructure",
        "single contract", "currently", "procurement relates", "great british railways",
        "regional distribution", "rdc", "8 year contract", "£372", "competitive flexible",
    ],
    "requirements": [
        "requires", "requirement", "shall", "scope", "24/7", "road haulage service",
        "warehousing management", "transport management system", "order portal",
        "kpi", "otif", "stock accuracy", "carbon reduction", "tupe", "mobilisation",
        "specification", "trunking",
    ],
    "pain_points": [
        "two separate contracts", "supply chain risk", "interface", "inefficien",
        "improvement", "safety", "life-expired", "stock loss", "abnormally low",
        "downscal", "upscal", "flex", "demand", "incumbent", "risk",
    ],
    "key_drivers": [
        "aim to", "benefit", "efficiency", "value", "sustainab", "carbon",
        "safety", "seamless", "minimise", "evaluation", "weighting", "70%", "25%",
        "pricing", "technical", "gain & pain", "gain and pain", "most advantageous",
    ],
}


# 1-based inclusive page ranges to search, per category. In this tender the narrative
# (overview, timetable, process) is pages 1-17 and the tender criteria (Appendix C,
# including weightings) start at page 81. Appendix A/B (T&Cs, PSQ scoring) is mostly
# boilerplate and would otherwise drown out the signal.
NARRATIVE = [(1, 17)]
NARRATIVE_AND_TENDER_CRITERIA = [(1, 17), (81, 10_000)]
CATEGORY_PAGE_RANGES: dict[str, list[tuple[int, int]]] = {
    "background": NARRATIVE,
    "requirements": NARRATIVE_AND_TENDER_CRITERIA,
    "pain_points": NARRATIVE,
    "key_drivers": NARRATIVE_AND_TENDER_CRITERIA,
}


def _in_ranges(page_no: int, ranges: list[tuple[int, int]] | None) -> bool:
    return ranges is None or any(lo <= page_no <= hi for lo, hi in ranges)


def _pdf_path() -> Path:
    return Path(os.getenv("TENDER_PDF_PATH", str(DEFAULT_PDF)))


@lru_cache(maxsize=1)
def load_pages() -> tuple[str, ...]:
    """Extract and cache the text of every PDF page (index 0 == page 1)."""
    path = _pdf_path()
    if not path.exists():
        raise FileNotFoundError(f"Tender PDF not found at {path}")
    reader = PdfReader(str(path))
    return tuple((page.extract_text() or "") for page in reader.pages)


def _score_pages(
    keywords: list[str], ranges: list[tuple[int, int]] | None = None
) -> list[tuple[int, int]]:
    """Return [(score, page_index)] sorted best-first, for pages with score > 0."""
    scored: list[tuple[int, int]] = []
    for idx, text in enumerate(load_pages()):
        if not _in_ranges(idx + 1, ranges):
            continue
        lowered = text.lower()
        score = sum(lowered.count(k) for k in keywords)
        if score:
            scored.append((score, idx))
    scored.sort(reverse=True)
    return scored


def _clean(text: str) -> str:
    text = text.replace("OFFICIAL", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


def _excerpts_for(category: str, extra_query: str | None = None) -> str:
    keywords = list(CATEGORY_KEYWORDS[category])
    if extra_query:
        keywords += [w.lower() for w in re.findall(r"[A-Za-z0-9£%/&-]{4,}", extra_query)]
    top = _score_pages(keywords, CATEGORY_PAGE_RANGES[category])[:TOP_PAGES]
    if not top:
        return "No relevant passages found in the tender document."

    # Present in document order so the narrative reads naturally.
    chunks: list[str] = []
    budget = MAX_EXCERPT_CHARS
    for _, idx in sorted(top, key=lambda t: t[1]):
        body = _clean(load_pages()[idx])
        piece = f"[Page {idx + 1}]\n{body}"[:budget]
        chunks.append(piece)
        budget -= len(piece)
        if budget <= 0:
            break
    return "\n\n".join(chunks)


@tool
def get_document_overview() -> str:
    """Return basic facts about the tender PDF: file name, page count, and the opening
    text of the first pages (title, procurement reference, publication date)."""
    pages = load_pages()
    head = _clean("\n".join(pages[:3]))[:2500]
    return f"File: {_pdf_path().name}\nPages: {len(pages)}\n\nOpening text:\n{head}"


@tool
def extract_client_background(focus: str = "") -> str:
    """Retrieve tender excerpts describing the CLIENT BACKGROUND: who the client is,
    what the procurement is, contract size/term, scale of current operations.
    Optionally pass `focus` to bias retrieval toward specific terms."""
    return _excerpts_for("background", focus)


@tool
def extract_client_requirements(focus: str = "") -> str:
    """Retrieve tender excerpts describing the CLIENT REQUIREMENTS: services in scope,
    systems required, KPIs, workforce/TUPE, and submission requirements.
    Optionally pass `focus` to bias retrieval toward specific terms."""
    return _excerpts_for("requirements", focus)


@tool
def extract_client_pain_points() -> str:
    """Retrieve tender excerpts that reveal CLIENT PAIN POINTS: problems with the current
    arrangement (e.g. split contracts, interfaces, supply-chain risk, flexibility needs)."""
    return _excerpts_for("pain_points")


@tool
def extract_client_key_drivers() -> str:
    """Retrieve tender excerpts that reveal the CLIENT'S KEY DRIVERS: why they are
    procuring this way and what they will reward (benefits sought, evaluation weighting,
    safety, sustainability, value)."""
    return _excerpts_for("key_drivers")


@tool
def search_tender_document(query: str) -> str:
    """Free-text search over the tender PDF. Use for follow-up questions that the four
    category tools do not cover. Returns the most relevant page excerpts."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9£%/&-]{3,}", query)]
    if not words:
        return "Please provide a non-empty query."
    top = _score_pages(words)[:TOP_PAGES]
    if not top:
        return "No matching passages found."
    return "\n\n".join(
        f"[Page {idx + 1}]\n{_clean(load_pages()[idx])[:1800]}"
        for _, idx in sorted(top, key=lambda t: t[1])
    )


ALL_TOOLS = [
    get_document_overview,
    extract_client_background,
    extract_client_requirements,
    extract_client_pain_points,
    extract_client_key_drivers,
    search_tender_document,
]
