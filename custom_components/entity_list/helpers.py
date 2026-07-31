"""Shared helpers for the Entity List integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_MAX_SIZE,
    CONF_MAX_SIZE_ENTITY,
    DOMAIN,
    SORT_NEWEST_FIRST,
    SORT_OLDEST_FIRST,
    SORT_STATUS,
    STATUS_PRIORITY,
)


def effective_config(entry: ConfigEntry) -> dict:
    """Return a list's effective configuration.

    entry.data holds the values fixed at creation time (list_id, list_type,
    plus the original name/description/sort_order/notify_targets).
    entry.options holds only the keys the user has since changed via the
    options flow. Merging them here means the config entry is always the
    single source of truth for list metadata - storage only ever holds items.
    """
    return {**entry.data, **entry.options}


def sort_items(items: list[dict], sort_order: str) -> list[dict]:
    """Sort a list of items based on the selected sort order.

    Falls back to leaving the list untouched for unknown sort orders,
    so a bad/legacy value never raises.
    """
    if sort_order == SORT_NEWEST_FIRST:
        return sorted(items, key=lambda x: x["created"], reverse=True)

    if sort_order == SORT_OLDEST_FIRST:
        return sorted(items, key=lambda x: x["created"])

    if sort_order == SORT_STATUS:
        return sorted(
            items,
            key=lambda x: (
                STATUS_PRIORITY.get(x.get("status"), 99),
                x["created"],
            ),
            reverse=False,
        )

    return items


def effective_max_size(hass: HomeAssistant, config: dict) -> int | None:
    """Resolve the effective max list size, or None if unlimited.

    An entity reference (CONF_MAX_SIZE_ENTITY) takes priority over a fixed
    number (CONF_MAX_SIZE) when both are somehow set, since the entity is
    the more dynamic/intentional choice. Missing, unavailable, or
    non-numeric entity states are treated as "unlimited" rather than
    raising, so a temporarily unavailable input_number doesn't block adding
    items.
    """
    entity_id = config.get(CONF_MAX_SIZE_ENTITY)
    if entity_id:
        state = hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            value = int(float(state.state))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    max_size = config.get(CONF_MAX_SIZE)
    if max_size:
        return int(max_size)

    return None


def enforce_max_size(items: list[dict], max_size: int | None) -> list[dict]:
    """Drop the oldest items (by creation time) once max_size is exceeded.

    "Oldest" is always based on the `created` timestamp, independent of the
    list's configured sort_order, so the eviction behavior doesn't change
    if the user later switches how the list is displayed.
    """
    if max_size is None or max_size <= 0 or len(items) <= max_size:
        return items

    oldest_first = sorted(items, key=lambda x: x["created"])
    drop_ids = {item["id"] for item in oldest_first[: len(items) - max_size]}
    return [item for item in items if item["id"] not in drop_ids]


def resolve_list_id(hass: HomeAssistant, list_id_or_entity_id: str) -> str | None:
    """Resolve a service-call 'list_id' field to a storage list_id.

    The entity selector in services.yaml supplies an entity_id (e.g.
    'sensor.groceries'). Because the entity_id a user sees can be renamed
    at any time via the entity registry, we never parse the entity_id
    string itself. Instead we look up the entity's registry entry and
    read its unique_id, which we control and which never changes.

    Also accepts a raw list_id directly (no dot) for convenience/back-compat,
    e.g. when called from a script with a hardcoded id.
    """
    if "." not in list_id_or_entity_id:
        return list_id_or_entity_id

    registry = er.async_get(hass)
    entry = registry.async_get(list_id_or_entity_id)
    if entry is None or entry.unique_id is None:
        return None

    prefix = f"{DOMAIN}_"
    if not entry.unique_id.startswith(prefix):
        return None

    return entry.unique_id[len(prefix):]
