import requests
import csv
import os
import time
import shutil
import argparse
import re
import json
from datetime import datetime, timedelta
import math  # Import math module for entropy calculation

CACHE_DIR = 'cache'
REQUEST_DELAY = 1  # seconds
API_KEY = None  # Will be loaded from opendota.properties

TIME_FRAMES = {
    'all_time': None,
    'last_2_years': (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d'),
    'last_9_months': (datetime.now() - timedelta(days=270)).strftime('%Y-%m-%d'),
}

def load_api_key():
    global API_KEY
    properties_file = 'opendota.properties'
    if os.path.exists(properties_file):
        with open(properties_file, 'r') as f:
            for line in f:
                if line.startswith('api_key='):
                    API_KEY = line.strip().split('=', 1)[1]
                    print("API key loaded from opendota.properties")
                    break
    else:
        print("opendota.properties file not found. Continuing without API key.")

def make_api_request(url, params=None):
    # Append the API key to the params if it's available
    if API_KEY:
        if params is None:
            params = {}
        params['api_key'] = API_KEY
    try:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            print("Rate limit exceeded. Sleeping for 60 seconds.")
            time.sleep(60)
            return make_api_request(url, params)
        else:
            return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def fetch_player_data(account_id, date_range, refresh=False):
    cache_filename = os.path.join(CACHE_DIR, f"{account_id}_{date_range if date_range else 'all'}.json")

    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    if not refresh and os.path.exists(cache_filename):
        with open(cache_filename, 'r', encoding='utf-8') as cache_file:
            print(f"Using cached data for account ID {account_id} and date range {date_range if date_range else 'all'}")
            return json.load(cache_file)

    params = {}
    if date_range:
        days = (datetime.now() - datetime.strptime(date_range, '%Y-%m-%d')).days
        params['date'] = days

    # Fetch win/loss data
    wl_url = f'https://api.opendota.com/api/players/{account_id}/wl'
    time.sleep(REQUEST_DELAY)
    wl_response = make_api_request(wl_url, params)
    if not wl_response or wl_response.status_code != 200:
        print(f"Failed to fetch win/loss data for account ID {account_id}.")
        return None
    wl_data = wl_response.json()

    # Fetch hero stats
    heroes_url = f'https://api.opendota.com/api/players/{account_id}/heroes'
    time.sleep(REQUEST_DELAY)
    heroes_response = make_api_request(heroes_url, params)
    if not heroes_response or heroes_response.status_code != 200:
        print(f"Failed to fetch hero stats for account ID {account_id}.")
        return None
    heroes_data = heroes_response.json()

    # Fetch role counts
    counts_url = f'https://api.opendota.com/api/players/{account_id}/counts'
    time.sleep(REQUEST_DELAY)
    counts_response = make_api_request(counts_url, params)
    if not counts_response or counts_response.status_code != 200:
        print(f"Failed to fetch counts data for account ID {account_id}.")
        return None
    counts_data = counts_response.json()

    player_data = {
        'wl': wl_data,
        'heroes': heroes_data,
        'counts': counts_data,
    }

    with open(cache_filename, 'w', encoding='utf-8') as cache_file:
        json.dump(player_data, cache_file)

    return player_data

def calculate_overall_winrate(wl_data):
    wins = wl_data.get('win', 0)
    losses = wl_data.get('lose', 0)
    total_games = wins + losses
    if total_games == 0:
        return 0.0
    return (wins / total_games) * 100

def calculate_winrate_excluding_top_20(hero_stats):
    top_20_heroes = hero_stats[:20]
    games_in_top_20 = sum(hero['games'] for hero in top_20_heroes)
    wins_in_top_20 = sum(hero['win'] for hero in top_20_heroes)

    total_games = sum(hero['games'] for hero in hero_stats)
    total_wins = sum(hero['win'] for hero in hero_stats)

    games_excl_top_20 = total_games - games_in_top_20
    wins_excl_top_20 = total_wins - wins_in_top_20

    if games_excl_top_20 == 0:
        return 'N/A'  # Cannot calculate winrate if no games outside top 20 heroes
    else:
        return (wins_excl_top_20 / games_excl_top_20) * 100

def calculate_discomfort_factor(hero_stats, time_frame_name):
    # Get the threshold for the time frame
    if time_frame_name == 'all_time':
        threshold = 40
    elif time_frame_name == 'last_2_years':
        threshold = 24
    elif time_frame_name == 'last_9_months':
        threshold = 9
    else:
        threshold = 0  # Should not occur

    # Separate heroes into comfy and uncomfy
    comfy_heroes = [hero for hero in hero_stats if hero['games'] >= threshold]
    uncomfy_heroes = [hero for hero in hero_stats if 0 < hero['games'] < threshold]

    # Calculate comfy winrate
    comfy_games = sum(hero['games'] for hero in comfy_heroes)
    comfy_wins = sum(hero['win'] for hero in comfy_heroes)
    comfy_winrate = (comfy_wins / comfy_games) if comfy_games > 0 else None

    # Calculate uncomfy winrate
    uncomfy_games = sum(hero['games'] for hero in uncomfy_heroes)
    uncomfy_wins = sum(hero['win'] for hero in uncomfy_heroes)
    uncomfy_winrate = (uncomfy_wins / uncomfy_games) if uncomfy_games > 0 else None

    # Handle cases where we cannot compute the discomfort factor
    if comfy_winrate is None or comfy_winrate == 0 or uncomfy_winrate is None:
        discomfort_factor = 0
    else:
        discomfort_factor = (uncomfy_winrate / comfy_winrate) * 100

    # If the discomfort factor is 0, set it to 50
    if discomfort_factor == 0:
        discomfort_factor = 50

    discomfort_factor = round(discomfort_factor, 2)

    return discomfort_factor

def calculate_versatility_factor(hero_stats):
    num_heroes_played = len([hero for hero in hero_stats if hero['games'] > 0])
    versatility_factor = (num_heroes_played / 123) * 100  # Assuming 123 heroes in Dota 2
    return versatility_factor

def calculate_role_diversity(counts_data):
    # Roles are represented by integers 1 to 5 in OpenDota API
    role_counts = counts_data.get('lane_role', {})
    total_games = 0
    role_game_counts = {}
    for role_id in ['1', '2', '3', '4', '5']:
        role_data = role_counts.get(role_id, {})
        games_played = role_data.get('games', 0) if isinstance(role_data, dict) else role_data if isinstance(role_data, int) else 0
        role_game_counts[role_id] = games_played
        total_games += games_played

    if total_games == 0:
        return 0.0

    entropy = 0.0
    for games_played in role_game_counts.values():
        if games_played > 0:
            p_i = games_played / total_games
            entropy -= p_i * math.log2(p_i)

    max_entropy = math.log2(5)  # There are 5 roles

    # Normalize entropy to a percentage
    role_diversity_factor = (entropy / max_entropy) * 100

    return round(role_diversity_factor, 2)

def calculate_aggregated_value(data):
    try:
        overall_winrate = float(data['overall_winrate'])
        winrate_excl_top20 = float(data['winrate_excl_top20']) if data['winrate_excl_top20'] != 'N/A' else 0
        discomfort_factor = float(data['discomfort_factor'])
        versatility_factor = float(data['versatility_factor'])
        role_diversity_factor = float(data['role_diversity_factor'])

        aggregated_value = (
            overall_winrate +
            winrate_excl_top20 * 2 +
            discomfort_factor * 2 +
            versatility_factor * 2 +
            role_diversity_factor
        ) / 8

        aggregated_value = round(aggregated_value, 2)
        return aggregated_value
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
                    'dotabuff_url': dotabuff_url,
                    'data': {}
                }
                for time_frame in TIME_FRAMES.keys():
                    player_info['data'][time_frame] = {
                        'games_played': 'N/A',
                        'overall_winrate': 'N/A',
                        'winrate_excl_top20': 'N/A',
                        'discomfort_factor': 'N/A',
                        'versatility_factor': 'N/A',
                        'role_diversity_factor': 'N/A',
                        'aggregated_value': 'N/A'
                    }
                players_data[name] = player_info
                continue

            print(f"Processing player: {name} (ID: {player_id})")

            player_info = {
                'name': name,
                'dotabuff_url': dotabuff_url,
                'data': {}
            }

            for time_frame_name, date_range in TIME_FRAMES.items():
                print(f"  Time frame: {time_frame_name}")
                player_data = fetch_player_data(player_id, date_range, refresh=refresh)
                if player_data is not None:
                    wl_data = player_data['wl']
                    hero_stats = player_data['heroes']
                    counts_data = player_data['counts']

                    total_games_played = sum(hero['games'] for hero in hero_stats)

                    overall_winrate = calculate_overall_winrate(wl_data)
                    winrate_excl_top20 = calculate_winrate_excluding_top_20(hero_stats)
                    discomfort_factor = calculate_discomfort_factor(hero_stats, time_frame_name)
                    versatility_factor = calculate_versatility_factor(hero_stats)
                    role_diversity_factor = calculate_role_diversity(counts_data)

                    data_dict = {
                        'games_played': total_games_played,
                        'overall_winrate': f"{overall_winrate:.2f}",
                        'winrate_excl_top20': f"{winrate_excl_top20:.2f}" if winrate_excl_top20 != 'N/A' else 'N/A',
                        'discomfort_factor': f"{discomfort_factor:.2f}",
                        'versatility_factor': f"{versatility_factor:.2f}",
                        'role_diversity_factor': f"{role_diversity_factor:.2f}",
                    }

                    aggregated_value = calculate_aggregated_value(data_dict)
                    data_dict['aggregated_value'] = aggregated_value

                    player_info['data'][time_frame_name] = data_dict
                else:
                    player_info['data'][time_frame_name] = {
                        'games_played': 'N/A',
                        'overall_winrate': 'N/A',
                        'winrate_excl_top20': 'N/A',
                        'discomfort_factor': 'N/A',
                        'versatility_factor': 'N/A',
                        'role_diversity_factor': 'N/A',
                        'aggregated_value': 'N/A'
                    }
            players_data[name] = player_info

    generate_html_report(players_data, output_html)
    print(f"HTML report generated at {output_html}")

