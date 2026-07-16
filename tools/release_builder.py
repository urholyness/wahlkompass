"""
Wahlkompass release builder (v1.2) — Germany / Bundestag.

Takes statements + parties + evidence, runs the v1.2 aggregation engine to derive
positions, and emits a signed, versioned data-release bundle:

    meta.json  methodology.json  statements.json  parties.json
    positions.json  evidence.json  release.sig  pubkey.ed25519

PROVISIONAL PREVIEW: the statement set and the evidence in this file are a
labelled technical preview ("technische Vorschau — noch nicht vom Beirat
geprüft"), synthesized deterministically so the whole pipeline runs end to end
and reproduce.py verifies it byte-identically. Real releases replace the
evidence with dual-coded items ingested from the live sources; NO code changes.
"""
import os
import sys
import json
import hashlib
import base64
from datetime import date

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from src.aggregation import AggregationEngine

RELEASE_TAG = "2026.11.0-preview"
TARGET_DATE = "2026-11-01"
METHODOLOGY_VERSION = "1.0"
CONFIG = os.path.join(os.path.dirname(__file__), "..", "pipeline", "evidence_config", "deu-bundestag.yaml")

# --- Parties (21st Bundestag Fraktionen + two ballot parties for the Volt rule) ---
PARTIES = [
    {"id": "cdu",   "short_name": "CDU/CSU", "name": "CDU/CSU",            "color_hex": "#121212", "ballot_status": "parliamentary", "seats": 197},
    {"id": "spd",   "short_name": "SPD",     "name": "Sozialdemokratische Partei Deutschlands", "color_hex": "#E3000F", "ballot_status": "parliamentary", "seats": 120},
    {"id": "gruene","short_name": "GRÜNE",   "name": "Bündnis 90/Die Grünen", "color_hex": "#46962B", "ballot_status": "parliamentary", "seats": 85},
    {"id": "fdp",   "short_name": "FDP",     "name": "Freie Demokratische Partei", "color_hex": "#D9B300", "ballot_status": "parliamentary", "seats": 61},
    {"id": "afd",   "short_name": "AfD",     "name": "Alternative für Deutschland", "color_hex": "#009EE0", "ballot_status": "parliamentary", "seats": 92},
    {"id": "linke", "short_name": "Linke",   "name": "Die Linke",          "color_hex": "#BE3075", "ballot_status": "parliamentary", "seats": 40},
    {"id": "bsw",   "short_name": "BSW",     "name": "Bündnis Sahra Wagenknecht", "color_hex": "#7D254F", "ballot_status": "parliamentary", "seats": 30},
    {"id": "volt",  "short_name": "Volt",    "name": "Volt Deutschland",   "color_hex": "#5A2A82", "ballot_status": "admitted", "seats": 0},
]

