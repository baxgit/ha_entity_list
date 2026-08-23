"""The Entity List integration."""
from __future__ import annotations

import uuid

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LIST_ID,
    CONF_LIST_TYPE,
    CONF_NAME,
    CONF_NOTIFY_TARGETS,
    CONF_SORT_ORDER,
    DEFAULT_NOTIFY_ON_CREATE,
    DEFAULT_SORT_ORDER,
    DOMAIN,
    EVENT_ITEM_CREATED,
    ISSUE_STALE_NOTIFY_TARGET,
    LIST_TYPE_ALERT,
    NOTIFY_APP,
    NOTIFY_NONE,
    NOTIFY_OPTIONS,
    NOTIFY_PERSISTENT,
    PLATFORMS,
    SIGNAL_LIST_UPDATED,
    STATUS_ACTIVE,
    STATUS_CLEARED,
    STATUS_NEW,
)
from .helpers import (
    effective_config,
    effective_max_size,
    enforce_max_size,
    resolve_list_id,
    sort_items,
)
from .storage import EntityListStorage

ADD_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LIST_ID): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("type"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("url"): cv.string,
        vol.Optional("high_priority", default=False): cv.boolean,
        vol.Optional("notify_on_create", default=DEFAULT_NOTIFY_ON_CREATE): vol.In(
            NOTIFY_OPTIONS
        ),
    }
)

ITEM_NAME_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LIST_ID): cv.string,
        vol.Required("item_name"): cv.string,
    }
)

LIST_ID_SCHEMA = vol.Schema({vol.Required(CONF_LIST_ID): cv.string})

CLEAR_ALERT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LIST_ID): cv.string,
        vol.Required("item_name"): cv.string,
        vol.Optional("description"): cv.string,
    }
)

UPDATE_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LIST_ID): cv.string,
        vol.Required("item_name"): cv.string,
        vol.Optional("type"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("url"): cv.string,
        vol.Optional("high_priority"): cv.boolean,
    }
)