def generate_html_report(players_data, output_html):
    # Collect metrics across all players and time frames for normalization
    metrics = ['games_played', 'overall_winrate', 'winrate_excl_top20', 'discomfort_factor', 'versatility_factor', 'role_diversity_factor', 'aggregated_value']
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
        outfile.write('<html><head><title>PST-SUN Player Report</title>\n')  # Changed title here
        outfile.write('<style>\n')
        outfile.write('body { font-family: Arial, sans-serif; background-color: #1e1e1e; color: #f0f0f0; }\n')
        outfile.write('table { border-collapse: collapse; width: 80%; margin: 20px auto; }\n')
        outfile.write('th, td { border: 1px solid #555; padding: 8px; text-align: center; }\n')
        outfile.write('th { background-color: #333; color: #f0f0f0; cursor: pointer; position: relative; }\n')
        outfile.write('tr:nth-child(even) { background-color: #2e2e2e; }\n')
        outfile.write('tr:nth-child(odd) { background-color: #262626; }\n')
        outfile.write('td.name-column {\n')
        outfile.write('  background-color: #dcdcdc;\n')  # Slightly darker eggshell greyish color
        outfile.write('}\n')
        outfile.write('td.name-column a {\n')
        outfile.write('  color: #1e90ff;\n')  # Dark blue color
        outfile.write('  text-decoration: none;\n')
        outfile.write('}\n')
        outfile.write('td.name-column a:hover {\n')
        outfile.write('  text-decoration: underline;\n')
        outfile.write('}\n')
        outfile.write('.tooltip {\n')
        outfile.write('  position: relative;\n')
        outfile.write('  display: inline-block;\n')
        outfile.write('}\n')
        outfile.write('.tooltip .tooltiptext {\n')
        outfile.write('  visibility: hidden;\n')
        outfile.write('  width: 250px;\n')
        outfile.write('  background-color: #555;\n')
        outfile.write('  color: #fff;\n')
        outfile.write('  text-align: center;\n')
        outfile.write('  border-radius: 6px;\n')
        outfile.write('  padding: 5px;\n')
        outfile.write('  position: absolute;\n')
        outfile.write('  z-index: 1;\n')
        outfile.write('  bottom: 125%;\n')
        outfile.write('  left: 50%;\n')
        outfile.write('  margin-left: -125px;\n')
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
        outfile.write('        tables[i].style.display = "none";\n')
        outfile.write('    }\n')
        outfile.write('    document.getElementById("table_" + timeFrame).style.display = "table";\n')
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
        # Set initial display state
        outfile.write('    showTimeFrame(timeFrameSelect.value);\n')
        outfile.write('};\n')
        outfile.write('</script>\n')
        outfile.write('</head><body>\n')
        outfile.write('<h1 style="text-align:center;">PST-SUN Player Report</h1>\n')  # Changed title here
        outfile.write('<p style="text-align:center;"><a href="https://joedobrow.github.io/hero_stats/hero_report.html">View Hero Report</a></p>\n')  # Added link here

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
            # Sort players by aggregated value for display purposes
            players_data_sorted = sorted(players_data.values(), key=lambda x: float(x['data'][time_frame]['aggregated_value']) if x['data'][time_frame]['aggregated_value'] != 'N/A' else 0, reverse=True)

            # Set initial display style
            display_style = "display: table;" if time_frame == 'all_time' else "display: none;"
            outfile.write(f'<table id="table_{time_frame}" class="data-table" style="{display_style}">\n')
            outfile.write('<thead>\n')
            outfile.write('<tr>')
            outfile.write('<th>Player Name</th>')
            outfile.write('<th>Games Played</th>')
            outfile.write('<th>Overall Winrate (%)</th>')
            outfile.write('<th>Winrate Excl. Top 20 Heroes (%)</th>')
            outfile.write('<th><span class="tooltip">Discomfort Factor<span class="tooltiptext">Calculated as (Uncomfy Winrate / Comfy Winrate) x 100. If zero, set to 50.</span></span></th>')
            outfile.write('<th><span class="tooltip">Versatility Factor<span class="tooltiptext">The variety of different heroes a player has played.</span></span></th>')
            outfile.write('<th><span class="tooltip">Role Diversity Factor<span class="tooltiptext">Based on the entropy of roles played across all games.</span></span></th>')
            outfile.write('<th><span class="tooltip">Aggregated Value<span class="tooltiptext">Calculated as: (Overall Winrate + (Winrate Excl. Top 20 x 2) + (Discomfort Factor x 2) + (Versatility Factor x 2) + Role Diversity Factor) divided by 8.</span></span></th>')
            outfile.write('</tr>\n')
            outfile.write('</thead>\n')
            outfile.write('<tbody>\n')

            for player_info in players_data_sorted:
                data = player_info['data'][time_frame]
                dotabuff_url = player_info.get('dotabuff_url', '#')
                outfile.write('<tr>')
                outfile.write(f"<td class='name-column'><a href='{dotabuff_url}' target='_blank'>{player_info['name']}</a></td>")
                # Apply color gradient to 'Games Played'
                value = data['games_played']
                if value != 'N/A':
                    val_float = float(value)
                    min_val, max_val = metric_min_max[time_frame]['games_played']
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
                for metric in metrics[1:]:
                    value = data[metric]
                    if value != 'N/A':
                        val_float = float(value)
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
    parser.add_argument('output_html', nargs='?', default='player_report.html', help='Output HTML file name')
    parser.add_argument('--refresh', action='store_true', help='Force refresh of cached data')

    args = parser.parse_args()

    load_api_key()  # Load the API key before making any requests

    if args.refresh:
        # Delete the cache directory or specific cache files
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
            print("Cache cleared.")

    process_players(args.input_csv, args.output_html, refresh=args.refresh)

if __name__ == '__main__':
    main()

