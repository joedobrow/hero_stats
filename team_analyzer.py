import csv
import time
import requests
import argparse
import math
import os
import json
import datetime

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
    parser = argparse.ArgumentParser(description='Team Analyzer: Analyze Dota 2 team hero statistics.')
    parser.add_argument('players_csv', help='Path to the players CSV file')
    parser.add_argument('-o', '--output', default='team_analyzer.html', help='Output HTML file name (default: team_analyzer.html)')
    parser.add_argument('--refresh', action='store_true', help='Force refresh of cached data')
    args = parser.parse_args()

    load_api_key()

    players = []
    with open(args.players_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['name'].strip()  # Trim whitespaces
            dotabuff_link = row['dotabuff']
            player_id = dotabuff_link.strip().split('/')[-1]
            players.append({'name': name, 'player_id': player_id})

    # Alphabetize players by name
    players.sort(key=lambda x: x['name'].lower())

    # Fetch all heroes
    print("Fetching hero list...")
    heroes_response = load_cached_data('heroStats.json') if not args.refresh else None
    if heroes_response is None:
        heroes_response = make_api_request('https://api.opendota.com/api/heroStats')
        if heroes_response is not None:
            cache_data('heroStats.json', heroes_response)
    else:
        print("Loaded hero stats from cache.")

    hero_name_to_id = {hero['localized_name']: hero['id'] for hero in heroes_response}
    hero_id_to_name = {hero['id']: hero['name'] for hero in heroes_response}  # 'name' is like 'npc_dota_hero_antimage'
    hero_id_to_localized_name = {hero['id']: hero['localized_name'] for hero in heroes_response}
    hero_ids = list(hero_id_to_name.keys())

    # Create a sorted list of (hero_name, hero_id) tuples for alphabetical ordering
    hero_names_and_ids = sorted([(hero_id_to_localized_name[hero_id], hero_id) for hero_id in hero_ids])

    player_hero_stats = {}
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

    # Generate report generated timestamp
    report_generated_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Generate HTML report
    with open(args.output, 'w', encoding='utf-8') as outfile:
        outfile.write('<html><head><title>Team Analyzer</title>\n')
        outfile.write('<style>\n')
        # CSS Styles
        outfile.write('body { font-family: Arial, sans-serif; background-color: #1e1e1e; color: #f0f0f0; }\n')
        outfile.write('.container { width: 80%; margin: 0 auto; }\n')
        outfile.write('.player-selection { margin: 20px 0; }\n')
        outfile.write('.player-selection h3 { text-align: center; }\n')
        outfile.write('.player-grid { display: flex; flex-wrap: wrap; justify-content: center; }\n')
        outfile.write('.player-item { width: 120px; height: 50px; margin: 5px; line-height: 50px; text-align: center; background-color: #555; color: #ccc; cursor: pointer; border-radius: 5px; user-select: none; font-size: 14px; }\n')
        outfile.write('.player-item.selected { background-color: #4a7a4a; color: #fff; }\n')
        outfile.write('.player-item.unselected { background-color: #555; color: #ccc; }\n')
        outfile.write('.timeframe-selection { text-align: center; margin: 20px 0; }\n')
        outfile.write('.timeframe-selection select { font-size: 16px; padding: 5px; }\n')
        outfile.write('table { width: 80%; border-collapse: collapse; margin: 20px auto; }\n')
        outfile.write('th, td { border: 1px solid #555; padding: 8px; text-align: center; }\n')
        outfile.write('th { background-color: #333; color: #f0f0f0; cursor: pointer; }\n')
        outfile.write('tr:nth-child(even) { background-color: #2e2e2e; }\n')
        outfile.write('tr:nth-child(odd) { background-color: #262626; }\n')
        outfile.write('.report-timestamp { text-align: left; font-size: 14px; color: #ccc; margin: 10px 0; }\n')
        outfile.write('.suggested-bans { margin: 20px 0; }\n')  # Added margin to top and bottom
        outfile.write('.suggested-bans h2 { text-align: center; }\n')
        outfile.write('.suggested-bans-grid { display: flex; flex-wrap: wrap; justify-content: center; }\n')
        outfile.write('.hero-item { position: relative; width: 80px; margin: 5px; }\n')
        outfile.write('.hero-image { width: 100%; object-fit: cover; height: 80px; }\n')
        outfile.write('.hero-name { text-align: center; margin-top: 5px; color: #ccc; font-size: 12px; }\n')
        
        # **New CSS for Custom Tooltips**
        outfile.write('''
/* Custom Tooltip Styles */
.hero-item .tooltip {
    visibility: hidden;
    background-color: rgba(0, 0, 0, 0.8);
    color: #fff;
    text-align: left;
    padding: 8px;
    border-radius: 6px;
    position: absolute;
    z-index: 10;
    bottom: 100%; /* Position above the hero image */
    left: 50%;
    transform: translateX(-50%);
    white-space: pre-line; /* Allow newline characters */
    width: max-content;
    max-width: 200px;
    box-shadow: 0px 0px 10px rgba(0,0,0,0.5);
}

.hero-item:hover .tooltip {
    visibility: visible;
}
''')
        outfile.write('</style>\n')
        # JavaScript Code
        outfile.write('<script>\n')
        # Data variables

        # Pass players as an array to preserve order
        outfile.write('let players = [\n')
        for player in players:
            # Escape double quotes in player names
            escaped_name = player["name"].replace('"', '\\"')
            outfile.write(f'    {{ id: "{player["player_id"]}", name: "{escaped_name}" }},\n')
        outfile.write('];\n')

        outfile.write('let heroNames = {};\n')
        outfile.write('let heroNameToId = {};\n')
        outfile.write('let heroIdToDotaName = {};\n')
        for hero_name, hero_id in hero_names_and_ids:
            # Escape double quotes in hero names
            escaped_hero_name = hero_name.replace('"', '\\"')
            escaped_dota_name = hero_id_to_name[hero_id].replace('"', '\\"')
            outfile.write(f'heroNames[{hero_id}] = "{escaped_hero_name}";\n')
            outfile.write(f'heroNameToId["{escaped_hero_name}"] = {hero_id};\n')
            outfile.write(f'heroIdToDotaName[{hero_id}] = "{escaped_dota_name}";\n')
        # Modify playerHeroStats to include games, wins, winrate, and score
        outfile.write('let playerHeroStats = {};\n')
        for time_frame_name in TIME_FRAMES.keys():
            outfile.write(f'playerHeroStats["{time_frame_name}"] = {{}};\n')
            for player in players:
                account_id = player['player_id']
                stats = player_hero_stats[time_frame_name][account_id]
                outfile.write(f'playerHeroStats["{time_frame_name}"]["{account_id}"] = {{}};\n')
                for stat in stats:
                    hero_id = stat['hero_id']
                    games = stat['games']
                    wins = stat['win']
                    score = adjusted_score(wins, games, gamma=0.69)
                    winrate = wins / games if games > 0 else 0
                    # Ensure winrate is rounded to 4 decimal places
                    outfile.write(f'playerHeroStats["{time_frame_name}"]["{account_id}"][{hero_id}] = {{ "score": {score:.4f}, "games": {games}, "wins": {wins}, "winrate": {winrate:.4f} }};\n')
        # Thresholds
        outfile.write('let thresholds = {\n')
        outfile.write('    "all_time": 1.9,\n')
        outfile.write('    "last_2_years": 1.7,\n')
        outfile.write('    "last_9_months": 1.5\n')
        outfile.write('};\n')
        # Function to update the report
        outfile.write('function updateReport() {\n')
        outfile.write('    let selectedPlayers = [];\n')
        outfile.write('    for (let player of players) {\n')
        outfile.write('        let playerDiv = document.getElementById(`player-${player.id}`);\n')
        outfile.write('        if (playerDiv.classList.contains("selected")) {\n')
        outfile.write('            selectedPlayers.push(player.id);\n')
        outfile.write('        }\n')
        outfile.write('    }\n')
        outfile.write('    let timeFrameSelect = document.getElementById("timeFrameSelect");\n')
        outfile.write('    let selectedTimeFrame = timeFrameSelect.value;\n')
        outfile.write('    let combinedScores = {};\n')
        outfile.write('    let suggestedBans = {};\n')  # Changed from Set to Object
        outfile.write('    for (let heroId in heroNames) {\n')
        outfile.write('        let totalScore = 0;\n')
        outfile.write('        for (let playerId of selectedPlayers) {\n')
        outfile.write('            let playerStats = playerHeroStats[selectedTimeFrame][playerId][heroId];\n')
        outfile.write('            if (playerStats && playerStats.score) {\n')
        outfile.write('                let score = playerStats.score;\n')
        outfile.write('                totalScore += score;\n')
        outfile.write('                if (score >= thresholds[selectedTimeFrame]) {\n')
        outfile.write('                    if (!suggestedBans[heroId]) {\n')
        outfile.write('                        suggestedBans[heroId] = [];\n')
        outfile.write('                    }\n')
        outfile.write('                    suggestedBans[heroId].push({\n')
        outfile.write('                        playerId: playerId,\n')
        outfile.write('                        playerName: players.find(p => p.id === playerId).name,\n')
        outfile.write('                        games: playerStats.games,\n')
        outfile.write('                        wins: playerStats.wins,\n')
        outfile.write('                        winrate: (playerStats.winrate * 100).toFixed(2)\n')
        outfile.write('                    });\n')
        outfile.write('                }\n')
        outfile.write('            }\n')
        outfile.write('        }\n')
        outfile.write('        if (totalScore > 0) {\n')
        outfile.write('            combinedScores[heroId] = totalScore;\n')
        outfile.write('        }\n')
        outfile.write('    }\n')
        # Update Suggested Bans
        outfile.write('    let bansGrid = document.getElementById("bansGrid");\n')
        outfile.write('    bansGrid.innerHTML = "";\n')
        outfile.write('    let bansArray = Object.keys(suggestedBans).sort(function(a, b) { return heroNames[a].localeCompare(heroNames[b]); });\n')
        outfile.write('    for (let heroId of bansArray) {\n')
        outfile.write('        let heroName = heroNames[heroId];\n')
        outfile.write('        let heroDotaName = heroIdToDotaName[heroId];\n')
        outfile.write('        let heroImageName = heroDotaName.replace("npc_dota_hero_", "");\n')
        outfile.write('        let heroImageUrl = `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${heroImageName}.png`;\n')
        outfile.write('        let heroDiv = document.createElement("div");\n')
        outfile.write('        heroDiv.classList.add("hero-item");\n')
        outfile.write('        let img = document.createElement("img");\n')
        outfile.write('        img.src = heroImageUrl;\n')
        outfile.write('        img.alt = heroName;\n')
        outfile.write('        img.classList.add("hero-image");\n')
        # Remove setting the title attribute
        # Instead, create a tooltip div
        outfile.write('        let tooltipDiv = document.createElement("div");\n')
        outfile.write('        tooltipDiv.classList.add("tooltip");\n')
        outfile.write('        let tooltipText = "";\n')
        outfile.write('        for (let playerStats of suggestedBans[heroId]) {\n')
        outfile.write('            let playerName = playerStats.playerName;\n')
        outfile.write('            let games = playerStats.games;\n')
        outfile.write('            let winrate = playerStats.winrate;\n')
        outfile.write('            tooltipText += `${playerName}: ${games} games, ${winrate}% winrate\\n`;\n')
        outfile.write('        }\n')
        outfile.write('        tooltipDiv.textContent = tooltipText.trim();\n')
        outfile.write('        let nameDiv = document.createElement("div");\n')
        outfile.write('        nameDiv.classList.add("hero-name");\n')
        outfile.write('        nameDiv.textContent = heroName;\n')
        outfile.write('        heroDiv.appendChild(img);\n')
        outfile.write('        heroDiv.appendChild(tooltipDiv);\n')  # Append tooltipDiv
        outfile.write('        heroDiv.appendChild(nameDiv);\n')
        outfile.write('        bansGrid.appendChild(heroDiv);\n')
        outfile.write('    }\n')
        # Update Hero Table
        outfile.write('    let heroTableBody = document.getElementById("heroTableBody");\n')
        outfile.write('    heroTableBody.innerHTML = "";\n')
        outfile.write('    let heroEntries = [];\n')
        outfile.write('    for (let heroId in combinedScores) {\n')
        outfile.write('        heroEntries.push({heroId: heroId, score: combinedScores[heroId]});\n')
        outfile.write('    }\n')
        outfile.write('    heroEntries.sort(function(a, b) { return b.score - a.score; });\n')
        outfile.write('    for (let entry of heroEntries) {\n')
        outfile.write('        let row = heroTableBody.insertRow();\n')
        outfile.write('        let cellHero = row.insertCell(0);\n')
        outfile.write('        let cellScore = row.insertCell(1);\n')
        outfile.write('        cellHero.textContent = heroNames[entry.heroId];\n')
        outfile.write('        cellScore.textContent = entry.score.toFixed(4);\n')
        outfile.write('    }\n')
        outfile.write('}\n')
        # Event Listeners
        outfile.write('function togglePlayerSelection(event) {\n')
        outfile.write('    let playerDiv = event.currentTarget;\n')
        outfile.write('    if (playerDiv.classList.contains("selected")) {\n')
        outfile.write('        playerDiv.classList.remove("selected");\n')
        outfile.write('        playerDiv.classList.add("unselected");\n')
        outfile.write('    } else {\n')
        outfile.write('        playerDiv.classList.remove("unselected");\n')
        outfile.write('        playerDiv.classList.add("selected");\n')
        outfile.write('    }\n')
        outfile.write('    updateReport();\n')
        outfile.write('}\n')
        outfile.write('window.onload = function() {\n')
        outfile.write('    let playerGrid = document.querySelector(".player-grid");\n')
        outfile.write('    for (let player of players) {\n')
        outfile.write('        let playerDiv = document.createElement("div");\n')
        outfile.write('        playerDiv.classList.add("player-item", "unselected");\n')
        outfile.write('        playerDiv.id = `player-${player.id}`;\n')  # Assign unique ID for each player
        outfile.write('        // Limit player name to 15 characters\n')
        outfile.write('        let playerName = player.name;\n')
        outfile.write('        if (playerName.length > 15) {\n')
        outfile.write('            playerName = playerName.substring(0, 15) + "...";\n')
        outfile.write('        }\n')
        outfile.write('        playerDiv.textContent = playerName;\n')
        outfile.write('        playerDiv.addEventListener("click", togglePlayerSelection);\n')
        outfile.write('        playerGrid.appendChild(playerDiv);\n')
        outfile.write('    }\n')
        outfile.write('    let timeFrameSelect = document.getElementById("timeFrameSelect");\n')
        outfile.write('    timeFrameSelect.addEventListener("change", updateReport);\n')
        outfile.write('    updateReport();\n')
        outfile.write('};\n')
        outfile.write('</script>\n')
        outfile.write('</head><body>\n')
        outfile.write('<div class="container">\n')
        outfile.write(f'<div class="report-timestamp">Report generated: {report_generated_time}</div>\n')
        outfile.write('<h1 style="text-align:center;">Team Analyzer</h1>\n')
        # Time Frame Selection
        outfile.write('<div class="timeframe-selection">\n')
        outfile.write('<h3>Time Frame:</h3>\n')
        outfile.write('<select id="timeFrameSelect">\n')
        outfile.write('<option value="all_time">All Time</option>\n')
        outfile.write('<option value="last_2_years">Last 2 Years</option>\n')
        outfile.write('<option value="last_9_months">Last 9 Months</option>\n')
        outfile.write('</select>\n')
        outfile.write('</div>\n')
        # Player Selection
        outfile.write('<div class="player-selection">\n')
        outfile.write('<h3>Select Players:</h3>\n')
        outfile.write('<div class="player-grid">\n')
        # Player items will be generated by JavaScript
        outfile.write('</div>\n')
        outfile.write('</div>\n')
        # Suggested Bans (Moved above the hero table)
        outfile.write('<div class="suggested-bans">\n')
        outfile.write('<h2>Suggested Bans</h2>\n')
        outfile.write('<div class="suggested-bans-grid" id="bansGrid">\n')
        # Bans will be populated by JavaScript
        outfile.write('</div>\n')
        outfile.write('</div>\n')
        # Hero Table
        outfile.write('<div><h2 style="margin-top:20px; text-align: center;">Combined Hero Scores</h2></div>\n')
        outfile.write('<table>\n')
        outfile.write('<thead>\n')
        outfile.write('<tr><th>Hero Name</th><th>Combined Score</th></tr>\n')
        outfile.write('</thead>\n')
        outfile.write('<tbody id="heroTableBody">\n')
        outfile.write('</tbody>\n')
        outfile.write('</table>\n')
        outfile.write('</div>\n')  # Close container
        outfile.write('</body></html>\n')

    print(f"\nHTML report has been generated: {args.output}")

if __name__ == '__main__':
    main()

