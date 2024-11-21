#!/usr/bin/env python3

import requests
import csv
import sys
import re
import math
import time
import datetime
import os
import json
import argparse
import shutil

# Time frames in days
TIME_FRAMES = {
    'all_time': 0,  # 0 indicates all time
    'last_2_years': 730,
    'last_9_months': 274
}

# Rate limit settings
MAX_RETRIES = 5
RATE_LIMIT_SLEEP = 61
REQUEST_DELAY = 1.1

CACHE_DIR = 'cache'  # Directory to store cached data

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

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

def fetch_player_data(account_id, date_range, refresh=False):
    """
    Fetches player data, including win/loss, heroes, counts, and MMR.
    Checks if data is cached; if not, fetches from API and caches it.
    Returns a dictionary with 'wl', 'heroes', 'counts', and 'mmr' keys.
    """
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, f'player_{account_id}_{date_range}.json')

    if not refresh and os.path.exists(cache_file):
        print(f"Loading cached data for player {account_id}, date range {date_range}")
        with open(cache_file, 'r', encoding='utf-8') as f:
            player_data = json.load(f)
    else:
        print(f"Fetching data from API for player {account_id}, date range {date_range}")
        player_data = {}

        wl_data = fetch_player_wl(account_id, date_range)
        hero_stats = fetch_player_heroes(account_id, date_range)
        counts_data = fetch_player_counts(account_id, date_range)
        mmr = fetch_player_mmr(account_id)  # Fetch MMR

        if wl_data is None or hero_stats is None or counts_data is None or mmr is None:
            print(f"Failed to fetch all data for player {account_id}.")
            return None  # Return None if any API call fails

        player_data['wl'] = wl_data
        player_data['heroes'] = hero_stats
        player_data['counts'] = counts_data
        player_data['mmr'] = mmr

        # Save to cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(player_data, f)
        print(f"Cached data for player {account_id}, date range {date_range}")

    return player_data

def fetch_player_wl(account_id, date_range):
    if date_range == 0:
        url = f'https://api.opendota.com/api/players/{account_id}/wl'
    else:
        url = f'https://api.opendota.com/api/players/{account_id}/wl?date={date_range}'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    if response and response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch win/loss data for account ID {account_id}.")
        return None

def fetch_player_heroes(account_id, date_range):
    if date_range == 0:
        url = f'https://api.opendota.com/api/players/{account_id}/heroes'
    else:
        url = f'https://api.opendota.com/api/players/{account_id}/heroes?date={date_range}'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    if response and response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch hero data for account ID {account_id}.")
        return None

def fetch_player_counts(account_id, date_range):
    if date_range == 0:
        url = f'https://api.opendota.com/api/players/{account_id}/counts'
    else:
        url = f'https://api.opendota.com/api/players/{account_id}/counts?date={date_range}'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    if response and response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch counts data for account ID {account_id}.")
        return None

def fetch_player_mmr(account_id):
    url = f'https://api.opendota.com/api/players/{account_id}/ratings'
    time.sleep(REQUEST_DELAY)
    response = make_api_request(url)
    
    if response and response.status_code == 200:
        data = response.json()
        if data:
            # Filter out objects with a `competitive_rank` value, sort by `time`, and get the latest one
            recent_rank = next(
                (item['competitive_rank'] for item in sorted(data, key=lambda x: x['time'], reverse=True) 
                 if item.get('competitive_rank')), 
                None
            )
            if recent_rank:
                return recent_rank
            else:
                print(f"Competitive rank not available for account ID {account_id}.")
                return 'N/A'
        else:
            print(f"No data found for account ID {account_id}.")
            return 'N/A'
    else:
        print(f"Failed to fetch MMR data for account ID {account_id}.")
        return None

def extract_count(value):
    if isinstance(value, dict):
        return value.get('games', 0)
    elif isinstance(value, (int, float)):
        return value
    else:
        return 0

