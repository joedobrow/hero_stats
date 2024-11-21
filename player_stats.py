#!/usr/bin/env python3

import requests
import csv
import sys
import re
import math
import time

DAYS_IN_18_MONTHS = 720  # not 18 months lol

# Rate limit settings
MAX_RETRIES = 5
RATE_LIMIT_SLEEP = 61 
REQUEST_DELAY = 1.1 

def make_api_request(url):
    retries = 0
    while retries < MAX_RETRIES:
        response = requests.get(url)
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            print(f"Rate limit hit. Sleeping for {RATE_LIMIT_SLEEP} seconds before retrying.")
            time.sleep(RATE_LIMIT_SLEEP)
            retries += 1
        else:
            print(f"Failed to fetch data from {url}. Status code: {response.status_code}")
            return None
    print(f"Max retries exceeded for {url}")
    return None

def fetch_player_wl(account_id, date_range):
    url = f'https://api.opendota.com/api/players/{account_id}/wl?date={date_range}'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    if response and response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch win/loss data for account ID {account_id}.")
        return None

def fetch_player_heroes(account_id, date_range):
    url = f'https://api.opendota.com/api/players/{account_id}/heroes?date={date_range}'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    if response and response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch hero data for account ID {account_id}.")
        return None

def fetch_player_counts(account_id, date_range):
    url = f'https://api.opendota.com/api/players/{account_id}/counts?date={date_range}'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    if response and response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch counts data for account ID {account_id}.")
        return None

def calculate_discomfort_factor(hero_stats):
    comfortable_games = comfortable_wins = 0
    uncomfortable_games = uncomfortable_wins = 0

    for hero in hero_stats:
        games = hero['games']
        wins = hero['win']

        if games >= 10:
            comfortable_games += games
            comfortable_wins += wins
        else:
            uncomfortable_games += games
            uncomfortable_wins += wins

    comfortable_win_rate = (comfortable_wins / comfortable_games * 100) if comfortable_games else 0
    uncomfortable_win_rate = (uncomfortable_wins / uncomfortable_games * 100) if uncomfortable_games else 0

    if comfortable_win_rate > 0:
        discomfort_factor = (uncomfortable_win_rate / comfortable_win_rate) * 100
    else:
        discomfort_factor = 50  # just set to 50 if no comfortable games

    return discomfort_factor

def calculate_versatility_factor(hero_stats):
    total_games = sum(hero['games'] for hero in hero_stats)
    if total_games == 0:
        return 0  # set to zero if no games played

    # Calculate the proportion of games played on each hero
    p_list = [hero['games'] / total_games for hero in hero_stats if hero['games'] > 0]

    N = len(p_list)
    if N <= 1:
        return 0  # Versatility is zero if only one hero is played

    entropy = -sum(p * math.log(p) for p in p_list)

    max_entropy = math.log(N)

    versatility_factor = entropy / max_entropy if max_entropy > 0 else 0

    versatility_factor *= 100

    return versatility_factor

def calculate_role_diversity(counts_data):
    if 'lane_role' not in counts_data:
        print("Lane role data not available.")
        return 0

    lane_role_counts = counts_data['lane_role']

    def extract_count(value):
        if isinstance(value, dict):
            return value.get('games', 0)
        elif isinstance(value, (int, float)):
            return value
        else:
            return 0

    # Exclude lane_role '0' (unknown lane roles)
    total_games = sum(
        extract_count(count)
        for lane_role, count in lane_role_counts.items()
        if lane_role != '0'
    )

    if total_games == 0:
        return 0

    # Map lane roles to positions
    role_counts = {
        'Carry': 0,    # Position 1
        'Mid': 0,      # Position 2
        'Offlane': 0,  # Position 3
        'Support4': 0, # Position 4
        'Support5': 0  # Position 5
    }

    for lane_role, count in lane_role_counts.items():
        if lane_role == '0':
            continue

        lane_role_int = int(lane_role)
        count = extract_count(count)
        if count == 0:
            continue

        if lane_role_int == 1:  # Safe Lane
            # Assume half are Carry, half are Support5
            role_counts['Carry'] += count * 0.5
            role_counts['Support5'] += count * 0.5
        elif lane_role_int == 2:  # Mid Lane
            role_counts['Mid'] += count
        elif lane_role_int == 3:  # Off Lane
            # Assume half are Offlane, half are Support4
            role_counts['Offlane'] += count * 0.5
            role_counts['Support4'] += count * 0.5
        elif lane_role_int == 4:  # Jungle
            role_counts['Support4'] += count
        elif lane_role_int == 5:  # Roaming
            role_counts['Support4'] += count

    total_games = sum(role_counts.values())
    if total_games == 0:
        return 0

    p_list = [count / total_games for count in role_counts.values() if count > 0]
    N = len(p_list)
    if N <= 1:
        return 0

    entropy = -sum(p * math.log(p) for p in p_list)

    max_entropy = math.log(N)

    role_diversity_factor = entropy / max_entropy if max_entropy > 0 else 0

    role_diversity_factor *= 100

    return role_diversity_factor

