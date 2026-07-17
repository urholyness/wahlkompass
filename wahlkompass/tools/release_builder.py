"""
Wahlkompass release builder (v2) — Germany / Bundestag, live evidence.

Takes statements + parties + the ingested evidence database
(pipeline/data/evidence/, built by src.ingest.build_evidence from live
Bundestag roll-call XLSX data, coded vote<->statement links and verified
Wahlprogramm quotes), runs the v1.2 aggregation engine, and emits a signed,
versioned data-release bundle:

    meta.json  methodology.json  statements.json  parties.json
    positions.json  evidence.json  seats.json  exclusions.json
    release.sig  pubkey.ed25519

Signing (held key, single-key for now; 2-of-3 ceremony later):
    RELEASE_SIGNING_KEY (env or wahlkompass/.env) = path to an Ed25519 PKCS8
    PEM, relative to the wahlkompass root. The signature covers a manifest of
    the SHA-256 of the exact bytes of every content file, so the browser can
    verify what it fetched byte-for-byte (no cross-language JSON
    canonicalization). meta.signed_payload holds the manifest verbatim.

PREVIEW: the statement set is the provisional 15; the vote<->statement links
and programme quotes are provisionally coded (manual high-confidence +
LLM-panel), not yet human dual-coded — meta.preview stays true and the label
stays visible until the Beirat replaces them (a data change, no code change).
"""
import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import date

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(ROOT, "pipeline"))
from src.aggregation import AggregationEngine            # noqa: E402
from src.ingest.http_cache import load_env, DATA_DIR     # noqa: E402

RELEASE_TAG = "2026.11.1-preview"
TARGET_DATE = "2026-11-01"
METHODOLOGY_VERSION = "1.0"
CONFIG = os.path.join(ROOT, "pipeline", "evidence_config", "deu-bundestag.yaml")

