#!/usr/bin/env python3
"""
Fetch NFL games from SportsBlaze API
"""
import requests
import json
import os
from datetime import datetime, timedelta

API_KEY = os.environ.get('SPORTSBLAZE_API_KEY')
BASE_URL = "https://api.sportsblaze.com/nfl/v1/boxscores"

# Logo lookups
TEAM_LOGOS = {
    "Arizona Cardinals": "https://static.www.nfl.com/image/private/f_auto/league/u9fltoslqdsyao8cpm0k",
    "Atlanta Falcons": "https://static.www.nfl.com/image/private/f_auto/league/d8m7hzpsbrl6pnqht8op",
    "Carolina Panthers": "https://static.www.nfl.com/image/private/f_auto/league/ervfzgrqdpnc7lh5gqwq",
    "Chicago Bears": "https://static.www.nfl.com/image/private/f_auto/league/ijrplti0kmzsyoaikhv1",
    "Dallas Cowboys": "https://static.www.nfl.com/image/private/f_auto/league/ieid8hoygzdlmzo0tnf6",
    "Detroit Lions": "https://static.www.nfl.com/image/private/f_auto/league/ocvxwnapdvwevupe4tpr",
    "Green Bay Packers": "https://static.www.nfl.com/image/private/f_auto/league/gppfvr7n8gljgjaqux2x",
    "Los Angeles Rams": "https://static.www.nfl.com/image/private/f_auto/league/ayvwcmluj2ohkdlbiegi",
    "Minnesota Vikings": "https://static.www.nfl.com/image/private/f_auto/league/teguylrnqqmfcwxvcmmz",
    "New Orleans Saints": "https://static.www.nfl.com/image/private/f_auto/league/grhjkahghjkk17v43hdx",
    "New York Giants": "https://static.www.nfl.com/image/private/f_auto/league/t6mhdmgizi6qhndh8b9p",
    "Philadelphia Eagles": "https://static.www.nfl.com/image/private/f_auto/league/puhrqgj71gobgdkdo6uq",
    "San Francisco 49ers": "https://static.www.nfl.com/image/private/f_auto/league/dxibuyxbk0b9ua5ih9hn",
    "Seattle Seahawks": "https://static.www.nfl.com/image/private/f_auto/league/gcytzwpjdzbpwnwxincg",
    "Tampa Bay Buccaneers": "https://static.www.nfl.com/image/private/f_auto/league/v8uqiualryypwqgvwcih",
    "Washington Commanders": "https://static.www.nfl.com/image/private/f_auto/league/xymxwrxtyj9fhaemhdyd",
    "Baltimore Ravens": "https://static.www.nfl.com/image/private/f_auto/league/ucsdijmddsqcj1i9tddd",
    "Buffalo Bills": "https://static.www.nfl.com/image/private/f_auto/league/giphcy6ie9mxbnldntsf",
    "Cincinnati Bengals": "https://static.www.nfl.com/image/private/f_auto/league/okxpteoliyayufypqalq",
    "Cleveland Browns": "https://static.www.nfl.com/image/upload/f_auto/league/bedyixmmjhszfcx5wv2l",
    "Denver Broncos": "https://static.www.nfl.com/image/private/f_auto/league/t0p7m5cjdjy18rnzzqbx",
    "Houston Texans": "https://static.www.nfl.com/image/upload/f_auto/league/u6camnphqvjc6mku6u3c",
    "Indianapolis Colts": "https://static.www.nfl.com/image/private/f_auto/league/ketwqeuschqzjsllbid5",
    "Jacksonville Jaguars": "https://static.www.nfl.com/image/private/f_auto/league/qycbib6ivrm9dqaexryk",
    "Kansas City Chiefs": "https://static.www.nfl.com/image/private/f_auto/league/ujshjqvmnxce8m4obmvs",
    "Las Vegas Raiders": "https://static.www.nfl.com/image/private/f_auto/league/gzcojbzcyjgubgyb6xf2",
    "Los Angeles Chargers": "https://static.www.nfl.com/image/private/f_auto/league/dhfidtn8jrumakbogeu4",
    "Miami Dolphins": "https://static.www.nfl.com/image/private/f_auto/league/lits6p8ycthy9to70bnt",
    "New England Patriots": "https://static.www.nfl.com/image/private/f_auto/league/moyfxx3dq5pio4aiftnc",
    "New York Jets": "https://static.www.nfl.com/image/upload/f_auto/league/vdqo4iiufmdrimkaxslj",
    "Pittsburgh Steelers": "https://static.www.nfl.com/image/private/f_auto/league/xujg9t3t4u5nmjgr54wx",
    "Tennessee Titans": "https://static.www.nfl.com/image/private/f_auto/league/pln44vuzugjgipyidsre",
}

