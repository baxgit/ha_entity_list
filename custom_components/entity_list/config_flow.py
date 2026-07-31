"""Config flow for the Entity List integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_DESCRIPTION,
    CONF_LIST_ID,
    CONF_LIST_TYPE,
    CONF_MAX_SIZE,
    CONF_MAX_SIZE_ENTITY,
    CONF_NAME,
    CONF_NOTIFY_TARGETS,
    CONF_SORT_ORDER,
    DEFAULT_SORT_ORDER,
    DOMAIN,
    LIST_TYPE_ALERT,
    LIST_TYPE_STANDARD,
    MAX_NOTIFY_TARGETS,
    MAX_SIZE_ENTITY_DOMAINS,
    SORT_ORDERS,
)


def _list_type_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[LIST_TYPE_STANDARD, LIST_TYPE_ALERT],
            translation_key=CONF_LIST_TYPE,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


def _sort_order_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SORT_ORDERS,
            translation_key=CONF_SORT_ORDER,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _notify_targets_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="notify", multiple=True)
    )


def _max_size_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, step=1, mode=selector.NumberSelectorMode.BOX
        )
    )


def _max_size_entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=MAX_SIZE_ENTITY_DOMAINS)
    )


def _check_max_size_conflict(
    user_input: dict[str, Any], errors: dict[str, str]
) -> None:
    """Reject configs that set both a fixed max size and an entity reference."""
    if user_input.get(CONF_MAX_SIZE) and user_input.get(CONF_MAX_SIZE_ENTITY):
        errors[CONF_MAX_SIZE_ENTITY] = "max_size_conflict"


class EntityListConfigFlow(config_entries.ConfigFlow, domain="entity_list"):
    """Handle creation of a new Entity List."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            list_id = user_input[CONF_LIST_ID].strip().lower()
            try:
                cv.slug(list_id)
            except vol.Invalid:
                errors[CONF_LIST_ID] = "invalid_list_id"

            _check_max_size_conflict(user_input, errors)

            if not errors:
                await self.async_set_unique_id(list_id)
                self._abort_if_unique_id_configured()

                self._data = {
                    CONF_LIST_ID: list_id,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_DESCRIPTION: user_input.get(CONF_DESCRIPTION, ""),
                    CONF_LIST_TYPE: user_input[CONF_LIST_TYPE],
                    CONF_SORT_ORDER: user_input.get(
                        CONF_SORT_ORDER, DEFAULT_SORT_ORDER
                    ),
                    CONF_MAX_SIZE: user_input.get(CONF_MAX_SIZE),
                    CONF_MAX_SIZE_ENTITY: user_input.get(CONF_MAX_SIZE_ENTITY),
                }

                if self._data[CONF_LIST_TYPE] == LIST_TYPE_ALERT:
                    return await self.async_step_alert_targets()

                self._data[CONF_NOTIFY_TARGETS] = []
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_LIST_ID): selector.TextSelector(),
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_DESCRIPTION, default=""): str,
                vol.Required(CONF_LIST_TYPE, default=LIST_TYPE_STANDARD): _list_type_selector(),
                vol.Optional(CONF_SORT_ORDER, default=DEFAULT_SORT_ORDER): _sort_order_selector(),
                vol.Optional(CONF_MAX_SIZE): _max_size_selector(),
                vol.Optional(CONF_MAX_SIZE_ENTITY): _max_size_entity_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_alert_targets(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            targets = user_input.get(CONF_NOTIFY_TARGETS, [])
            if len(targets) > MAX_NOTIFY_TARGETS:
                errors[CONF_NOTIFY_TARGETS] = "too_many_targets"
            else:
                self._data[CONF_NOTIFY_TARGETS] = targets
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NOTIFY_TARGETS, default=[]): _notify_targets_selector(),
            }
        )
        return self.async_show_form(
            step_id="alert_targets", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user fix the list_id without deleting/recreating the list.

        This is intentionally narrow - list_id is the only thing you can't
        already change via the options flow (Configure button). list_type
        stays fixed forever since it underpins the item schema.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            old_list_id = entry.data[CONF_LIST_ID]
            new_list_id = user_input[CONF_LIST_ID].strip().lower()

            try:
                cv.slug(new_list_id)
            except vol.Invalid:
                errors[CONF_LIST_ID] = "invalid_list_id"

            if not errors and new_list_id != old_list_id:
                await self.async_set_unique_id(new_list_id)
                self._abort_if_unique_id_configured()

            if not errors:
                if new_list_id != old_list_id:
                    storage = self.hass.data[DOMAIN]["storage"]
                    storage.data[new_list_id] = storage.data.pop(
                        old_list_id, {"items": []}
                    )
                    await storage.save()

                    entries_map = self.hass.data[DOMAIN]["entries"]
                    entries_map[new_list_id] = entries_map.pop(old_list_id, entry)

                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=new_list_id,
                    data_updates={CONF_LIST_ID: new_list_id},
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LIST_ID, default=entry.data[CONF_LIST_ID]
                ): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "EntityListOptionsFlow":
        return EntityListOptionsFlow()


class EntityListOptionsFlow(config_entries.OptionsFlow):
    """Let the user edit a list's mutable settings after creation.

    list_id (fixable via the separate Reconfigure flow, see
    async_step_reconfigure above) and list_type (permanently fixed - it
    underpins the item schema) are NOT editable here.

    Deliberately does not override __init__ / set self.config_entry:
    recent Home Assistant versions provide self.config_entry automatically,
    and manually assigning it is deprecated (and has since been removed in
    some versions).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            targets = user_input.get(CONF_NOTIFY_TARGETS, [])
            if len(targets) > MAX_NOTIFY_TARGETS:
                errors[CONF_NOTIFY_TARGETS] = "too_many_targets"

            _check_max_size_conflict(user_input, errors)

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=user_input[CONF_NAME]
                )
                return self.async_create_entry(data=user_input)

        is_alert = current[CONF_LIST_TYPE] == LIST_TYPE_ALERT

        schema_dict = {
            vol.Required(CONF_NAME, default=current[CONF_NAME]): str,
            vol.Optional(
                CONF_DESCRIPTION, default=current.get(CONF_DESCRIPTION, "")
            ): str,
            vol.Optional(
                CONF_SORT_ORDER, default=current.get(CONF_SORT_ORDER, DEFAULT_SORT_ORDER)
            ): _sort_order_selector(),
        }
        if current.get(CONF_MAX_SIZE) is not None:
            schema_dict[
                vol.Optional(CONF_MAX_SIZE, default=current[CONF_MAX_SIZE])
            ] = _max_size_selector()
        else:
            schema_dict[vol.Optional(CONF_MAX_SIZE)] = _max_size_selector()
        if current.get(CONF_MAX_SIZE_ENTITY) is not None:
            schema_dict[
                vol.Optional(
                    CONF_MAX_SIZE_ENTITY, default=current[CONF_MAX_SIZE_ENTITY]
                )
            ] = _max_size_entity_selector()
        else:
            schema_dict[vol.Optional(CONF_MAX_SIZE_ENTITY)] = _max_size_entity_selector()
        if is_alert:
            schema_dict[
                vol.Optional(
                    CONF_NOTIFY_TARGETS, default=current.get(CONF_NOTIFY_TARGETS, [])
                )
            ] = _notify_targets_selector()

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema_dict), errors=errors
        )
