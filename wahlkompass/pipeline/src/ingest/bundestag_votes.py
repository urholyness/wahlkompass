"""
Live ingester: Bundestag namentliche Abstimmungen (T1, Wahlperiode 21).

Enumerates the roll-call vote list via the bundestag.de ajax endpoint (the
human list page at /parlament/plenum/abstimmung/liste delegates to it),
downloads every per-vote XLSX, parses it with BundestagXLSXParser and writes
pipeline/data/votes/wp21_votes.json — one record per vote with provenance
(source_url + sha256 of the raw XLSX) and scoring-ready per-Fraktion
aggregates.

Idempotent: XLSX blobs are immutable and cached; only list pages are refetched.
"""
import json
import os
import re
import sys
from datetime import date
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import fetch, DATA_DIR
from src.ingestors.bundestag_xlsx_parser import BundestagXLSXParser

LIST_URL = ("https://www.bundestag.de/ajax/filterlist/de/parlament/plenum/abstimmung/"
            "liste/462112-462112?limit=30&noFilterSet=true&offset={offset}")
WP21_START = date(2025, 3, 25)   # constitution of the 21st Bundestag
OUT_PATH = os.path.join(DATA_DIR, "votes", "wp21_votes.json")

_ROW_RE = re.compile(r"<tr\b.*?</tr>", re.S)
_TITLE_RE = re.compile(
    r"<strong>\s*(\d{2})\.(\d{2})\.(\d{4}):\s*(?:<span>)?(.*?)(?:</span>)?\s*</strong>", re.S)
_XLSX_RE = re.compile(r'href="(https://www\.bundestag\.de/resource/blob/[^"]+?\.xlsx)"')
_PDF_RE = re.compile(r'href="(https://www\.bundestag\.de/resource/blob/[^"]+?\.pdf)"')
_TAG_RE = re.compile(r"<[^>]+>")
_DRS_RE = re.compile(r"\b(2[01])/(\d{1,5})\b")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text)).strip()


def list_votes(max_pages: int = 40) -> List[Dict[str, Any]]:
    """Walk the ajax list newest-first until a pre-WP21 date appears."""
    votes: List[Dict[str, Any]] = []
    offset = 0
    for _ in range(max_pages):
        body, _sha = fetch(LIST_URL.format(offset=offset), cache=False)
        html = body.decode("utf-8", errors="replace")
        rows = _ROW_RE.findall(html)
        hit_pre_wp21 = False
        found_any = False
        for row in rows:
            m = _TITLE_RE.search(row)
            if not m:
                continue
            found_any = True
            dd, mm, yyyy, raw_title = m.groups()
            vote_date = date(int(yyyy), int(mm), int(dd))
            if vote_date < WP21_START:
                hit_pre_wp21 = True
                continue
            xlsx = _XLSX_RE.search(row)
            if not xlsx:
                continue    # a handful of very old rows are PDF-only
            pdf = _PDF_RE.search(row)
            votes.append({
                "date": vote_date.isoformat(),
                "title": _clean(raw_title),
                "xlsx_url": xlsx.group(1),
                "pdf_url": pdf.group(1) if pdf else None,
            })
        if hit_pre_wp21 or not found_any:
            break
        offset += 30
    return votes


def ingest(verbose: bool = True) -> List[Dict[str, Any]]:
    listed = list_votes()
    out: List[Dict[str, Any]] = []
    seen_ids = set()
    for v in listed:
        body, sha256 = fetch(v["xlsx_url"], cache=True)
        parsed = BundestagXLSXParser.parse_bytes(body)
        meta = parsed["metadata"]
        if meta["period"] not in ("21", "21.0"):
            # authoritative WP filter: column A inside the workbook
            continue
        session = meta["session"].split(".")[0]
        vote_no = meta["vote_number"].split(".")[0]
        vote_id = f"{v['date']}-s{session}-a{vote_no}"
        if vote_id in seen_ids:
            continue
        seen_ids.add(vote_id)
        drucksachen = [f"{a}/{b}" for a, b in _DRS_RE.findall(v["title"])]
        out.append({
            "vote_id": vote_id,
            "date": v["date"],
            "title": v["title"],
            "session": session,
            "vote_number": vote_no,
            "source_url": v["xlsx_url"],
            "pdf_url": v["pdf_url"],
            "sha256": sha256,
            "drucksachen": drucksachen,
            "fraktion_aggregates": parsed["fraktion_aggregates"],
        })
        if verbose:
            print(f"  {vote_id}  {v['title'][:70]}")

    out.sort(key=lambda r: (r["date"], int(r["session"] or 0), int(r["vote_number"] or 0)))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if verbose:
        print(f"wrote {len(out)} WP21 roll-call votes -> {OUT_PATH}")
    return out


if __name__ == "__main__":
    ingest()