NETWORK_LOGOS = {
    "ESPN": "https://upload.wikimedia.org/wikipedia/commons/2/2f/ESPN_wordmark.svg",
    "NBC": "https://upload.wikimedia.org/wikipedia/commons/d/d3/NBCUniversal_Peacock_Logo.svg",
    "FOX": "https://upload.wikimedia.org/wikipedia/commons/c/c0/Fox_Broadcasting_Company_logo_%282019%29.svg",
    "CBS": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Paramount_Plus.svg",
    "Prime Video": "https://upload.wikimedia.org/wikipedia/commons/9/90/Prime_Video_logo_%282024%29.svg",
}

def get_date_range():
    today = datetime.now()
    dates = []
    for offset in range(-3, 4):
        date = today + timedelta(days=offset)
        dates.append(date.strftime('%Y-%m-%d'))
    return dates

def fetch_daily_boxscores(date):
    url = f"{BASE_URL}/daily/{date}.json"
    params = {'key': API_KEY}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except:
        return None

def convert_to_pacific(utc_time_str):
    try:
        from zoneinfo import ZoneInfo
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        pacific = ZoneInfo('America/Los_Angeles')
        pacific_time = utc_time.astimezone(pacific)
        return pacific_time.strftime('%Y-%m-%d %I:%M %p %Z')
    except:
        return utc_time_str

def parse_game(game_data):
    """Parse game data into clean format with logos."""
    teams = game_data.get('teams', {})
    away = teams.get('away', {})
    home = teams.get('home', {})
    
    away_name = away.get('name', 'Unknown')
    home_name = home.get('name', 'Unknown')
    
    broadcasters = []
    for bc in game_data.get('broadcasts', []):
        bc_name = bc.get('name', '')
        broadcasters.append({
            'name': bc_name,
            'type': bc.get('type', ''),
            'logo': NETWORK_LOGOS.get(bc_name, '')
        })
    
    result = {
        'id': game_data.get('id', ''),
        'status': game_data.get('status', 'Unknown'),
        'start_time_pacific': convert_to_pacific(game_data.get('date', '')),
        'start_time_utc': game_data.get('date', ''),
        'season': game_data.get('season', {}),
        'away_team': {
            'id': away.get('id', ''),
            'name': away_name,
            'logo': TEAM_LOGOS.get(away_name, '')
        },
        'home_team': {
            'id': home.get('id', ''),
            'name': home_name,
            'logo': TEAM_LOGOS.get(home_name, '')
        },
        'venue': game_data.get('venue', {}),
        'broadcasters': broadcasters
    }
    
    # Add scores if present
    if 'scores' in game_data:
        scores = game_data['scores']
        result['scores'] = {
            'periods': scores.get('periods', []),
            'final': {
                'away': scores.get('total', {}).get('away', {}).get('points', 0),
                'home': scores.get('total', {}).get('home', {}).get('points', 0)
            }
        }
    
    return result

def rank_games(games):
    """Rank games: In Progress first, then Final, then Scheduled."""
    in_progress = [g for g in games if g['status'] == 'In Progress']
    final = [g for g in games if g['status'] == 'Final']
    scheduled = [g for g in games if g['status'] == 'Scheduled']
    
    # Sort scheduled by start time
    scheduled.sort(key=lambda g: g['start_time_utc'])
    
    ranked = in_progress + final + scheduled
    for i, game in enumerate(ranked):
        game['display_rank'] = i + 1
    
    return ranked

def main():
    print("="*60)
    print("NFL SportsBlaze API - Game Fetcher")
    print("="*60)
    
    dates = get_date_range()
    print(f"Date range: {dates[0]} to {dates[-1]}")
    
    all_games = []
    game_ids = set()
    
    # Fetch daily boxscores for each date
    for date in dates:
        print(f"Fetching {date}...")
        daily_data = fetch_daily_boxscores(date)
        
        if daily_data:
            games = daily_data.get('games', [])
            print(f"  Found {len(games)} games")
            
            for game in games:
                game_id = game.get('id')
                if game_id and game_id not in game_ids:
                    game_ids.add(game_id)
                    parsed = parse_game(game)
                    all_games.append(parsed)
    
    # Rank games
    all_games = rank_games(all_games)
    
    print(f"\nTotal games: {len(all_games)}")
    for g in all_games:
        print(f"  {g['display_rank']}. {g['away_team']['name']} @ {g['home_team']['name']} ({g['status']})")
    
    # Save to JSON
    os.makedirs('docs', exist_ok=True)
    output = {'games': all_games}
    with open('docs/nfl_games.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved to docs/nfl_games.json")

if __name__ == "__main__":
    main()