# --- Statements (provisional preview set across the topic rubric) ---
STATEMENTS = [
    ("schuldenbremse", "wirtschaft", "Die Schuldenbremse im Grundgesetz soll reformiert werden, um höhere staatliche Investitionen zu ermöglichen.", "Der Staat soll mehr Schulden machen dürfen, um mehr zu investieren."),
    ("mindestlohn-15", "wirtschaft", "Der gesetzliche Mindestlohn soll auf 15 Euro pro Stunde angehoben werden.", "Wer arbeitet, soll mindestens 15 Euro in der Stunde bekommen."),
    ("tempolimit", "klima", "Auf Autobahnen soll ein generelles Tempolimit von 130 km/h eingeführt werden.", "Auf der Autobahn soll man höchstens 130 fahren dürfen."),
    ("klima-2035", "klima", "Deutschland soll bereits bis 2035 klimaneutral werden.", "Deutschland soll schon 2035 das Klima nicht mehr schädigen."),
    ("buergergeld", "sozial", "Das Bürgergeld soll erhöht und die Sanktionen sollen abgebaut werden.", "Menschen ohne Arbeit sollen mehr Geld und weniger Strafen bekommen."),
    ("rente-63", "sozial", "Der abschlagsfreie Renteneintritt mit 63 nach 45 Beitragsjahren soll erhalten bleiben.", "Wer 45 Jahre gearbeitet hat, soll mit 63 ohne Abzüge in Rente gehen."),
    ("wehrpflicht", "sicherheit", "Die allgemeine Wehrpflicht soll wieder eingeführt werden.", "Junge Menschen sollen wieder zur Bundeswehr müssen."),
    ("waffen-ukraine", "sicherheit", "Deutschland soll weiterhin schwere Waffen an die Ukraine liefern.", "Deutschland soll der Ukraine weiter große Waffen geben."),
    ("asyl-drittstaaten", "migration", "Asylverfahren sollen in sichere Drittstaaten außerhalb der EU ausgelagert werden.", "Über Asyl soll in anderen Ländern außerhalb der EU entschieden werden."),
    ("fachkraefte", "migration", "Die Zuwanderung von Fachkräften soll deutlich erleichtert werden.", "Fachleute aus dem Ausland sollen leichter nach Deutschland kommen dürfen."),
    ("vermoegensteuer", "wirtschaft", "Eine Vermögensteuer auf große Vermögen soll wieder eingeführt werden.", "Sehr reiche Menschen sollen eine Steuer auf ihr Vermögen zahlen."),
    ("cannabis", "gesellschaft", "Die Teil-Legalisierung von Cannabis soll beibehalten werden.", "Cannabis soll für Erwachsene erlaubt bleiben."),
    ("eurobonds", "europa", "Die EU soll gemeinsame europäische Schulden (Eurobonds) für Investitionen aufnehmen.", "EU-Länder sollen zusammen Schulden für Investitionen machen."),
    ("vorratsdaten", "digital", "Zur Kriminalitätsbekämpfung soll eine anlasslose Vorratsdatenspeicherung eingeführt werden.", "Daten über Telefon und Internet sollen allgemein gespeichert werden."),
    ("heizungsgesetz", "klima", "Der verpflichtende Umstieg auf klimafreundliche Heizungen (Heizungsgesetz) soll zurückgenommen werden.", "Die Pflicht zu neuen, klimafreundlichen Heizungen soll wegfallen."),
]

# --- Leaning matrix: approximate stance in [-1,1] per party per statement (provisional). ---
# None = deliberately no evidence -> "keine belegbare Position" (honest coverage demo).
L = {
    "schuldenbremse":   {"cdu":-0.7,"spd":0.8,"gruene":0.9,"fdp":-0.9,"afd":-0.3,"linke":0.9,"bsw":0.4,"volt":0.8},
    "mindestlohn-15":   {"cdu":-0.5,"spd":0.9,"gruene":0.8,"fdp":-0.8,"afd":0.0,"linke":1.0,"bsw":0.8,"volt":0.5},
    "tempolimit":       {"cdu":-0.6,"spd":0.6,"gruene":1.0,"fdp":-0.9,"afd":-0.9,"linke":0.8,"bsw":0.2,"volt":0.8},
    "klima-2035":       {"cdu":-0.5,"spd":0.3,"gruene":0.9,"fdp":-0.6,"afd":-1.0,"linke":0.8,"bsw":-0.2,"volt":0.9},
    "buergergeld":      {"cdu":-0.7,"spd":0.4,"gruene":0.7,"fdp":-0.8,"afd":-0.6,"linke":1.0,"bsw":0.2,"volt":0.5},
    "rente-63":         {"cdu":-0.2,"spd":0.7,"gruene":0.1,"fdp":-0.8,"afd":0.5,"linke":0.8,"bsw":0.8,"volt":None},
    "wehrpflicht":      {"cdu":0.5,"spd":-0.2,"gruene":-0.6,"fdp":-0.1,"afd":0.7,"linke":-0.9,"bsw":-0.2,"volt":-0.4},
    "waffen-ukraine":   {"cdu":0.8,"spd":0.5,"gruene":0.9,"fdp":0.8,"afd":-0.9,"linke":-0.8,"bsw":-1.0,"volt":0.7},
    "asyl-drittstaaten":{"cdu":0.7,"spd":-0.3,"gruene":-0.8,"fdp":0.3,"afd":0.9,"linke":-1.0,"bsw":0.4,"volt":-0.7},
    "fachkraefte":      {"cdu":0.2,"spd":0.7,"gruene":0.8,"fdp":0.8,"afd":-0.9,"linke":0.5,"bsw":-0.3,"volt":0.9},
    "vermoegensteuer":  {"cdu":-0.7,"spd":0.6,"gruene":0.7,"fdp":-0.9,"afd":-0.2,"linke":1.0,"bsw":0.7,"volt":0.3},
    "cannabis":         {"cdu":-0.8,"spd":0.5,"gruene":0.9,"fdp":0.7,"afd":-0.6,"linke":0.7,"bsw":-0.2,"volt":0.6},
    "eurobonds":        {"cdu":-0.5,"spd":0.5,"gruene":0.7,"fdp":-0.8,"afd":-1.0,"linke":0.6,"bsw":-0.7,"volt":0.9},
    "vorratsdaten":     {"cdu":0.7,"spd":0.1,"gruene":-0.8,"fdp":-0.7,"afd":0.4,"linke":-0.9,"bsw":0.1,"volt":-0.6},
    "heizungsgesetz":   {"cdu":0.6,"spd":-0.4,"gruene":-0.9,"fdp":0.7,"afd":0.9,"linke":-0.5,"bsw":0.5,"volt":-0.6},
}

