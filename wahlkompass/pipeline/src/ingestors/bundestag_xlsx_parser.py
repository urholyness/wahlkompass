"""
Parser for Bundestag namentliche Abstimmungen XLSX files.

Since the 2025/26 bundestag.de relaunch, per-vote roll-call records are
published as XLSX only (verified 2026-07: the opendata page says
"Abstimmungslisten ... als Excel-Listen", per-vote XML blobs 404). This parser
reads the workbook with the standard library (zipfile + ElementTree — no
openpyxl dependency, deterministic) and emits the SAME scoring-ready
`fraktion_aggregates` shape as bundestag_xml_parser.BundestagXMLParser, using
the identical v1.2 rules:

    direction   = (Y - N) / (Y + N)          # active votes only
    item_weight = (Y + N) / (Y + N + E)      # participation share
    unified abstention: item_weight < 0.10 -> excluded (weight 0)
    FCI = max(Y, N, E) / (Y + N + E)         # display only, never scored

XLSX schema (verified against live WP21 files): one sheet, header row
    Wahlperiode | Sitzungnr | Abstimmnr | Fraktion/Gruppe | Name | Vorname |
    Titel | ja | nein | Enthaltung | ungültig | nichtabgegeben | Bezeichnung | Bemerkung
one row per MdB, the vote one-hot encoded across ja/nein/Enthaltung/ungültig/
nichtabgegeben. "ungültig" (invalid ballot) is counted like "nicht abgegeben":
it is neither an active vote nor a deliberate abstention.
"""
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List

from .bundestag_xml_parser import UNIFIED_ABSTENTION_FLOOR

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    strings = []
    for si in root.findall("m:si", _NS):
        strings.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    return strings


def _col_letter(cell_ref: str) -> str:
    return "".join(ch for ch in cell_ref if ch.isalpha())


def _read_rows(xlsx_bytes: bytes) -> List[Dict[str, str]]:
    """Return the sheet as a list of dicts keyed by header names."""
    zf = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    shared = _shared_strings(zf)
    sheet_name = next((n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")), None)
    if sheet_name is None:
        raise ValueError("XLSX has no worksheet")
    root = ET.fromstring(zf.read(sheet_name))

    raw_rows: List[Dict[str, str]] = []
    for row in root.iter(f"{{{_NS['m']}}}row"):
        cells: Dict[str, str] = {}
        for c in row.findall("m:c", _NS):
            ref = c.get("r", "")
            v = c.find("m:v", _NS)
            if v is None or v.text is None:
                value = ""
            elif c.get("t") == "s":
                value = shared[int(v.text)]
            else:
                value = v.text
            cells[_col_letter(ref)] = value
        raw_rows.append(cells)

    if not raw_rows:
        return []
    header = raw_rows[0]
    cols = sorted(header.keys())
    out = []
    for cells in raw_rows[1:]:
        if not any(cells.values()):
            continue
        out.append({header[col]: cells.get(col, "") for col in cols if col in header})
    return out


class BundestagXLSXParser:
    """Roll-call XLSX -> metadata + individual votes + per-Fraktion aggregates."""

    @staticmethod
    def parse_bytes(xlsx_bytes: bytes) -> Dict[str, Any]:
        rows = _read_rows(xlsx_bytes)
        if not rows:
            raise ValueError("XLSX contains no data rows")

        metadata = {
            "period": rows[0].get("Wahlperiode", "").strip(),
            "session": rows[0].get("Sitzungnr", "").strip(),
            "vote_number": rows[0].get("Abstimmnr", "").strip(),
        }

        individual_votes: List[Dict[str, str]] = []
        fraktion_counts: Dict[str, Dict[str, int]] = {}

        def flag(row: Dict[str, str], key: str) -> bool:
            return row.get(key, "").strip() in ("1", "1.0")

        for row in rows:
            fraktion = row.get("Fraktion/Gruppe", "").strip() or "Fraktionslos"
            name = row.get("Bezeichnung", "").strip() or (
                f"{row.get('Vorname', '').strip()} {row.get('Name', '').strip()}".strip())

            if flag(row, "ja"):
                vote = "ja"
            elif flag(row, "nein"):
                vote = "nein"
            elif flag(row, "Enthaltung"):
                vote = "enthalten"
            else:
                # ungültig and nichtabgegeben both count as not voting
                vote = "nicht_abgegeben"

            individual_votes.append({"name": name, "fraktion": fraktion, "vote": vote})
            counts = fraktion_counts.setdefault(
                fraktion, {"ja": 0, "nein": 0, "enthalten": 0, "nicht_abgegeben": 0})
            counts[vote] += 1

        fraktion_aggregates: Dict[str, Dict[str, Any]] = {}
        for fraktion, counts in fraktion_counts.items():
            ja, nein, enthalten = counts["ja"], counts["nein"], counts["enthalten"]
            present = ja + nein + enthalten
            active = ja + nein

            if present == 0:
                fci = 1.0
                participation = 0.0
            else:
                fci = max(ja, nein, enthalten) / present
                participation = active / present

            direction = 0.0 if active == 0 else (ja - nein) / active
            excluded = participation < UNIFIED_ABSTENTION_FLOOR
            item_weight = 0.0 if excluded else participation

            fraktion_aggregates[fraktion] = {
                "counts": counts,
                "present": present,
                "active": active,
                "direction": round(direction, 4),
                "participation": round(participation, 4),
                "item_weight": round(item_weight, 4),
                "fci": round(fci, 4),
                "excluded_unified_abstention": excluded,
            }

        return {
            "metadata": metadata,
            "individual_votes": individual_votes,
            "fraktion_aggregates": fraktion_aggregates,
        }

    @classmethod
    def parse_file(cls, filepath: str) -> Dict[str, Any]:
        with open(filepath, "rb") as f:
            return cls.parse_bytes(f.read())
