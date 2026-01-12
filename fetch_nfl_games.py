#!/usr/bin/env python3
"""
Fetch NFL games from ESPN API - SLIM Version (<100KB output)
Optimized for TRMNL e-ink display constraints
"""
import requests
import json
import os
import random
from datetime import datetime

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"

# Broadcaster logo lookups
NETWORK_LOGOS = {
    "ESPN": "https://upload.wikimedia.org/wikipedia/commons/2/2f/ESPN_wordmark.svg",
    "NBC": "https://upload.wikimedia.org/wikipedia/commons/d/3/NBCUniversal_Peacock_Logo.svg",
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
    """Extract broadcaster info (slim)."""
    broadcasters = []
    seen = set()
    for gb in geo_broadcasts:
        name = gb.get('media', {}).get('shortName', '')
        if name and name not in seen:
            seen.add(name)
            broadcasters.append({
                'name': name,
                'logo': NETWORK_LOGOS.get(name, '')
            })
    return broadcasters[:2]  # Max 2 broadcasters


def parse_situation_from_scoreboard(situation_data):
    """Parse live game situation (slim)."""
    if not situation_data:
        return None
    
    last_play = situation_data.get('lastPlay', {})
    
    return {
        'down': situation_data.get('down', 0),
        'distance': situation_data.get('distance', 0),
        'yard_line': situation_data.get('yardLine', 0),
        'down_distance_text': situation_data.get('downDistanceText', ''),
        'possession': situation_data.get('possession', ''),
        'is_red_zone': situation_data.get('isRedZone', False),
        'home_timeouts': situation_data.get('homeTimeouts', 3),
        'away_timeouts': situation_data.get('awayTimeouts', 3),
        'last_play': {
            'text': last_play.get('text', ''),
            'type': last_play.get('type', {}).get('text', '') if isinstance(last_play.get('type'), dict) else '',
        } if last_play else None
    }


def parse_game(event_data):
    """Parse ESPN event data into slim format."""
    competition = event_data.get('competitions', [{}])[0]
    competitors = competition.get('competitors', [])
    
    home_data = next((c for c in competitors if c.get('homeAway') == 'home'), {})
    away_data = next((c for c in competitors if c.get('homeAway') == 'away'), {})
    
    home_team_info = home_data.get('team', {})
    away_team_info = away_data.get('team', {})
    
    home_score = int(home_data.get('score', 0) or 0)
    away_score = int(away_data.get('score', 0) or 0)
    
    home_records = home_data.get('records', [])
    away_records = away_data.get('records', [])
    home_record = next((r.get('summary', '') for r in home_records if r.get('type') == 'total'), '')
    away_record = next((r.get('summary', '') for r in away_records if r.get('type') == 'total'), '')
    
    status_data = competition.get('status', {})
    status = parse_status(status_data)
    
    # Quarter scores
    periods = []
    home_linescores = home_data.get('linescores', [])
    away_linescores = away_data.get('linescores', [])
    for i, (h, a) in enumerate(zip(home_linescores, away_linescores)):
        periods.append({
            'number': i + 1,
            'away': {'points': int(a.get('value', 0))},
            'home': {'points': int(h.get('value', 0))}
        })
    
    situation = None
    if status == 'In Progress':
        situation = parse_situation_from_scoreboard(competition.get('situation'))
    
    game = {
        'id': event_data.get('id', ''),
        'status': status,
        'start_time_utc': event_data.get('date', ''),
        'start_time_pacific': convert_to_pacific(event_data.get('date', '')),
        'short_name': event_data.get('shortName', ''),
        'season': {
            'type_name': 'Postseason' if event_data.get('season', {}).get('type') == 3 else 'Regular Season',
            'week': event_data.get('week', {}).get('number', 0)
        },
        'away_team': {
            'id': away_team_info.get('id', ''),
            'abbreviation': away_team_info.get('abbreviation', ''),
            'short_name': away_team_info.get('shortDisplayName', ''),
            'record': away_record,
        },
        'home_team': {
            'id': home_team_info.get('id', ''),
            'abbreviation': home_team_info.get('abbreviation', ''),
            'short_name': home_team_info.get('shortDisplayName', ''),
            'record': home_record,
        },
        'broadcasters': parse_broadcasters(competition.get('geoBroadcasts', [])),
        'scores': {
            'periods': periods,
            'total': {'away': away_score, 'home': home_score}
        },
        'clock': status_data.get('displayClock', '0:00'),
        'period': status_data.get('period', 0),
        'situation': situation
    }
    
    return game


# ============================================================================
# SLIM DATA EXTRACTION FROM SUMMARY ENDPOINT
# ============================================================================

def parse_slim_team_stats(boxscore):
    """Parse team stats - VALUES ONLY (no labels/descriptions)."""
    teams = boxscore.get('teams', [])
    stats = {'away': {}, 'home': {}}
    
    # Stats we actually use in the template
    WANTED_STATS = [
        'totalYards', 'netPassingYards', 'rushingYards', 'firstDowns',
        'thirdDownEff', 'fourthDownEff', 'redZoneAttempts',
        'turnovers', 'totalPenaltiesYards', 'possessionTime'
    ]
    
    for team_data in teams:
        side = team_data.get('homeAway', '')
        if side not in ['home', 'away']:
            continue
        
        team_stats = team_data.get('statistics', [])
        parsed = {}
        
        for stat in team_stats:
            stat_name = stat.get('name', '')
            if stat_name in WANTED_STATS:
                parsed[stat_name] = stat.get('displayValue', '0')
        
        stats[side] = parsed
    
    return stats


def parse_slim_scoring_plays(scoring_plays):
    """Parse scoring plays - SLIM format."""
    plays = []
    for play in scoring_plays:
        team = play.get('team', {})
        clock = play.get('clock', {})
        period = play.get('period', {})
        
        plays.append({
            'period': period.get('number', 0),
            'clock': clock.get('displayValue', ''),
            'team': team.get('abbreviation', ''),
            'text': play.get('text', ''),
            'away_score': play.get('awayScore', 0),
            'home_score': play.get('homeScore', 0),
        })
    return plays


def parse_slim_drive(drive):
    """Parse a single drive with SLIM plays."""
    plays = []
    for play in drive.get('plays', []):
        play_type = play.get('type', {})
        end_info = play.get('end', {})
        
        # Only keep essential play info
        plays.append({
            'type': play_type.get('abbreviation', '') or play_type.get('text', ''),
            'text': play.get('text', ''),
            'yards': play.get('statYardage', 0),
            'scoring': play.get('scoringPlay', False),
            'end_down': end_info.get('shortDownDistanceText', ''),
            'end_pos': end_info.get('possessionText', ''),
        })
    
    team = drive.get('team', {})
    
    return {
        'id': drive.get('id', ''),
        'team': team.get('abbreviation', ''),
        'description': drive.get('description', ''),
        'yards': drive.get('yards', 0),
        'result': drive.get('shortDisplayResult', '') or drive.get('displayResult', ''),
        'is_score': drive.get('isScore', False),
        'plays': plays
    }


def parse_slim_drives(drives_data, num_drives=2):
    """Parse only the last N drives (chronologically)."""
    if not drives_data:
        return None
    
    previous = drives_data.get('previous', [])
    current = drives_data.get('current', {})
    
    # Get last N drives from previous
    recent_drives = previous[-num_drives:] if len(previous) >= num_drives else previous
    
    result = {
        'recent': [parse_slim_drive(d) for d in recent_drives]
    }
    
    # Add current drive if it exists and has plays
    if current and current.get('plays'):
        result['current'] = parse_slim_drive(current)
    
    return result


def parse_slim_situation(situation_data):
    """Parse live game situation - SLIM format."""
    if not situation_data:
        return None
    
    last_play = situation_data.get('lastPlay', {})
    lp_end = last_play.get('end', {}) if last_play else {}
    
    return {
        'down': situation_data.get('down', 0),
        'distance': situation_data.get('distance', 0),
        'yard_line': situation_data.get('yardLine', 0),
        'down_distance_text': situation_data.get('downDistanceText', ''),
        'possession': situation_data.get('possession', ''),
        'is_red_zone': situation_data.get('isRedZone', False),
        'home_timeouts': situation_data.get('homeTimeouts', 3),
        'away_timeouts': situation_data.get('awayTimeouts', 3),
        'last_play': {
            'text': last_play.get('text', ''),
            'type': last_play.get('type', {}).get('text', '') if isinstance(last_play.get('type'), dict) else '',
            'yards': last_play.get('statYardage', 0),
        } if last_play else None
    }


def parse_slim_odds(pickcenter):
    """Extract just the essential betting info."""
    if not pickcenter:
        return None
    
    pc = pickcenter[0] if pickcenter else {}
    
    return {
        'spread': pc.get('details', ''),
        'over_under': pc.get('overUnder', 0),
        'home_ml': pc.get('homeTeamOdds', {}).get('moneyLine', 0),
        'away_ml': pc.get('awayTeamOdds', {}).get('moneyLine', 0),
    }


def parse_slim_weather(game_info):
    """Extract essential weather info."""
    if not game_info:
        return None
    
    weather = game_info.get('weather', {})
    if not weather:
        return None
    
    return {
        'temp': weather.get('temperature', 0),
        'condition': weather.get('conditionId', ''),
        'wind': weather.get('gust', 0),
    }


def parse_slim_venue(game_info):
    """Extract essential venue info."""
    if not game_info:
        return None
    
    venue = game_info.get('venue', {})
    if not venue:
        return None
    
    return {
        'name': venue.get('fullName', ''),
        'city': venue.get('address', {}).get('city', ''),
        'state': venue.get('address', {}).get('state', ''),
    }


def enrich_featured_game_slim(game, summary):
    """Add SLIM detailed data to featured game."""
    if not summary:
        return game
    
    # Team stats - values only
    boxscore = summary.get('boxscore', {})
    game['stats'] = parse_slim_team_stats(boxscore)
    
    # Scoring plays - slim
    game['scoring_plays'] = parse_slim_scoring_plays(summary.get('scoringPlays', []))
    
    # Only last 2 drives
    game['drives'] = parse_slim_drives(summary.get('drives'), num_drives=2)
    
    # Full situation (needed for live display)
    summary_situation = parse_slim_situation(summary.get('situation'))
    if summary_situation:
        game['situation'] = summary_situation
    
    # Slim odds
    game['odds'] = parse_slim_odds(summary.get('pickcenter'))
    
    # Slim weather
    game['weather'] = parse_slim_weather(summary.get('gameInfo'))
    
    # Slim venue
    game['venue'] = parse_slim_venue(summary.get('gameInfo'))
    
    return game


# ============================================================================
# SLIM OUTPUT FOR NON-FEATURED GAMES
# ============================================================================

def slim_other_game(game):
    """Minimal data for non-featured games."""
    return {
        'status': game.get('status', ''),
        'start_time_pacific': game.get('start_time_pacific', ''),
        'away_team': {
            'abbreviation': game.get('away_team', {}).get('abbreviation', ''),
            'short_name': game.get('away_team', {}).get('short_name', ''),
            'record': game.get('away_team', {}).get('record', ''),
        },
        'home_team': {
            'abbreviation': game.get('home_team', {}).get('abbreviation', ''),
            'short_name': game.get('home_team', {}).get('short_name', ''),
            'record': game.get('home_team', {}).get('record', ''),
        },
        'scores': game.get('scores', {}),
        'clock': game.get('clock', ''),
        'period': game.get('period', 0),
    }


def rank_games(games):
    """Rank games: In Progress first, then Final, then Scheduled."""
    in_progress = [g for g in games if g['status'] == 'In Progress']
    final = [g for g in games if g['status'] == 'Final']
    scheduled = [g for g in games if g['status'] == 'Scheduled']
    
    if in_progress:
        featured = random.choice(in_progress)
        in_progress.remove(featured)
        in_progress = [featured] + in_progress
    elif final:
        featured = random.choice(final)
        final.remove(featured)
        final = [featured] + final
    
    scheduled.sort(key=lambda g: g['start_time_utc'])
    
    ranked = in_progress + final + scheduled
    for i, game in enumerate(ranked):
        game['display_rank'] = i + 1
    
    return ranked


def main():
    print("=" * 60)
    print("NFL ESPN API - SLIM Fetcher (<100KB)")
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
    
    # Enrich #1 ranked game with SLIM data
    if all_games:
        rank1_game = all_games[0]
        print(f"\nFetching SLIM summary for: {rank1_game['short_name']}...")
        
        summary = fetch_game_summary(rank1_game['id'])
        
        if summary:
            enrich_featured_game_slim(rank1_game, summary)
            print("  ✓ Loaded slim stats")
            print("  ✓ Loaded scoring plays")
            print("  ✓ Loaded last 2 drives")
            if rank1_game.get('drives', {}).get('recent'):
                print(f"    - {len(rank1_game['drives']['recent'])} recent drives")
        else:
            print("  Could not load summary")
    
    # Get season info
    season_info = {
        'year': scoreboard.get('season', {}).get('year', 0),
        'type_name': 'Postseason' if scoreboard.get('season', {}).get('type') == 3 else 'Regular Season',
        'week': scoreboard.get('week', {}).get('number', 0)
    }
    
    # Build output - featured game is first, others are slimmed
    output_games = []
    for i, game in enumerate(all_games[:4]):
        if i == 0:
            output_games.append(game)
        else:
            output_games.append(slim_other_game(game))
    
    # Save to JSON
    os.makedirs('docs', exist_ok=True)
    output = {
        'fetched_at': datetime.now().isoformat(),
        'season': season_info,
        'games': output_games
    }
    
    # Compact version only
    with open('docs/nfl_games.json', 'w') as f:
        json.dump(output, f, separators=(',', ':'))
    
    # Also save pretty version for debugging
    with open('docs/nfl_games_debug.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    # Report sizes
    compact_size = os.path.getsize('docs/nfl_games.json')
    debug_size = os.path.getsize('docs/nfl_games_debug.json')
    print(f"\nSaved to docs/nfl_games.json ({compact_size:,} bytes / {compact_size/1024:.1f} KB)")
    print(f"Debug version: docs/nfl_games_debug.json ({debug_size:,} bytes / {debug_size/1024:.1f} KB)")
    
    if compact_size > 100000:
        print(f"⚠️  WARNING: Output exceeds 100KB limit!")
    else:
        print(f"✓ Output is within 100KB limit")


if __name__ == "__main__":
    main()
