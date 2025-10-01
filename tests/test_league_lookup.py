"""Utility script to locate a league ID on OpenDota by name."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dota_league_bot.api_client import OpenDotaClient, OpenDotaError
from dota_league_bot.config import OpenDotaConfig

TARGET_LEAGUE_NAME = "RD2L PST-SUN Season 36"


def find_leagues_by_name(name: str) -> List[Mapping[str, object]]:
    """Fetch OpenDota leagues and return those whose name matches ``name``.

    Args:
        name: League name to search for. The match is case-insensitive and
            ignores leading/trailing whitespace.

    Returns:
        A list of league metadata dictionaries whose ``name`` field matches the
        requested value.
    """

    normalized_target = name.strip().casefold()

    client = OpenDotaClient(OpenDotaConfig())
    try:
        leagues: Iterable[Mapping[str, object]] = client.get("leagues")
    except OpenDotaError as exc:
        print(f"Failed to fetch leagues from OpenDota: {exc}")
        return []

    return [
        league
        for league in leagues
        if str(league.get("name", "")).strip().casefold() == normalized_target
    ]


def main() -> None:
    matches = find_leagues_by_name(TARGET_LEAGUE_NAME)
    if not matches:
        print(f"No leagues found matching: {TARGET_LEAGUE_NAME}")
        return

    for league in matches:
        league_id = league.get("leagueid")
        tier = league.get("tier")
        print(f"Found league: id={league_id}, name={league.get('name')}, tier={tier}")


if __name__ == "__main__":
    main()
