# Changelog

All notable changes to this project are documented here. `manifest.json`'s
`version` field should always match the most recent entry below.

## 1.4.2

- Moved the local brand images into a `brand/` subfolder
  (`brand/icon.png`, `brand/icon@2x.png`, `brand/logo.png`,
  `brand/logo@2x.png`) instead of the integration root, matching the
  path HA's 2026.3+ local brand-image support expects.

## 1.4.1

- The creation form's List type field now has helper text
  (`data_description`) explaining that choosing Alert leads to a second
  screen (notification targets) after submitting. Text-only change — no
  behavior change. HA's generic config-flow form renderer only supports a
  `description` block above the form and per-field `data_description`
  helper text below each individual field; there's no native slot for a
  message pinned below the whole form, so this was attached to the
  `list_type` field specifically since that's the field the note is
  actually about.

## 1.4.0

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

## 1.3.0

- `_send_alert_notification` now appends the item's `description` (if
  populated) on a new line after the `name (type)` line, for both
  notification channels. Previously the description was stored and shown
  as a sensor attribute but never surfaced in notifications.

## Earlier versions

Changes prior to 1.3.0 were not tracked in a changelog and aren't
reconstructed here.
