import xml.etree.ElementTree as ET
from typing import Dict, Any, List

# v1.2 §3.2 — unified-abstention participation floor.
# If (Y+N)/(Y+N+E) < this, the Fraktion's vote on this Abstimmung is a
# "geschlossene Enthaltung" (strategic abstention = coalition discipline, not
# neutrality) and is excluded from scoring (item_weight -> 0), logged for the
# evidence drawer. Scoring a closed abstention as 0 was a category error (v1.1).
UNIFIED_ABSTENTION_FLOOR = 0.10


class BundestagXMLParser:
    """
    Parser for Bundestag namentliche Abstimmungen (roll-call vote) XML files.

    v1.2 direction coding (replaces the earlier Enthaltung-as-0 rule):

        direction   x  = (Y - N) / (Y + N)          # active votes only
        item_weight    = (Y + N) / (Y + N + E)       # participation share
        unified abstention: if item_weight < 0.10 -> item excluded (weight 0)

    Every Fraktion vote also carries a display-only Fraktion Cohesion Index:

        FCI = max(Y, N, E) / (Y + N + E)

    FCI is presentation, never a scoring modifier — intra-party division is
    displayed, never scored (D6-compliant). The rule is identical for every party.
    """

    @staticmethod
    def parse_xml_string(xml_content: str) -> Dict[str, Any]:
        """
        Parse raw XML string of a roll-call vote.
        Returns a dict with metadata, individual votes, and per-Fraktion aggregates.
        Each Fraktion aggregate is scoring-ready: it carries `direction` and the
        participation-share `item_weight` the aggregation engine consumes directly.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML content: {e}")

        metadata = {
            "title": root.findtext(".//titel", "").strip(),
            "date": root.findtext(".//datum", "").strip(),
            "doc_number": root.findtext(".//dokumenten-nr", "").strip(),
            "period": root.findtext(".//wahlperiode", "").strip(),
        }

        individual_votes: List[Dict[str, str]] = []
        fraktion_counts: Dict[str, Dict[str, int]] = {}

        for abgeordneter in root.findall(".//abgeordneter"):
            nachname = abgeordneter.findtext("nachname", "").strip()
            vorname = abgeordneter.findtext("vorname", "").strip()
            name = f"{vorname} {nachname}".strip()

            fraktion = abgeordneter.findtext("fraktion", "").strip() or "Fraktionslos"

            stimmabgabe = abgeordneter.findtext("stimmabgabe", "").strip().lower()

            # Map vote to standardized vocabulary. Order matters: check
            # "enthalt" before "nein"/"ja" substrings cannot collide, but keep
            # "nicht abgegeben" as the default so it is never mistaken for a vote.
            vote = "nicht_abgegeben"
            if "enthalt" in stimmabgabe:
                vote = "enthalten"
            elif "nein" in stimmabgabe:
                vote = "nein"
            elif "ja" in stimmabgabe:
                vote = "ja"

            individual_votes.append({"name": name, "fraktion": fraktion, "vote": vote})

            if fraktion not in fraktion_counts:
                fraktion_counts[fraktion] = {"ja": 0, "nein": 0, "enthalten": 0, "nicht_abgegeben": 0}
            fraktion_counts[fraktion][vote] += 1

        fraktion_aggregates: Dict[str, Dict[str, Any]] = {}
        for fraktion, counts in fraktion_counts.items():
            ja = counts["ja"]
            nein = counts["nein"]
            enthalten = counts["enthalten"]

            present = ja + nein + enthalten   # Y + N + E (members present who voted/abstained)
            active = ja + nein                 # Y + N (active Ja/Nein votes)

            # Fraktion Cohesion Index over present members (display only).
            if present == 0:
                fci = 1.0                      # nobody present cast a vote -> vacuously cohesive
                participation = 0.0
            else:
                fci = max(ja, nein, enthalten) / present
                participation = active / present

            # v1.2 split-vote direction: (Y - N) / (Y + N), active votes only.
            if active == 0:
                direction = 0.0                # undefined; item is excluded below anyway
            else:
                direction = (ja - nein) / active

            excluded = participation < UNIFIED_ABSTENTION_FLOOR   # geschlossene Enthaltung
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
        """Read and parse an XML file from a local filepath."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return cls.parse_xml_string(content)
