"""HTTP client utilities for communicating with the OpenDota API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional

import requests

from .config import OpenDotaConfig


class OpenDotaError(RuntimeError):
    """Raised when the OpenDota API returns an error response."""


@dataclass
class OpenDotaClient:
    """Lightweight OpenDota API client."""

    config: OpenDotaConfig

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        """Perform a GET request against the OpenDota API.

        Args:
            path: API path, e.g. "/leagues" or "/leagues/{league_id}".
            params: Optional query parameters to include in the request.

        Returns:
            Parsed JSON response.

        Raises:
            OpenDotaError: If the request fails or returns a non-200 status.
        """

        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = self._build_headers()
        with requests.Session() as session:
            session.trust_env = False
            try:
                response = session.get(
                    url, headers=headers, params=params, timeout=30
                )
            except requests.RequestException as exc:  # pragma: no cover - network failure
                raise OpenDotaError(
                    f"OpenDota API request failed: {exc}"
                ) from exc
        if response.status_code >= 400:
            raise OpenDotaError(
                f"OpenDota API request failed with status {response.status_code}: {response.text}"
            )
        return response.json()

    def get_league(self, league_id: int) -> MutableMapping[str, Any]:
        """Fetch metadata for a specific league."""

        return self.get(f"leagues/{league_id}")

    def get_league_matches(
        self, league_id: int, *, limit: Optional[int] = None
    ) -> Any:
        """Fetch matches for a league.

        Args:
            league_id: Target league identifier.
            limit: Optional maximum number of matches to return.
        """

        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        return self.get(f"leagues/{league_id}/matches", params=params)

    def get_team(self, team_id: int) -> MutableMapping[str, Any]:
        """Fetch details for a Dota team."""

        return self.get(f"teams/{team_id}")
