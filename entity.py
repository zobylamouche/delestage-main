"""Entités du délestage électrique."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import *

_LOGGER = logging.getLogger(__name__)


def _device_info(entry) -> DeviceInfo:
    """Info device commune à toutes les entités."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Délestage Électrique",
        manufacturer="Custom",
        model="Délestage",
        entry_type="service",
    )


class DelestageSensor(CoordinatorEntity, SensorEntity):
    """Capteur principal exposant l'état complet du délestage."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "État Délestage"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_state"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.state

    @property
    def extra_state_attributes(self):
        # Puissance actuelle
        power_state = self.hass.states.get(self.coordinator.power_sensor)
        try:
            current_power = float(power_state.state) if power_state else 0
        except (ValueError, TypeError):
            current_power = 0

        max_power = self.coordinator.max_power
        pct = round((current_power / max_power) * 100, 1) if max_power else 0

        # Équipements délestés
        shed_details = []
        for entity_id in self.coordinator.devices_shed:
            eq = next(
                (e for e in self.coordinator.equipments
                 if e.get(CONF_DEVICE_ENTITY) == entity_id),
                None,
            )
            if eq:
                shed_details.append({
                    "name":      eq.get(CONF_DEVICE_NAME, entity_id),
                    "entity_id": entity_id,
                    "priority":  eq.get(CONF_DEVICE_PRIORITY, 0),
                    "power":     eq.get(CONF_DEVICE_FIXED_PWR, 0),
                })

        # Tous les équipements
        all_devices = []
        for eq in sorted(
            self.coordinator.equipments,
            key=lambda e: e.get(CONF_DEVICE_PRIORITY, 99),
        ):
            state = self.hass.states.get(eq.get(CONF_DEVICE_ENTITY, ""))
            all_devices.append({
                "name":      eq.get(CONF_DEVICE_NAME, "?"),
                "entity_id": eq.get(CONF_DEVICE_ENTITY, ""),
                "priority":  eq.get(CONF_DEVICE_PRIORITY, 0),
                "power":     eq.get(CONF_DEVICE_FIXED_PWR, 0),
                "status":    state.state if state else "inconnu",
                "shed":      eq.get(CONF_DEVICE_ENTITY) in self.coordinator.devices_shed,
            })

        return {
            ATTR_CURRENT_POWER:          current_power,
            ATTR_MAX_POWER:              max_power,
            "charge_percent":            pct,
            "rearm_margin":              self.coordinator.rearm_margin,
            "threshold_with_margin":     max_power - self.coordinator.rearm_margin,
            "devices_shed_count":        len(self.coordinator.devices_shed),
            "devices_shed_details":      shed_details,
            "total_power_shed":          sum(d["power"] for d in shed_details),
            "all_devices":               all_devices,
            ATTR_LAST_SHED_TIME:         str(self.coordinator.last_shed_time) if self.coordinator.last_shed_time else None,
            ATTR_LAST_RECOVERY_TIME:     str(self.coordinator.last_recovery_time) if self.coordinator.last_recovery_time else None,
            "recovery_delay":            self.coordinator.recovery_delay,
            ATTR_RECOVERY_REMAINING:     self.coordinator._get_recovery_countdown(),
        }


class DelestageEquipmentSensor(CoordinatorEntity, SensorEntity):
    """Un sensor par équipement piloté."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, eq: dict):
        super().__init__(coordinator)
        self._entry = entry
        self._eq = eq
        self._entity_id = eq.get(CONF_DEVICE_ENTITY, "")
        name = eq.get(CONF_DEVICE_NAME, self._entity_id)
        self._attr_name = f"Équipement — {name}"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self._entity_id}"
        self._attr_icon = "mdi:power-plug"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        """Retourne l'état on/off de l'équipement."""
        state = self.hass.states.get(self._entity_id)
        return state.state if state else "inconnu"

    @property
    def extra_state_attributes(self):
        return {
            "priority":  self._eq.get(CONF_DEVICE_PRIORITY, 0),
            "power":     self._eq.get(CONF_DEVICE_FIXED_PWR, 0),
            "shed":      self._entity_id in self.coordinator.devices_shed,
            "entity_id": self._entity_id,
        }
