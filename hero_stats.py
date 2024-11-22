import csv
import time
import requests
import argparse
import math
import os
import json

CACHE_DIR = 'cache'
REQUEST_DELAY = 1  # seconds
API_KEY = None  # Will be loaded from opendota.properties

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
        elif response.status_code == 200:
            time.sleep(REQUEST_DELAY)
            return response.json()
        else:
            print(f"Error {response.status_code} for URL: {url}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def adjusted_score(wins, games, gamma=0.69):
    if games == 0:
        return 0
    winrate = wins / games
    score = winrate * (math.log(games + 1) ** gamma)
    return score

def cache_data(filename, data):
    try:
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        with open(os.path.join(CACHE_DIR, filename), 'w', encoding='utf-8') as f:
            json.dump(data, f)
        print(f"Cached data to {filename}")
    except Exception as e:
        print(f"Error caching data to {filename}: {e}")

def load_cached_data(filename):
    try:
        with open(os.path.join(CACHE_DIR, filename), 'r', encoding='utf-8') as f:
            print(f"Loaded cached data from {filename}")
            return json.load(f)
    except FileNotFoundError:
        print(f"Cache file {filename} not found.")
        return None
    except Exception as e:
        print(f"Error loading cache file {filename}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Analyze Dota 2 player hero statistics.')
    parser.add_argument('players_csv', help='Path to the players CSV file')
    parser.add_argument('-o', '--output', default='hero_report.html', help='Output HTML file name (default: report.html)')
    parser.add_argument('--refresh', action='store_true', help='Force refresh of cached data')
    args = parser.parse_args()

    load_api_key()

    players = []
    with open(args.players_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['name']
            dotabuff_link = row['dotabuff']
            player_id = dotabuff_link.strip().split('/')[-1]
            players.append({'name': name, 'player_id': player_id})

    # Fetch all heroes
    print("Fetching hero list...")
    heroes_response = load_cached_data('heroStats.json') if not args.refresh else None
    if heroes_response is None:
        heroes_response = make_api_request('https://api.opendota.com/api/heroStats')
        if heroes_response is not None:
            cache_data('heroStats.json', heroes_response)
    else:
        print("Loaded hero stats from cache.")

    hero_name_to_id = {hero['localized_name'].lower(): hero['id'] for hero in heroes_response}
    hero_id_to_name = {hero['id']: hero['name'] for hero in heroes_response}  # 'name' is like 'npc_dota_hero_antimage'
    hero_id_to_localized_name = {hero['id']: hero['localized_name'] for hero in heroes_response}
    hero_ids = list(hero_id_to_name.keys())

    # Create a sorted list of (hero_name, hero_id) tuples for alphabetical ordering
    hero_names_and_ids = sorted([(hero_id_to_localized_name[hero_id], hero_id) for hero_id in hero_ids])

    player_hero_stats = {}
    hero_stats = {}
    player_totals = {}
    hero_averages = {}

    TIME_FRAMES = {
        'all_time': None,
        'last_2_years': 730,
        'last_9_months': 270,
    }

    for player in players:
        account_id = player['player_id']
        print(f"Processing player {player['name']} (ID: {account_id})...")

        for time_frame_name, days in TIME_FRAMES.items():
            # Fetch hero stats
            filename = f"{account_id}_heroes_{time_frame_name}.json"
            data = load_cached_data(filename) if not args.refresh else None
            if data is None:
                print(f"Fetching hero stats for {time_frame_name} for player {player['name']}...")
                params = {}
                if days is not None:
                    params['date'] = days
                url = f'https://api.opendota.com/api/players/{account_id}/heroes'
                data = make_api_request(url, params)
                if data is not None:
                    cache_data(filename, data)
            else:
                print(f"Loaded hero stats for {time_frame_name} for player {player['name']} from cache.")
            player_hero_stats.setdefault(time_frame_name, {})[account_id] = data if data is not None else []

    for time_frame_name, days in TIME_FRAMES.items():
        player_totals[time_frame_name] = {}
        hero_averages[time_frame_name] = {}
        hero_stats[time_frame_name] = {}

        for hero_name, hero_id in hero_names_and_ids:
            hero_name_lower = hero_name.lower()
            hero_stats[time_frame_name][hero_name_lower] = []
            hero_scores = []  # For calculating average score per hero
            for player in players:
                account_id = player['player_id']
                name = player['name']
                stats = player_hero_stats[time_frame_name].get(account_id, [])
                hero_stat = next((s for s in stats if s['hero_id'] == hero_id), None)
                if hero_stat:
                    games = hero_stat['games']
                    wins = hero_stat['win']
                else:
                    games = 0
                    wins = 0
                winrate = wins / games if games > 0 else 0
                score = adjusted_score(wins, games, gamma=0.69)
                player_totals[time_frame_name][name] = player_totals[time_frame_name].get(name, 0) + score
                hero_scores.append(score)
                hero_stats[time_frame_name][hero_name_lower].append({
                    'name': name,
                    'wins': wins,
                    'games': games,
                    'winrate': winrate,
                    'score': score
                })
            if hero_scores:
                average_score = sum(hero_scores) / len(hero_scores)
            else:
                average_score = 0
            hero_averages[time_frame_name][hero_name_lower] = average_score
            hero_stats[time_frame_name][hero_name_lower].sort(key=lambda x: x['score'], reverse=True)

    # Generate HTML report
    with open(args.output, 'w', encoding='utf-8') as outfile:
        outfile.write('<html><head><title>PST-SUN Hero Report</title>\n')
        outfile.write('<style>\n')
        # CSS
        outfile.write('body { font-family: Arial, sans-serif; margin: 0; padding: 0 20px; background-color: #1e1e1e; color: #f0f0f0; }\n')
        outfile.write('.container { display: flex; flex-wrap: wrap; padding: 20px; }\n')
        outfile.write('.hero-section { width: 48%; box-sizing: border-box; padding: 10px; margin: 1%; }\n')
        outfile.write('.hero-image { width: 80%; height: auto; margin: 0 auto; display: block; }\n')
        outfile.write('table { border-collapse: collapse; width: 100%; }\n')
        outfile.write('th, td { border: 1px solid #555; padding: 8px; text-align: center; }\n')
        outfile.write('th { background-color: #333; color: #f0f0f0; cursor: pointer; }\n')
        outfile.write('tr:nth-child(even) { background-color: #2e2e2e; }\n')
        outfile.write('tr:nth-child(odd) { background-color: #262626; }\n')
        outfile.write('.hidden { display: none; }\n')
        # New styles for hero selection grid
        outfile.write('.hero-selection-container { padding: 10px; border: 1px solid #555; margin: 10px; }\n')
        outfile.write('.hero-grid { display: flex; flex-wrap: wrap; justify-content: center; }\n')
        outfile.write('.hero-item { position: relative; width: 80px; height: 80px; margin: 5px; cursor: pointer; }\n')
        outfile.write('.hero-select-image { width: 100%; height: 100%; object-fit: cover; }\n')
        outfile.write('.hero-name-overlay { position: absolute; bottom: 0; width: 100%; text-align: center; background: rgba(0, 0, 0, 0.6); color: #fff; font-size: 10px; padding: 2px 0; }\n')
        outfile.write('.hero-item.deselected { filter: grayscale(100%); opacity: 0.5; }\n')
        outfile.write('.hero-item.selected { filter: none; opacity: 1; }\n')
        # Buttons styling
        outfile.write('.hero-selection-container button { margin: 5px; padding: 5px 10px; font-size: 14px; }\n')
        outfile.write('</style>\n')
        # JavaScript
        outfile.write('<script>\n')
        outfile.write('function sortTable(table, col, reverse) {\n')
        outfile.write('    let tb = table.tBodies[0],\n')
        outfile.write('        tr = Array.prototype.slice.call(tb.rows, 0),\n')
        outfile.write('        i;\n')
        outfile.write('    reverse = -((+reverse) || -1);\n')
        outfile.write('    tr = tr.sort(function (a, b) {\n')
        outfile.write('        let aText = a.cells[col].textContent.trim(),\n')
        outfile.write('            bText = b.cells[col].textContent.trim();\n')
        outfile.write('        let aNum = parseFloat(aText) || aText;\n')
        outfile.write('        let bNum = parseFloat(bText) || bText;\n')
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
        outfile.write('function toggleTimeFrame() {\n')
        outfile.write('    let select = document.getElementById("timeFrameSelect");\n')
        outfile.write('    let timeFrames = ["all_time", "last_2_years", "last_9_months"];\n')
        outfile.write('    let selectedTimeFrame = select.value;\n')
        outfile.write('    for (let tf of timeFrames) {\n')
        outfile.write('        let elements = document.getElementsByClassName(tf);\n')
        outfile.write('        for (let elem of elements) {\n')
        outfile.write('            if (tf === selectedTimeFrame) {\n')
        outfile.write('                elem.classList.remove("hidden");\n')
        outfile.write('            } else {\n')
        outfile.write('                elem.classList.add("hidden");\n')
        outfile.write('            }\n')
        outfile.write('        }\n')
        outfile.write('    }\n')
        outfile.write('    updateTotals();\n')
        outfile.write('}\n')
        outfile.write('function toggleHeroSelection(heroId) {\n')
        outfile.write('    let heroItem = document.getElementById("hero_select_" + heroId);\n')
        outfile.write('    let heroSection = document.getElementById("hero_" + heroId);\n')
        outfile.write('    if (heroItem.classList.contains("selected")) {\n')
        outfile.write('        heroItem.classList.remove("selected");\n')
        outfile.write('        heroItem.classList.add("deselected");\n')
        outfile.write('        heroSection.classList.add("hidden");\n')
        outfile.write('    } else {\n')
        outfile.write('        heroItem.classList.remove("deselected");\n')
        outfile.write('        heroItem.classList.add("selected");\n')
        outfile.write('        heroSection.classList.remove("hidden");\n')
        outfile.write('    }\n')
        outfile.write('    updateTotals();\n')
        outfile.write('}\n')
        outfile.write('function selectAllHeroes() {\n')
        outfile.write('    let heroItems = document.getElementsByClassName("hero-item");\n')
        outfile.write('    for (let heroItem of heroItems) {\n')
        outfile.write('        heroItem.classList.add("selected");\n')
        outfile.write('        heroItem.classList.remove("deselected");\n')
        outfile.write('        let heroId = heroItem.dataset.heroId;\n')
        outfile.write('        document.getElementById("hero_" + heroId).classList.remove("hidden");\n')
        outfile.write('    }\n')
        outfile.write('    updateTotals();\n')
        outfile.write('}\n')
        outfile.write('function deselectAllHeroes() {\n')
        outfile.write('    let heroItems = document.getElementsByClassName("hero-item");\n')
        outfile.write('    for (let heroItem of heroItems) {\n')
        outfile.write('        heroItem.classList.remove("selected");\n')
        outfile.write('        heroItem.classList.add("deselected");\n')
        outfile.write('        let heroId = heroItem.dataset.heroId;\n')
        outfile.write('        document.getElementById("hero_" + heroId).classList.add("hidden");\n')
        outfile.write('    }\n')
        outfile.write('    updateTotals();\n')
        outfile.write('}\n')
        outfile.write('function updateTotals() {\n')
        outfile.write('    let playerTotals = {};\n')
        outfile.write('    let heroSections = document.getElementsByClassName("hero-section");\n')
        outfile.write('    let select = document.getElementById("timeFrameSelect");\n')
        outfile.write('    let selectedTimeFrame = select.value;\n')
        outfile.write('    for (let section of heroSections) {\n')
        outfile.write('        if (section.classList.contains("hidden")) continue;\n')
        outfile.write('        let tables = section.getElementsByClassName(selectedTimeFrame);\n')
        outfile.write('        for (let table of tables) {\n')
        outfile.write('            let rows = table.tBodies[0].rows;\n')
        outfile.write('            for (let row of rows) {\n')
        outfile.write('                let playerName = row.cells[0].textContent;\n')
        outfile.write('                let score = parseFloat(row.cells[4].textContent);\n')
        outfile.write('                if (!playerTotals[playerName]) playerTotals[playerName] = 0;\n')
        outfile.write('                playerTotals[playerName] += score;\n')
        outfile.write('            }\n')
        outfile.write('        }\n')
        outfile.write('    }\n')
        outfile.write('    let totalTables = document.getElementsByClassName("player-totals");\n')
        outfile.write('    for (let table of totalTables) {\n')
        outfile.write('        if (table.classList.contains(selectedTimeFrame)) {\n')
        outfile.write('            table.classList.remove("hidden");\n')
        outfile.write('            let tbody = table.tBodies[0];\n')
        outfile.write('            // Remove existing rows\n')
        outfile.write('            while (tbody.firstChild) {\n')
        outfile.write('                tbody.removeChild(tbody.firstChild);\n')
        outfile.write('            }\n')
        outfile.write('            // Create new rows\n')
        outfile.write('            let players = [];\n')
        outfile.write('            for (let playerName in playerTotals) {\n')
        outfile.write('                players.push({ name: playerName, totalScore: playerTotals[playerName] });\n')
        outfile.write('            }\n')
        outfile.write('            // Sort players by totalScore in descending order\n')
        outfile.write('            players.sort(function(a, b) {\n')
        outfile.write('                return b.totalScore - a.totalScore;\n')
        outfile.write('            });\n')
        outfile.write('            // Add rows to table\n')
        outfile.write('            for (let player of players) {\n')
        outfile.write('                let row = tbody.insertRow();\n')
        outfile.write('                let cellName = row.insertCell(0);\n')
        outfile.write('                let cellTotalScore = row.insertCell(1);\n')
        outfile.write('                cellName.textContent = player.name;\n')
        outfile.write('                cellTotalScore.textContent = player.totalScore.toFixed(4);\n')
        outfile.write('            }\n')
        outfile.write('        } else {\n')
        outfile.write('            table.classList.add("hidden");\n')
        outfile.write('        }\n')
        outfile.write('    }\n')
        outfile.write('}\n')
        outfile.write('window.onload = function() {\n')
        outfile.write('    let tables = document.getElementsByTagName("table");\n')
        outfile.write('    for(let i = 0; i < tables.length; i++) {\n')
        outfile.write('        makeSortable(tables[i]);\n')
        outfile.write('    }\n')
        outfile.write('    document.getElementById("timeFrameSelect").addEventListener("change", toggleTimeFrame);\n')
        outfile.write('    let heroItems = document.getElementsByClassName("hero-item");\n')
        outfile.write('    for (let heroItem of heroItems) {\n')
        outfile.write('        heroItem.addEventListener("click", function() { toggleHeroSelection(this.dataset.heroId); });\n')
        outfile.write('    }\n')
        outfile.write('    document.getElementById("selectAllBtn").addEventListener("click", selectAllHeroes);\n')
        outfile.write('    document.getElementById("deselectAllBtn").addEventListener("click", deselectAllHeroes);\n')
        outfile.write('    toggleTimeFrame();\n')  # Initialize with selected time frame
        outfile.write('    updateTotals();\n')
        outfile.write('};\n')
        outfile.write('</script>\n')
        outfile.write('</head><body>\n')
        outfile.write('<h1 style="text-align:center;">PST-SUN Hero Report</h1>\n')
        # Link to other report
        outfile.write('<div style="text-align:center; margin-bottom:20px;">\n')
        outfile.write('<a href="https://joedobrow.github.io/hero_stats/player_report.html" style="color:#1e90ff;">View Player Metrics Report</a>\n')
        outfile.write('</div>\n')
        # Time frame selection
        outfile.write('<div class="hero-selection-container">\n')
        outfile.write('<div style="width:100%;"><h3>Time Frame:</h3></div>\n')
        outfile.write('<div style="width:100%; margin-bottom: 10px;">\n')
        outfile.write('<select id="timeFrameSelect">\n')
        outfile.write('<option value="all_time">All Time</option>\n')
        outfile.write('<option value="last_2_years">Last 2 Years</option>\n')
        outfile.write('<option value="last_9_months">Last 9 Months</option>\n')
        outfile.write('</select>\n')
        outfile.write('</div>\n')
        outfile.write('</div>\n')
        # Hero selection grid
        outfile.write('<div class="hero-selection-container">\n')
        outfile.write('<div style="width:100%;"><h3>Select Heroes:</h3></div>\n')
        outfile.write('<div style="width:100%; margin-bottom: 10px;"><button id="selectAllBtn">Select All</button>\n')
        outfile.write('<button id="deselectAllBtn">Deselect All</button></div>\n')
        outfile.write('<div class="hero-grid">\n')
        for hero_name, hero_id in hero_names_and_ids:
            hero_dota_name = hero_id_to_name[hero_id]  # e.g., 'npc_dota_hero_antimage'
            hero_image_name = hero_dota_name.replace('npc_dota_hero_', '')  # e.g., 'antimage'
            hero_image_url = f'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{hero_image_name}.png'
            outfile.write(f'<div class="hero-item selected" data-hero-id="{hero_id}" id="hero_select_{hero_id}">\n')
            outfile.write(f'<img src="{hero_image_url}" alt="{hero_name}" class="hero-select-image">\n')
            outfile.write(f'<div class="hero-name-overlay">{hero_name}</div>\n')
            outfile.write('</div>\n')
        outfile.write('</div>\n')
        outfile.write('</div>\n')
        outfile.write('<div class="container">\n')
        for hero_name, hero_id in hero_names_and_ids:
            hero_name_lower = hero_name.lower()
            display_hero_name = hero_name  # Already properly capitalized
            hero_dota_name = hero_id_to_name[hero_id]  # e.g., 'npc_dota_hero_antimage'
            hero_image_name = hero_dota_name.replace('npc_dota_hero_', '')  # e.g., 'antimage'
            hero_image_url = f'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{hero_image_name}.png'
            outfile.write(f'<div class="hero-section" id="hero_{hero_id}">\n')
            outfile.write(f'<h2 style="text-align:center;">{display_hero_name}</h2>\n')
            outfile.write(f'<img src="{hero_image_url}" alt="{display_hero_name}" class="hero-image">\n')
            for time_frame_name in TIME_FRAMES.keys():
                hero_stats_tf = hero_stats[time_frame_name]
                table_class = time_frame_name
                caption = time_frame_name.replace('_', ' ').title() + ' Stats'
                outfile.write(f'<table class="{table_class}">\n')
                outfile.write(f'<caption style="caption-side:top; text-align:left; color:#f0f0f0;">{caption}</caption>\n')
                outfile.write('<thead>\n')
                outfile.write('<tr><th>Player</th><th>Games</th><th>Wins</th><th>Win Rate (%)</th><th>Score</th></tr>\n')
                outfile.write('</thead>\n')
                outfile.write('<tbody>\n')

                scores = [player['score'] for player in hero_stats_tf[hero_name_lower]]
                max_score = max(scores) if scores else 0
                min_score = min(scores) if scores else 0

                for player in hero_stats_tf[hero_name_lower]:
                    name = player['name']
                    wins = player['wins']
                    games = player['games']
                    winrate = wins / games * 100 if games > 0 else 0
                    score = player['score']

                    if max_score > min_score:
                        score_normalized = (score - min_score) / (max_score - min_score)
                    else:
                        score_normalized = 0.5

                    hue = 30 + 90 * score_normalized  # From 30 (reddish brown) to 120 (dark green)
                    saturation = 50 + 10 * score_normalized  # From 50% to 60%
                    lightness = 25 + 10 * score_normalized  # From 25% to 35%
                    color = f'hsl({hue:.0f}, {saturation:.0f}%, {lightness:.0f}%)'

                    outfile.write(f'<tr style="background-color:{color}; color: #f0f0f0;">')
                    outfile.write(f'<td>{name}</td>')
                    outfile.write(f'<td>{games}</td>')
                    outfile.write(f'<td>{wins}</td>')
                    outfile.write(f'<td>{winrate:.2f}</td>')
                    outfile.write(f'<td>{score:.4f}</td>')
                    outfile.write('</tr>\n')

                outfile.write('</tbody>\n')
                outfile.write('</table>\n')
                outfile.write('<br/>\n')
            outfile.write('</div>\n')
        outfile.write('</div>\n')  # Close container
        for time_frame_name in TIME_FRAMES.keys():
            table_class = f'{time_frame_name} player-totals'
            caption = f'Total Scores per Player ({time_frame_name.replace("_", " ").title()})'

            # Get the list of all player names
            all_player_names = [player['name'] for player in players]

            outfile.write(f'<h2 class="{time_frame_name}" style="text-align:center;">{caption}</h2>\n')
            outfile.write(f'<table class="{table_class}" style="margin: 0 auto;">\n')
            outfile.write('<thead>\n')
            outfile.write('<tr><th>Player</th><th>Total Score</th></tr>\n')
            outfile.write('</thead>\n')
            outfile.write('<tbody>\n')
            # The tbody will be populated dynamically by JavaScript
            outfile.write('</tbody>\n')
            outfile.write('</table>\n')
        outfile.write('</body></html>')

    print(f"\nHTML report has been generated: {args.output}")

if __name__ == '__main__':
    main()

