#!/usr/bin/env python3
import json, time, re
from pathlib import Path
from typing import Optional
import requests
from bs4 import BeautifulSoup

URL = "https://windrun.io/ability-high-skill"
HEADERS = {
    "User-Agent": "AD-Builder/1.2 (+github.com/you)",
    "Accept": "text/html,application/xhtml+xml",
}

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "ability_high_skill.json"

_num = re.compile(r"[-+]?\d*\.?\d+")

def _to_float(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.replace(",", "")
    m = _num.search(s)
    return float(m.group(0)) if m else None

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text

def parse_table(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise RuntimeError("Could not find table on ability-high-skill page")

    # headers
    thead = table.find("thead")
    if not thead:
        raise RuntimeError("No thead found")
    headers = [th.get_text(strip=True) for th in thead.find_all("th")]
    header_idx = {h: i for i, h in enumerate(headers)}

    # find needed columns by name (case-insensitive contains)
    def find_col(name_contains: str) -> int:
        name_l = name_contains.lower()
        for h, i in header_idx.items():
            if name_l in h.lower():
                return i
        raise RuntimeError(f"Header containing '{name_contains}' not found. Got: {headers}")

    # Ability name column
    ability_idx = find_col("Ability")
    # Exact columns requested
    win_idx = find_col("HS Win %")
    pick_idx = find_col("HS Pick #")

    # rows
    tbody = table.find("tbody") or table
    out = {}
    for tr in tbody.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) <= max(ability_idx, win_idx, pick_idx):
            continue

        ability = tds[ability_idx].get_text(" ", strip=True)
        if not ability:
            continue

        win_pct = _to_float(tds[win_idx].get_text(strip=True))
        pick_num = _to_float(tds[pick_idx].get_text(strip=True))

        # keep only rows with a name; numbers can be None if missing
        out[ability] = {"win_pct": win_pct, "pick_num": pick_num}

    if not out:
        raise RuntimeError("Parsed zero abilities; page structure may have changed.")
    return out

def save_cache(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": URL,
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def main():
    html = fetch_html(URL)
    data = parse_table(html)
    save_cache(data)
    print(f"Saved {len(data)} abilities -> {CACHE_FILE}")

if __name__ == "__main__":
    main()

