"""Constantes de l'intégration Délestage Électrique."""

DOMAIN = "delestage"

# ── Configuration globale ──────────────────────────────────────────
CONF_POWER_SENSOR  = "power_sensor"   # Entité sensor puissance totale
CONF_MAX_POWER     = "max_power"      # Seuil de déclenchement en W
CONF_RECOVERY_DELAY = "recovery_delay" # Secondes avant réarmement
CONF_REARM_MARGIN  = "rearm_margin"   # Marge anti-ping-pong en W

# ── Configuration des équipements (stockée dans entry.options) ─────
CONF_EQUIPMENTS       = "equipments"      # Liste des équipements
CONF_DEVICE_NAME      = "device_name"     # Nom lisible
CONF_DEVICE_ENTITY    = "entity_id"       # Entité à piloter
CONF_DEVICE_PRIORITY  = "priority"        # 1 = délestage en premier
CONF_DEVICE_POWER_MODE = "power_mode"     # "fixed" ou "sensor"
CONF_DEVICE_FIXED_PWR  = "fixed_power"    # Puissance fixe en W
CONF_DEVICE_PWR_SENSOR = "power_sensor_device"  # Capteur puissance équipement

# ── États internes du coordinator ─────────────────────────────────
STATE_IDLE       = "idle"       # Aucun délestage en cours
STATE_SHEDDING   = "shedding"   # Délestage actif
STATE_RECOVERING = "recovering" # En attente de réarmement

# ── Attributs exposés par l'entité ────────────────────────────────
ATTR_CURRENT_POWER     = "current_power"
ATTR_MAX_POWER         = "max_power"
ATTR_DEVICES_SHED      = "devices_shed"
ATTR_LAST_SHED_TIME    = "last_shed_time"
ATTR_LAST_RECOVERY_TIME = "last_recovery_time"
ATTR_RECOVERY_REMAINING = "recovery_remaining_s"
