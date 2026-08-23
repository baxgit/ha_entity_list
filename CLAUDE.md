# Entity List — Home Assistant Custom Integration

## Purpose

A generic, multi-purpose list integration for Home Assistant. Each list the
user creates becomes its own `sensor` entity. Two flavors:

- **Standard list** — simple items: name, optional type, optional
  description, optional dashboard link.
- **Alert list** — same fields, plus a status lifecycle
  (`Active (new)` → `Active` → `Cleared`), a `high_priority` flag, and
  optional notifications (persistent notification and/or up to two
  companion-app push targets) fired on item creation.

Both list types can optionally cap their size (oldest item evicted by
creation time when the cap is exceeded).

## Repo layout

```
custom_components/entity_list/
  __init__.py       services (add_item, remove_item, update_item,
                     reset_list, acknowledge_new_item, clear_active_alert),
                     setup/teardown of config entries, alert notification
                     logic
  config_flow.py     create/reconfigure/options flows, list_id
                     auto-generation
  const.py           all constant keys, enums, defaults
  helpers.py         effective_config, sort_items, max-size resolution,
                     list_id <-> entity_id resolution
  sensor.py          the SensorEntity exposing state + attributes
  storage.py         thin wrapper around HA's Store (all lists, keyed by
                     list_id)
  services.yaml      service field schemas (UI-facing)
  strings.json / translations/en.json  config/options flow UI strings
  icon.png, icon@2x.png, logo.png, logo@2x.png  local brand images (HA
  2026.3+ local brand-image support, no home-assistant/brands submission
  needed)
```

Current version: see `manifest.json` (`version`). Bump this on any
user-visible change, per HA custom-integration convention.

## Key design decisions (read before changing behavior)

- **list_id is the storage/API key; entity_id is just a UI convenience.**
  `helpers.resolve_list_id` always resolves via the entity registry's
  `unique_id` (`entity_list_<list_id>`), never by parsing the entity_id
  string, because entity_ids can be renamed by the user at any time.
- **entry.data vs entry.options**: `entry.data` holds values fixed at
  creation (list_id, list_type, and the *original* name/description/etc).
  `entry.options` holds only what's been changed since via the options
  flow. `helpers.effective_config()` merges them — always use that, never
  read `entry.data` directly for anything mutable.
- **list_id and list_type are immutable after creation.** list_type
  underpins the item schema (alert-only fields). list_id can only be
  changed via the separate `async_step_reconfigure` flow (not the options
  flow), which also migrates the storage key and entity registry entry.
- **list_id is optional at creation.** In `async_step_user`, if the user
  leaves the List ID field blank, `config_flow._generate_list_id` derives
  one from the Name via `homeassistant.util.slugify`, de-duplicating
  against existing entries' `CONF_LIST_ID` with an incrementing `_2`, `_3`,
  ... suffix. `async_set_unique_id` + `_abort_if_unique_id_configured()`
  still run afterwards as the authoritative uniqueness check either way.
- **max_size**: an entity reference (`input_number`/`counter`) always wins
  over a fixed number if both are somehow set. Eviction is always by
  `created` timestamp, independent of the list's display sort_order.
- **Notifications only fire on item creation**, never on
  acknowledge/clear/update. Two channels: `persistent_notification.create`
  (with a stable id `entity_list_<list_id>_<item_id>`) and
  `notify.send_message` per configured target entity (assumes iOS
  companion app).
- **Stale notify targets**: if a configured notify target entity doesn't
  resolve, a repair issue is raised (`ISSUE_STALE_NOTIFY_TARGET`) instead
  of failing silently; it clears automatically once the target resolves.
- **An `entity_list_item_created` event fires on the bus for every new
  item**, regardless of `notify_on_create`, so users can build their own
  automations without being limited to the two built-in channels.
- **update_item is a partial overwrite, keyed by presence in `call.data`.**
  Its schema fields (`type`, `description`, `url`, `high_priority`) have no
  defaults, so an omitted field is simply absent from `call.data` and left
  untouched — only fields the caller actually passed are applied. `name`
  is deliberately excluded from the schema; renaming an item isn't
  supported by this service. `high_priority` is only applied when the
  list is alert-type, mirroring `add_item`'s existing behavior of
  silently dropping alert-only fields on standard lists.
  `notify_on_create` is deliberately NOT part of this service's schema —
  unlike `high_priority`, it isn't really persisted state about the item,
  it's a one-time instruction consumed at creation to decide whether/how
  to notify. There's nothing meaningful to "update" about it after the
  fact, so don't add it here without a real use case driving it.
- **clear_active_alert's `description` field follows the same
  presence-based pattern** as `update_item` (`"description" in call.data`,
  not `.get()`), so it only overwrites the item's description when the
  caller actually supplies one.
- **async_migrate_entry is currently a no-op** — all fields added since
  v1 (item description, max_size, max_size_entity) are optional and
  read with `.get()`-style defaults, so old entries keep working
  unmodified. Kept as a ready landing spot for when a real migration is
  next needed.

## Known platform limitation

As of HA 2026.5, the entity-based `notify.send_message` action doesn't
support the companion app's advanced `data` payload (custom
`interruption-level`, images, badges) — only `title`/`message`. So
`high_priority` is surfaced via a title prefix
(`⚠ High priority — ...`), not a true iOS critical/time-sensitive
interruption level. If HA closes this gap, `_send_alert_notification` in
`__init__.py` is the only place that needs updating.

## Recent changes

- **v1.4.0**:
  - `clear_active_alert` now accepts an optional `description` field that
    overwrites the item's description at the same time it's cleared.
  - Added a new `update_item` service: overwrites any of `type`,
    `description`, `url`, `high_priority` on an existing item (identified
    by its current name), leaving unspecified fields untouched. Does not
    allow renaming an item, and deliberately excludes `notify_on_create`
    (a creation-time instruction, not persisted item state).
  - The creation form's List ID field is now optional and moved to the
    second position (after Name, which is now the only required field on
    that step). A blank List ID is auto-generated from the Name via
    `config_flow._generate_list_id`.
- **v1.3.0**: `_send_alert_notification` now appends the item's
  `description` (if populated) on a new line after the `name (type)`
  line, for both notification channels. Previously the description was
  stored and shown as a sensor attribute but never surfaced in
  notifications.

## Conventions when making changes

- Keep `README.md` in sync with any user-facing behavior change
  (services, attributes, notification format).
- Keep `strings.json` and `translations/en.json` in sync with each other
  — `translations/en.json` is what HA actually loads at runtime;
  `strings.json` is the English source for future translators and isn't
  loaded itself.
- Bump `manifest.json`'s `version` on user-visible changes.
- Validate Python files parse (`python3 -m py_compile`) and JSON files
  parse before considering a change done.