def calculate_discomfort_factor(hero_stats, total_games_played):
    threshold = total_games_played / 20 if total_games_played > 0 else 0
    comfortable_games = comfortable_wins = 0
    uncomfortable_games = uncomfortable_wins = 0

    for hero in hero_stats:
        games = hero['games']
        wins = hero['win']

        if games >= threshold:
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
        discomfort_factor = 50  # Arbitrary value if no comfortable games

    return discomfort_factor

def calculate_versatility_factor(hero_stats):
    total_games = sum(hero['games'] for hero in hero_stats)
    if total_games == 0:
        return 0  # Zero if no games played

    # Proportion of games played on each hero
    p_list = [hero['games'] / total_games for hero in hero_stats if hero['games'] > 0]

    N = len(p_list)
    if N <= 1:
        return 0  # Zero if only one hero is played

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
        return 'N/A'  # Set to 'N/A' if no games played outside top 20 heroes
    winrate = (total_wins / total_games) * 100
    return winrate

def calculate_suggested_bid(data):
    """
    Calculate the Suggested Relative Bid using the formula:
    (MMR / 50) * ((%winrate + 50) / 100)^2 * ((%winrate_excluding_top_20 + 50) / 100)^2 *
    (discomfort_factor / 100)^3 * (versatility_factor / 100)^3 * (role_diversity_factor / 100)
    """
    try:
        mmr = data['mmr']
        if mmr == 'N/A':
            return 'N/A'
        mmr = float(mmr)
        overall_winrate = float(data['overall_winrate'])
        discomfort_factor = float(data['discomfort_factor'])
        versatility_factor = float(data['versatility_factor'])
        role_diversity_factor = float(data['role_diversity_factor'])

        winrate_excl_top20 = data['winrate_excl_top20']
        if winrate_excl_top20 == 'N/A':
            # Exclude from calculation
            winrate_excl_top20_factor = 1
        else:
            winrate_excl_top20 = float(winrate_excl_top20)
            winrate_excl_top20_factor = ((winrate_excl_top20 + 50) / 100) ** 2

        bid = (mmr / 50) * (((overall_winrate + 50) / 100) ** 2) * winrate_excl_top20_factor \
            * ((discomfort_factor / 100) ** 3) * ((versatility_factor / 100) ** 3) \
            * (role_diversity_factor / 100)

        bid = round(bid, 2)
        return bid
    except (ValueError, ZeroDivisionError):
        return 'N/A'

def extract_player_id(dotabuff_url):
    match = re.search(r'/players/(\d+)', dotabuff_url)
    if match:
        return match.group(1)
    else:
        print(f"Error: Could not extract player ID from URL '{dotabuff_url}'. Please ensure it is a valid Dotabuff player URL.")
        return None

