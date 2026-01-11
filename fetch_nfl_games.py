#!/usr/bin/env python3
"""
Fetch NFL games from ESPN API
"""
import requests
import json
import os
import random
from datetime import datetime

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"

# Broadcaster logo lookups (ESPN doesn't provide good ones)
NETWORK_LOGOS = {
    "ESPN": "https://upload.wikimedia.org/wikipedia/commons/2/2f/ESPN_wordmark.svg",
    "NBC": "https://upload.wikimedia.org/wikipedia/commons/d/d3/NBCUniversal_Peacock_Logo.svg",
    "FOX": "https://upload.wikimedia.org/wikipedia/commons/c/c0/Fox_Broadcasting_Company_logo_%282019%29.svg",
    "CBS": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Paramount_Plus.svg",
    "ABC": "https://upload.wikimedia.org/wikipedia/commons/2/2f/ABC-2021-LOGO.svg",
    "Prime Video": "https://upload.wikimedia.org/wikipedia/commons/9/90/Prime_Video_logo_%282024%29.svg",
    "Amazon": "https://upload.wikimedia.org/wikipedia/commons/9/90/Prime_Video_logo_%282024%29.svg",
    "NFL Network": "https://upload.wikimedia.org/wikipedia/en/7/7a/NFL_Network_logo.svg",
    "Peacock": "https://upload.wikimedia.org/wikipedia/commons/d/d3/NBCUniversal_Peacock_Logo.svg",
}


def convert_to_pacific(utc_time_str):
    """Convert UTC time string to Pacific."""
    try:
        from zoneinfo import ZoneInfo
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        pacific = ZoneInfo('America/Los_Angeles')
        pacific_time = utc_time.astimezone(pacific)
        return pacific_time.strftime('%Y-%m-%d %I:%M %p %Z')
    except:
        return utc_time_str


