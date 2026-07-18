"""
T2 programme-quote verification (deterministic, no LLM).

Input : pipeline/data/t2/t2_research.json  — per-party {program_title, program_url,
        program_date, items:[{statement, direction, quote, page, source_url,...}]}
        (verbatim quotes proposed by the research pass).
Output: pipeline/data/t2/t2_quotes.json     — only the quotes that actually appear,
        verbatim, in the downloaded programme PDF. Anything that fails the check is
        dropped and logged. This is the mechanical equivalent of the adversarial
        verifier: a quote is admitted iff it is really in the source document.

Matching is whitespace/hyphenation/soft-hyphen/ligature-insensitive but otherwise
exact — a paraphrase will not match. Provenance on each admitted quote is the PDF
URL + SHA-256 of the downloaded bytes (added by build_evidence via the extract).
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import fetch, DATA_DIR

RESEARCH_PATH = os.path.join(DATA_DIR, "t2", "t2_research.json")
OUT_PATH = os.path.join(DATA_DIR, "t2", "t2_quotes.json")

_LIG = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "„": '"', "“": '"',
        "”": '"', "‟": '"', "‚": "'", "‘": "'", "’": "'", "–": "-", "—": "-", "­": ""}


def _norm(text: str) -> str:
    for a, b in _LIG.items():
        text = text.replace(a, b)
    text = text.replace("-\n", "").replace("-\r\n", "")   # de-hyphenate line breaks
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


# Alphanumeric-only collapse (keeps German letters): removes ALL whitespace,
# punctuation, and line-break artifacts so a quote split across PDF columns/lines
# still matches. This is the primary verbatim test.
_KEEP = re.compile(r"[^0-9a-zäöüßáéíóúàèçñ]+", re.IGNORECASE)


def _collapse(text: str) -> str:
    for a, b in _LIG.items():
        text = text.replace(a, b)
    return _KEEP.sub("", text.lower())


def _pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _match(quote_collapsed: str, hay_collapsed: str) -> bool:
    """Verbatim test on alphanumeric-collapsed text (whitespace/punct-insensitive)."""
    if len(quote_collapsed) < 12:
        return False
    return quote_collapsed in hay_collapsed


def verify(verbose: bool = True):
    with open(RESEARCH_PATH, "r", encoding="utf-8") as f:
        research = json.load(f)

    out = []
    stats = {}
    for party, rec in sorted(research.items()):
        url = rec.get("program_url")
        try:
            pdf_bytes, sha = fetch(url, cache=True)
            hay = _collapse(_pdf_text(pdf_bytes))
        except Exception as e:
            if verbose:
                print(f"  {party}: PDF fetch/parse FAILED ({e}) — skipping party")
            stats[party] = (0, len(rec.get("items", [])))
            continue

        kept = 0
        for it in rec.get("items", []):
            if _match(_collapse(it["quote"]), hay):
                out.append({
                    "party": party,
                    "statement": it["statement"],
                    "direction": it["direction"],
                    "quote": it["quote"].strip(),
                    "page": it.get("page"),
                    "source_url": it.get("source_url") or url,
                    "program_title": rec.get("program_title"),
                    "program_date": rec.get("program_date") or "2025-02-01",
                    "source_sha256": sha,
                    "verification": "verbatim-confirmed-in-pdf",
                })
                kept += 1
            elif verbose:
                print(f"  DROP {party}/{it['statement']}: quote not found verbatim — “{it['quote'][:60]}…”")
        stats[party] = (kept, len(rec.get("items", [])))
        if verbose:
            print(f"  {party}: {kept}/{len(rec.get('items', []))} quotes confirmed against {url[:60]}")

    out.sort(key=lambda q: (q["statement"], q["party"]))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    total_kept = sum(k for k, _ in stats.values())
    total = sum(t for _, t in stats.values())
    if verbose:
        print(f"\nT2: {total_kept}/{total} quotes verbatim-confirmed across {len(research)} parties -> {OUT_PATH}")
    return out


if __name__ == "__main__":
    verify()
