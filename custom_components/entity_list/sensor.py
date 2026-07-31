"""Sensor platform for the Entity List integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DESCRIPTION,
    CONF_LIST_ID,
    CONF_LIST_TYPE,
    CONF_NAME,
    CONF_NOTIFY_TARGETS,
    CONF_SORT_ORDER,
    DEFAULT_SORT_ORDER,
    DOMAIN,
    LIST_TYPE_ALERT,
    SIGNAL_LIST_UPDATED,
    STATUS_ACTIVE,
    STATUS_CLEARED,
    STATUS_NEW,
)
from .helpers import effective_config, effective_max_size, sort_items


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EntityListSensor(hass, entry)])


class EntityListSensor(SensorEntity):
    """Represents a single Entity List as a sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self.list_id = entry.data[CONF_LIST_ID]
        self._attr_unique_id = f"{DOMAIN}_{self.list_id}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_LIST_UPDATED.format(list_id=self.list_id),
                self.async_write_ha_state,
            )
        )

    @property
    def _config(self) -> dict:
        return effective_config(self._entry)

    @property
    def _items(self) -> list[dict]:
        lst = self.hass.data[DOMAIN]["storage"].data.get(self.list_id)
        if lst is None:
            return []
        config = self._config
        return sort_items(
            [item.copy() for item in lst["items"]],
            config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER),
        )

    @property
    def name(self) -> str:
        return self._config[CONF_NAME]

    @property
    def icon(self) -> str:
        return (
            "mdi:alert-box-outline"
            if self._config[CONF_LIST_TYPE] == LIST_TYPE_ALERT
            else "mdi:format-list-bulleted"
        )

    @property
    def available(self) -> bool:
        return self.list_id in self.hass.data[DOMAIN]["storage"].data

    @property
    def state(self) -> int:
        items = self._items
        config = self._config

        if config[CONF_LIST_TYPE] == LIST_TYPE_ALERT:
            return sum(
                1 for item in items if item.get("status") in (STATUS_NEW, STATUS_ACTIVE)
            )
        return len(items)

    @property
    def extra_state_attributes(self) -> dict:
        items = self._items
        config = self._config
        attrs = {
            "list_type": config[CONF_LIST_TYPE],
            "description": config.get(CONF_DESCRIPTION, ""),
            "sort_order": config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER),
            "item_count": len(items),
            "max_size": effective_max_size(self.hass, config),
            "items": items,
        }

        if config[CONF_LIST_TYPE] == LIST_TYPE_ALERT:
            attrs["notify_targets"] = config.get(CONF_NOTIFY_TARGETS, [])
            attrs["new_count"] = sum(
                1 for item in items if item.get("status") == STATUS_NEW
            )
            attrs["active_count"] = sum(
                1 for item in items if item.get("status") in (STATUS_NEW, STATUS_ACTIVE)
            )
            attrs["cleared_count"] = sum(
                1 for item in items if item.get("status") == STATUS_CLEARED
            )

        return attrs
