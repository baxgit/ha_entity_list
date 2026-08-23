# Entity List

A generic, multi-purpose list integration for Home Assistant. Each list you
create becomes its own `sensor` entity, and comes in one of two flavors:

- **Standard list** — simple items: name, optional type, optional
  description, optional dashboard link.
- **Alert list** — the same fields, plus a status lifecycle
  (`Active (new)` → `Active` → `Cleared`), a high-priority flag, and
  optional notifications (persistent notification and/or up to two
  companion-app push targets) fired when an item is created.

Either list type can optionally cap its size. Once the cap is reached,
adding a new item removes the oldest one (by creation time) to make room.

## Installation

Copy this `entity_list/` folder into your Home Assistant
`config/custom_components/` directory, then restart Home Assistant.
Add lists via **Settings → Devices & services → Add integration → Entity List**.

## Creating a list

Only **Name** is required. **List ID** is optional — leave it blank and one
is generated automatically from the name (lowercased, spaces replaced with
underscores, and de-duplicated with a numeric suffix if that id is already
taken). Provide your own List ID instead if you want a stable id that
doesn't track the name, or a particular id for use in automations/scripts.

If you choose **Alert** as the list type, note that notification targets
are set up on a second screen shown after you submit this one — a hint to
that effect appears under the List type field.

## Sensor state

- **Standard lists**: state = total number of items.
- **Alert lists**: state = number of *unresolved* items (status
  `Active (new)` or `Active`). Cleared items don't count towards state, but
  are still visible (and counted) in the entity's attributes.

Every list entity exposes `list_type`, `description`, `sort_order`,
`item_count`, and the full `items` array as attributes. Alert lists
additionally expose `notify_targets`, `new_count`, `active_count`, and
`cleared_count`.

## Max list size

Both list types can optionally be capped, via two fields shown together
when creating or reconfiguring a list:

- **Max list size (number)** — a fixed cap.
- **Max list size (entity)** — an `input_number` or `counter` instead,
  useful if you want to tune the cap from a dashboard or automation
  without reopening the integration's options. If both are set, the
  entity wins; the form rejects setting both at once.

Whenever `entity_list.add_item` would push the list past its cap, the
oldest item *by creation time* is removed first — this is independent of
the list's configured sort order, so changing how the list is displayed
never changes which item gets evicted. The effective resolved size (or
`null` if unlimited) is exposed on the sensor as the `max_size` attribute.

## Reconfiguring a list

`list_id` and `list_type` are fixed at creation and can't be changed
afterwards (they underpin the storage key and the item schema). Everything
else — name, description, sort order, max size, and (for alert lists) the
two notify targets — can be edited any time via the integration's
**Configure** button, which opens an options flow.

If you need to fix a typo'd `list_id` specifically, use the entry's
**Reconfigure** action (separate from Configure) instead of deleting and
recreating the list. It renames the list's stored items to the new ID and
updates the entity's unique ID, so history is preserved. `list_type` still
can't be changed even via Reconfigure — it determines the item schema.

## Services

| Service | Purpose | Alert-list only |
| --- | --- | --- |
| `entity_list.add_item` | Add (or replace, by name) an item | no |
| `entity_list.remove_item` | Delete an item by name | no |
| `entity_list.update_item` | Overwrite one or more fields of an existing item, by name | no |
| `entity_list.reset_list` | Clear all items | no |
| `entity_list.acknowledge_new_item` | Move an item from `Active (new)` to `Active` | yes |
| `entity_list.clear_active_alert` | Move an item to `Cleared`, stamping `cleared_at` | yes |

`add_item` additionally accepts `high_priority` (bool) and `notify_on_create`
(`none` / `persistent` / `app`) — both are only meaningful on alert lists.

`update_item` identifies the item by its current `item_name` and lets you
overwrite `type`, `description`, `url`, and (alert lists only)
`high_priority` — every field is optional, and only the ones you pass are
changed; the rest of the item is left as-is. The item's `name` itself
cannot be changed with this service. `notify_on_create` is deliberately
not editable here — it's a one-time instruction for what to do at item
creation, not persisted state worth overwriting later.

`clear_active_alert` also accepts an optional `description`, which — if
provided — replaces the item's description at the same time it's cleared
(handy for recording resolution notes without a separate `update_item`
call).

## Notifications

Notifications only fire on item **creation**, never on acknowledge/clear/update.

- **Persistent**: creates a dismissible Home Assistant persistent
  notification with a stable ID
  (`entity_list_<list_id>_<item_id>`).
- **App**: sends via `notify.send_message` to each of the list's configured
  notify-entity targets (assumes iOS companion app). `high_priority` items
  get their notification title prefixed (`⚠ High priority — ...`).

Both channels build the same message body: `name (type)`, followed by the
item's `description` on a new line if one was provided when the item was
added.

### Known platform limitation

As of Home Assistant 2026.5, the entity-based `notify.send_message` action
does not yet support the companion app's advanced `data` payload (custom
`interruption-level`, images, badges, etc.) — only `title`/`message`. That
means `high_priority` is currently surfaced via the notification title, not
a true iOS time-sensitive/critical interruption level, and per-notification
icons aren't attempted (also a hard iOS platform limitation regardless of
this gap — iOS doesn't allow arbitrary custom icons in the notification body
itself). If/when Home Assistant closes this gap, `_send_alert_notification`
in `__init__.py` is the only place that needs updating.

An `entity_list_item_created` event is also fired on the bus for every new
item (regardless of `notify_on_create`), so you can build your own
automations without being limited to these two channels. Its payload:

| Field | Type | Notes |
| --- | --- | --- |
| `list_id` | string | The list's storage id. |
| `list_name` | string | The list's configured name at the time of firing. |
| `list_type` | string | `standard` or `alert`. |
| `item` | dict | The full item as stored — see below. |

`item` always has `id`, `name`, `type`, `description`, `url`, and `created`.
Alert-list items additionally have `status`, `high_priority`,
`notify_on_create`, and `cleared_at`.

### Stale notify targets

If an alert list's configured notify target entity no longer resolves
(e.g. removed or renamed), Home Assistant raises a repair issue under
**Settings → System → Repairs** instead of silently failing on the next
notification. The issue clears automatically once the target resolves
again.

## Brand assets

`brand/icon.png` and `brand/logo.png` (plus `@2x` variants) are bundled
directly in the integration folder, using the local brand-image support
added in Home Assistant 2026.3 — no submission to the `home-assistant/brands`
repository is required. SVG sources are included for future edits.

## Translations

Runtime UI strings live in `translations/en.json` — that's the path Home
Assistant actually reads at runtime for custom integrations. `strings.json`
at the integration root mirrors it and is the English source or future
translators to work from; it isn't loaded at runtime itself. If you add or
rename a config/options flow field, update both files together.
