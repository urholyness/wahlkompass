"""
Vote <-> statement candidate matching (deterministic, recall-oriented).

Produces pipeline/data/links/candidates.json: for every (vote, statement)
pair where the statement's keyword set hits the vote's title / DIP metadata /
abgeordnetenwatch intro, one candidate record with all the text context a
coder needs. The ALIGNMENT decision (does Ja on this motion mean agreement
with the statement, or the opposite? or is the motion off-topic?) is the one
human-judgment step in the pipeline (design v1.2 §5): candidates are coded
into links.json — dual human coding for board-approved releases, an
LLM-panel + spot-check for the labelled technical preview.

Deliberately over-matches (keywords are broad); the coding step rejects
off-topic candidates. Missing a relevant vote here means missing evidence, so
recall beats precision.
"""
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import DATA_DIR

VOTES_PATH = os.path.join(DATA_DIR, "votes", "wp21_votes.json")
AW_PATH = os.path.join(DATA_DIR, "votes", "aw_polls.json")
DIP_PATH = os.path.join(DATA_DIR, "dip", "vorgaenge.json")
OUT_PATH = os.path.join(DATA_DIR, "links", "candidates.json")

# statement id -> lowercase keyword fragments (substring match)
KEYWORDS: Dict[str, List[str]] = {
    "schuldenbremse": ["schuldenbremse", "artikel 109", "artikel 115", "art. 143h",
                       "artikels 143h", "sondervermögen", "kreditaufnahme"],
    "mindestlohn-15": ["mindestlohn"],
    "tempolimit": ["tempolimit", "geschwindigkeitsbegrenzung", "höchstgeschwindigkeit"],
    "klima-2035": ["klimaneutral", "klimaschutzgesetz", "klimaschutzfolgen",
                   "emissionsobergrenzen", "co2", "treibhausgas", "emissionshandel"],
    "buergergeld": ["bürgergeld", "grundsicherung", "sanktionen", "sozialhilfe"],
    "rente-63": ["rente", "renteneintritt", "abschlagsfrei", "altersgrenze"],
    "wehrpflicht": ["wehrpflicht", "wehrdienst", "musterung", "kriegsdienst"],
    "waffen-ukraine": ["ukraine", "taurus", "waffenlieferung"],
    "asyl-drittstaaten": ["asyl", "drittstaat", "flüchtling", "familiennachzug",
                          "abschiebung", "schutzberechtigt", "zurückweisung", "migration"],
    "fachkraefte": ["fachkräfte", "einwanderung", "zuwanderung", "aufenthaltsgesetz",
                    "staatsangehörigkeit", "arbeitsmigration"],
    "vermoegensteuer": ["vermögensteuer", "vermögensabgabe", "vermögenssteuer"],
    "cannabis": ["cannabis", "canG".lower()],
    "eurobonds": ["eurobonds", "gemeinsame schulden", "eu-anleihen", "eigenmittel",
                  "next generation eu"],
    "vorratsdaten": ["vorratsdaten", "ip-adress", "speicherpflicht", "verkehrsdaten",
                     "telekommunikationsüberwachung", "chatkontrolle"],
    "heizungsgesetz": ["heizung", "gebäudeenergiegesetz", "geg", "wärmeplanung", "wärmepumpe"],
}


def _load(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def build_candidates(verbose: bool = True) -> List[Dict[str, Any]]:
    votes = _load(VOTES_PATH, [])
    aw_polls = _load(AW_PATH, [])
    dip = _load(DIP_PATH, {})

    # attach aw poll + dip context to each bundestag vote (match by date, then title overlap)
    aw_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for p in aw_polls:
        aw_by_date.setdefault(p.get("date") or "", []).append(p)

    def aw_match(vote):
        cands = aw_by_date.get(vote["date"], [])
        if len(cands) == 1:
            return cands[0]
        vt = set(vote["title"].lower().split())
        best, best_overlap = None, 0
        for p in cands:
            overlap = len(vt & set((p.get("label") or "").lower().split()))
            if overlap > best_overlap:
                best, best_overlap = p, overlap
        return best if best_overlap >= 2 else None

    out: List[Dict[str, Any]] = []
    for vote in votes:
        aw = aw_match(vote)
        drs = list(vote.get("drucksachen") or [])
        if aw:
            drs.extend(aw.get("drucksachen") or [])
        drs = sorted(set(drs))
        dip_meta = [dip[n] for n in drs if n in dip]

        haystack = " ".join(filter(None, [
            vote["title"],
            aw.get("label") if aw else "",
            aw.get("intro") if aw else "",
            " ".join((aw.get("topics") or [])) if aw else "",
            " ".join(str(m.get("titel") or "") for m in dip_meta),
            " ".join(str(m.get("abstract") or "") for m in dip_meta),
            " ".join(" ".join(m.get("sachgebiet") or []) for m in dip_meta),
        ])).lower()

        for slug, words in KEYWORDS.items():
            hits = sorted({w for w in words if w in haystack})
            if not hits:
                continue
            out.append({
                "vote_id": vote["vote_id"],
                "statement": slug,
                "matched_terms": hits,
                "vote_title": vote["title"],
                "vote_date": vote["date"],
                "drucksachen": drs,
                "aw_poll_id": aw.get("poll_id") if aw else None,
                "aw_intro": (aw.get("intro") or "")[:500] if aw else "",
                "dip": [{"nummer": n, **dip[n]} for n in drs if n in dip],
            })

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if verbose:
        by_stmt: Dict[str, int] = {}
        for c in out:
            by_stmt[c["statement"]] = by_stmt.get(c["statement"], 0) + 1
        print(f"{len(out)} candidates -> {OUT_PATH}")
        for slug in sorted(by_stmt):
            print(f"  {slug:20s} {by_stmt[slug]}")
    return out


if __name__ == "__main__":
    build_candidates()
