"""Business logic for fetching and shaping league data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .api_client import OpenDotaClient
from .config import BotConfig


@dataclass
class LeagueService:
    """High-level operations for retrieving league data."""

    client: OpenDotaClient
    config: BotConfig

    def get_league_overview(self) -> Dict[str, Any]:
        """Return metadata for the configured league.

        Raises:
            ValueError: If the league id is not configured.
        """

        league_id = self._require_league_id()
        return self.client.get_league(league_id)

    def get_recent_matches(self, *, limit: Optional[int] = 20) -> List[Dict[str, Any]]:
        """Return recent matches for the configured league."""

        league_id = self._require_league_id()
        matches = self.client.get_league_matches(league_id, limit=limit)
        return list(matches)

    def _require_league_id(self) -> int:
        league_id = self.config.league.league_id
        if league_id is None:
            raise ValueError("League ID has not been configured yet.")
        return league_id