def _signal(list_id: str) -> str:
    return SIGNAL_LIST_UPDATED.format(list_id=list_id)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Entity List integration and register its services."""
    hass.data.setdefault(DOMAIN, {"entries": {}})
    storage = EntityListStorage(hass)
    await storage.load()
    hass.data[DOMAIN]["storage"] = storage

    def _get_list(list_id: str) -> dict:
        lst = storage.data.get(list_id)
        if lst is None:
            raise HomeAssistantError(f"Entity List '{list_id}' was not found")
        return lst

    def _get_entry(list_id: str) -> ConfigEntry:
        entry = hass.data[DOMAIN]["entries"].get(list_id)
        if entry is None:
            raise HomeAssistantError(f"Entity List '{list_id}' was not found")
        return entry

    async def _send_alert_notification(config: dict, item: dict) -> None:
        title = config[CONF_NAME]
        if item.get("high_priority"):
            title = f"⚠ High priority — {title}"

        message = item["name"]
        if item.get("type"):
            message = f"{message} ({item['type']})"
        if item.get("description"):
            message = f"{message}\n{item['description']}"

        mode = item["notify_on_create"]

        if mode == NOTIFY_PERSISTENT:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": f"{DOMAIN}_{config[CONF_LIST_ID]}_{item['id']}",
                },
            )
        elif mode == NOTIFY_APP:
            for target in config.get(CONF_NOTIFY_TARGETS, []):
                issue_id = f"{ISSUE_STALE_NOTIFY_TARGET}_{config[CONF_LIST_ID]}_{target}"

                if hass.states.get(target) is None:
                    ir.async_create_issue(
                        hass,
                        DOMAIN,
                        issue_id,
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key=ISSUE_STALE_NOTIFY_TARGET,
                        translation_placeholders={
                            "target": target,
                            "list_name": config[CONF_NAME],
                        },
                    )
                    continue

                ir.async_delete_issue(hass, DOMAIN, issue_id)
                await hass.services.async_call(
                    "notify",
                    "send_message",
                    {"entity_id": target, "title": title, "message": message},
                )

    async def add_item(call: ServiceCall) -> None:
        list_id = resolve_list_id(hass, call.data[CONF_LIST_ID])
        if list_id is None:
            raise HomeAssistantError(f"Unknown entity list: {call.data[CONF_LIST_ID]}")
        lst = _get_list(list_id)
        entry = _get_entry(list_id)
        config = effective_config(entry)
        list_type = config[CONF_LIST_TYPE]

        name = call.data["name"].strip()
        new_item = {
            "id": str(uuid.uuid4()),
            "name": name,
            "type": call.data.get("type"),
            "description": call.data.get("description"),
            "url": call.data.get("url"),
            "created": dt_util.utcnow().isoformat(),
        }

        if list_type == LIST_TYPE_ALERT:
            new_item.update(
                {
                    "status": STATUS_NEW,
                    "high_priority": call.data.get("high_priority", False),
                    "notify_on_create": call.data.get(
                        "notify_on_create", DEFAULT_NOTIFY_ON_CREATE
                    ),
                    "cleared_at": None,
                }
            )

        for idx, item in enumerate(lst["items"]):
            if item["name"].strip().lower() == name.lower():
                lst["items"][idx] = new_item
                break
        else:
            lst["items"].append(new_item)

        lst["items"] = enforce_max_size(lst["items"], effective_max_size(hass, config))
        lst["items"] = sort_items(
            lst["items"], config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER)
        )
        await storage.save()

        hass.bus.async_fire(
            EVENT_ITEM_CREATED,
            {
                "list_id": list_id,
                "list_name": config[CONF_NAME],
                "list_type": list_type,
                "item": new_item,
            },
        )

        if list_type == LIST_TYPE_ALERT and new_item["notify_on_create"] != NOTIFY_NONE:
            await _send_alert_notification(config, new_item)

        async_dispatcher_send(hass, _signal(list_id))

    async def remove_item(call: ServiceCall) -> None:
        list_id = resolve_list_id(hass, call.data[CONF_LIST_ID])
        if list_id is None:
            raise HomeAssistantError(f"Unknown entity list: {call.data[CONF_LIST_ID]}")
        lst = _get_list(list_id)
        entry = _get_entry(list_id)
        config = effective_config(entry)
        item_name_input = call.data["item_name"].strip().lower()

        lst["items"] = [
            item
            for item in lst["items"]
            if item.get("name", "").strip().lower() != item_name_input
        ]
        lst["items"] = sort_items(
            lst["items"], config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER)
        )
        await storage.save()
        async_dispatcher_send(hass, _signal(list_id))

    async def reset_list(call: ServiceCall) -> None:
        list_id = resolve_list_id(hass, call.data[CONF_LIST_ID])
        if list_id is None:
            raise HomeAssistantError(f"Unknown entity list: {call.data[CONF_LIST_ID]}")
        lst = _get_list(list_id)

        lst["items"] = []
        await storage.save()
        async_dispatcher_send(hass, _signal(list_id))

    async def acknowledge_new_item(call: ServiceCall) -> None:
        list_id = resolve_list_id(hass, call.data[CONF_LIST_ID])
        if list_id is None:
            raise HomeAssistantError(f"Unknown entity list: {call.data[CONF_LIST_ID]}")
        lst = _get_list(list_id)
        entry = _get_entry(list_id)
        config = effective_config(entry)

        if config[CONF_LIST_TYPE] != LIST_TYPE_ALERT:
            raise HomeAssistantError(
                "acknowledge_new_item is only supported on alert-type lists"
            )

        item_name_input = call.data["item_name"].strip().lower()
        updated = False
        new_items = []
        for item in lst["items"]:
            if item.get("name", "").strip().lower() == item_name_input:
                if item.get("status") == STATUS_NEW:
                    item = item.copy()
                    item["status"] = STATUS_ACTIVE
                    updated = True
            new_items.append(item)

        if updated:
            lst["items"] = sort_items(
                new_items, config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER)
            )
            await storage.save()
            async_dispatcher_send(hass, _signal(list_id))

    async def clear_active_alert(call: ServiceCall) -> None:
        list_id = resolve_list_id(hass, call.data[CONF_LIST_ID])
        if list_id is None:
            raise HomeAssistantError(f"Unknown entity list: {call.data[CONF_LIST_ID]}")
        lst = _get_list(list_id)
        entry = _get_entry(list_id)
        config = effective_config(entry)

        if config[CONF_LIST_TYPE] != LIST_TYPE_ALERT:
            raise HomeAssistantError(
                "clear_active_alert is only supported on alert-type lists"
            )

        item_name_input = call.data["item_name"].strip().lower()
        updated = False
        new_items = []
        for item in lst["items"]:
            if item.get("name", "").strip().lower() == item_name_input:
                if item.get("status") in (STATUS_NEW, STATUS_ACTIVE):
                    item = item.copy()
                    item["status"] = STATUS_CLEARED
                    item["cleared_at"] = dt_util.utcnow().isoformat()
                    if "description" in call.data:
                        item["description"] = call.data["description"]
                    updated = True
            new_items.append(item)

        if updated:
            lst["items"] = sort_items(
                new_items, config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER)
            )
            await storage.save()
            async_dispatcher_send(hass, _signal(list_id))

    async def update_item(call: ServiceCall) -> None:
        list_id = resolve_list_id(hass, call.data[CONF_LIST_ID])
        if list_id is None:
            raise HomeAssistantError(f"Unknown entity list: {call.data[CONF_LIST_ID]}")
        lst = _get_list(list_id)
        entry = _get_entry(list_id)
        config = effective_config(entry)
        list_type = config[CONF_LIST_TYPE]

        item_name_input = call.data["item_name"].strip().lower()
        updated = False
        new_items = []
        for item in lst["items"]:
            if item.get("name", "").strip().lower() == item_name_input:
                item = item.copy()
                if "type" in call.data:
                    item["type"] = call.data["type"]
                if "description" in call.data:
                    item["description"] = call.data["description"]
                if "url" in call.data:
                    item["url"] = call.data["url"]
                if list_type == LIST_TYPE_ALERT and "high_priority" in call.data:
                    item["high_priority"] = call.data["high_priority"]
                updated = True
            new_items.append(item)

        if updated:
            lst["items"] = sort_items(
                new_items, config.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER)
            )
            await storage.save()
            async_dispatcher_send(hass, _signal(list_id))

    hass.services.async_register(DOMAIN, "add_item", add_item, schema=ADD_ITEM_SCHEMA)
    hass.services.async_register(
        DOMAIN, "remove_item", remove_item, schema=ITEM_NAME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "reset_list", reset_list, schema=LIST_ID_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "acknowledge_new_item",
        acknowledge_new_item,
        schema=ITEM_NAME_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, "clear_active_alert", clear_active_alert, schema=CLEAR_ALERT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "update_item", update_item, schema=UPDATE_ITEM_SCHEMA
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Push a state refresh when a list's options are changed."""
    list_id = entry.data[CONF_LIST_ID]
    async_dispatcher_send(hass, _signal(list_id))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Entity List from a config entry."""
    storage: EntityListStorage = hass.data[DOMAIN]["storage"]
    list_id = entry.data[CONF_LIST_ID]

    storage.data.setdefault(list_id, {"items": []})
    await storage.save()

    hass.data[DOMAIN]["entries"][list_id] = entry
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry (integration reload/disable, not deletion)."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN]["entries"].pop(entry.data[CONF_LIST_ID], None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry to the current version.

    No-op today: entry.data.VERSION is still 1, and the fields added since
    (item description, max_size, max_size_entity) are all optional and
    read with .get()-style defaults, so existing entries keep working
    unmodified. Kept as a ready landing spot for the next time the config
    entry's data shape needs an actual migration.
    """
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up stored items when a list is fully removed."""
    storage: EntityListStorage = hass.data[DOMAIN]["storage"]
    storage.data.pop(entry.data[CONF_LIST_ID], None)
    await storage.save()
