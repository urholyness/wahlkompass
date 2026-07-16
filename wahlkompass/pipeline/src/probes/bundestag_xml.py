import urllib.request
import xml.etree.ElementTree as ET
import sys

def probe_bundestag_xml(xml_url: str):
    """
    Fetch and parse a Bundestag namentliche Abstimmung XML document.
    Outputs a summary of votes by Fraktion.
    """
    print(f"Fetching Bundestag XML from: {xml_url}")
    try:
        req = urllib.request.Request(
            xml_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"Error fetching XML: {e}", file=sys.stderr)
        return

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return

    # Basic structure check (based on bundestag.de schema for namentliche abstimmungen)
    title = root.findtext(".//titel") or "Unknown Roll Call"
    datum = root.findtext(".//datum") or "Unknown Date"
    dok_nr = root.findtext(".//dokumenten-nr") or "Unknown Doc"
    
    print(f"\nTitle: {title}")
    print(f"Date: {datum} | Document: {dok_nr}")
    print("-" * 50)

    # Aggregate by Fraktion/Gruppe
    vote_stats = {} # fraktion -> {ja, nein, enthalten, ungueltig, nicht_abgegeben}

    for abgeordneter in root.findall(".//abgeordneter"):
        fraktion = abgeordneter.findtext("fraktion") or "Fraktionslos"
        stimme = abgeordneter.findtext("stimmabgabe")
        if not stimme:
            continue
            
        stimme = stimme.strip().lower()

        if fraktion not in vote_stats:
            vote_stats[fraktion] = {"ja": 0, "nein": 0, "enthalten": 0, "nicht_abgegeben": 0}

        if "ja" in stimme:
            vote_stats[fraktion]["ja"] += 1
        elif "nein" in stimme:
            vote_stats[fraktion]["nein"] += 1
        elif "enthalten" in stimme:
            vote_stats[fraktion]["enthalten"] += 1
        else:
            vote_stats[fraktion]["nicht_abgegeben"] += 1

    for fraktion, counts in vote_stats.items():
        total = sum(counts.values())
        print(f"Fraktion: {fraktion}")
        print(f"  Ja: {counts['ja']} | Nein: {counts['nein']} | Enthalten: {counts['enthalten']} | DNF: {counts['nicht_abgegeben']} (Total: {total})")
        # Compute dynamic Fraktion Cohesion Index (FCI)
        max_vote = max(counts['ja'], counts['nein'], counts['enthalten'])
        fci = max_vote / total if total > 0 else 0
        print(f"  Fraktion Cohesion Index (FCI): {fci:.2%}")

if __name__ == "__main__":
    # Sample URL representing an official Bundestag vote XML (mock or real URL)
    sample_xml = "https://www.bundestag.de/resource/blob/949012/6b3644fe115e584f932e652bf1c9c450/xml-data.xml"
    if len(sys.argv) > 1:
        sample_xml = sys.argv[1]
    probe_bundestag_xml(sample_xml)
