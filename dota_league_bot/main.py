"""Entry point for manual testing of the Dota league bot services."""

from __future__ import annotations

from pprint import pprint

from .api_client import OpenDotaClient
from .config import BotConfig, LeagueConfig, OpenDotaConfig
from .league_service import LeagueService


def create_default_service() -> LeagueService:
    """Create a league service with default configuration placeholders."""

    config = BotConfig(
        opendota=OpenDotaConfig(api_key=None),
        league=LeagueConfig(league_id=None),
    )
    client = OpenDotaClient(config.opendota)
    return LeagueService(client=client, config=config)


def demo() -> None:
    """Demonstrate how the service could be invoked."""

    service = create_default_service()
    print("League overview placeholder (configure league_id before use):")
    try:
        pprint(service.get_league_overview())
    except ValueError as exc:
        print(f"Configuration error: {exc}")


if __name__ == "__main__":
    demo()
