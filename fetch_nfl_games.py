#!/usr/bin/env python3
"""
Fetch NFL games from SportsBlaze API for a 7-day window
(3 days before today, today, and 3 days after)
Then fetch full boxscore for each game found.
"""

import requests
import json
from datetime import datetime, timedelta

# API Configuration - ADD YOUR KEY HERE
import os
API_KEY = os.environ.get('SPORTSBLAZE_API_KEY')
BASE_URL = "https://api.sportsblaze.com/nfl/v1/boxscores"

def get_date_range():
    """Generate 7-day window: 3 days before today through 3 days after."""
    today = datetime.now()
    dates = []
    for offset in range(-3, 4):  # -3, -2, -1, 0, 1, 2, 3
        date = today + timedelta(days=offset)
        dates.append(date.strftime('%Y-%m-%d'))
    return dates

def fetch_daily_boxscores(date):
    """Fetch all games for a specific date."""
    url = f"{BASE_URL}/daily/{date}.json"
    params = {'key': API_KEY}
    
    print(f"\n{'='*60}")
    print(f"Fetching games for date: {date}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        games = data.get('games', [])
        print(f"Found {len(games)} game(s) on {date}")
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching daily boxscores for {date}: {e}")
        return None

def fetch_game_boxscore(game_id):
    """Fetch full boxscore for a specific game."""
    url = f"{BASE_URL}/game/{game_id}.json"
    params = {'key': API_KEY}
    
    print(f"\n{'-'*40}")
    print(f"Fetching full boxscore for game: {game_id}")
    print(f"URL: {url}")
    print(f"{'-'*40}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching game boxscore for {game_id}: {e}")
        return None

def main():
    print("="*60)
    print("NFL SportsBlaze API - 7 Day Game Fetcher")
    print("="*60)
    
    # Get date range
    dates = get_date_range()
    print(f"\nDate range: {dates[0]} to {dates[-1]}")
    print(f"Today: {datetime.now().strftime('%Y-%m-%d')}")
    
    all_games = []
    game_ids = set()
    
    # Step 1: Fetch daily boxscores for each date
    for date in dates:
        daily_data = fetch_daily_boxscores(date)
        
        if daily_data:
            print(f"\n--- Full Daily Boxscores Response for {date} ---")
            print(json.dumps(daily_data, indent=2))
            
            games = daily_data.get('games', [])
            for game in games:
                game_id = game.get('id')
                if game_id and game_id not in game_ids:
                    game_ids.add(game_id)
                    all_games.append({
                        'id': game_id,
                        'date': date,
                        'daily_data': game
                    })
    
    print(f"\n{'='*60}")
    print(f"Total unique games found: {len(all_games)}")
    print(f"{'='*60}")
    
    # Step 2: Fetch full boxscore for each game
    for game_info in all_games:
        game_id = game_info['id']
        full_boxscore = fetch_game_boxscore(game_id)
        
        if full_boxscore:
            print(f"\n--- Full Game Boxscore Response for {game_id} ---")
            print(json.dumps(full_boxscore, indent=2))
            game_info['full_boxscore'] = full_boxscore
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Date range searched: {dates[0]} to {dates[-1]}")
    print(f"Total games found: {len(all_games)}")
    
    for game in all_games:
        daily = game['daily_data']
        away = daily.get('teams', {}).get('away', {}).get('name', 'Unknown')
        home = daily.get('teams', {}).get('home', {}).get('name', 'Unknown')
        status = daily.get('status', 'Unknown')
        game_date = daily.get('date', game['date'])
        print(f"  - {away} @ {home} ({status}) - {game_date}")

if __name__ == "__main__":
    main()
