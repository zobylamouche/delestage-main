"""Toutes les entités de l'intégration Délestage."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import UnitOfPower, PERCENTAGE
from .const import *

_LOGGER = logging.getLogger(__name__)


def _device_info(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Délestage Électrique",
        manufacturer="Custom Integration",
        model="Délestage v2",
        entry_type="service",
    )


# ══════════════════════════════════════════════════════════════════
# Sensor principal
# ══════════════════════════════════════════════════════════════════

class DelestageSensor(CoordinatorEntity, SensorEntity):
    """Sensor principal : état + tous les attributs."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "État Délestage"
        self._attr_unique_id = f"{DOMAIN}_etat"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return self.coordinator.state
        return data.get("state", self.coordinator.state)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "current_power":      data.get("current_power", 0),
            "max_power":          data.get("max_power", 0),
            "charge_percent":     data.get("charge_percent", 0),
            "devices_shed":       data.get("devices_shed", []),
            "devices_shed_count": data.get("devices_shed_count", 0),
            "total_power_shed":   data.get("total_power_shed", 0),
            "recovery_countdown": data.get("recovery_countdown"),
            "last_shed_time":     data.get("last_shed_time"),
            "last_recovery_time": data.get("last_recovery_time"),
            "all_devices":        data.get("all_devices", []),
        }


# ══════════════════════════════════════════════════════════════════
# Sensor par équipement
# ══════════════════════════════════════════════════════════════════

class DelestageEquipmentSensor(CoordinatorEntity, SensorEntity):
    """Un sensor par équipement configuré."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:power-plug"

    def __init__(self, coordinator, entry, eq: dict):
        super().__init__(coordinator)
        self._entry = entry
        self._eq = eq
        name = eq.get(CONF_DEVICE_NAME, eq.get(CONF_DEVICE_ENTITY, "?"))
        uid  = eq.get(CONF_DEVICE_ENTITY, name).replace(".", "_")
        self._attr_name       = f"Délestage {name}"
        self._attr_unique_id  = f"{DOMAIN}_equip_{uid}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        entity_id = self._eq.get(CONF_DEVICE_ENTITY, "")
        s = self.hass.states.get(entity_id)
        return s.state if s else "inconnu"

    @property
    def extra_state_attributes(self):
        entity_id = self._eq.get(CONF_DEVICE_ENTITY, "")
        return {
            "priority":  int(float(self._eq.get(CONF_DEVICE_PRIORITY, 99))),
            "power":     self.coordinator._get_device_power(self._eq),
            "shed":      entity_id in self.coordinator.devices_shed,
            "entity_id": entity_id,
        }


# ══════════════════════════════════════════════════════════════════
# Sensor puissance actuelle
# ══════════════════════════════════════════════════════════════════

class DelestagePowerSensor(CoordinatorEntity, SensorEntity):
    """Puissance électrique actuelle en W."""

    _attr_has_entity_name  = False
    _attr_device_class     = SensorDeviceClass.POWER
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon             = "mdi:flash"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Puissance actuelle"
        self._attr_unique_id = f"{DOMAIN}_current_power"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if data:
            return data.get("current_power")
        s = self.hass.states.get(self.coordinator.power_sensor)
        try:
            return float(s.state) if s else None
        except (ValueError, TypeError):
            return None


# ══════════════════════════════════════════════════════════════════
# Sensor charge %
# ══════════════════════════════════════════════════════════════════

class DelestageChargeSensor(CoordinatorEntity, SensorEntity):
    """Charge électrique en %."""

    _attr_has_entity_name  = False
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon             = "mdi:percent"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Charge"
        self._attr_unique_id = f"{DOMAIN}_charge"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if data:
            return data.get("charge_percent", 0)
        return 0


# ══════════════════════════════════════════════════════════════════
# Sensor nombre équipements délestés
# ══════════════════════════════════════════════════════════════════

class DelestageCountSensor(CoordinatorEntity, SensorEntity):
    """Nombre d'équipements délestés."""

    _attr_has_entity_name = False
    _attr_icon            = "mdi:power-plug-off"
    _attr_state_class     = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Équipements délestés"
        self._attr_unique_id = f"{DOMAIN}_shed_count"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if data:
            return data.get("devices_shed_count", 0)
        return len(self.coordinator.devices_shed)


# ══════════════════════════════════════════════════════════════════
# Sensor puissance délestée
# ══════════════════════════════════════════════════════════════════

class DelestageShedPowerSensor(CoordinatorEntity, SensorEntity):
    """Puissance totale délestée en W."""

    _attr_has_entity_name  = False
    _attr_device_class     = SensorDeviceClass.POWER
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon             = "mdi:power-off"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Puissance délestée"
        self._attr_unique_id = f"{DOMAIN}_total_power_shed"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if data:
            return data.get("total_power_shed", 0)
        return 0


# ══════════════════════════════════════════════════════════════════
# Sensor countdown réarmement
# ══════════════════════════════════════════════════════════════════

class DelestageCountdownSensor(CoordinatorEntity, SensorEntity):
    """Secondes avant réarmement."""

    _attr_has_entity_name = False
    _attr_icon            = "mdi:timer-outline"
    _attr_state_class     = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Réarmement dans"
        self._attr_unique_id = f"{DOMAIN}_countdown"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        data = self.coordinator.data
        if data:
            return data.get("recovery_countdown")
        return self.coordinator._get_recovery_countdown()