def calculate_overall_winrate(wl_data):
    wins = wl_data.get('win', 0)
    losses = wl_data.get('lose', 0)
    total_games = wins + losses
    if total_games == 0:
        return 0
    winrate = (wins / total_games) * 100
    return winrate

def calculate_winrate_excluding_top_20(hero_stats):
    # Sort heroes by games played in descending order
    sorted_heroes = sorted(hero_stats, key=lambda x: x['games'], reverse=True)
    # Get the top 20 most played heroes
    top_20_heroes = [hero['hero_id'] for hero in sorted_heroes[:20]]
    # Exclude top 20 heroes
    remaining_heroes = [hero for hero in hero_stats if hero['hero_id'] not in top_20_heroes]
    total_games = sum(hero['games'] for hero in remaining_heroes)
    total_wins = sum(hero['win'] for hero in remaining_heroes)
    if total_games == 0:
        return 0
    winrate = (total_wins / total_games) * 100
    return winrate

def extract_player_id(dotabuff_url):
    match = re.search(r'/players/(\d+)', dotabuff_url)
    if match:
        return match.group(1)
    else:
        print(f"Error: Could not extract player ID from URL '{dotabuff_url}'. Please ensure it is a valid Dotabuff player URL.")
        return None

def process_players(input_csv, output_csv):
    with open(input_csv, 'r', newline='', encoding='utf-8') as csv_in, \
         open(output_csv, 'w', newline='', encoding='utf-8') as csv_out:

        reader = csv.DictReader(csv_in)
        fieldnames = [
            'name',
            'games-played',
            'overall-winrate',
            'winrate-excl-top20',
            'discomfort-factor',
            'versatility-factor',
            'role-diversity-factor'
        ]
        writer = csv.DictWriter(csv_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            name = row['name']
            dotabuff_url = row['dotabuff']

            player_id = extract_player_id(dotabuff_url)
            if player_id is None:
                # If player ID couldn't be extracted, write 'N/A' and continue
                writer.writerow({
                    'name': name,
                    'games-played': 'N/A',
                    'overall-winrate': 'N/A',
                    'winrate-excl-top20': 'N/A',
                    'discomfort-factor': 'N/A',
                    'versatility-factor': 'N/A',
                    'role-diversity-factor': 'N/A'
                })
                continue

            print(f"Processing player: {name} (ID: {player_id})")

            hero_stats = fetch_player_heroes(player_id, DAYS_IN_18_MONTHS)
            counts_data = fetch_player_counts(player_id, DAYS_IN_18_MONTHS)
            wl_data = fetch_player_wl(player_id, DAYS_IN_18_MONTHS)

            if hero_stats is not None and counts_data is not None and wl_data is not None:
                total_games_played = sum(hero['games'] for hero in hero_stats)

                overall_winrate = calculate_overall_winrate(wl_data)
                winrate_excl_top20 = calculate_winrate_excluding_top_20(hero_stats)
                discomfort_factor = calculate_discomfort_factor(hero_stats)
                versatility_factor = calculate_versatility_factor(hero_stats)
                role_diversity_factor = calculate_role_diversity(counts_data)
                writer.writerow({
                    'name': name,
                    'games-played': total_games_played,
                    'overall-winrate': f"{overall_winrate:.2f}",
                    'winrate-excl-top20': f"{winrate_excl_top20:.2f}",
                    'discomfort-factor': f"{discomfort_factor:.2f}",
                    'versatility-factor': f"{versatility_factor:.2f}",
                    'role-diversity-factor': f"{role_diversity_factor:.2f}"
                })
            else:
                # If API call failed, write 'N/A' or handle as needed
                writer.writerow({
                    'name': name,
                    'games-played': 'N/A',
                    'overall-winrate': 'N/A',
                    'winrate-excl-top20': 'N/A',
                    'discomfort-factor': 'N/A',
                    'versatility-factor': 'N/A',
                    'role-diversity-factor': 'N/A'
                })

    print(f"Results written to {output_csv}")

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python dota_scrape.py input.csv [output.csv]")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) == 3 else 'output.csv'

    process_players(input_csv, output_csv)

if __name__ == '__main__':
    main()

