import urllib.request
import urllib.parse
import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DIPAPIClient:
    """
    Client for querying the Bundestag Document Information System (DIP) API.
    Ref: https://dip.bundestag.de/ueber-dip/hilfe/api
    """
    
    BASE_URL = "https://search.dip.bundestag.de/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DIP_API_KEY")
        if not self.api_key:
            logger.warning("No DIP_API_KEY provided or found in environment. DIP API requests will fail if auth is required.")

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper method to execute authenticated GET requests to the DIP API.
        """
        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/{endpoint}?{query_string}"
        
        req = urllib.request.Request(url)
        if self.api_key:
            req.add_header("Authorization", f"ApiKey {self.api_key}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "Wahlkompass Ingest/1.0")

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error querying DIP API: {e.code} - {e.reason} (URL: {url})")
            raise RuntimeError(f"DIP API HTTP Error: {e.code} {e.reason}") from e
        except Exception as e:
            logger.error(f"Network/Serialization Error querying DIP API: {e} (URL: {url})")
            raise RuntimeError(f"DIP API Request Failed: {e}") from e

    def search_processes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for Vorgänge (parliamentary processes/bills/motions) matching a keyword.
        """
        params = {
            "f.suchbegriff": query,
            "limit": limit
        }
        
        try:
            data = self._make_request("vorgang", params)
        except Exception as e:
            logger.error(f"Failed searching processes: {e}")
            return []

        results = []
        for doc in data.get("documents", []):
            results.append({
                "id": doc.get("id"),
                "title": doc.get("titel"),
                "abstract": doc.get("abstract"),
                "date": doc.get("datum"),
                "type": doc.get("vorgangstyp"),
                "status": doc.get("beratungsstand"),
                "initiator": doc.get("initiative"),
                "url": f"https://dip.bundestag.de/vorgang/{doc.get('id')}"
            })
            
        return results

    def get_process_details(self, process_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve detailed information about a specific Vorgang.
        """
        try:
            doc = self._make_request(f"vorgang/{process_id}", {})
            return {
                "id": doc.get("id"),
                "title": doc.get("titel"),
                "abstract": doc.get("abstract"),
                "date": doc.get("datum"),
                "type": doc.get("vorgangstyp"),
                "status": doc.get("beratungsstand"),
                "initiator": doc.get("initiative"),
                "url": f"https://dip.bundestag.de/vorgang/{doc.get('id')}"
            }
        except Exception as e:
            logger.error(f"Failed getting details for process {process_id}: {e}")
            return None
