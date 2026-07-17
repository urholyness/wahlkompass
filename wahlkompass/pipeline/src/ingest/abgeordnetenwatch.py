"""
Live ingester: abgeordnetenwatch.de API v2 (license CC0 1.0).

Pulls every WP21 Bundestag Abstimmung (legislature parliament_period id 161)
with per-mandate votes, aggregates by Fraktion, and stores the result as the
independent T3/cross-check record next to the authoritative bundestag.de XLSX
data. The poll intros carry Drucksache references, which feed vote<->statement
linking and the DIP metadata join.

Rate limit: 30 requests/min/IP -> uncached requests are throttled. All poll
detail responses are cached, so nightly re-runs only fetch new polls.
"""
import json
import os
import re
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import fetch, DATA_DIR
from src.ingestors.bundestag_xml_parser import UNIFIED_ABSTENTION_FLOOR

BASE = "https://www.abgeordnetenwatch.de/api/v2"
LEGISLATURE_WP21 = 161
OUT_PATH = os.path.join(DATA_DIR, "votes", "aw_polls.json")
THROTTLE = 2.2   # seconds between uncached calls (30/min limit)

_TAG_RE = re.compile(r"<[^>]+>")
# dserver PDF paths split the number: /btd/21/059/2105921.pdf -> 21/5921
_DSERVER_RE = re.compile(r"dserver\.bundestag\.de/btd/(\d{2})/\d{3}/\d{2}(\d{5})\.pdf")
_DRS_TEXT_RE = re.compile(r"\b(2[01])/(\d{2,5})\b")


def _drucksachen(field_intro_html: str) -> List[str]:
    found = set()
    for wp, num in _DSERVER_RE.findall(field_intro_html or ""):
        found.add(f"{wp}/{int(num)}")
    text = _TAG_RE.sub(" ", field_intro_html or "")
    for wp, num in _DRS_TEXT_RE.findall(text):
        found.add(f"{wp}/{int(num)}")
    return sorted(found)

# fraction label prefix -> wahlkompass party id ("SPD (Bundestag 2025 - 2029)")
FRACTION_MAP = {
    "SPD": "spd", "CDU/CSU": "cdu", "AfD": "afd",
    "BÜNDNIS 90/DIE GRÜNEN": "gruene", "Die Linke": "linke",
}


def _clean(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    text = text.replace("­", "")          # soft hyphens in labels
    return re.sub(r"\s+", " ", text).strip()


def _get(url: str, cache: bool = True) -> Dict[str, Any]:
    body, _sha = fetch(url, cache=cache, throttle_seconds=THROTTLE)
    data = json.loads(body.decode("utf-8"))
    if data.get("meta", {}).get("status") != "ok":
        raise RuntimeError(f"aw API status not ok for {url}")
    return data


def list_polls() -> List[Dict[str, Any]]:
    polls: List[Dict[str, Any]] = []
    start = 0
    while True:
        url = (f"{BASE}/polls?field_legislature={LEGISLATURE_WP21}"
               f"&sort_by=field_poll_date&sort_direction=asc&range_start={start}&range_end=100")
        data = _get(url, cache=False)   # the list grows; always refetch
        batch = data.get("data", [])
        polls.extend(batch)
        total = data.get("meta", {}).get("result", {}).get("total") or 0
        start += len(batch)
        if not batch or start >= total:
            break
    return polls


def ingest(verbose: bool = True) -> List[Dict[str, Any]]:
    polls = list_polls()
    out: List[Dict[str, Any]] = []
    for poll in polls:
        pid = poll["id"]
        detail = _get(f"{BASE}/polls/{pid}?related_data=votes", cache=True)
        votes = (detail.get("data", {}).get("related_data") or {}).get("votes", [])

        counts_by_party: Dict[str, Dict[str, int]] = {}
        for v in votes:
            fraction_label = _clean((v.get("fraction") or {}).get("label", ""))
            prefix = fraction_label.split(" (")[0].strip()
            party = FRACTION_MAP.get(prefix)
            if party is None:
                continue    # fraktionslos and unknown fractions are not a party position
            c = counts_by_party.setdefault(party, {"ja": 0, "nein": 0, "enthalten": 0, "nicht_abgegeben": 0})
            vv = v.get("vote")
            if vv == "yes":
                c["ja"] += 1
            elif vv == "no":
                c["nein"] += 1
            elif vv == "abstain":
                c["enthalten"] += 1
            else:
                c["nicht_abgegeben"] += 1

        aggregates: Dict[str, Any] = {}
        for party, c in counts_by_party.items():
            present = c["ja"] + c["nein"] + c["enthalten"]
            active = c["ja"] + c["nein"]
            participation = (active / present) if present else 0.0
            direction = ((c["ja"] - c["nein"]) / active) if active else 0.0
            excluded = participation < UNIFIED_ABSTENTION_FLOOR
            aggregates[party] = {
                "counts": c,
                "direction": round(direction, 4),
                "participation": round(participation, 4),
                "item_weight": 0.0 if excluded else round(participation, 4),
                "excluded_unified_abstention": excluded,
            }

        intro = _clean(poll.get("field_intro", ""))
        drucksachen = _drucksachen(poll.get("field_intro", "") or "")
        out.append({
            "poll_id": pid,
            "date": poll.get("field_poll_date"),
            "label": _clean(poll.get("label", "")),
            "accepted": poll.get("field_accepted"),
            "topics": [t.get("label") for t in (poll.get("field_topics") or []) if isinstance(t, dict)],
            "intro": intro[:600],
            "drucksachen": drucksachen,
            "url": poll.get("abgeordnetenwatch_url"),
            "fraktion_aggregates": aggregates,
        })
        if verbose:
            print(f"  aw {pid} {poll.get('field_poll_date')} {(_clean(poll.get('label',''))[:60])} drs={drucksachen}")

    out.sort(key=lambda r: (r["date"] or "", r["poll_id"]))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if verbose:
        print(f"wrote {len(out)} WP21 aw polls -> {OUT_PATH}")
    return out


if __name__ == "__main__":
    ingest()
