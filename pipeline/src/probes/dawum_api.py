import urllib.request
import json
import sys

def probe_dawum_api():
    """
    Probe the Dawum API to fetch latest poll aggregates for German federal elections.
    """
    url = "https://api.dawum.de/"
    print(f"Fetching polling data from Dawum API: {url}")
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Wahlkompass Ingestion Probe/1.0'}
        )
        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode('utf-8')
            data = json.loads(raw_data)
    except Exception as e:
        print(f"Error calling Dawum API: {e}", file=sys.stderr)
        return

    # Dawum database structure contains:
    # 'Parla': Parliament IDs (e.g. '0' for Bundestag)
    # 'Institutes': Pollsters
    # 'Taskers': Client newspapers/outlets
    # 'Parties': Party profiles
    # 'Surveys': Actual poll results, sorted by ID/Date
    
    parliaments = data.get("Parla", {})
    parties = data.get("Parties", {})
    surveys = data.get("Surveys", {})
    
    # Find Bundestag Parliament ID (usually "0")
    bt_id = None
    for pid, pinfo in parliaments.items():
        if "Bundestag" in pinfo.get("Name", ""):
            bt_id = pid
            break
            
    if not bt_id:
        print("Bundestag Parliament ID not found in metadata.", file=sys.stderr)
        return

    print(f"Bundestag ID identified as: {bt_id}")
    
    # Get recent surveys for Bundestag
    bt_surveys = []
    for sid, sinfo in surveys.items():
        if sinfo.get("Parliament_ID") == bt_id:
            sinfo["id"] = sid
            bt_surveys.append(sinfo)
            
    # Sort surveys by date descending
    bt_surveys.sort(key=lambda x: x.get("Date", ""), reverse=True)
    
    if not bt_surveys:
        print("No Bundestag surveys found.", file=sys.stderr)
        return
        
    latest_survey = bt_surveys[0]
    pollster_id = latest_survey.get("Institute_ID")
    pollster = data.get("Institutes", {}).get(pollster_id, {}).get("Name", "Unknown")
    pub_date = latest_survey.get("Date")
    respondents = latest_survey.get("Respondents", "Unknown")
    
    print(f"\nLatest Pollster: {pollster} (As of {pub_date}, Respondents: {respondents})")
    print("-" * 50)
    
    results = latest_survey.get("Results", {})
    for party_id, percentage in results.items():
        party_name = parties.get(party_id, {}).get("Name", f"Party ID {party_id}")
        party_shortcut = parties.get(party_id, {}).get("Shortcut", "")
        print(f"  {party_shortcut:<10} ({party_name:<40}): {percentage}%")

if __name__ == "__main__":
    probe_dawum_api()