# Cells where "said" (T2 programme) diverges from "did" (T1 votes) — to exercise
# the Sagen-vs-Tun flag. (statement, party) -> (p_said_target, p_did_target).
DIVERGENCES = {
    ("schuldenbremse", "cdu"): (0.4, -0.8),   # softer in the programme than in votes
    ("klima-2035", "spd"):     (0.8, -0.1),   # ambitious on paper, cautious in votes
    ("fachkraefte", "cdu"):    (0.7, -0.2),
    ("mindestlohn-15", "afd"): (0.6, -0.5),
}


def clamp(x):
    return max(-1.0, min(1.0, x))


def build_evidence():
    """Deterministically synthesize evidence items from the leaning matrix.
    Returns (evidence_by_id, cell_to_evidence_ids)."""
    evidence = {}
    cell_ids = {}
    counter = 1
    for s_idx, (slug, topic, text, easy) in enumerate(STATEMENTS):
        for p_idx, p in enumerate(PARTIES):
            pid = p["id"]
            lean = L[slug].get(pid)
            ids = []
            if lean is not None:
                div = DIVERGENCES.get((slug, pid))
                if div is not None:
                    said, did = div
                    items = [
                        ("t1", 1, clamp(did), "2026-04-18", "namentliche_abstimmung",
                         f"Fraktion stimmte bei Drucksache 21/{1000+counter} überwiegend {'zu' if did>0 else 'dagegen'}.", 1.0),
                        ("t2", 2, clamp(said), "2025-11-04", "wahlprogramm",
                         "Wahlprogramm 2025: sinngemäße Selbstverpflichtung (Vorschau-Extrakt).", 1.0),
                    ]
                else:
                    # a fresh T1 vote + a T2 programme statement, both near the leaning
                    jitter = 0.05 if (s_idx + p_idx) % 2 == 0 else -0.05
                    part = 0.5 if (s_idx % 5 == 0 and pid in ("bsw", "volt")) else 1.0
                    items = [
                        ("t1", 1, clamp(lean + jitter), "2026-03-12", "namentliche_abstimmung",
                         f"Fraktion stimmte bei Drucksache 21/{1000+counter} {'mit Ja' if lean>0 else 'mit Nein'} (Vorschau).", part),
                        ("t2", 2, clamp(lean - jitter), "2025-10-20", "wahlprogramm",
                         "Wahlprogramm 2025, thematischer Abschnitt (Vorschau-Extrakt).", 1.0),
                    ]
                for kind, tier, direction, dt, evkind, extract, iw in items:
                    ev_id = f"ev-{counter:04d}"
                    evidence[ev_id] = {
                        "tier": tier,
                        "direction": round(direction, 2),
                        "item_weight": iw,
                        "date": dt,
                        "kind": evkind,
                        "title_de": f"{p['short_name']} · {slug}",
                        "extract": extract,
                        "source_url": "https://www.bundestag.de/…  (Vorschau)",
                        "sha256": hashlib.sha256(f"{slug}:{pid}:{ev_id}".encode()).hexdigest(),
                    }
                    ids.append(ev_id)
                    counter += 1
            cell_ids[f"{pid}:{slug}"] = ids
    return evidence, cell_ids


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data-releases", RELEASE_TAG)
    os.makedirs(out_dir, exist_ok=True)

    engine = AggregationEngine(CONFIG)
    target = date.fromisoformat(TARGET_DATE)
    evidence, cell_ids = build_evidence()

    statements_json = [
        {"id": slug, "policy_slug": slug, "topic": topic, "text_de": text, "text_easy_de": easy,
         "context_de": "Neutraler Hintergrund folgt in der redaktionellen Fassung.",
         "admission_ref": (cell_ids.get(f"cdu:{slug}") or ["—"])[0]}
        for (slug, topic, text, easy) in STATEMENTS
    ]

    positions = {}
    for (slug, topic, text, easy) in STATEMENTS:
        for p in PARTIES:
            pid = p["id"]
            ids = cell_ids[f"{pid}:{slug}"]
            items = [{
                "tier": evidence[i]["tier"],
                "direction": evidence[i]["direction"],
                "item_weight": evidence[i]["item_weight"],
                "evidence_date": date.fromisoformat(evidence[i]["date"]),
            } for i in ids]
            pval, conf, p_said, p_did, divergent = engine.calculate_cell_position(items, target)
            key = f"{pid}:{slug}"
            if pval is None:
                positions[key] = {"p": None, "evidence_ids": ids}
            else:
                # salience: display-only, deterministic bucket
                sal = "hoch" if abs(pval) > 0.6 else ("mittel" if abs(pval) > 0.3 else "gering")
                positions[key] = {
                    "p": pval, "confidence": conf, "p_said": p_said, "p_did": p_did,
                    "divergent": divergent, "evidence_ids": ids, "salience": sal,
                }

    meta = {
        "release": RELEASE_TAG, "legislature": "deu-bundestag-21",
        "methodology_version": METHODOLOGY_VERSION, "as_of": TARGET_DATE,
        "statement_count": len(STATEMENTS), "frozen_at": None,
        "preview": True,
        "preview_label_de": "technische Vorschau — Belege synthetisch, noch nicht vom Beirat geprüft",
        "signature_verified": False,
    }
    methodology = {
        "methodology_version": METHODOLOGY_VERSION,
        "lambda": engine.lambda_decay, "W_0": engine.w0,
        "tier_weights": {str(k): v for k, v in engine.tier_weights.items()},
        "target_date": TARGET_DATE,
        "notes_de": "τ, λ, W₀ und Formeln gemäß consolidated-design v1.2 §2–3.",
    }

    files = {
        "meta.json": meta, "methodology.json": methodology,
        "statements.json": statements_json, "parties.json": PARTIES,
        "positions.json": positions, "evidence.json": evidence,
    }
    for name, obj in files.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    # --- Sign: Ed25519 over "tag|sha256(positions)|sha256(evidence)" ---
    def sha_canon(obj):
        return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    signed_payload = f"{RELEASE_TAG}|{sha_canon(positions)}|{sha_canon(evidence)}"
    sig_info = {"signed": False}
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        sk = Ed25519PrivateKey.generate()
        pk = sk.public_key()
        sig = sk.sign(signed_payload.encode())
        pub_raw = pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        with open(os.path.join(out_dir, "release.sig"), "w") as f:
            f.write(base64.b64encode(sig).decode())
        with open(os.path.join(out_dir, "pubkey.ed25519"), "w") as f:
            f.write(base64.b64encode(pub_raw).decode())
        meta["signature_verified"] = True
        meta["signed_payload"] = signed_payload
        meta["signature_b64"] = base64.b64encode(sig).decode()
        meta["pubkey_b64"] = base64.b64encode(pub_raw).decode()
        with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        sig_info = {"signed": True, "pubkey_b64": meta["pubkey_b64"]}
        # NOTE: ephemeral demo key. Real releases use a held minisign/Ed25519 key (2-of-3 ceremony).
    except Exception as e:
        sig_info = {"signed": False, "error": str(e)}

    n_cells = len(positions)
    n_null = sum(1 for v in positions.values() if v.get("p") is None)
    n_div = sum(1 for v in positions.values() if v.get("divergent"))
    print(f"Release {RELEASE_TAG} built at {out_dir}")
    print(f"  parties={len(PARTIES)} statements={len(STATEMENTS)} cells={n_cells} "
          f"evidence={len(evidence)} keine-belegbare={n_null} divergent={n_div}")
    print(f"  signed={sig_info.get('signed')}")
    return out_dir


if __name__ == "__main__":
    main()
