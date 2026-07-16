import urllib.request
import json
import os
import sys

def probe_dip_api(api_key: str = None, query: str = "Schuldenbremse"):
    """
    Probe the DIP (Document Information System) API.
    Fetches recent parliamentary activities or processes matching a query.
    """
    if not api_key:
        api_key = os.environ.get("DIP_API_KEY")
        
    if not api_key:
        print("Warning: No DIP_API_KEY environment variable found. Request will likely fail unless using public sandbox endpoints (if any).")
        api_key = "dummy_key" # Replace with actual key

    # DIP API endpoint for Vorgänge (processes/proceedings)
    # Ref: https://dip.bundestag.de/ueber-dip/hilfe/api
    url = f"https://search.dip.bundestag.de/api/v1/vorgang?f.suchbegriff={urllib.parse.quote(query)}"
    
    print(f"Querying DIP API at: {url}")
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"ApiKey {api_key}")
    req.add_header("Accept", "application/json")
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}", file=sys.stderr)
        if e.code == 401:
            print("Verify your DIP_API_KEY is active and passed correctly in the headers.", file=sys.stderr)
        return
    except Exception as e:
        print(f"Error querying DIP API: {e}", file=sys.stderr)
        return

    num_documents = data.get("anzahl", 0)
    print(f"Successfully connected! Found {num_documents} records matching query '{query}'.\n")

    for item in data.get("documents", [])[:5]:
        vorgang_id = item.get("id")
        titel = item.get("titel")
        beratungsstand = item.get("beratungsstand")
        datum = item.get("datum")
        
        print(f"[{vorgang_id}] {titel}")
        print(f"  Date: {datum} | Status: {beratungsstand}")
        print("-" * 50)

if __name__ == "__main__":
    query_term = sys.argv[1] if len(sys.argv) > 1 else "Schuldenbremse"
    probe_dip_api(query=query_term)
