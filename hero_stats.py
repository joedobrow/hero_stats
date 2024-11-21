import csv
import time
import requests
import argparse
import math
import datetime

def api_request(url):
    while True:
        response = requests.get(url)
        if response.status_code == 429:
            print("Received 429 response, sleeping for 60 seconds...")
            time.sleep(60)
            continue
        elif response.status_code == 200:
            time.sleep(1) 
            return response.json()
        else:
            print(f"Error {response.status_code} for URL: {url}")
            return None

def adjusted_score(wins, games, gamma=0.69):
    if games == 0:
        return 0
    winrate = wins / games
    score = winrate * (math.log(games + 1) ** gamma)
    return score

def main():
    parser = argparse.ArgumentParser(description='Analyze Dota 2 player hero statistics.')
    parser.add_argument('players_csv', help='Path to the players CSV file')
    parser.add_argument('heroes_csv', help='Path to the heroes CSV file')
    parser.add_argument('-o', '--output', default='report.html', help='Output HTML file name (default: report.html)')
    args = parser.parse_args()

    players = []
    with open(args.players_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['name']
            dotabuff_link = row['dotabuff']
            player_id = dotabuff_link.strip().split('/')[-1]
            players.append({'name': name, 'player_id': player_id})

    with open(args.heroes_csv, 'r', encoding='utf-8') as f:
        content = f.read()
        hero_names = [name.strip().lower() for name in content.split(',')]

    heroes_response = api_request('https://api.opendota.com/api/heroStats')
    hero_name_to_id = {hero['localized_name'].lower(): hero['id'] for hero in heroes_response}
    hero_id_to_name = {hero['id']: hero['name'] for hero in heroes_response}  # 'name' is like 'npc_dota_hero_antimage'

    player_hero_stats_all = {}
    player_hero_stats_recent = {}
    hero_stats_all = {}
    hero_stats_recent = {}

    player_totals_all = {}
    player_totals_recent = {}
    hero_averages_all = {}
    hero_averages_recent = {}

    two_years_ago = int((datetime.datetime.now() - datetime.timedelta(days=730)).timestamp())

    for player in players:
        account_id = player['player_id']
        print(f"Fetching all-time hero stats for player {player['name']} (ID: {account_id})...")
        url = f'https://api.opendota.com/api/players/{account_id}/heroes'
        data = api_request(url)
        if data is not None:
            player_hero_stats_all[account_id] = data
        else:
            player_hero_stats_all[account_id] = []
        time.sleep(1) 

        print(f"Fetching recent matches for player {player['name']} (ID: {account_id})...")
        matches = []
        offset = 0
        while True:
            url = f'https://api.opendota.com/api/players/{account_id}/matches?date=730&offset={offset}'
            matches_batch = api_request(url)
            if matches_batch is None or len(matches_batch) == 0:
                break
            matches.extend(matches_batch)
            offset += len(matches_batch)
            if len(matches_batch) < 100:
                break
        hero_stats = {}
        for match in matches:
            hero_id = match['hero_id']
            win = 1 if (match['radiant_win'] == (match['player_slot'] < 128)) else 0
            if hero_id not in hero_stats:
                hero_stats[hero_id] = {'games': 0, 'wins': 0}
            hero_stats[hero_id]['games'] += 1
            hero_stats[hero_id]['wins'] += win
        player_hero_stats_recent[account_id] = hero_stats

    for time_frame in ['all', 'recent']:
        if time_frame == 'all':
            player_hero_stats = player_hero_stats_all
            hero_stats = hero_stats_all
            player_totals = player_totals_all
            hero_averages = hero_averages_all
        else:
            player_hero_stats = player_hero_stats_recent
            hero_stats = hero_stats_recent
            player_totals = player_totals_recent
            hero_averages = hero_averages_recent

        for hero_name in hero_names:
            hero_id = hero_name_to_id.get(hero_name)
            if hero_id is None:
                print(f"Hero '{hero_name}' not found in OpenDota API.")
                continue
            hero_stats[hero_name] = []
            hero_scores = []  # For calculating average score per hero
            for player in players:
                account_id = player['player_id']
                name = player['name']
                if time_frame == 'all':
                    stats = player_hero_stats.get(account_id, [])
                    hero_stat = next((s for s in stats if s['hero_id'] == hero_id), None)
                    if hero_stat:
                        games = hero_stat['games']
                        wins = hero_stat['win']
                    else:
                        games = 0
                        wins = 0
                else:
                    stats = player_hero_stats.get(account_id, {})
                    hero_stat = stats.get(hero_id, {'games': 0, 'wins': 0})
                    games = hero_stat['games']
                    wins = hero_stat['wins']
                winrate = wins / games if games > 0 else 0
                score = adjusted_score(wins, games, gamma=0.69)
                player_totals[name] = player_totals.get(name, 0) + score
                hero_scores.append(score)
                hero_stats[hero_name].append({
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
            hero_averages[hero_name] = average_score
            hero_stats[hero_name].sort(key=lambda x: x['score'], reverse=True)

    with open(args.output, 'w', encoding='utf-8') as outfile:
        outfile.write('<html><head><title>PST-SUN Hero Report</title>\n')
        outfile.write('<style>\n')
        # CSS
        outfile.write('body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #1e1e1e; color: #f0f0f0; }\n')
        outfile.write('.container { display: flex; flex-wrap: wrap; }\n')
        outfile.write('.hero-section { width: 50%; box-sizing: border-box; padding: 10px; }\n')
        outfile.write('.hero-image { width: 100%; height: auto; }\n')
        outfile.write('table { border-collapse: collapse; width: 100%; }\n')
        outfile.write('th, td { border: 1px solid #555; padding: 8px; text-align: center; }\n')
        outfile.write('th { background-color: #333; color: #f0f0f0; cursor: pointer; }\n')
        outfile.write('tr:nth-child(even) { background-color: #2e2e2e; }\n')
        outfile.write('tr:nth-child(odd) { background-color: #262626; }\n')
        outfile.write('.hidden { display: none; }\n')
        outfile.write('.checkbox-container { padding: 10px; border: 1px solid #555; margin: 10px; display: inline-block; }\n')
        outfile.write('.checkbox-container label { font-size: 18px; color: #f0f0f0; }\n')
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
        outfile.write('    let checkbox = document.getElementById("timeFrameCheckbox");\n')
        outfile.write('    let allTimeElements = document.getElementsByClassName("allTime");\n')
        outfile.write('    let recentElements = document.getElementsByClassName("recent");\n')
        outfile.write('    if(checkbox.checked) {\n')
        outfile.write('        for(let elem of allTimeElements) { elem.classList.add("hidden"); }\n')
        outfile.write('        for(let elem of recentElements) { elem.classList.remove("hidden"); }\n')
        outfile.write('    } else {\n')
        outfile.write('        for(let elem of allTimeElements) { elem.classList.remove("hidden"); }\n')
        outfile.write('        for(let elem of recentElements) { elem.classList.add("hidden"); }\n')
        outfile.write('    }\n')
        outfile.write('}\n')
        outfile.write('window.onload = function() {\n')
        outfile.write('    let tables = document.getElementsByTagName("table");\n')
        outfile.write('    for(let i = 0; i < tables.length; i++) {\n')
        outfile.write('        makeSortable(tables[i]);\n')
        outfile.write('    }\n')
        outfile.write('    document.getElementById("timeFrameCheckbox").addEventListener("change", toggleTimeFrame);\n')
        outfile.write('    toggleTimeFrame();\n')  # Initialize with checkbox state
        outfile.write('};\n')
        outfile.write('</script>\n')
        outfile.write('</head><body>\n')
        outfile.write('<h1 style="text-align:center;">PST-SUN Hero Report</h1>\n')
        outfile.write('<div class="checkbox-container">\n')
        outfile.write('<label>\n')
        outfile.write('<input type="checkbox" id="timeFrameCheckbox" />\n')
        outfile.write('Filter by last 2 years\n')
        outfile.write('</label>\n')
        outfile.write('</div>\n')
        outfile.write('<div class="container">\n')

        for hero_name in hero_names:
            hero_id = hero_name_to_id.get(hero_name)
            if hero_id is None:
                continue
            display_hero_name = hero_name.title()
            hero_dota_name = hero_id_to_name[hero_id]  # e.g., 'npc_dota_hero_antimage'
            hero_image_name = hero_dota_name.replace('npc_dota_hero_', '')  # e.g., 'antimage'
            hero_image_url = f'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{hero_image_name}.png'
            outfile.write('<div class="hero-section">\n')
            outfile.write(f'<h2 style="text-align:center;">{display_hero_name}</h2>\n')
            outfile.write(f'<img src="{hero_image_url}" alt="{display_hero_name}" class="hero-image">\n')
            for time_frame in ['all', 'recent']:
                if time_frame == 'all':
                    hero_stats = hero_stats_all
                    table_class = 'allTime'
                    caption = 'All-Time Stats'
                else:
                    hero_stats = hero_stats_recent
                    table_class = 'recent'
                    caption = 'Last 2 Years Stats'
                outfile.write(f'<table class="{table_class}">\n')
                outfile.write(f'<caption style="caption-side:top; text-align:left; color:#f0f0f0;">{caption}</caption>\n')
                outfile.write('<thead>\n')
                outfile.write('<tr><th>Player</th><th>Games</th><th>Wins</th><th>Win Rate (%)</th><th>Score</th></tr>\n')
                outfile.write('</thead>\n')
                outfile.write('<tbody>\n')

                scores = [player['score'] for player in hero_stats[hero_name]]
                max_score = max(scores)
                min_score = min(scores)

                for player in hero_stats[hero_name]:
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

        outfile.write('</div>\n') 

        for time_frame in ['all', 'recent']:
            if time_frame == 'all':
                player_totals = player_totals_all
                table_class = 'allTime'
                caption = 'Total Scores per Player (All-Time)'
            else:
                player_totals = player_totals_recent
                table_class = 'recent'
                caption = 'Total Scores per Player (Last 2 Years)'

            player_totals_list = [{'name': name, 'total_score': total_score} for name, total_score in player_totals.items()]
            player_totals_list.sort(key=lambda x: x['total_score'], reverse=True)

            outfile.write(f'<h2 style="text-align:center;">{caption}</h2>\n')
            outfile.write(f'<table class="{table_class}" style="margin: 0 auto;">\n')
            outfile.write('<thead>\n')
            outfile.write('<tr><th>Player</th><th>Total Score</th></tr>\n')
            outfile.write('</thead>\n')
            outfile.write('<tbody>\n')

            scores = [player['total_score'] for player in player_totals_list]
            max_score = max(scores)
            min_score = min(scores)

            for player in player_totals_list:
                name = player['name']
                total_score = player['total_score']

                if max_score > min_score:
                    score_normalized = (total_score - min_score) / (max_score - min_score)
                else:
                    score_normalized = 0.5

                hue = 30 + 90 * score_normalized
                saturation = 50 + 10 * score_normalized
                lightness = 25 + 10 * score_normalized
                color = f'hsl({hue:.0f}, {saturation:.0f}%, {lightness:.0f}%)'

                outfile.write(f'<tr style="background-color:{color}; color: #f0f0f0;">')
                outfile.write(f'<td>{name}</td>')
                outfile.write(f'<td>{total_score:.4f}</td>')
                outfile.write('</tr>\n')

            outfile.write('</tbody>\n')
            outfile.write('</table>\n')

        for time_frame in ['all', 'recent']:
            if time_frame == 'all':
                hero_averages = hero_averages_all
                table_class = 'allTime'
                caption = 'Average Scores per Hero (All-Time)'
            else:
                hero_averages = hero_averages_recent
                table_class = 'recent'
                caption = 'Average Scores per Hero (Last 2 Years)'

            hero_averages_list = [{'hero': hero_name.title(), 'average_score': avg_score} for hero_name, avg_score in hero_averages.items()]
            hero_averages_list.sort(key=lambda x: x['average_score'], reverse=True)

            outfile.write(f'<h2 style="text-align:center;">{caption}</h2>\n')
            outfile.write(f'<table class="{table_class}" style="margin: 0 auto;">\n')
            outfile.write('<thead>\n')
            outfile.write('<tr><th>Hero</th><th>Average Score</th></tr>\n')
            outfile.write('</thead>\n')
            outfile.write('<tbody>\n')

            scores = [hero['average_score'] for hero in hero_averages_list]
            max_score = max(scores)
            min_score = min(scores)

            for hero in hero_averages_list:
                hero_name = hero['hero']
                average_score = hero['average_score']

                if max_score > min_score:
                    score_normalized = (average_score - min_score) / (max_score - min_score)
                else:
                    score_normalized = 0.5

                hue = 30 + 90 * score_normalized
                saturation = 50 + 10 * score_normalized
                lightness = 25 + 10 * score_normalized
                color = f'hsl({hue:.0f}, {saturation:.0f}%, {lightness:.0f}%)'

                outfile.write(f'<tr style="background-color:{color}; color: #f0f0f0;">')
                outfile.write(f'<td>{hero_name}</td>')
                outfile.write(f'<td>{average_score:.4f}</td>')
                outfile.write('</tr>\n')

            outfile.write('</tbody>\n')
            outfile.write('</table>\n')

        outfile.write('</body></html>')

    print(f"\nHTML report has been generated: {args.output}")

if __name__ == '__main__':
    main()

