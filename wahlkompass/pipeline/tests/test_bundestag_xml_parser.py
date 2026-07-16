import unittest
from src.ingestors.bundestag_xml_parser import BundestagXMLParser


class TestBundestagXMLParser(unittest.TestCase):

    def test_parse_valid_xml(self):
        sample_xml = """<?xml version="1.0" encoding="utf-8"?>
        <doku>
            <wahlperiode>21</wahlperiode>
            <dokumenten-nr>21/9999</dokumenten-nr>
            <titel>Entwurf eines Gesetzes zur Reform der Schuldenbremse</titel>
            <datum>2026-07-16</datum>
            <abgeordnetenliste>
                <abgeordneter><vorname>Bärbel</vorname><nachname>Bas</nachname>
                    <fraktion>SPD</fraktion><stimmabgabe>Ja</stimmabgabe></abgeordneter>
                <abgeordneter><vorname>Rolf</vorname><nachname>Mützenich</nachname>
                    <fraktion>SPD</fraktion><stimmabgabe>Ja</stimmabgabe></abgeordneter>
                <abgeordneter><vorname>Friedrich</vorname><nachname>Merz</nachname>
                    <fraktion>CDU/CSU</fraktion><stimmabgabe>Nein</stimmabgabe></abgeordneter>
                <abgeordneter><vorname>Alexander</vorname><nachname>Dobrindt</nachname>
                    <fraktion>CDU/CSU</fraktion><stimmabgabe>Enthaltung</stimmabgabe></abgeordneter>
                <abgeordneter><vorname>Alice</vorname><nachname>Weidel</nachname>
                    <fraktion>AfD</fraktion><stimmabgabe>nicht abgegeben</stimmabgabe></abgeordneter>
            </abgeordnetenliste>
        </doku>
        """

        result = BundestagXMLParser.parse_xml_string(sample_xml)

        self.assertEqual(result["metadata"]["title"], "Entwurf eines Gesetzes zur Reform der Schuldenbremse")
        self.assertEqual(result["metadata"]["date"], "2026-07-16")
        self.assertEqual(result["metadata"]["doc_number"], "21/9999")
        self.assertEqual(result["metadata"]["period"], "21")

        self.assertEqual(len(result["individual_votes"]), 5)
        self.assertEqual(result["individual_votes"][0]["name"], "Bärbel Bas")
        self.assertEqual(result["individual_votes"][0]["vote"], "ja")

        # SPD — unanimous support, full participation.
        spd = result["fraktion_aggregates"]["SPD"]
        self.assertEqual(spd["counts"]["ja"], 2)
        self.assertEqual(spd["fci"], 1.0)
        self.assertEqual(spd["direction"], 1.0)
        self.assertEqual(spd["item_weight"], 1.0)
        self.assertFalse(spd["excluded_unified_abstention"])

        # CDU/CSU — v1.2: among ACTIVE votes it was unanimously Nein -> direction
        # -1.0; half the present members abstained -> participation weight 0.5.
        cdu = result["fraktion_aggregates"]["CDU/CSU"]
        self.assertEqual(cdu["counts"]["nein"], 1)
        self.assertEqual(cdu["counts"]["enthalten"], 1)
        self.assertEqual(cdu["fci"], 0.5)
        self.assertEqual(cdu["direction"], -1.0)
        self.assertEqual(cdu["item_weight"], 0.5)
        self.assertFalse(cdu["excluded_unified_abstention"])

        # AfD — no active votes -> unified abstention, excluded from scoring.
        afd = result["fraktion_aggregates"]["AfD"]
        self.assertEqual(afd["counts"]["nicht_abgegeben"], 1)
        self.assertEqual(afd["item_weight"], 0.0)
        self.assertTrue(afd["excluded_unified_abstention"])

    def test_unified_abstention_excluded(self):
        # A Fraktion where >90% abstain (participation < 0.10) is a geschlossene
        # Enthaltung: excluded (item_weight 0), not scored toward the position.
        members = (
            [("Ja", "X")]                       # 1 active
            + [("Enthaltung", "X")] * 19        # 19 abstain -> participation 1/20 = 0.05
        )
        rows = "".join(
            f"<abgeordneter><vorname>A</vorname><nachname>{i}</nachname>"
            f"<fraktion>{frak}</fraktion><stimmabgabe>{vote}</stimmabgabe></abgeordneter>"
            for i, (vote, frak) in enumerate(members)
        )
        xml = f"<doku><titel>t</titel><datum>2026-07-16</datum><wahlperiode>21</wahlperiode>{rows}</doku>"
        agg = BundestagXMLParser.parse_xml_string(xml)["fraktion_aggregates"]["X"]
        self.assertEqual(agg["participation"], 0.05)
        self.assertEqual(agg["item_weight"], 0.0)
        self.assertTrue(agg["excluded_unified_abstention"])


if __name__ == "__main__":
    unittest.main()