def fetch_scoreboard():
    """Fetch current NFL scoreboard from ESPN."""
    try:
        response = requests.get(SCOREBOARD_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching scoreboard: {e}")
        return None


def fetch_game_summary(event_id):
    """Fetch detailed game summary from ESPN."""
    try:
        response = requests.get(f"{SUMMARY_URL}?event={event_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching game summary: {e}")
        return None


def parse_status(status_data):
    """Convert ESPN status to our format."""
    state = status_data.get('type', {}).get('state', 'pre')
    if state == 'pre':
        return 'Scheduled'
    elif state == 'in':
        return 'In Progress'
    elif state == 'post':
        return 'Final'
    return 'Unknown'


def parse_broadcasters(geo_broadcasts):
    """Extract broadcaster info with logos."""
    broadcasters = []
    seen = set()
    for gb in geo_broadcasts:
        name = gb.get('media', {}).get('shortName', '')
        if name and name not in seen:
            seen.add(name)
            broadcasters.append({
                'name': name,
                'type': 'TV',
                'logo': NETWORK_LOGOS.get(name, '')
            })
    return broadcasters


def parse_odds(odds_data):
    """Extract betting odds."""
    if not odds_data:
        return None
    
    odds = odds_data[0] if odds_data else {}
    return {
        'spread': odds.get('details', ''),
        'over_under': odds.get('overUnder', 0),
        'provider': odds.get('provider', {}).get('name', '')
    }


def parse_weather(weather_data):
    """Extract weather info."""
    if not weather_data:
        return None
    
    return {
        'temperature': weather_data.get('temperature', 0),
        'condition': weather_data.get('displayValue', ''),
        'precipitation': weather_data.get('precipitation', 0),
        'gust': weather_data.get('gust', 0)
    }


def parse_leader(leader_data):
    """Parse a single leader entry."""
    if not leader_data or not leader_data.get('leaders'):
        return None
    
    top = leader_data['leaders'][0]
    athlete = top.get('athlete', {})
    
    return {
        'name': athlete.get('displayName', ''),
        'short_name': athlete.get('shortName', ''),
        'position': athlete.get('position', {}).get('abbreviation', ''),
        'headshot': athlete.get('headshot', ''),
        'display_value': top.get('displayValue', ''),
        'value': top.get('value', 0)
    }


def parse_team_leaders(leaders_data):
    """Parse team leaders (passing, rushing, receiving)."""
    result = {}
    for leader in leaders_data:
        name = leader.get('name', '')
        if name == 'passingLeader':
            result['passing'] = parse_leader(leader)
        elif name == 'rushingLeader':
            result['rushing'] = parse_leader(leader)
        elif name == 'receivingLeader':
            result['receiving'] = parse_leader(leader)
    return result


def parse_game(event_data):
    """Parse ESPN event data into our format."""
    competition = event_data.get('competitions', [{}])[0]
    competitors = competition.get('competitors', [])
    
    # ESPN puts home team first in competitors, away second
    home_data = next((c for c in competitors if c.get('homeAway') == 'home'), {})
    away_data = next((c for c in competitors if c.get('homeAway') == 'away'), {})
    
    home_team_info = home_data.get('team', {})
    away_team_info = away_data.get('team', {})
    
    # Get scores
    home_score = int(home_data.get('score', 0) or 0)
    away_score = int(away_data.get('score', 0) or 0)
    
    # Get records
    home_records = home_data.get('records', [])
    away_records = away_data.get('records', [])
    home_record = next((r.get('summary', '') for r in home_records if r.get('type') == 'total'), '')
    away_record = next((r.get('summary', '') for r in away_records if r.get('type') == 'total'), '')
    
    # Parse status
    status_data = competition.get('status', {})
    status = parse_status(status_data)
    
    # Get period scores from linescores if available
    periods = []
    home_linescores = home_data.get('linescores', [])
    away_linescores = away_data.get('linescores', [])
    for i, (h, a) in enumerate(zip(home_linescores, away_linescores)):
        periods.append({
            'number': i + 1,
            'type': 'Overtime' if i >= 4 else 'Regulation',
            'away': {'points': int(a.get('value', 0))},
            'home': {'points': int(h.get('value', 0))}
        })
    
    # Build game object
    game = {
        'id': event_data.get('id', ''),
        'status': status,
        'start_time_utc': event_data.get('date', ''),
        'start_time_pacific': convert_to_pacific(event_data.get('date', '')),
        'name': event_data.get('name', ''),
        'short_name': event_data.get('shortName', ''),
        'season': {
            'year': event_data.get('season', {}).get('year', 0),
            'type': event_data.get('season', {}).get('type', 0),
            'type_name': 'Postseason' if event_data.get('season', {}).get('type') == 3 else 'Regular Season',
            'week': event_data.get('week', {}).get('number', 0)
        },
        'away_team': {
            'id': away_team_info.get('id', ''),
            'name': away_team_info.get('displayName', ''),
            'abbreviation': away_team_info.get('abbreviation', ''),
            'short_name': away_team_info.get('shortDisplayName', ''),
            'logo': away_team_info.get('logo', ''),
            'color': away_team_info.get('color', ''),
            'record': away_record,
            'score': away_score
        },
        'home_team': {
            'id': home_team_info.get('id', ''),
            'name': home_team_info.get('displayName', ''),
            'abbreviation': home_team_info.get('abbreviation', ''),
            'short_name': home_team_info.get('shortDisplayName', ''),
            'logo': home_team_info.get('logo', ''),
            'color': home_team_info.get('color', ''),
            'record': home_record,
            'score': home_score
        },
        'venue': {
            'name': competition.get('venue', {}).get('fullName', ''),
            'city': competition.get('venue', {}).get('address', {}).get('city', ''),
            'state': competition.get('venue', {}).get('address', {}).get('state', ''),
            'indoor': competition.get('venue', {}).get('indoor', False)
        },
        'broadcasters': parse_broadcasters(competition.get('geoBroadcasts', [])),
        'scores': {
            'periods': periods,
            'total': {
                'away': away_score,
                'home': home_score
            }
        },
        'odds': parse_odds(competition.get('odds', [])),
        'weather': parse_weather(competition.get('weather', {})),
        'clock': status_data.get('displayClock', '0:00'),
        'period': status_data.get('period', 0),
        'period_detail': status_data.get('type', {}).get('shortDetail', ''),
        'leaders': {
            'away': parse_team_leaders(away_data.get('leaders', [])),
            'home': parse_team_leaders(home_data.get('leaders', []))
        }
    }
    
    return game


def extract_stat(statistics, stat_name):
    """Extract a specific stat from ESPN statistics array."""
    for stat in statistics:
        if stat.get('name') == stat_name:
            return stat.get('displayValue', '0')
    return '0'


def parse_detailed_stats(boxscore):
    """Parse detailed team stats from boxscore."""
    teams = boxscore.get('teams', [])
    
    stats = {'away': {}, 'home': {}}
    
    for team_data in teams:
        side = team_data.get('homeAway', '')
        if side not in ['home', 'away']:
            continue
            
        team_stats = team_data.get('statistics', [])
        
        stats[side] = {
            'total_yards': extract_stat(team_stats, 'totalYards'),
            'passing_yards': extract_stat(team_stats, 'netPassingYards'),
            'rushing_yards': extract_stat(team_stats, 'rushingYards'),
            'first_downs': extract_stat(team_stats, 'firstDowns'),
            'third_down_efficiency': extract_stat(team_stats, 'thirdDownEff'),
            'fourth_down_efficiency': extract_stat(team_stats, 'fourthDownEff'),
            'total_plays': extract_stat(team_stats, 'totalPlays'),
            'yards_per_play': extract_stat(team_stats, 'yardsPerPlay'),
            'turnovers': extract_stat(team_stats, 'turnovers'),
            'fumbles_lost': extract_stat(team_stats, 'fumblesLost'),
            'interceptions': extract_stat(team_stats, 'interceptions'),
            'penalties': extract_stat(team_stats, 'totalPenaltiesYards'),
            'sacks': extract_stat(team_stats, 'sacksYardsLost'),
            'red_zone_efficiency': extract_stat(team_stats, 'redZoneAttempts'),
            'completion_pct': extract_stat(team_stats, 'completionPct'),
            'time_of_possession': extract_stat(team_stats, 'possessionTime')
        }
    
    return stats


def parse_scoring_plays(scoring_plays):
    """Parse scoring plays into clean format."""
    plays = []
    for play in scoring_plays:
        team = play.get('team', {})
        plays.append({
            'period': play.get('period', {}).get('number', 0),
            'clock': play.get('clock', {}).get('displayValue', ''),
            'team': {
                'id': team.get('id', ''),
                'name': team.get('displayName', ''),
                'abbreviation': team.get('abbreviation', ''),
                'logo': team.get('logo', '')
            },
            'type': play.get('type', {}).get('text', ''),
            'text': play.get('text', ''),
            'away_score': play.get('awayScore', 0),
            'home_score': play.get('homeScore', 0)
        })
    return plays


def parse_situation(situation_data):
    """Parse live game situation."""
    if not situation_data:
        return None
    
    last_play = situation_data.get('lastPlay', {})
    
    return {
        'down': situation_data.get('down', 0),
        'distance': situation_data.get('distance', 0),
        'yard_line': situation_data.get('yardLine', 0),
        'down_distance_text': situation_data.get('downDistanceText', ''),
        'spot_text': situation_data.get('shortDownDistanceText', ''),
        'possession': {
            'id': situation_data.get('possession', ''),
            'team': situation_data.get('team', {}).get('abbreviation', '') if situation_data.get('team') else ''
        },
        'is_red_zone': situation_data.get('isRedZone', False),
        'last_play': {
            'text': last_play.get('text', ''),
            'type': last_play.get('type', {}).get('text', '') if last_play.get('type') else '',
            'yards': last_play.get('statYardage', 0)
        }
    }


def parse_game_leaders(leaders_data):
    """Parse game leaders from summary."""
    result = {'away': {}, 'home': {}}
    
    for team_leaders in leaders_data:
        team = team_leaders.get('team', {})
        home_away = team_leaders.get('homeAway', '')
        
        if home_away not in ['home', 'away']:
            continue
        
        leaders = {}
        for leader_cat in team_leaders.get('leaders', []):
            cat_name = leader_cat.get('name', '')
            cat_leaders = leader_cat.get('leaders', [])
            
            if cat_leaders:
                top = cat_leaders[0]
                athlete = top.get('athlete', {})
                headshot = athlete.get('headshot', '')
                if isinstance(headshot, dict):
                    headshot = headshot.get('href', '')
                
                leaders[cat_name] = {
                    'name': athlete.get('displayName', ''),
                    'short_name': athlete.get('shortName', ''),
                    'position': athlete.get('position', {}).get('abbreviation', '') if athlete.get('position') else '',
                    'headshot': headshot,
                    'jersey': athlete.get('jersey', ''),
                    'display_value': top.get('displayValue', ''),
                    'value': top.get('value', 0)
                }
        
        result[home_away] = leaders
    
    return result


def enrich_featured_game(game, summary):
    """Add detailed data to featured game from summary endpoint."""
    if not summary:
        return game
    
    # Add detailed stats
    boxscore = summary.get('boxscore', {})
    game['stats'] = parse_detailed_stats(boxscore)
    
    # Add scoring plays
    game['scoring_plays'] = parse_scoring_plays(summary.get('scoringPlays', []))
    
    # Add live situation (for in-progress games)
    game['situation'] = parse_situation(summary.get('situation'))
    
    # Add game leaders from summary (more detailed than scoreboard)
    if summary.get('leaders'):
        game['leaders'] = parse_game_leaders(summary.get('leaders', []))
    
    # Add weather from gameInfo if not present
    game_info = summary.get('gameInfo', {})
    if game_info.get('weather'):
        weather = game_info.get('weather', {})
        game['weather'] = {
            'temperature': weather.get('temperature', 0),
            'condition': weather.get('displayValue', ''),
            'precipitation': weather.get('precipitation', 0),
            'gust': weather.get('gust', 0)
        }
    
    # Add venue details
    if game_info.get('venue'):
        venue = game_info.get('venue', {})
        game['venue'] = {
            'name': venue.get('fullName', ''),
            'city': venue.get('address', {}).get('city', ''),
            'state': venue.get('address', {}).get('state', ''),
            'indoor': not venue.get('grass', True),
            'capacity': venue.get('capacity', 0)
        }
    
    # Add attendance
    game['attendance'] = game_info.get('attendance', 0)
    
    return game


def rank_games(games):
    """Rank games: In Progress first, then Final, then Scheduled.
    
    Randomly selects the featured game from the highest priority tier
    to provide variety across runs.
    """
    in_progress = [g for g in games if g['status'] == 'In Progress']
    final = [g for g in games if g['status'] == 'Final']
    scheduled = [g for g in games if g['status'] == 'Scheduled']
    
    # Randomly select featured game from highest priority tier
    if in_progress:
        featured = random.choice(in_progress)
        in_progress.remove(featured)
        in_progress = [featured] + in_progress
    elif final:
        featured = random.choice(final)
        final.remove(featured)
        final = [featured] + final
    
    # Sort scheduled by start time
    scheduled.sort(key=lambda g: g['start_time_utc'])
    
    ranked = in_progress + final + scheduled
    for i, game in enumerate(ranked):
        game['display_rank'] = i + 1
    
    return ranked


def main():
    print("=" * 60)
    print("NFL ESPN API - Game Fetcher")
    print("=" * 60)
    
    # Fetch scoreboard
    print("Fetching NFL scoreboard...")
    scoreboard = fetch_scoreboard()
    
    if not scoreboard:
        print("Failed to fetch scoreboard")
        return
    
    # Parse all games
    events = scoreboard.get('events', [])
    print(f"Found {len(events)} games")
    
    all_games = []
    for event in events:
        game = parse_game(event)
        all_games.append(game)
    
    # Rank games
    all_games = rank_games(all_games)
    
    print(f"\nGames ranked:")
    for g in all_games:
        print(f"  {g['display_rank']}. {g['away_team']['abbreviation']} @ {g['home_team']['abbreviation']} ({g['status']})")
    
    # Fetch detailed summary for featured game
    featured_game = None
    if all_games:
        rank1_game = all_games[0]
        print(f"\nFetching detailed summary for: {rank1_game['away_team']['name']} @ {rank1_game['home_team']['name']}...")
        
        summary = fetch_game_summary(rank1_game['id'])
        
        if summary:
            featured_game = enrich_featured_game(rank1_game.copy(), summary)
            print("  Loaded detailed stats, scoring plays, and game leaders")
        else:
            print("  Could not load summary, using scoreboard data")
            featured_game = rank1_game
    
    # Get season info from scoreboard
    season_info = {
        'year': scoreboard.get('season', {}).get('year', 0),
        'type': scoreboard.get('season', {}).get('type', 0),
        'week': scoreboard.get('week', {}).get('number', 0)
    }
    
    # Sort games by display_rank before output (ensures correct order for Liquid template)
    all_games.sort(key=lambda g: g.get('display_rank', 999))
    
    # Save to JSON
    os.makedirs('docs', exist_ok=True)
    output = {
        'fetched_at': datetime.now().isoformat(),
        'season': season_info,
        'featured_game': featured_game,
        'games': all_games
    }
    
    with open('docs/nfl_games.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved to docs/nfl_games.json")


if __name__ == "__main__":
    main()
