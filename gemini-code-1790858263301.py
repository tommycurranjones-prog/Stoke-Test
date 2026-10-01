import requests
import json
from datetime import datetime
import time

# Stoke City Coordinates & IDs
STOKE_LAT = 52.9883
STOKE_LON = -2.1756
STOKE_TEAM_ID = 17 # Sofascore ID for Stoke City

# Headers to bypass basic bot-protection on Sofascore
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/"
}

def get_stoke_home_matches():
    """Fetches historical Stoke matches and filters for home games after 5 PM."""
    print("Fetching Stoke City matches...")
    matches = []
    # Loop through historical pages (0 to 10 for recent years, increase for more history)
    for page in range(0, 5): 
        url = f"https://api.sofascore.com/api/v1/team/{STOKE_TEAM_ID}/events/last/{page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            continue
            
        events = response.json().get('events', [])
        for event in events:
            # Check if Stoke is home (homeTeam id = 17)
            if event.get('homeTeam', {}).get('id') == STOKE_TEAM_ID:
                timestamp = event.get('startTimestamp')
                dt = datetime.fromtimestamp(timestamp)
                
                # CRITERIA 1: Match starts at or after 17:00 (5 PM)
                if dt.hour >= 17:
                    matches.append({
                        "id": event['id'],
                        "date_str": dt.strftime('%Y-%m-%d'),
                        "hour": dt.hour,
                        "away_team": event.get('awayTeam', {}).get('name')
                    })
        time.sleep(1) # Be polite to the API
    return matches

def check_cold_rainy_weather(date_str, hour):
    """Checks Open-Meteo historical API for rain and < 8 degrees."""
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={STOKE_LAT}&longitude={STOKE_LON}&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,rain"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        try:
            # Get weather at the specific hour the match started
            temp = data['hourly']['temperature_2m'][hour]
            rain = data['hourly']['rain'][hour]
            
            # CRITERIA 2 & 3: Below 8 degrees AND Raining
            if temp is not None and rain is not None:
                if temp < 8.0 and rain > 0.0:
                    return {"is_cold_and_rainy": True, "temp": temp, "rain": rain}
        except (KeyError, IndexError):
            pass
    return {"is_cold_and_rainy": False}

def get_players_who_did_it(match_id):
    """Fetches away team lineups and finds players with rating > 8.0."""
    url = f"https://api.sofascore.com/api/v1/event/{match_id}/lineups"
    response = requests.get(url, headers=HEADERS)
    successful_players = []
    
    if response.status_code == 200:
        data = response.json()
        # We only care about the away team (the ones visiting Stoke)
        away_lineup = data.get('away', {}).get('players', [])
        for player_data in away_lineup:
            player_info = player_data.get('player', {})
            statistics = player_data.get('statistics', {})
            rating = statistics.get('rating', 0)
            
            # CRITERIA 4: Rating over 8.0
            if rating > 8.0:
                successful_players.append({
                    "id": player_info.get('id'),
                    "name": player_info.get('name'),
                    "rating": rating
                })
        time.sleep(1) # Be polite to API
    return successful_players

def build_database():
    database = {
        "stoked_players": {}, # Dictionary of player names/IDs who succeeded
        "matches_analyzed": 0
    }
    
    matches = get_stoke_home_matches()
    print(f"Found {len(matches)} home evening matches. Analyzing weather...")
    
    for match in matches:
        weather = check_cold_rainy_weather(match['date_str'], match['hour'])
        
        if weather['is_cold_and_rainy']:
            print(f"[{match['date_str']}] YES! {match['away_team']} - Temp: {weather['temp']}C, Rain: {weather['rain']}mm")
            
            # Fetch the players who got > 8.0 in this specific match
            players = get_players_who_did_it(match['id'])
            for p in players:
                # Add to our hall of fame database
                database["stoked_players"][p['name'].lower()] = {
                    "name": p['name'],
                    "match_date": match['date_str'],
                    "rating": p['rating'],
                    "temp": weather['temp'],
                    "team": match['away_team']
                }
                print(f"   -> {p['name']} DID IT! (Rating: {p['rating']})")
        else:
            print(f"[{match['date_str']}] Failed weather check.")
            
        database["matches_analyzed"] += 1
        
    # Save the database for the website to use
    with open('stoke_data.json', 'w') as f:
        json.dump(database, f, indent=4)
    print("Database built successfully: stoke_data.json")

if __name__ == "__main__":
    build_database()