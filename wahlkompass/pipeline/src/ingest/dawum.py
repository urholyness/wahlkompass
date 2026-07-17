"""
Live ingester: dawum.de poll aggregation -> seats.json (Koalitionen view).

Data: ODC Open Database License (ODbL) — attribution required and emitted into
the output ("Daten von dawum.de", link + license link). Descriptive only: the
projection is the mechanical seat translation of recent published polls, never
a prediction (D5).

Method (deterministic):
  * newest survey per institute for the Bundestag (Parliament_ID == "0")
    within the last WINDOW_DAYS of the newest survey date
  * simple average per party over those surveys
  * 5%-Hürde, then proportional (largest remainder) allocation of 630 seats
"""
import json
import os
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingest.http_cache import fetch, DATA_DIR

API_URL = "https://api.dawum.de/"
OUT_PATH = os.path.join(DATA_DIR, "polls", "seats.json")

# dawum party ID -> wahlkompass party id (verified against live /Parties)
PARTY_MAP = {
    "1": "cdu", "2": "spd", "3": "fdp", "4": "gruene",
    "5": "linke", "7": "afd", "18": "volt", "23": "bsw",
}
BUNDESTAG_SEATS = 630
HURDLE = 5.0
WINDOW_DAYS = 21


def ingest(verbose: bool = True) -> Dict[str, Any]:
    body, sha256 = fetch(API_URL, cache=False)
    db = json.loads(body.decode("utf-8"))

    surveys = []
    for sid, s in db.get("Surveys", {}).items():
        if s.get("Parliament_ID") != "0":
            continue
        surveys.append({**s, "id": sid})
    surveys.sort(key=lambda s: (s.get("Date", ""), int(s["id"])), reverse=True)
    if not surveys:
        raise RuntimeError("no Bundestag surveys in dawum response")

    newest = date.fromisoformat(surveys[0]["Date"])
    cutoff = (newest - timedelta(days=WINDOW_DAYS)).isoformat()

    latest_by_institute: Dict[str, Dict[str, Any]] = {}
    for s in surveys:
        if s.get("Date", "") < cutoff:
            break
        latest_by_institute.setdefault(s["Institute_ID"], s)

    used = list(latest_by_institute.values())
    sums: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for s in used:
        for dawum_pid, pct in s.get("Results", {}).items():
            pid = PARTY_MAP.get(dawum_pid)
            if pid is None:
                continue    # Sonstige and micro-parties are not projected
            sums[pid] = sums.get(pid, 0.0) + float(pct)
            counts[pid] = counts.get(pid, 0) + 1

    averages = {pid: sums[pid] / counts[pid] for pid in sums}
    qualified = {pid: v for pid, v in averages.items() if v >= HURDLE}
    total_q = sum(qualified.values())

    # largest-remainder seat allocation among hurdle-clearing parties
    raw = {pid: v / total_q * BUNDESTAG_SEATS for pid, v in qualified.items()}
    seats = {pid: int(r) for pid, r in raw.items()}
    leftover = BUNDESTAG_SEATS - sum(seats.values())
    for pid, _ in sorted(raw.items(), key=lambda kv: (-(kv[1] - int(kv[1])), kv[0]))[:leftover]:
        seats[pid] += 1

    institutes = db.get("Institutes", {})
    out = {
        "as_of": newest.isoformat(),
        "projection": dict(sorted(seats.items())),
        "averages_pct": {pid: round(v, 1) for pid, v in sorted(averages.items())},
        "below_hurdle": sorted(pid for pid, v in averages.items() if v < HURDLE),
        "total": BUNDESTAG_SEATS,
        "majority": BUNDESTAG_SEATS // 2 + 1,
        "surveys_used": [
            {
                "dawum_id": s["id"],
                "date": s["Date"],
                "institute": institutes.get(s["Institute_ID"], {}).get("Name", s["Institute_ID"]),
            }
            for s in sorted(used, key=lambda s: (s["Date"], s["id"]), reverse=True)
        ],
        "method_de": (f"Mechanische Sitzumrechnung: je Institut die neueste Bundestags-Umfrage "
                      f"der letzten {WINDOW_DAYS} Tage, einfacher Mittelwert, {HURDLE:.0f}%-Hürde, "
                      f"proportionale Verteilung von {BUNDESTAG_SEATS} Sitzen (größte Reste). "
                      "Beschreibend, keine Vorhersage."),
        "attribution": {
            "text": "Daten von dawum.de (Open Database License (ODbL))",
            "source_url": "https://dawum.de",
            "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
        },
        "source_sha256": sha256,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if verbose:
        print(f"seats.json (as of {out['as_of']}, {len(used)} institutes): {out['projection']}")
        print(f"averages: {out['averages_pct']} | below hurdle: {out['below_hurdle']}")
    return out


if __name__ == "__main__":
    ingest()
