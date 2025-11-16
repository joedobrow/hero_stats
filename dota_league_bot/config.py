"""Configuration objects and helpers for the Dota league bot project."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OpenDotaConfig:
    """Configuration for accessing the OpenDota API."""

    base_url: str = "https://api.opendota.com/api"
    api_key: Optional[str] = None


@dataclass
class LeagueConfig:
    """Metadata about the league we want to track."""

    league_id: Optional[int] = None


@dataclass
class BotConfig:
    """Aggregate configuration for the bot."""

    opendota: OpenDotaConfig = field(default_factory=OpenDotaConfig)
    league: LeagueConfig = field(default_factory=LeagueConfig)
