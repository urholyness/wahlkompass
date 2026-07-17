"""
Live ingester: DIP (Dokumentations- und Informationssystem) Vorgang metadata.

For every Drucksache number referenced by a roll-call vote (bundestag.de title
or abgeordnetenwatch intro), resolve the owning Vorgang via
/vorgang?f.dokumentnummer=21%2FNNNN and store its metadata (titel, abstract,
vorgangstyp, beratungsstand, initiative, sachgebiet). Feeds evidence display
and vote<->statement linking.

Auth: DIP_API_KEY from wahlkompass/.env (header "Authorization: ApiKey ...").
Trap (verified): unknown f.* params are silently ignored -> only
f.dokumentnummer is used, and numFound is sanity-checked.
"""
import json
import os
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import fetch, load_env, DATA_DIR

BASE = "https://search.dip.bundestag.de/api/v1"
OUT_PATH = os.path.join(DATA_DIR, "dip", "vorgaenge.json")
VOTES_PATH = os.path.join(DATA_DIR, "votes", "wp21_votes.json")
AW_PATH = os.path.join(DATA_DIR, "votes", "aw_polls.json")


def _api_key() -> Optional[str]:
    return os.environ.get("DIP_API_KEY") or load_env().get("DIP_API_KEY") or None


def lookup_vorgang(dokumentnummer: str, api_key: str) -> Optional[Dict[str, Any]]:
    url = f"{BASE}/vorgang?f.dokumentnummer={urllib.parse.quote(dokumentnummer, safe='')}&format=json"
    body, _sha = fetch(url, cache=True, headers={"Authorization": f"ApiKey {api_key}"},
                       throttle_seconds=0.4)
    data = json.loads(body.decode("utf-8"))
    n = data.get("numFound", 0)
    if not isinstance(n, int) or n < 1 or n > 20:
        return None       # 0 = unknown number; huge = the silently-ignored-filter trap
    docs = data.get("documents", [])
    if not docs:
        return None
    # prefer Gesetzgebung/Antrag over Q&A process types when several match
    order = {"Gesetzgebung": 0, "Antrag": 1, "Entschließungsantrag BT": 2}
    docs.sort(key=lambda d: order.get(d.get("vorgangstyp"), 9))
    d = docs[0]
    return {
        "vorgang_id": d.get("id"),
        "titel": d.get("titel"),
        "abstract": d.get("abstract"),
        "vorgangstyp": d.get("vorgangstyp"),
        "beratungsstand": d.get("beratungsstand"),
        "initiative": d.get("initiative"),
        "sachgebiet": d.get("sachgebiet"),
        "url": f"https://dip.bundestag.de/vorgang/{d.get('id')}",
    }


def ingest(verbose: bool = True) -> Dict[str, Any]:
    key = _api_key()
    if not key:
        print("DIP_API_KEY missing — skipping DIP enrichment (re-run once the key is in .env).")
        return {}

    numbers: List[str] = []
    for path in (VOTES_PATH, AW_PATH):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for rec in json.load(f):
                    numbers.extend(rec.get("drucksachen", []))
    wanted = sorted({n for n in numbers if n.startswith("21/")})

    out: Dict[str, Any] = {}
    for number in wanted:
        v = lookup_vorgang(number, key)
        if v:
            out[number] = v
            if verbose:
                print(f"  {number}: [{v['vorgangstyp']}] {str(v['titel'])[:70]}")
        elif verbose:
            print(f"  {number}: no unique Vorgang")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if verbose:
        print(f"wrote {len(out)} Vorgänge -> {OUT_PATH}")
    return out


if __name__ == "__main__":
    ingest()