def process_players(input_csv, output_html, refresh=False):
    with open(input_csv, 'r', newline='', encoding='utf-8') as csv_in:

        reader = csv.DictReader(csv_in)
        players_data = {}

        for row in reader:
            name = row['name']
            dotabuff_url = row['dotabuff']

            player_id = extract_player_id(dotabuff_url)
            if player_id is None:
                # If player ID couldn't be extracted, write 'N/A' and continue
                player_info = {
                    'name': name,
                    'data': {}
                }
                for time_frame in TIME_FRAMES.keys():
                    player_info['data'][time_frame] = {
                        'games_played': 'N/A',
                        'mmr': 'N/A',
                        'overall_winrate': 'N/A',
                        'winrate_excl_top20': 'N/A',
                        'discomfort_factor': 'N/A',
                        'versatility_factor': 'N/A',
                        'role_diversity_factor': 'N/A',
                        'suggested_bid': 'N/A'
                    }
                players_data[name] = player_info
                continue

            print(f"Processing player: {name} (ID: {player_id})")

            player_info = {
                'name': name,
                'data': {}
            }

            for time_frame_name, date_range in TIME_FRAMES.items():
                print(f"  Time frame: {time_frame_name}")
                player_data = fetch_player_data(player_id, date_range, refresh=refresh)
                if player_data is not None:
                    wl_data = player_data['wl']
                    hero_stats = player_data['heroes']
                    counts_data = player_data['counts']
                    mmr = player_data['mmr']

                    total_games_played = sum(hero['games'] for hero in hero_stats)

                    overall_winrate = calculate_overall_winrate(wl_data)
                    winrate_excl_top20 = calculate_winrate_excluding_top_20(hero_stats)
                    discomfort_factor = calculate_discomfort_factor(hero_stats, total_games_played)
                    versatility_factor = calculate_versatility_factor(hero_stats)
                    role_diversity_factor = calculate_role_diversity(counts_data)

                    data_dict = {
                        'games_played': total_games_played,
                        'mmr': mmr,
                        'overall_winrate': f"{overall_winrate:.2f}",
                        'winrate_excl_top20': f"{winrate_excl_top20:.2f}" if winrate_excl_top20 != 'N/A' else 'N/A',
                        'discomfort_factor': f"{discomfort_factor:.2f}",
                        'versatility_factor': f"{versatility_factor:.2f}",
                        'role_diversity_factor': f"{role_diversity_factor:.2f}",
                    }

                    suggested_bid = calculate_suggested_bid(data_dict)
                    data_dict['suggested_bid'] = suggested_bid

                    player_info['data'][time_frame_name] = data_dict
                else:
                    player_info['data'][time_frame_name] = {
                        'games_played': 'N/A',
                        'mmr': 'N/A',
                        'overall_winrate': 'N/A',
                        'winrate_excl_top20': 'N/A',
                        'discomfort_factor': 'N/A',
                        'versatility_factor': 'N/A',
                        'role_diversity_factor': 'N/A',
                        'suggested_bid': 'N/A'
                    }
            players_data[name] = player_info

    generate_html_report(players_data, output_html)
    print(f"HTML report generated at {output_html}")

