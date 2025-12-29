#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL_HS = "https://windrun.io/ability-high-skill"
URL_BY_HERO = "https://windrun.io/ability-by-hero"

HEADERS = {
    "User-Agent": "AD-Builder/2.1 (+github.com/you)",
    "Accept": "text/html,application/xhtml+xml",
}

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "ability_high_skill.json"

_num = re.compile(r"[-+]?\d*\.?\d+")

def _first_match_float(text: str, pat: str) -> Optional[float]:
    m = re.search(pat, text, re.IGNORECASE)
    return float(m.group(1)) if m else None

def _to_float(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.replace(",", "")
    m = _num.search(s)
    return float(m.group(0)) if m else None


def _abs(base: str, maybe_url: Optional[str]) -> Optional[str]:
    return urljoin(base, maybe_url) if maybe_url else None


def _parse_id_from_href(href: str, prefix: str) -> Optional[int]:
    # Works for relative or absolute URLs
    if not href:
        return None
    m = re.search(re.escape(prefix) + r"(\d+)", href)
    return int(m.group(1)) if m else None


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text


def _pick_table_with_text(soup: BeautifulSoup, must_contain: str) -> Optional[Any]:
    must = must_contain.lower()
    best = None
    best_score = -1
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True).lower()
        score = 0
        if must in txt:
            score += 3
        if t.find("a", href=re.compile(r"/abilities/\d+")):
            score += 2
        if t.find("a", href=re.compile(r"/heroes/\d+")):
            score += 1
        if score > best_score:
            best_score = score
            best = t
    return best if best_score >= 3 else None

def parse_hs_table(html: str) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Returns:
      hs_abilities: ability_id (>0) -> {ability_id, ability_name, img, win_pct, pick_num}
      hs_models:   hero_name -> {model_ability_id (<0), hero_name, img, win_pct, pick_num}
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise RuntimeError("Could not find table on ability-high-skill page")

    thead = table.find("thead")
    if not thead:
        raise RuntimeError("No thead found")
    headers = [th.get_text(strip=True) for th in thead.find_all("th")]
    header_idx = {h: i for i, h in enumerate(headers)}

    def find_col(name_contains: str) -> int:
        name_l = name_contains.lower()
        for h, i in header_idx.items():
            if name_l in h.lower():
                return i
        raise RuntimeError(f"Header containing '{name_contains}' not found. Got: {headers}")

    win_idx = find_col("HS Win %")
    pick_idx = find_col("HS Pick #")

    tbody = table.find("tbody") or table

    hs_abilities: Dict[int, Dict[str, Any]] = {}
    hs_models: Dict[str, Dict[str, Any]] = {}

    for tr in tbody.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) <= max(win_idx, pick_idx):
            continue

        # HS page links are /abilities/<id>, where hero models use negative IDs (e.g. /abilities/-35). :contentReference[oaicite:1]{index=1}
        link = tr.find("a", href=re.compile(r"^/abilities/-?\d+"))
        if not link:
            continue

        href = link.get("href", "")
        name = link.get_text(" ", strip=True)
        if not name:
            continue

        m = re.search(r"^/abilities/(-?\d+)$", href)
        if not m:
            continue
        abil_id = int(m.group(1))

        img_tag = tr.find("img")
        img = _abs(URL_HS, img_tag.get("src")) if img_tag else None

        win_pct = _to_float(tds[win_idx].get_text(strip=True))
        pick_num = _to_float(tds[pick_idx].get_text(strip=True))

        if abil_id < 0:
            # hero model row keyed by hero name
            hs_models[name] = {
                "model_ability_id": abil_id,
                "hero_name": name,
                "img": img,
                "win_pct": win_pct,
                "pick_num": pick_num,
            }
        else:
            hs_abilities[abil_id] = {
                "ability_id": abil_id,
                "ability_name": name,
                "img": img,
                "win_pct": win_pct,
                "pick_num": pick_num,
            }

    if not hs_abilities:
        raise RuntimeError("Parsed zero HS abilities; page structure may have changed.")
    return hs_abilities, hs_models

