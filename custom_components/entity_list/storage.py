"""Persistent storage for the Entity List integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

STORAGE_VERSION = 1
STORAGE_KEY = "entity_list.storage"


class EntityListStorage:
    """Wraps a single HA Store holding all lists, keyed by list_id."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, dict] = {}

    async def load(self) -> None:
        self.data = await self.store.async_load() or {}

    async def save(self) -> None:
        await self.store.async_save(self.data)
