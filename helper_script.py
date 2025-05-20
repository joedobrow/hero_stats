import csv
import json
import re

def slugify(name):
    return re.sub(r'\W+', '_', name.strip().lower()).strip('_')

def parse_teams(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    teams = {}
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell == 'Position' and c+1 < len(row) and row[c+1].strip():
                key = slugify(row[c+1])
                players = []
                for pr in rows[r+1:r+6]:
                    name = pr[c+1].strip()
                    if name:
                        players.append(name.lower())
                teams[key] = players
    return teams

if __name__ == '__main__':
    teams = parse_teams('teams.csv')

    # alphabetize each player list
    for key in teams:
        teams[key].sort()

    # write out with alphabetized team keys
    with open('teams.json', 'w', encoding='utf-8') as out:
        json.dump(teams, out, indent=2, sort_keys=True)

    print("wrote alphabetical teams.json with", len(teams), "teams")