def generate_html_report(players_data, output_html):
    # Collect metrics across all players and time frames for normalization
    metrics = ['overall_winrate', 'winrate_excl_top20', 'discomfort_factor', 'versatility_factor', 'role_diversity_factor', 'suggested_bid']
    metric_values = {tf: {metric: [] for metric in metrics} for tf in TIME_FRAMES.keys()}

    for player_info in players_data.values():
        for time_frame, data in player_info['data'].items():
            for metric in metrics:
                value = data[metric]
                if value != 'N/A':
                    metric_values[time_frame][metric].append(float(value))

    metric_min_max = {}
    for time_frame in TIME_FRAMES.keys():
        metric_min_max[time_frame] = {}
        for metric in metrics:
            values = metric_values[time_frame][metric]
            metric_min_max[time_frame][metric] = (min(values) if values else 0, max(values) if values else 100)

    # Generate HTML
    with open(output_html, 'w', encoding='utf-8') as outfile:
        outfile.write('<html><head><title>Dota 2 Player Metrics Report</title>\n')
        outfile.write('<style>\n')
        outfile.write('body { font-family: Arial, sans-serif; background-color: #1e1e1e; color: #f0f0f0; }\n')
        outfile.write('table { border-collapse: collapse; width: 80%; margin: 20px auto; }\n')
        outfile.write('th, td { border: 1px solid #555; padding: 8px; text-align: center; }\n')
        outfile.write('th { background-color: #333; color: #f0f0f0; cursor: pointer; position: relative; }\n')
        outfile.write('tr:nth-child(even) { background-color: #2e2e2e; }\n')
        outfile.write('tr:nth-child(odd) { background-color: #262626; }\n')
        outfile.write('.hidden { display: none; }\n')
        outfile.write('.tooltip {\n')
        outfile.write('  position: relative;\n')
        outfile.write('  display: inline-block;\n')
        outfile.write('}\n')
        outfile.write('.tooltip .tooltiptext {\n')
        outfile.write('  visibility: hidden;\n')
        outfile.write('  width: 200px;\n')
        outfile.write('  background-color: #555;\n')
        outfile.write('  color: #fff;\n')
        outfile.write('  text-align: center;\n')
        outfile.write('  border-radius: 6px;\n')
        outfile.write('  padding: 5px;\n')
        outfile.write('  position: absolute;\n')
        outfile.write('  z-index: 1;\n')
        outfile.write('  bottom: 125%;\n')
        outfile.write('  left: 50%;\n')
        outfile.write('  margin-left: -100px;\n')
        outfile.write('  opacity: 0;\n')
        outfile.write('  transition: opacity 0.3s;\n')
        outfile.write('}\n')
        outfile.write('.tooltip:hover .tooltiptext {\n')
        outfile.write('  visibility: visible;\n')
        outfile.write('  opacity: 1;\n')
        outfile.write('}\n')
        outfile.write('</style>\n')
        outfile.write('<script>\n')
        outfile.write('function sortTable(table, col, reverse) {\n')
        outfile.write('    let tb = table.tBodies[0],\n')
        outfile.write('        tr = Array.prototype.slice.call(tb.rows, 0),\n')
        outfile.write('        i;\n')
        outfile.write('    reverse = -((+reverse) || -1);\n')
        outfile.write('    tr = tr.sort(function (a, b) {\n')
        outfile.write('        let aText = a.cells[col].textContent.trim(),\n')
        outfile.write('            bText = b.cells[col].textContent.trim();\n')
        outfile.write('        let aNum = parseFloat(aText) || 0;\n')
        outfile.write('        let bNum = parseFloat(bText) || 0;\n')
        outfile.write('        return reverse * ((aNum > bNum) - (bNum > aNum));\n')
        outfile.write('    });\n')
        outfile.write('    for(i = 0; i < tr.length; ++i) tb.appendChild(tr[i]);\n')
        outfile.write('}\n')
        outfile.write('function makeSortable(table) {\n')
        outfile.write('    let th = table.tHead.rows[0].cells;\n')
        outfile.write('    for(let i = 0; i < th.length; i++) {\n')
        outfile.write('        (function(i){\n')
        outfile.write('            let dir = 1;\n')
        outfile.write('            th[i].addEventListener("click", function() {\n')
        outfile.write('                sortTable(table, i, (dir = 1 - dir));\n')
        outfile.write('            });\n')
        outfile.write('        }(i));\n')
        outfile.write('    }\n')
        outfile.write('}\n')
        outfile.write('function showTimeFrame(timeFrame) {\n')
        outfile.write('    let tables = document.getElementsByClassName("data-table");\n')
        outfile.write('    for(let i = 0; i < tables.length; i++) {\n')
        outfile.write('        tables[i].classList.add("hidden");\n')
        outfile.write('    }\n')
        outfile.write('    document.getElementById("table_" + timeFrame).classList.remove("hidden");\n')
        outfile.write('}\n')
        outfile.write('window.onload = function() {\n')
        outfile.write('    let timeFrameSelect = document.getElementById("timeFrameSelect");\n')
        outfile.write('    timeFrameSelect.addEventListener("change", function() {\n')
        outfile.write('        showTimeFrame(this.value);\n')
        outfile.write('    });\n')
        outfile.write('    let tables = document.getElementsByClassName("data-table");\n')
        outfile.write('    for(let i = 0; i < tables.length; i++) {\n')
        outfile.write('        makeSortable(tables[i]);\n')
        outfile.write('    }\n')
        outfile.write('    showTimeFrame(timeFrameSelect.value);\n')
        outfile.write('};\n')
        outfile.write('</script>\n')
        outfile.write('</head><body>\n')
        outfile.write('<h1 style="text-align:center;">Dota 2 Player Metrics Report</h1>\n')

        # Time frame selection
        outfile.write('<div style="text-align:center; margin-bottom:20px;">\n')
        outfile.write('<label for="timeFrameSelect">Select Time Frame: </label>\n')
        outfile.write('<select id="timeFrameSelect">\n')
        outfile.write('<option value="all_time">All Time</option>\n')
        outfile.write('<option value="last_2_years">Last 2 Years</option>\n')
        outfile.write('<option value="last_9_months">Last 9 Months</option>\n')
        outfile.write('</select>\n')
        outfile.write('</div>\n')

        # Generate tables for each time frame
        for time_frame in TIME_FRAMES.keys():
            # Sort players by suggested bid for display purposes
            players_data_sorted = sorted(players_data.values(), key=lambda x: float(x['data'][time_frame]['suggested_bid']) if x['data'][time_frame]['suggested_bid'] != 'N/A' else 0, reverse=True)

            outfile.write(f'<table id="table_{time_frame}" class="data-table">\n')
            outfile.write('<thead>\n')
            outfile.write('<tr>')
            outfile.write('<th>Player Name</th>')
            outfile.write('<th>Games Played</th>')
            outfile.write('<th>MMR</th>')
            outfile.write('<th>Overall Winrate (%)</th>')
            outfile.write('<th>Winrate Excl. Top 20 Heroes (%)</th>')
            outfile.write('<th class="tooltip">Discomfort Factor<span class="tooltiptext">Comparison of win rates between less and more played heroes</span></th>')
            outfile.write('<th class="tooltip">Versatility Factor<span class="tooltiptext">Measure of how many different heroes a player can play effectively</span></th>')
            outfile.write('<th class="tooltip">Role Diversity Factor<span class="tooltiptext">Measure of how many different roles a player plays</span></th>')
            outfile.write('<th class="tooltip">Suggested Relative Bid<span class="tooltiptext">(MMR / 50) * ((%Winrate + 50)/100)^2 * ((%Winrate Excl. Top 20 + 50)/100)^2 * (Discomfort Factor / 100)^3 * (Versatility Factor / 100)^3 * (Role Diversity Factor / 100)</span></th>')
            outfile.write('</tr>\n')
            outfile.write('</thead>\n')
            outfile.write('<tbody>\n')

            for player_info in players_data_sorted:
                data = player_info['data'][time_frame]
                outfile.write('<tr>')
                outfile.write(f"<td>{player_info['name']}</td>")
                outfile.write(f"<td>{data['games_played']}</td>")
                outfile.write(f"<td>{data['mmr']}</td>")
                for metric in metrics:
                    value = data[metric]
                    if metric == 'suggested_bid':
                        # Format as currency
                        if value != 'N/A':
                            value = f"${value}"
                    if value != 'N/A':
                        val_float = float(value.strip('$')) if isinstance(value, str) else float(value)
                        min_val, max_val = metric_min_max[time_frame][metric]
                        if max_val > min_val:
                            normalized = (val_float - min_val) / (max_val - min_val)
                        else:
                            normalized = 0.5
                        hue = 30 + 90 * normalized  # From red to green
                        saturation = 50 + 10 * normalized
                        lightness = 25 + 10 * normalized
                        color = f'hsl({hue:.0f}, {saturation:.0f}%, {lightness:.0f}%)'
                        outfile.write(f'<td style="background-color:{color};">{value}</td>')
                    else:
                        outfile.write('<td>N/A</td>')
                outfile.write('</tr>\n')

            outfile.write('</tbody>\n')
            outfile.write('</table>\n')

        outfile.write('</body></html>')

def main():
    parser = argparse.ArgumentParser(description='Generate Dota 2 Player Metrics Report')
    parser.add_argument('input_csv', help='Input CSV file with player data')
    parser.add_argument('output_html', nargs='?', default='report.html', help='Output HTML file name')
    parser.add_argument('--refresh', action='store_true', help='Force refresh of cached data')

    args = parser.parse_args()

    if args.refresh:
        # Delete the cache directory or specific cache files
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            print("Cache cleared.")

    process_players(args.input_csv, args.output_html, refresh=args.refresh)

if __name__ == '__main__':
    main()

