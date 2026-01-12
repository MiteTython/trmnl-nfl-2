#!/usr/bin/env python3
"""
Fetch NFL games from ESPN API - Full Data Version
Pulls all available data from ESPN for the featured game
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


def parse_situation_from_scoreboard(situation_data, home_abbrev, away_abbrev):
    """Parse live game situation from scoreboard API."""
    if not situation_data:
        return None
    
    last_play = situation_data.get('lastPlay', {})
    poss_id = situation_data.get('possession', '')
    poss_abbrev = ''
    
    short_text = situation_data.get('shortDownDistanceText', '')
    possession_text = situation_data.get('possessionText', '')
    
    if situation_data.get('team'):
        poss_abbrev = situation_data.get('team', {}).get('abbreviation', '')
    
    return {
        'down': situation_data.get('down', 0),
        'distance': situation_data.get('distance', 0),
        'yard_line': situation_data.get('yardLine', 0),
        'down_distance_text': situation_data.get('downDistanceText', ''),
        'spot_text': short_text,
        'possession_text': possession_text,
        'possession': poss_id,
        'possession_short': poss_abbrev,
        'is_red_zone': situation_data.get('isRedZone', False),
        'home_timeouts': situation_data.get('homeTimeouts', 3),
        'away_timeouts': situation_data.get('awayTimeouts', 3),
        'last_play': {
            'text': last_play.get('text', ''),
            'type': last_play.get('type', {}).get('text', '') if isinstance(last_play.get('type'), dict) else '',
            'yards': last_play.get('statYardage', 0)
        } if last_play else None
    }


def parse_game(event_data):
    """Parse ESPN event data into our format."""
    competition = event_data.get('competitions', [{}])[0]
    competitors = competition.get('competitors', [])
    
    home_data = next((c for c in competitors if c.get('homeAway') == 'home'), {})
    away_data = next((c for c in competitors if c.get('homeAway') == 'away'), {})
    
    home_team_info = home_data.get('team', {})
    away_team_info = away_data.get('team', {})
    
    home_abbrev = home_team_info.get('abbreviation', '')
    away_abbrev = away_team_info.get('abbreviation', '')
    
    home_score = int(home_data.get('score', 0) or 0)
    away_score = int(away_data.get('score', 0) or 0)
    
    home_records = home_data.get('records', [])
    away_records = away_data.get('records', [])
    home_record = next((r.get('summary', '') for r in home_records if r.get('type') == 'total'), '')
    away_record = next((r.get('summary', '') for r in away_records if r.get('type') == 'total'), '')
    
    status_data = competition.get('status', {})
    status = parse_status(status_data)
    
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
    
    situation = None
    if status == 'In Progress':
        situation = parse_situation_from_scoreboard(
            competition.get('situation'),
            home_abbrev,
            away_abbrev
        )
    
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
        },
        'situation': situation
    }
    
    return game


# ============================================================================
# FULL DATA EXTRACTION FROM SUMMARY ENDPOINT
# ============================================================================

def extract_stat(statistics, stat_name):
    """Extract a specific stat from ESPN statistics array."""
    for stat in statistics:
        if stat.get('name') == stat_name:
            return stat.get('displayValue', '0')
    return '0'


def parse_full_team_stats(boxscore):
    """Parse ALL team stats from boxscore."""
    teams = boxscore.get('teams', [])
    stats = {'away': {}, 'home': {}}
    
    for team_data in teams:
        side = team_data.get('homeAway', '')
        if side not in ['home', 'away']:
            continue
            
        team_stats = team_data.get('statistics', [])
        
        # Extract ALL available stats
        parsed = {}
        for stat in team_stats:
            stat_name = stat.get('name', '')
            if stat_name:
                parsed[stat_name] = {
                    'value': stat.get('displayValue', '0'),
                    'label': stat.get('label', stat_name),
                    'description': stat.get('description', '')
                }
        
        stats[side] = parsed
    
    return stats


def parse_full_player_stats(boxscore):
    """Parse ALL player stats from boxscore."""
    players = boxscore.get('players', [])
    result = {'away': {}, 'home': {}}
    
    for team_players in players:
        side = team_players.get('homeAway', '')
        if side not in ['home', 'away']:
            continue
        
        team_stats = {}
        
        for stat_category in team_players.get('statistics', []):
            cat_name = stat_category.get('name', '')
            cat_labels = stat_category.get('labels', [])
            cat_descriptions = stat_category.get('descriptions', [])
            cat_athletes = stat_category.get('athletes', [])
            
            players_in_cat = []
            for athlete_data in cat_athletes:
                athlete = athlete_data.get('athlete', {})
                stats_values = athlete_data.get('stats', [])
                
                # Build stat dict with labels
                player_stats = {}
                for i, val in enumerate(stats_values):
                    if i < len(cat_labels):
                        player_stats[cat_labels[i]] = val
                
                players_in_cat.append({
                    'id': athlete.get('id', ''),
                    'name': athlete.get('displayName', ''),
                    'short_name': athlete.get('shortName', ''),
                    'jersey': athlete.get('jersey', ''),
                    'position': athlete.get('position', {}).get('abbreviation', '') if athlete.get('position') else '',
                    'headshot': athlete.get('headshot', {}).get('href', '') if isinstance(athlete.get('headshot'), dict) else athlete.get('headshot', ''),
                    'stats': player_stats
                })
            
            if players_in_cat:
                team_stats[cat_name] = {
                    'labels': cat_labels,
                    'descriptions': cat_descriptions,
                    'players': players_in_cat
                }
        
        result[side] = team_stats
    
    return result


def parse_scoring_plays(scoring_plays):
    """Parse ALL scoring play data."""
    plays = []
    for play in scoring_plays:
        team = play.get('team', {})
        clock = play.get('clock', {})
        period = play.get('period', {})
        play_type = play.get('type', {})
        
        plays.append({
            'id': play.get('id', ''),
            'sequence_number': play.get('sequenceNumber', 0),
            'period': {
                'number': period.get('number', 0),
                'type': period.get('type', '')
            },
            'clock': {
                'value': clock.get('value', 0),
                'display': clock.get('displayValue', '')
            },
            'team': {
                'id': team.get('id', ''),
                'name': team.get('displayName', ''),
                'abbreviation': team.get('abbreviation', ''),
                'logo': team.get('logo', '')
            },
            'type': {
                'id': play_type.get('id', ''),
                'text': play_type.get('text', ''),
                'abbreviation': play_type.get('abbreviation', '')
            },
            'text': play.get('text', ''),
            'away_score': play.get('awayScore', 0),
            'home_score': play.get('homeScore', 0),
            'scoring_type': play.get('scoringType', {})
        })
    return plays


def parse_drives(drives_data):
    """Parse ALL drive data including plays."""
    if not drives_data:
        return None
    
    previous = drives_data.get('previous', [])
    current = drives_data.get('current', {})
    
    def parse_single_drive(drive):
        plays = []
        for play in drive.get('plays', []):
            play_type = play.get('type', {})
            start_info = play.get('start', {})
            end_info = play.get('end', {})
            
            plays.append({
                'id': play.get('id', ''),
                'sequence_number': play.get('sequenceNumber', 0),
                'type': {
                    'id': play_type.get('id', ''),
                    'text': play_type.get('text', ''),
                    'abbreviation': play_type.get('abbreviation', '')
                },
                'text': play.get('text', ''),
                'short_text': play.get('shortText', ''),
                'alternative_text': play.get('alternativeText', ''),
                'home_score': play.get('homeScore', 0),
                'away_score': play.get('awayScore', 0),
                'period': play.get('period', {}).get('number', 0),
                'clock': {
                    'value': play.get('clock', {}).get('value', 0),
                    'display': play.get('clock', {}).get('displayValue', '')
                },
                'scoring_play': play.get('scoringPlay', False),
                'priority': play.get('priority', False),
                'modified': play.get('modified', ''),
                'wallclock': play.get('wallclock', ''),
                'start': {
                    'down': start_info.get('down', 0),
                    'distance': start_info.get('distance', 0),
                    'yard_line': start_info.get('yardLine', 0),
                    'yards_to_endzone': start_info.get('yardsToEndzone', 0),
                    'possession_text': start_info.get('possessionText', ''),
                    'down_distance_text': start_info.get('downDistanceText', ''),
                    'short_down_distance_text': start_info.get('shortDownDistanceText', '')
                },
                'end': {
                    'down': end_info.get('down', 0),
                    'distance': end_info.get('distance', 0),
                    'yard_line': end_info.get('yardLine', 0),
                    'yards_to_endzone': end_info.get('yardsToEndzone', 0),
                    'possession_text': end_info.get('possessionText', ''),
                    'down_distance_text': end_info.get('downDistanceText', ''),
                    'short_down_distance_text': end_info.get('shortDownDistanceText', '')
                },
                'stat_yardage': play.get('statYardage', 0),
                'scoring_type': play.get('scoringType', {})
            })
        
        team = drive.get('team', {})
        result_info = drive.get('result', '')
        start = drive.get('start', {})
        end = drive.get('end', {})
        time_elapsed = drive.get('timeElapsed', {})
        
        return {
            'id': drive.get('id', ''),
            'description': drive.get('description', ''),
            'team': {
                'id': team.get('id', ''),
                'name': team.get('displayName', ''),
                'abbreviation': team.get('abbreviation', ''),
                'logo': team.get('logo', '')
            },
            'start': {
                'period': start.get('period', {}).get('number', 0),
                'clock': start.get('clock', {}).get('displayValue', ''),
                'yard_line': start.get('yardLine', 0),
                'text': start.get('text', '')
            },
            'end': {
                'period': end.get('period', {}).get('number', 0),
                'clock': end.get('clock', {}).get('displayValue', ''),
                'yard_line': end.get('yardLine', 0),
                'text': end.get('text', '')
            },
            'time_elapsed': {
                'value': time_elapsed.get('value', 0),
                'display': time_elapsed.get('displayValue', '')
            },
            'yards': drive.get('yards', 0),
            'is_score': drive.get('isScore', False),
            'offense_plays': drive.get('offensivePlays', 0),
            'result': result_info if isinstance(result_info, str) else result_info.get('text', ''),
            'short_display_result': drive.get('shortDisplayResult', ''),
            'display_result': drive.get('displayResult', ''),
            'plays': plays
        }
    
    parsed_previous = [parse_single_drive(d) for d in previous]
    parsed_current = parse_single_drive(current) if current else None
    
    return {
        'previous': parsed_previous,
        'current': parsed_current
    }


def parse_full_situation(situation_data):
    """Parse FULL live game situation."""
    if not situation_data:
        return None
    
    last_play = situation_data.get('lastPlay', {})
    down_distance = situation_data.get('downDistanceText', '')
    
    # Parse last play fully
    last_play_parsed = None
    if last_play:
        lp_type = last_play.get('type', {})
        lp_start = last_play.get('start', {})
        lp_end = last_play.get('end', {})
        
        last_play_parsed = {
            'id': last_play.get('id', ''),
            'type': {
                'id': lp_type.get('id', '') if isinstance(lp_type, dict) else '',
                'text': lp_type.get('text', '') if isinstance(lp_type, dict) else str(lp_type),
                'abbreviation': lp_type.get('abbreviation', '') if isinstance(lp_type, dict) else ''
            },
            'text': last_play.get('text', ''),
            'short_text': last_play.get('shortText', ''),
            'alternative_text': last_play.get('alternativeText', ''),
            'scoring_play': last_play.get('scoringPlay', False),
            'priority': last_play.get('priority', False),
            'stat_yardage': last_play.get('statYardage', 0),
            'period': last_play.get('period', {}).get('number', 0) if isinstance(last_play.get('period'), dict) else 0,
            'clock': last_play.get('clock', {}).get('displayValue', '') if isinstance(last_play.get('clock'), dict) else '',
            'start': {
                'down': lp_start.get('down', 0),
                'distance': lp_start.get('distance', 0),
                'yard_line': lp_start.get('yardLine', 0),
                'yards_to_endzone': lp_start.get('yardsToEndzone', 0),
                'down_distance_text': lp_start.get('downDistanceText', ''),
                'possession_text': lp_start.get('possessionText', '')
            },
            'end': {
                'down': lp_end.get('down', 0),
                'distance': lp_end.get('distance', 0),
                'yard_line': lp_end.get('yardLine', 0),
                'yards_to_endzone': lp_end.get('yardsToEndzone', 0),
                'down_distance_text': lp_end.get('downDistanceText', ''),
                'possession_text': lp_end.get('possessionText', '')
            }
        }
    
    return {
        'down': situation_data.get('down', 0),
        'distance': situation_data.get('distance', 0),
        'yard_line': situation_data.get('yardLine', 0),
        'yards_to_endzone': situation_data.get('yardsToEndzone', 0),
        'down_distance_text': down_distance,
        'short_down_distance_text': situation_data.get('shortDownDistanceText', ''),
        'possession_text': situation_data.get('possessionText', ''),
        'possession': situation_data.get('possession', ''),
        'is_red_zone': situation_data.get('isRedZone', False),
        'home_timeouts': situation_data.get('homeTimeouts', 3),
        'away_timeouts': situation_data.get('awayTimeouts', 3),
        'last_play': last_play_parsed
    }


def parse_game_leaders(leaders_data):
    """Parse ALL game leaders from summary."""
    result = {'away': {}, 'home': {}}
    
    for team_leaders in leaders_data:
        team = team_leaders.get('team', {})
        home_away = team_leaders.get('homeAway', '')
        
        if home_away not in ['home', 'away']:
            continue
        
        leaders = {}
        for leader_cat in team_leaders.get('leaders', []):
            cat_name = leader_cat.get('name', '')
            cat_display_name = leader_cat.get('displayName', '')
            cat_leaders = leader_cat.get('leaders', [])
            
            parsed_leaders = []
            for leader in cat_leaders:
                athlete = leader.get('athlete', {})
                headshot = athlete.get('headshot', '')
                if isinstance(headshot, dict):
                    headshot = headshot.get('href', '')
                
                parsed_leaders.append({
                    'rank': leader.get('rank', 0),
                    'name': athlete.get('displayName', ''),
                    'short_name': athlete.get('shortName', ''),
                    'jersey': athlete.get('jersey', ''),
                    'position': athlete.get('position', {}).get('abbreviation', '') if athlete.get('position') else '',
                    'headshot': headshot,
                    'display_value': leader.get('displayValue', ''),
                    'value': leader.get('value', 0),
                    'athlete_id': athlete.get('id', '')
                })
            
            leaders[cat_name] = {
                'display_name': cat_display_name,
                'leaders': parsed_leaders
            }
        
        result[home_away] = leaders
    
    return result


def parse_game_info(game_info):
    """Parse full game info."""
    if not game_info:
        return {}
    
    venue = game_info.get('venue', {})
    weather = game_info.get('weather', {})
    officials = game_info.get('officials', [])
    
    return {
        'venue': {
            'id': venue.get('id', ''),
            'name': venue.get('fullName', ''),
            'city': venue.get('address', {}).get('city', ''),
            'state': venue.get('address', {}).get('state', ''),
            'indoor': venue.get('indoor', False),
            'grass': venue.get('grass', True),
            'capacity': venue.get('capacity', 0),
            'images': venue.get('images', [])
        },
        'weather': {
            'temperature': weather.get('temperature', 0),
            'condition': weather.get('displayValue', ''),
            'condition_id': weather.get('conditionId', ''),
            'link': weather.get('link', {}),
            'high_temperature': weather.get('highTemperature', 0),
            'precipitation': weather.get('precipitation', 0),
            'gust': weather.get('gust', 0)
        },
        'attendance': game_info.get('attendance', 0),
        'officials': [{
            'name': off.get('displayName', ''),
            'position': off.get('position', {}).get('name', '') if off.get('position') else '',
            'order': off.get('order', 0)
        } for off in officials]
    }


def parse_news(news_data):
    """Parse news/headlines."""
    if not news_data:
        return []
    
    articles = news_data.get('articles', [])
    return [{
        'headline': article.get('headline', ''),
        'description': article.get('description', ''),
        'published': article.get('published', ''),
        'type': article.get('type', ''),
        'premium': article.get('premium', False),
        'links': article.get('links', {})
    } for article in articles[:5]]  # Limit to 5 articles


def parse_win_probability(winprobability):
    """Parse win probability data."""
    if not winprobability:
        return []
    
    return [{
        'play_id': wp.get('playId', ''),
        'sequence_number': wp.get('sequenceNumber', 0),
        'home_win_percentage': wp.get('homeWinPercentage', 0),
        'away_win_percentage': wp.get('awayWinPercentage', 0) if 'awayWinPercentage' in wp else (1 - wp.get('homeWinPercentage', 0.5)),
        'tie_percentage': wp.get('tiePercentage', 0),
        'seconds_left': wp.get('secondsLeft', 0)
    } for wp in winprobability]


def parse_predictor(predictor):
    """Parse game predictor/betting data."""
    if not predictor:
        return None
    
    home_team = predictor.get('homeTeam', {})
    away_team = predictor.get('awayTeam', {})
    
    return {
        'header': predictor.get('header', ''),
        'home_team': {
            'id': home_team.get('id', ''),
            'game_projection': home_team.get('gameProjection', 0),
            'team_chance_loss': home_team.get('teamChanceLoss', 0),
            'team_chance_tie': home_team.get('teamChanceTie', 0)
        },
        'away_team': {
            'id': away_team.get('id', ''),
            'game_projection': away_team.get('gameProjection', 0),
            'team_chance_loss': away_team.get('teamChanceLoss', 0),
            'team_chance_tie': away_team.get('teamChanceTie', 0)
        }
    }


def parse_standings(standings_data):
    """Parse standings info if available."""
    if not standings_data:
        return None
    
    groups = standings_data.get('groups', [])
    return [{
        'name': group.get('name', ''),
        'header': group.get('header', ''),
        'standings': group.get('standings', {})
    } for group in groups]


def enrich_featured_game_full(game, summary):
    """Add ALL detailed data to featured game from summary endpoint."""
    if not summary:
        return game
    
    # Boxscore - team and player stats
    boxscore = summary.get('boxscore', {})
    game['team_stats'] = parse_full_team_stats(boxscore)
    game['player_stats'] = parse_full_player_stats(boxscore)
    
    # Scoring plays
    game['scoring_plays'] = parse_scoring_plays(summary.get('scoringPlays', []))
    
    # All drives with all plays
    game['drives'] = parse_drives(summary.get('drives'))
    
    # Full situation
    summary_situation = parse_full_situation(summary.get('situation'))
    if summary_situation:
        game['situation'] = summary_situation
    
    # Game leaders
    if summary.get('leaders'):
        game['leaders'] = parse_game_leaders(summary.get('leaders', []))
    
    # Game info (venue, weather, officials, attendance)
    game['game_info'] = parse_game_info(summary.get('gameInfo'))
    
    # News/headlines
    game['news'] = parse_news(summary.get('news'))
    
    # Win probability
    game['win_probability'] = parse_win_probability(summary.get('winprobability'))
    
    # Predictor
    game['predictor'] = parse_predictor(summary.get('predictor'))
    
    # Standings
    game['standings'] = parse_standings(summary.get('standings'))
    
    # Pickcenter (betting/picks)
    game['pickcenter'] = summary.get('pickcenter', [])
    
    # Against the spread
    game['against_the_spread'] = summary.get('againstTheSpread', [])
    
    # Odds
    game['odds'] = summary.get('odds', [])
    
    # Header info (for additional context)
    header = summary.get('header', {})
    if header:
        game['header'] = {
            'id': header.get('id', ''),
            'uid': header.get('uid', ''),
            'season': header.get('season', {}),
            'week': header.get('week', 0),
            'game_note': header.get('gameNote', ''),
            'time_valid': header.get('timeValid', False)
        }
    
    # Broadcasts
    broadcasts = summary.get('broadcasts', [])
    if broadcasts:
        game['broadcasts_full'] = broadcasts
    
    # Videos if available
    videos = summary.get('videos', [])
    if videos:
        game['videos'] = [{
            'id': v.get('id', ''),
            'headline': v.get('headline', ''),
            'description': v.get('description', ''),
            'duration': v.get('duration', 0),
            'thumbnail': v.get('thumbnail', ''),
            'links': v.get('links', {})
        } for v in videos[:10]]
    
    return game


# ============================================================================
# SLIM FUNCTIONS FOR NON-FEATURED GAMES
# ============================================================================

def slim_game(game, is_featured=False):
    """Strip unused fields for non-featured games. Featured games keep everything."""
    
    if is_featured:
        # For featured game, just clean up some redundant fields
        slim = game.copy()
        # Remove fields that are now in game_info
        if 'game_info' in slim:
            slim.pop('venue', None)
            slim.pop('weather', None)
            slim.pop('attendance', None)
        return slim
    
    # For non-featured games, slim down significantly
    def slim_team(team):
        return {
            'abbreviation': team.get('abbreviation', ''),
            'short_name': team.get('short_name', ''),
            'record': team.get('record', ''),
            'score': team.get('score', 0)
        }
    
    def slim_periods(periods):
        if not periods:
            return []
        return [{
            'number': p.get('number', 0),
            'away': p.get('away', {}),
            'home': p.get('home', {})
        } for p in periods]
    
    def slim_broadcasters(broadcasters):
        if not broadcasters:
            return []
        b = broadcasters[0] if broadcasters else {}
        return [{'name': b.get('name', '')}]
    
    status = game.get('status', '')
    
    slim = {
        'status': status,
        'start_time_pacific': game.get('start_time_pacific', ''),
        'away_team': slim_team(game.get('away_team', {})),
        'home_team': slim_team(game.get('home_team', {})),
        'scores': {
            'periods': slim_periods(game.get('scores', {}).get('periods', [])),
            'total': game.get('scores', {}).get('total', {})
        },
        'clock': game.get('clock', ''),
        'period': game.get('period', 0),
        'display_rank': game.get('display_rank', 0)
    }
    
    if status in ['Scheduled', 'In Progress']:
        venue = game.get('venue', {})
        slim['venue'] = {
            'name': venue.get('name', ''),
            'city': venue.get('city', ''),
            'state': venue.get('state', '')
        }
        slim['broadcasters'] = slim_broadcasters(game.get('broadcasters', []))
    
    return slim


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
    print("NFL ESPN API - Full Data Fetcher")
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
        if game['status'] == 'In Progress' and game.get('situation'):
            print(f"  {game['short_name']}: {game['situation'].get('down_distance_text', 'No situation')}")
    
    # Rank games
    all_games = rank_games(all_games)
    
    print(f"\nGames ranked:")
    for g in all_games:
        print(f"  {g['display_rank']}. {g['away_team']['abbreviation']} @ {g['home_team']['abbreviation']} ({g['status']})")
    
    # Sort by display_rank
    all_games.sort(key=lambda g: g.get('display_rank', 999))
    
    # Enrich #1 ranked game with FULL data
    if all_games:
        rank1_game = all_games[0]
        print(f"\nFetching FULL summary for: {rank1_game['away_team']['name']} @ {rank1_game['home_team']['name']}...")
        
        summary = fetch_game_summary(rank1_game['id'])
        
        if summary:
            enrich_featured_game_full(rank1_game, summary)
            print("  ✓ Loaded full team stats")
            print("  ✓ Loaded full player stats")
            print("  ✓ Loaded all drives and plays")
            print("  ✓ Loaded scoring plays")
            print("  ✓ Loaded game leaders")
            print("  ✓ Loaded win probability")
            print("  ✓ Loaded game info (venue, weather, officials)")
            if rank1_game.get('situation'):
                print(f"  Situation: {rank1_game['situation'].get('down_distance_text', 'N/A')}")
            if rank1_game.get('drives', {}).get('previous'):
                print(f"  Drives: {len(rank1_game['drives']['previous'])} completed")
        else:
            print("  Could not load summary, using scoreboard data")
    
    # Get season info
    season_info = {
        'year': scoreboard.get('season', {}).get('year', 0),
        'type': scoreboard.get('season', {}).get('type', 0),
        'type_name': 'Postseason' if scoreboard.get('season', {}).get('type') == 3 else 'Regular Season',
        'week': scoreboard.get('week', {}).get('number', 0)
    }
    
    # Build output - featured game gets full data, others get slimmed
    output_games = []
    for i, game in enumerate(all_games[:4]):
        is_featured = (i == 0)
        output_games.append(slim_game(game, is_featured=is_featured))
    
    # Save to JSON
    os.makedirs('docs', exist_ok=True)
    output = {
        'fetched_at': datetime.now().isoformat(),
        'season': season_info,
        'games': output_games
    }
    
    # Pretty version (full data is large, don't minify for debugging)
    with open('docs/nfl_games_full.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    # Compact version
    with open('docs/nfl_games.json', 'w') as f:
        json.dump(output, f, separators=(',', ':'))
    
    # Report sizes
    full_size = os.path.getsize('docs/nfl_games_full.json')
    compact_size = os.path.getsize('docs/nfl_games.json')
    print(f"\nSaved to docs/nfl_games_full.json ({full_size:,} bytes / {full_size/1024:.1f} KB)")
    print(f"Saved to docs/nfl_games.json ({compact_size:,} bytes / {compact_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
