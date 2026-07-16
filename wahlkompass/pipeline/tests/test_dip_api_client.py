import unittest
from unittest.mock import patch, MagicMock
from src.ingestors.dip_api_client import DIPAPIClient

class TestDIPAPIClient(unittest.TestCase):

    @patch('urllib.request.urlopen')
    def test_search_processes_success(self, mock_urlopen):
        # Mock response from urlopen
        mock_response = MagicMock()
        mock_response.read.return_value = b"""{
            "anzahl": 1,
            "documents": [
                {
                    "id": "12345",
                    "titel": "Gesetzentwurf zur Reform der Schuldenbremse",
                    "abstract": "Zusammenfassung des Gesetzes...",
                    "datum": "2026-07-16",
                    "vorgangstyp": "Gesetzgebung",
                    "beratungsstand": "In Beratung",
                    "initiative": "SPD, B90/GRUENEN, FDP"
                }
            ]
        }"""
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = DIPAPIClient(api_key="test_key")
        results = client.search_processes("Schuldenbremse")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "12345")
        self.assertEqual(results[0]["title"], "Gesetzentwurf zur Reform der Schuldenbremse")
        self.assertEqual(results[0]["status"], "In Beratung")
        self.assertEqual(results[0]["url"], "https://dip.bundestag.de/vorgang/12345")

    @patch('urllib.request.urlopen')
    def test_search_processes_failure(self, mock_urlopen):
        # Mock an HTTP error
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://...",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None
        )

        client = DIPAPIClient(api_key="invalid_key")
        results = client.search_processes("Schuldenbremse")
        
        # Should catch exception and return empty list
        self.assertEqual(results, [])

if __name__ == "__main__":
    unittest.main()
