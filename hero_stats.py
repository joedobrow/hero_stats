import csv
import time
import requests
import argparse
import math
import os
import json
import datetime  # Added for timestamp

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
    if API_KEY:
        params = params or {}
        params['api_key'] = API_KEY
    try:
        r = requests.get(url, params=params)
        if r.status_code == 429:
            print("Rate limit exceeded. Sleeping for 60 seconds.")
            time.sleep(60)
            return make_api_request(url, params)
        elif r.status_code == 200:
            time.sleep(REQUEST_DELAY)
            return r.json()
        else:
            print(f"Error {r.status_code} for URL: {url}")
            return None
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None


def adjusted_score(wins, games, gamma=0.69):
    if games == 0:
        return 0
    return (wins/games) * (math.log(games+1)**gamma)


def cache_data(fn, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, fn)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    print(f"Cached data to {fn}")


def load_cached_data(fn):
    path = os.path.join(CACHE_DIR, fn)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            print(f"Loaded cached data from {fn}")
            return json.load(f)
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description='Analyze Dota 2 player hero statistics.')
    parser.add_argument('players_csv', help='Path to the players CSV file')
    parser.add_argument('-o', '--output', default='hero_report.html', help='Output HTML file')
    parser.add_argument('--refresh', action='store_true', help='Force refresh of cached data')
    args = parser.parse_args()

    load_api_key()

    # Read players
    players = []
    with open(args.players_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row['dotabuff'].rstrip('/').split('/')[-1]
            players.append({'name': row['name'], 'player_id': pid})

    # Load hero stats
    heroes = load_cached_data('heroStats.json') if not args.refresh else None
    if not heroes:
        heroes = make_api_request('https://api.opendota.com/api/heroStats')
        cache_data('heroStats.json', heroes)

    # Mappings
    id_to_local = {h['id']: h['localized_name'] for h in heroes}
    id_to_key   = {h['id']: h['name'].replace('npc_dota_hero_', '') for h in heroes}
    hero_list   = sorted(id_to_local.items(), key=lambda x: x[1])

    TIME_FRAMES = {'all_time': None, 'last_2_years': 730, 'last_9_months': 270}

    # Fetch per-player hero data
    phs = {tf: {} for tf in TIME_FRAMES}
    for p in players:
        for tf, days in TIME_FRAMES.items():
            fn = f"{p['player_id']}_heroes_{tf}.json"
            data = None if args.refresh else load_cached_data(fn)
            if not data:
                url = f"https://api.opendota.com/api/players/{p['player_id']}/heroes"
                params = {'date': days} if days else None
                data = make_api_request(url, params)
                cache_data(fn, data or [])
            phs[tf][p['player_id']] = data or []

    # Compute scores
    hero_stats = {tf: {} for tf in TIME_FRAMES}
    for tf in TIME_FRAMES:
        for hid, _ in hero_list:
            stats = []
            for p in players:
                rec = next((x for x in phs[tf][p['player_id']] if x['hero_id']==hid), {})
                w, g = rec.get('win', 0), rec.get('games', 0)
                score = adjusted_score(w, g)
                stats.append({
                    'name': p['name'],
                    'games': g,
                    'wins': w,
                    'winrate': (w/g*100 if g>0 else 0),
                    'score': score
                })
            stats.sort(key=lambda x: x['score'], reverse=True)
            hero_stats[tf][hid] = stats

    # Compute trophy points for all_time
    trophies = {}
    for hid, _ in hero_list:
        top3 = hero_stats['all_time'][hid][:3]
        for idx, entry in enumerate(top3):
            pts = 3 - idx  # 3, 2, 1
            trophies[entry['name']] = trophies.get(entry['name'], 0) + pts
    sorted_trophies = sorted(trophies.items(), key=lambda x: x[1], reverse=True)

    # Generate HTML report
    report_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(args.output, 'w', encoding='utf-8') as out:
        # Header
        out.write('<!DOCTYPE html>\n<html lang="en">\n<head>\n')
        out.write('  <meta charset="UTF-8">\n')
        out.write('  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
        out.write('  <title>Lads Hero Report</title>\n')
        # Styles
        out.write('<style>\n')
        out.write('body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #1e1e1e; color: #f0f0f0; }\n')
        out.write('.timeframe-container { margin-bottom: 20px; }\n')
        out.write('.timeframe-container select { padding: 8px 12px; font-size: 1em; border-radius: 4px; background-color: #333; color: #f0f0f0; border: 1px solid #555; }\n')
        out.write('.container { display: flex; flex-wrap: wrap; }\n')
        out.write('.hero { width: 48%; box-sizing: border-box; padding: 10px; margin: 1%; border: 1px solid #444; border-radius: 4px; background-color: #2a2a2a; }\n')
        out.write('.hero h2 { margin: 0 0 10px; }\n')
        out.write('.hero img { display: block; margin: 0 auto 10px; width: 125px; }\n')
        out.write('table { width: 100%; border-collapse: collapse; margin-bottom: 5px; table-layout: fixed; }\n')
        out.write('th, td { border: 1px solid #555; padding: 6px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n')
        out.write('th { background-color: #333; cursor: pointer; }\n')
        out.write('th:nth-child(1), td:nth-child(1) { width: 45%; }\n')
        out.write('th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) { width: 15%; }\n')
        out.write('th:nth-child(4), td:nth-child(4), th:nth-child(5), td:nth-child(5) { width: 12.5%; }\n')
        out.write('tr:nth-child(even) { background-color: #2e2e2e; }\n')
        out.write('tr:nth-child(odd) { background-color: #262626; }\n')
        out.write('tr.hidden { display: none; }\n')
        out.write('button.toggle { display: block; margin: 5px auto; padding: 6px 12px; font-size: 0.9em; background: #444; color: #fff; border: none; border-radius: 3px; cursor: pointer; }\n')
        out.write('button.toggle:hover { background: #555; }\n')
        out.write('.tooltip { position: relative; display: inline-block; cursor: help; }\n')
        out.write('.tooltip .tooltiptext { visibility: hidden; width: 220px; background-color: #333; color: #fff; text-align: center; border-radius: 4px; padding: 5px; position: absolute; z-index: 1; bottom: 125%; left: 50%; transform: translateX(-50%); opacity: 0; transition: opacity 0.3s; }\n')
        out.write('.tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }\n')
        out.write('.trophies { margin: 40px auto; width: 50%; border-collapse: collapse; }\n')
        out.write('.trophies th, .trophies td { border: 1px solid #555; padding: 6px; text-align: center; }\n')
        out.write('.trophies th { background-color: #444; }\n')
        out.write('</style>\n')
        # Scripts
        out.write('<script>\n')
        out.write('document.addEventListener("DOMContentLoaded", ()=>{\n')
        out.write('  const timeSelect = document.getElementById("timeFrameSelect");\n')
        out.write('  function toggleTimeFrame(){ const tf=timeSelect.value; document.querySelectorAll(".hero").forEach(hero=>{hero.querySelectorAll("table").forEach(tbl=>tbl.style.display=tbl.classList.contains(tf)?"table":"none"); const btn=hero.querySelector("button.toggle"); btn.textContent="Show all"; hero.querySelectorAll(`table.${tf} tbody tr.hidden`).forEach(r=>r.style.display="none");});}\n')
        out.write('  timeSelect.addEventListener("change",toggleTimeFrame);\n')
        out.write('  document.querySelectorAll("button.toggle").forEach(btn=>btn.addEventListener("click",()=>{ const heroId=btn.dataset.hero; const tf=timeSelect.value; document.querySelectorAll(`#hero_${heroId} table.${tf} tbody tr.hidden`).forEach(r=>r.style.display=r.style.display==="none"?"table-row":"none"); btn.textContent=btn.textContent==="Show all"?"Show top 5":"Show all";}));\n')
        out.write('  function sortTable(tbl,col,asc){ const tb=tbl.tBodies[0]; Array.from(tb.rows).sort((a,b)=>{ const A=a.cells[col].textContent.trim(),B=b.cells[col].textContent.trim(),nA=parseFloat(A),nB=parseFloat(B); if(!isNaN(nA)&&!isNaN(nB))return asc?nA-nB:nB-nA; return asc?A.localeCompare(B):B.localeCompare(A); }).forEach(r=>tb.appendChild(r));}\n')
        out.write('  document.querySelectorAll("table").forEach(tbl=>Array.from(tbl.tHead.rows[0].cells).forEach((th,i)=>{let asc=true;th.addEventListener("click",()=>{sortTable(tbl,i,asc);asc=!asc;});}));\n')
        out.write('  toggleTimeFrame();\n')
        out.write('});\n')
        out.write('</script>\n')
        out.write('</head>\n<body>\n')
        out.write(f'<h1>League of Lads Season 18 Hero Report</h1><p>Generated: {report_time}</p>\n')
        # Timeframe selector
        out.write('<div class="timeframe-container"><label for="timeFrameSelect">Time Frame:</label>')
        out.write('<select id="timeFrameSelect">\n')
        out.write('<option value="all_time">All Time</option>\n')
        out.write('<option value="last_2_years">Last 2 Years</option>\n')
        out.write('<option value="last_9_months">Last 9 Months</option>\n')
        out.write('</select></div>\n')
        # Hero sections
        out.write('<div class="container">\n')
        for hid,lname in hero_list:
            img=id_to_key[hid]
            out.write(f'<div class="hero" id="hero_{hid}">\n')
            out.write(f'<h2>{lname}</h2>\n')
            out.write(f'<img src="https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{img}.png" alt="{lname}">\n')
            out.write(f'<button class="toggle" data-hero="{hid}">Show all</button>\n')
            for tf in TIME_FRAMES:
                stats=hero_stats[tf][hid]
                top5,rest=stats[:5],stats[5:]
                out.write(f'<table class="{tf}">\n<thead><tr><th>Player</th><th>Games</th><th>Wins</th><th>Win Rate</th><th>Score</th></tr></thead>\n<tbody>\n')
                for p in top5:
                    out.write(f'<tr><td>{p["name"]}</td><td>{p["games"]}</td><td>{p["wins"]}</td><td>{p["winrate"]:.2f}%</td><td>{p["score"]:.4f}</td></tr>\n')
                for p in rest:
                    out.write(f'<tr class="hidden"><td>{p["name"]}</td><td>{p["games"]}</td><td>{p["wins"]}</td><td>{p["winrate"]:.2f}%</td><td>{p["score"]:.4f}</td></tr>\n')
                out.write('</tbody>\n</table>\n')
            out.write('</div>\n')
        out.write('</div>\n')
        # Trophies summary with CSS tooltip
        out.write('<h2 style="text-align:center; margin-top:40px;">Top 5 Trophy Leaders ')
        out.write('<span class="tooltip">?')
        out.write('<span class="tooltiptext">Trophy points: 3 for 1st, 2 for 2nd, 1 for 3rd on each hero.</span>')
        out.write('</span></h2>\n')
        out.write('<table class="trophies">\n<thead><tr><th>Player</th><th>Trophy Points</th></tr></thead>\n<tbody>\n')
        for name,pts in sorted_trophies[:5]:
            out.write(f'<tr><td>{name}</td><td>{pts}</td></tr>\n')
        out.write('</tbody>\n</table>\n')
        # Footer
        out.write('</body>\n</html>')
    print(f"Report written to {args.output}")

if __name__=='__main__':
    main()