def _pick_data_table_byhero(soup: BeautifulSoup) -> Optional[Any]:
    # ability-by-hero may or may not be a table; if it is, pick the one with both hero and ability links
    best = None
    best_score = -1
    for t in soup.find_all("table"):
        score = 0
        if t.find("a", href=re.compile(r"/heroes/\d+")):
            score += 2
        if t.find("a", href=re.compile(r"/abilities/\d+")):
            score += 2
        if "body winrate" in t.get_text(" ", strip=True).lower():
            score += 1
        if score > best_score:
            best_score = score
            best = t
    return best if best_score >= 3 else None


def _nearest_prev_img_within(container, a_tag, base_url: str) -> Optional[str]:
    last_img = None
    for el in container.descendants:
        if getattr(el, "name", None) == "img":
            last_img = el
        if el is a_tag:
            break
    return _abs(base_url, last_img.get("src")) if last_img else None


def parse_by_hero(html: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse windrun ability-by-hero where each hero section contains multiple ability blocks in the same cell.
    Uses a linear scan inside the correct table to associate abilities with the most recent hero link.
    """
    BASE = URL_BY_HERO
    soup = BeautifulSoup(html, "html.parser")

    table = _pick_data_table_byhero(soup)
    if not table:
        raise RuntimeError("Could not find the data table on ability-by-hero page.")

    heroes: Dict[str, Dict[str, Any]] = {}
    current_hero: Optional[str] = None

    # Only scan within the data table (avoids nav/footer hero links)
    links = table.find_all("a", href=re.compile(r"^/(heroes|abilities)/\d+"))

    for link in links:
        href = link.get("href", "")
        text = link.get_text(" ", strip=True)

        if href.startswith("/heroes/"):
            hero_id = _parse_id_from_href(href, "/heroes/")
            hero_name = text
            hero_td = link.find_parent("td")
            hero_img = None
            if hero_td:
                pic_td = hero_td.find_previous_sibling("td", class_="hero-picture")
                img_tag = (pic_td.find("img") if pic_td else None) or hero_td.find("img")
                hero_img = img_tag.get("src") if img_tag else None
                if not hero_id or not hero_name:
                    continue

            current_hero = hero_name

            # body winrate is usually in the same hero <td>
            hero_td = link.find_parent("td")
            hero_td_text = hero_td.get_text(" ", strip=True) if hero_td else ""
            m = re.search(r"(\d+(?:\.\d+)?)%\s*body winrate", hero_td_text, re.IGNORECASE)
            body_winrate = float(m.group(1)) if m else None

            if current_hero not in heroes:
                heroes[current_hero] = {
                    "hero_id": hero_id,
                    "hero_img": hero_img,
                    "body_winrate": body_winrate,
                    "abilities": [],
                }
            else:
                # fill any missing basics
                heroes[current_hero]["hero_id"] = heroes[current_hero].get("hero_id") or hero_id
                heroes[current_hero]["body_winrate"] = heroes[current_hero].get("body_winrate") or body_winrate
                if not heroes[current_hero].get("hero_img"):
                    heroes[current_hero]["hero_img"] = hero_img

            continue

        # ability link
        if not current_hero:
            continue  # ignore abilities before we see the first hero

        ability_id = _parse_id_from_href(href, "/abilities/")
        ability_name = text
        if not ability_id or not ability_name:
            continue

        # ability stats live in the enclosing block (often a <span> that contains the img + link + numbers)
        block = link.find_parent("span") or link.parent
        block_text = block.get_text(" ", strip=True) if block else ""

        # anchored stats after this ability name (safer than grabbing random numbers)
        pat = re.escape(ability_name) + r".*?(\d+(?:\.\d+)?)%\s*win%.*?/\s*(\d+(?:\.\d+)?)\s*avg pick"
        m = re.search(pat, block_text, re.IGNORECASE)
        if m:
            win_pct = float(m.group(1))
            pick_num = float(m.group(2))
        else:
            win_pct = _first_match_float(block_text, r"(\d+(?:\.\d+)?)%\s*win%")
            pick_num = _first_match_float(block_text, r"/\s*(\d+(?:\.\d+)?)\s*avg pick")

        # ability img is typically right before the link inside the same block
        img = _nearest_prev_img_within(block or link.parent, link, BASE)

        # dedupe
        existing = {a.get("ability_id") for a in heroes[current_hero]["abilities"]}
        if ability_id in existing:
            continue

        heroes[current_hero]["abilities"].append({
            "ability_id": ability_id,
            "ability_name": ability_name,
            "img": img,
            "win_pct": win_pct,
            "pick_num": pick_num,
        })

    # keep only heroes that ended up with abilities
    heroes = {h: v for h, v in heroes.items() if v.get("abilities")}

    if not heroes:
        hero_links_total = len(table.find_all("a", href=re.compile(r"^/heroes/\d+")))
        ability_links_total = len(table.find_all("a", href=re.compile(r"^/abilities/\d+")))
        raise RuntimeError(f"Parsed zero heroes. hero_links_total={hero_links_total} ability_links_total={ability_links_total}")

    return heroes

def combine(
    heroes: Dict[str, Dict[str, Any]],
    hs_abilities: Dict[int, Dict[str, Any]],
    hs_models: Dict[int, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Final shape:
      data[HeroName] = {hero_id, hero_img, win_pct, pick_num, body_winrate, abilities:[{ability_id, ability_name, img, win_pct, pick_num}]}
    """
    out: Dict[str, Dict[str, Any]] = {}

    for hero_name, h in heroes.items():
        hero_id = h.get("hero_id")
        hs_m = hs_models.get(hero_name)

        abil_list = []
        for a in h.get("abilities", []) or []:
            aid = a.get("ability_id")
            hs_a = hs_abilities.get(aid) if isinstance(aid, int) else None

            abil_list.append(
                {
                    "ability_id": aid,
                    "ability_name": (hs_a.get("ability_name") if hs_a else a.get("ability_name")),
                    "img": (a.get("img") or (hs_a.get("img") if hs_a else None)),
                    "win_pct": (hs_a.get("win_pct") if hs_a else None),
                    "pick_num": (hs_a.get("pick_num") if hs_a else None),
                }
            )

            out[hero_name] = {
              "hero_id": hero_id,
              "hero_img": h.get("hero_img"),
              "body_winrate": h.get("body_winrate"),
              "win_pct": (hs_m.get("win_pct") if hs_m else None) or h.get("body_winrate"),
              "pick_num": (hs_m.get("pick_num") if hs_m else None),
              "abilities": abil_list,
            }
    return out


def save_cache(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": {"hs": URL_HS, "by_hero": URL_BY_HERO},
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    print("NOTE SOME ABILITIES MIGHT BE MISSING FROM HEROES, GO CHECK grimstroke (probably) for a dump of all the new abilities. You will need to manually enter them into the cache/ability_high_skill.json.")
    print("Fetching pages...")
    hs_html = fetch_html(URL_HS)
    byhero_html = fetch_html(URL_BY_HERO)
    Path("byhero_debug.html").write_text(byhero_html, encoding="utf-8")
    print("Wrote byhero_debug.html")

    print("Parsing HS...")
    hs_abilities, hs_models = parse_hs_table(hs_html)
    print(f"  HS abilities: {len(hs_abilities)} | HS hero-model rows: {len(hs_models)}")

    print("Parsing By-Hero...")
    heroes = parse_by_hero(byhero_html)
    first = next(iter(heroes.items()))
    print("Sample hero:", first[0], "abilities:", len(first[1]["abilities"]))
    print("First ability:", first[1]["abilities"][0])
    print(f"  Heroes parsed: {len(heroes)}")

    print("Combining + writing cache...")
    combined = combine(heroes, hs_abilities, hs_models)
    save_cache(combined)

    print(f"Saved {len(combined)} heroes -> {CACHE_FILE}")


if __name__ == "__main__":
    main()