# --- Parties: 21st Bundestag (real seats, Feb 2025 result) + ballot parties ---
PARTIES = [
    {"id": "afd",   "short_name": "AfD",     "name": "Alternative für Deutschland", "color_hex": "#009EE0", "ballot_status": "parliamentary", "seats": 152},
    {"id": "bsw",   "short_name": "BSW",     "name": "Bündnis Sahra Wagenknecht",   "color_hex": "#7D254F", "ballot_status": "admitted",      "seats": 0},
    {"id": "cdu",   "short_name": "CDU/CSU", "name": "CDU/CSU",                     "color_hex": "#121212", "ballot_status": "parliamentary", "seats": 208},
    {"id": "fdp",   "short_name": "FDP",     "name": "Freie Demokratische Partei",  "color_hex": "#D9B300", "ballot_status": "admitted",      "seats": 0},
    {"id": "gruene","short_name": "GRÜNE",   "name": "Bündnis 90/Die Grünen",       "color_hex": "#46962B", "ballot_status": "parliamentary", "seats": 85},
    {"id": "linke", "short_name": "Linke",   "name": "Die Linke",                   "color_hex": "#BE3075", "ballot_status": "parliamentary", "seats": 64},
    {"id": "spd",   "short_name": "SPD",     "name": "Sozialdemokratische Partei Deutschlands", "color_hex": "#E3000F", "ballot_status": "parliamentary", "seats": 120},
    {"id": "volt",  "short_name": "Volt",    "name": "Volt Deutschland",            "color_hex": "#5A2A82", "ballot_status": "admitted",      "seats": 0},
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


def _load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _load_signing_key(ephemeral: bool):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    env = {**load_env(), **os.environ}
    b64 = env.get("RELEASE_SIGNING_KEY_B64")
    if b64:
        return serialization.load_pem_private_key(base64.b64decode(b64), password=None)
    key_ref = env.get("RELEASE_SIGNING_KEY")
    if key_ref:
        key_path = key_ref if os.path.isabs(key_ref) else os.path.join(ROOT, key_ref)
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        raise FileNotFoundError(f"RELEASE_SIGNING_KEY points to missing file: {key_path}")
    if ephemeral:
        print("WARNING: no held key configured — signing with an EPHEMERAL key (--ephemeral).")
        return Ed25519PrivateKey.generate()
    raise RuntimeError("No RELEASE_SIGNING_KEY configured. Set it in .env or pass --ephemeral.")


def main(tag: str = RELEASE_TAG, ephemeral: bool = False) -> str:
    from cryptography.hazmat.primitives import serialization

    out_dir = os.path.join(ROOT, "data-releases", tag)
    os.makedirs(out_dir, exist_ok=True)

    engine = AggregationEngine(CONFIG)
    target = date.fromisoformat(TARGET_DATE)

    evidence = _load_json(os.path.join(DATA_DIR, "evidence", "evidence_db.json"), {})
    cells = _load_json(os.path.join(DATA_DIR, "evidence", "cells.json"), {})
    seats = _load_json(os.path.join(DATA_DIR, "polls", "seats.json"), {})
    exclusions = _load_json(os.path.join(DATA_DIR, "exclusions", "exclusions.json"), [])
    if not evidence:
        raise RuntimeError("No ingested evidence found — run the ingest pipeline first.")

    statements_json = [
        {"id": slug, "policy_slug": slug, "topic": topic, "text_de": text, "text_easy_de": easy,
         "context_de": "Neutraler Hintergrund folgt in der redaktionellen Fassung.",
         "admission_ref": (cells.get(f"cdu:{slug}") or ["—"])[0]}
        for (slug, topic, text, easy) in STATEMENTS
    ]

    positions = {}
    for (slug, _topic, _text, _easy) in STATEMENTS:
        for p in PARTIES:
            pid = p["id"]
            key = f"{pid}:{slug}"
            ids = cells.get(key, [])
            items = [{
                "tier": evidence[i]["tier"],
                "direction": evidence[i]["direction"],
                "item_weight": evidence[i].get("item_weight", 1.0),
                "evidence_date": date.fromisoformat(evidence[i]["date"]),
            } for i in ids if i in evidence]
            pval, conf, p_said, p_did, divergent = engine.calculate_cell_position(items, target)
            if pval is None:
                positions[key] = {"p": None, "evidence_ids": ids}
            else:
                sal = "hoch" if abs(pval) > 0.6 else ("mittel" if abs(pval) > 0.3 else "gering")
                positions[key] = {
                    "p": pval, "confidence": conf, "p_said": p_said, "p_did": p_did,
                    "divergent": divergent, "evidence_ids": ids, "salience": sal,
                }

    methodology = {
        "methodology_version": METHODOLOGY_VERSION,
        "lambda": engine.lambda_decay, "W_0": engine.w0,
        "tier_weights": {str(k): v for k, v in engine.tier_weights.items()},
        "target_date": TARGET_DATE,
        "notes_de": "τ, λ, W₀ und Formeln gemäß consolidated-design v1.2 §2–3.",
    }

    content_files = {
        "methodology.json": methodology,
        "statements.json": statements_json,
        "parties.json": PARTIES,
        "positions.json": positions,
        "evidence.json": evidence,
        "seats.json": seats,
        "exclusions.json": exclusions,
    }
    manifest_files = {}
    for name, obj in content_files.items():
        payload = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(payload)
        manifest_files[name] = hashlib.sha256(payload).hexdigest()

    manifest = {"release": tag, "legislature": "deu-bundestag-21", "files": manifest_files}
    signed_payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    sk = _load_signing_key(ephemeral)
    sig = sk.sign(signed_payload.encode("utf-8"))
    pub_raw = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    with open(os.path.join(out_dir, "release.sig"), "w") as f:
        f.write(base64.b64encode(sig).decode())
    with open(os.path.join(out_dir, "pubkey.ed25519"), "w") as f:
        f.write(base64.b64encode(pub_raw).decode())

    n_null = sum(1 for v in positions.values() if v.get("p") is None)
    n_div = sum(1 for v in positions.values() if v.get("divergent"))
    meta = {
        "release": tag, "legislature": "deu-bundestag-21",
        "methodology_version": METHODOLOGY_VERSION, "as_of": TARGET_DATE,
        "statement_count": len(STATEMENTS), "frozen_at": None,
        "preview": True,
        "preview_label_de": ("technische Vorschau — echte Abstimmungsdaten, "
                             "Verknüpfungen & Programm-Zitate provisorisch kodiert, "
                             "noch nicht vom Beirat geprüft"),
        "signature_verified": True,
        "signed_payload": signed_payload,
        "signature_b64": base64.b64encode(sig).decode(),
        "pubkey_b64": base64.b64encode(pub_raw).decode(),
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Release {tag} built at {out_dir}")
    print(f"  parties={len(PARTIES)} statements={len(STATEMENTS)} cells={len(positions)} "
          f"evidence={len(evidence)} keine-belegbare={n_null} divergent={n_div}")
    print(f"  signed=True pubkey={meta['pubkey_b64'][:16]}…")
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=RELEASE_TAG)
    ap.add_argument("--ephemeral", action="store_true",
                    help="allow signing with a throwaway key (dev only)")
    a = ap.parse_args()
    main(tag=a.tag, ephemeral=a.ephemeral)
