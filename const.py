"""Constantes de l'intégration Délestage Électrique."""

DOMAIN = "delestage"

# ── Configuration globale ──────────────────────────────────────────
CONF_POWER_SENSOR   = "power_sensor"
CONF_MAX_POWER      = "max_power"
CONF_RECOVERY_DELAY = "recovery_delay"
CONF_REARM_MARGIN   = "rearm_margin"

# ── Configuration des équipements ──────────────────────────────────
CONF_EQUIPMENTS        = "equipments"
CONF_DEVICE_NAME       = "device_name"
CONF_DEVICE_ENTITY     = "entity_id"
CONF_DEVICE_PRIORITY   = "priority"
CONF_DEVICE_POWER_MODE = "power_mode"
CONF_DEVICE_FIXED_PWR  = "fixed_power"
CONF_DEVICE_PWR_SENSOR = "power_sensor_device"

# ── États internes ─────────────────────────────────────────────────
STATE_IDLE       = "idle"
STATE_SHEDDING   = "shedding"
STATE_RECOVERING = "recovering"

# ── Attributs exposés ──────────────────────────────────────────────
ATTR_CURRENT_POWER      = "current_power"
ATTR_MAX_POWER          = "max_power"
ATTR_DEVICES_SHED       = "devices_shed"
ATTR_LAST_SHED_TIME     = "last_shed_time"
ATTR_LAST_RECOVERY_TIME = "last_recovery_time"
ATTR_RECOVERY_REMAINING = "recovery_remaining_s"
