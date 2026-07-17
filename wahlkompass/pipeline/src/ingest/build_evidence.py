"""
Evidence assembly: coded links + live votes + verified programme quotes
  -> pipeline/data/evidence/evidence_db.json  (ev_id -> evidence item)
  -> pipeline/data/evidence/cells.json        ("party:statement" -> [ev_ids])

T1 items come from Bundestag roll-call aggregates through links.json (the
coded vote<->statement mapping; each link carries alignment ∈ {+1,-1}:
+1 = a Ja on the motion affirms the statement, -1 = a Ja rejects it).
Unified abstentions are kept with item_weight 0 — visible in the drawer,
never scored (v1.2 §3.2).

T2 items are verbatim Wahlprogramm quotes (pipeline/data/t2/t2_quotes.json),
adversarially verified, provisional until human dual-coding.
"""
import hashlib
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import DATA_DIR

VOTES_PATH = os.path.join(DATA_DIR, "votes", "wp21_votes.json")
LINKS_PATH = os.path.join(DATA_DIR, "links", "links.json")
T2_PATH = os.path.join(DATA_DIR, "t2", "t2_quotes.json")
OUT_DB = os.path.join(DATA_DIR, "evidence", "evidence_db.json")
OUT_CELLS = os.path.join(DATA_DIR, "evidence", "cells.json")

FRAKTION_TO_PARTY = {
    "CDU/CSU": "cdu", "SPD": "spd", "AfD": "afd",
    "BÜ90/GR": "gruene", "Die Linke": "linke",
}


def _load(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def build(all_party_ids: List[str], statement_slugs: List[str], verbose: bool = True):
    votes = {v["vote_id"]: v for v in _load(VOTES_PATH, [])}
    links = _load(LINKS_PATH, [])
    t2 = _load(T2_PATH, [])

    evidence: Dict[str, Dict[str, Any]] = {}
    cells: Dict[str, List[str]] = {f"{pid}:{slug}": []
                                   for pid in all_party_ids for slug in statement_slugs}

    # ---- T1: roll-call votes through coded links ----
    for link in sorted(links, key=lambda l: (l["statement"], l["vote_id"])):
        vote = votes.get(link["vote_id"])
        if vote is None or link.get("alignment") not in (1, -1):
            continue
        slug = link["statement"]
        if slug not in statement_slugs:
            continue
        align = link["alignment"]
        drs = ", ".join(vote.get("drucksachen") or []) or None
        for fraktion, agg in sorted(vote["fraktion_aggregates"].items()):
            pid = FRAKTION_TO_PARTY.get(fraktion)
            if pid is None or pid not in all_party_ids:
                continue
            c = agg["counts"]
            ev_id = f"t1-{link['vote_id']}-{pid}-{slug}"
            direction = round(agg["direction"] * align, 4)
            excluded = agg["excluded_unified_abstention"]
            note_align = ("" if align == 1 else
                          " Bezug: Zustimmung zum Antrag bedeutet Ablehnung der Aussage (Vorzeichen gedreht).")
            note_excl = (" Geschlossene Enthaltung — nicht gewertet (Gewicht 0)." if excluded else "")
            evidence[ev_id] = {
                "tier": 1,
                "direction": direction,
                "item_weight": agg["item_weight"],
                "date": vote["date"],
                "kind": "namentliche_abstimmung",
                "title_de": vote["title"] + (f" (Drs. {drs})" if drs else ""),
                "extract": (f"{fraktion}: {c['ja']} Ja, {c['nein']} Nein, {c['enthalten']} Enthaltungen, "
                            f"{c['nicht_abgegeben']} nicht abgegeben.{note_align}{note_excl}"),
                "source_url": vote["source_url"],
                "sha256": vote["sha256"],
                "fci": agg["fci"],
                "vote_id": vote["vote_id"],
                "alignment": align,
                "provisional": True,
            }
            cells[f"{pid}:{slug}"].append(ev_id)

    # ---- T2: verified programme quotes ----
    for q in sorted(t2, key=lambda q: (q["statement"], q["party"])):
        pid, slug = q["party"], q["statement"]
        key = f"{pid}:{slug}"
        if key not in cells:
            continue
        ev_id = f"t2-{pid}-{slug}"
        quote = q["quote"].strip()
        evidence[ev_id] = {
            "tier": 2,
            "direction": round(float(q["direction"]), 4),
            "item_weight": 1.0,
            "date": q.get("program_date") or "2025-02-01",
            "kind": "wahlprogramm",
            "title_de": q.get("program_title") or "Wahlprogramm 2025",
            "extract": f"„{quote}“" + (f" (S. {q['page']})" if q.get("page") else ""),
            "source_url": q["source_url"],
            "sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            "provisional": True,
        }
        cells[key].append(ev_id)

    for key in cells:
        cells[key].sort()

    os.makedirs(os.path.dirname(OUT_DB), exist_ok=True)
    with open(OUT_DB, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=1, sort_keys=True)
    with open(OUT_CELLS, "w", encoding="utf-8") as f:
        json.dump(cells, f, ensure_ascii=False, indent=1, sort_keys=True)

    if verbose:
        n_t1 = sum(1 for e in evidence.values() if e["tier"] == 1)
        n_t2 = sum(1 for e in evidence.values() if e["tier"] == 2)
        covered = sum(1 for ids in cells.values() if ids)
        print(f"evidence: {len(evidence)} items (T1={n_t1}, T2={n_t2}); "
              f"cells covered: {covered}/{len(cells)}")
    return evidence, cells


if __name__ == "__main__":
    parties = ["cdu", "spd", "gruene", "fdp", "afd", "linke", "bsw", "volt"]
    slugs = ["schuldenbremse", "mindestlohn-15", "tempolimit", "klima-2035", "buergergeld",
             "rente-63", "wehrpflicht", "waffen-ukraine", "asyl-drittstaaten", "fachkraefte",
             "vermoegensteuer", "cannabis", "eurobonds", "vorratsdaten", "heizungsgesetz"]
    build(parties, slugs)
