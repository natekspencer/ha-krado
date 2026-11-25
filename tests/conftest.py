"""Fixtures for Krado tests."""

from __future__ import annotations

from collections.abc import Generator
import copy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.krado.const import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .common import MockConfigEntry, make_plant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def plants() -> list[dict[str, Any]]:
    """Return the plants the mocked API returns; tests may replace its contents."""
    return [make_plant("a"), make_plant("b", leaflet=False)]


@pytest.fixture
def mock_krado(plants: list[dict[str, Any]]) -> Generator[MagicMock]:
    """Mock the Krado client, returning a copy of `plants` on every poll."""
    with patch("custom_components.krado.Krado", autospec=True) as client_class:
        client = client_class.return_value
        client.query_plants = AsyncMock(side_effect=lambda: copy.deepcopy(plants))
        client.close = AsyncMock()
        yield client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a Krado config entry added to Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, title="Krado", data={CONF_TOKEN: "token"})
    entry.add_to_hass(hass)
    return entry
