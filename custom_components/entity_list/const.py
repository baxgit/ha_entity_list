"""Constants for the Entity List integration."""

DOMAIN = "entity_list"

PLATFORMS = ["sensor"]

# --- List types ---
LIST_TYPE_STANDARD = "standard"
LIST_TYPE_ALERT = "alert"
LIST_TYPES = [LIST_TYPE_STANDARD, LIST_TYPE_ALERT]

# --- Sort orders ---
SORT_NEWEST_FIRST = "newest_first"
SORT_OLDEST_FIRST = "oldest_first"
SORT_STATUS = "status"
SORT_ORDERS = [SORT_NEWEST_FIRST, SORT_OLDEST_FIRST, SORT_STATUS]
DEFAULT_SORT_ORDER = SORT_NEWEST_FIRST

# --- Alert item status values ---
STATUS_NEW = "Active (new)"
STATUS_ACTIVE = "Active"
STATUS_CLEARED = "Cleared"

STATUS_PRIORITY = {
    STATUS_NEW: 0,
    STATUS_ACTIVE: 1,
    STATUS_CLEARED: 2,
}

# --- Notification behavior for alert items ---
NOTIFY_NONE = "none"
NOTIFY_PERSISTENT = "persistent"
NOTIFY_APP = "app"
NOTIFY_OPTIONS = [NOTIFY_NONE, NOTIFY_PERSISTENT, NOTIFY_APP]
DEFAULT_NOTIFY_ON_CREATE = NOTIFY_NONE

# --- Config entry data / options keys ---
CONF_LIST_ID = "list_id"
CONF_NAME = "name"
CONF_DESCRIPTION = "description"
CONF_LIST_TYPE = "list_type"
CONF_SORT_ORDER = "sort_order"
CONF_NOTIFY_TARGETS = "notify_targets"
CONF_MAX_SIZE = "max_size"
CONF_MAX_SIZE_ENTITY = "max_size_entity"

MAX_NOTIFY_TARGETS = 2

# Domains allowed as a max-size entity reference. Both are user-writable
# and purpose-built for holding a single numeric value, so they're a good
# fit for something the user wants to tune from a dashboard/automation.
MAX_SIZE_ENTITY_DOMAINS = ["input_number", "counter"]

# --- Dispatcher signal ---
SIGNAL_LIST_UPDATED = f"{DOMAIN}_updated_{{list_id}}"

# --- Events fired on the HA event bus ---
EVENT_ITEM_CREATED = f"{DOMAIN}_item_created"

# --- Repair issue ids ---
ISSUE_STALE_NOTIFY_TARGET = "stale_notify_target"
