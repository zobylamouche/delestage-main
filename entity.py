"""Toutes les entités de l'intégration Délestage."""
import logging
from datetime import datetime
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import UnitOfPower, PERCENTAGE
from .const import *

_LOGGER = logging.getLogger(__name__)


def _device_info(entry) -> DeviceInfo:
    """DeviceInfo commune — regroupe toutes les entités sous un seul appareil."""
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
    """
    Sensor principal : état du délestage + tous les attributs.
    entity_id : sensor.etat_delestage
    """

    _attr_has_entity_name = False  # on gère le nom manuellement

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name        = "État Délestage"
        self._attr_unique_id   = f"{DOMAIN}_state"   # fixe → toujours sensor.etat_delestage
        self._attr_icon        = "mdi:lightning-bolt"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator.state

    @property
    def extra_state_attributes(self):
        # ── Puissance actuelle ──────────────────────────────────
        power_state = self.hass.states.get(self.coordinator.power_sensor)
        try:
            current_power = float(power_state.state) if power_state else 0
        except (ValueError, TypeError):
            current_power = 0

        max_power = self.coordinator.max_power
        pct = round((current_power / max_power) * 100, 1) if max_power else 0

        # ── Équipements délestés ────────────────────────────────
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

        # ── Tous les équipements ────────────────────────────────
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
            # Attributs utilisés par le dashboard
            ATTR_CURRENT_POWER:      current_power,
            ATTR_MAX_POWER:          max_power,
            "charge_percent":        pct,
            "rearm_margin":          self.coordinator.rearm_margin,
            "threshold_with_margin": max_power - self.coordinator.rearm_margin,
            "devices_shed_count":    len(self.coordinator.devices_shed),
            "devices_shed_details":  shed_details,
            "total_power_shed":      sum(d["power"] for d in shed_details),
            "all_devices":           all_devices,
            # Temps
            ATTR_LAST_SHED_TIME:     (
                self.coordinator.last_shed_time.strftime("%d/%m/%Y %H:%M:%S")
                if self.coordinator.last_shed_time else None
            ),
            ATTR_LAST_RECOVERY_TIME: (
                self.coordinator.last_recovery_time.strftime("%d/%m/%Y %H:%M:%S")
                if self.coordinator.last_recovery_time else None
            ),
            "recovery_delay":        self.coordinator.recovery_delay,
            ATTR_RECOVERY_REMAINING: self.coordinator._get_recovery_countdown(),
            "recovery_countdown":    self.coordinator._get_recovery_countdown(),
        }


# ══════════════════════════════════════════════════════════════════
# Sensors dédiés (chacun expose une valeur numérique propre)
# ══════════════════════════════════════════════════════════════════

class DelestagePowerSensor(CoordinatorEntity, SensorEntity):
    """
    Puissance électrique actuelle en W.
    entity_id : sensor.delestage_puissance_actuelle
    """

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
        state = self.hass.states.get(self.coordinator.power_sensor)
        try:
            return float(state.state) if state else None
        except (ValueError, TypeError):
            return None


class DelestageChargeSensor(CoordinatorEntity, SensorEntity):
    """
    Charge électrique en %.
    entity_id : sensor.delestage_charge
    """

    _attr_has_entity_name  = False
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon             = "mdi:percent"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Charge"
        self._attr_unique_id = f"{DOMAIN}_charge_percent"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        state = self.hass.states.get(self.coordinator.power_sensor)
        try:
            current = float(state.state) if state else 0
        except (ValueError, TypeError):
            current = 0
        if not self.coordinator.max_power:
            return 0
        return round((current / self.coordinator.max_power) * 100, 1)


class DelestageCountSensor(CoordinatorEntity, SensorEntity):
    """
    Nombre d'équipements délestés.
    entity_id : sensor.delestage_equipements_delestes
    """

    _attr_has_entity_name  = False
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_icon             = "mdi:power-plug-off"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Équipements délestés"
        self._attr_unique_id = f"{DOMAIN}_devices_shed_count"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return len(self.coordinator.devices_shed)


class DelestageShedPowerSensor(CoordinatorEntity, SensorEntity):
    """
    Puissance totale délestée en W.
    entity_id : sensor.delestage_puissance_delestee
    """

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
        total = 0.0
        for entity_id in self.coordinator.devices_shed:
            eq = next(
                (e for e in self.coordinator.equipments
                 if e.get(CONF_DEVICE_ENTITY) == entity_id),
                None,
            )
            if eq:
                total += float(eq.get(CONF_DEVICE_FIXED_PWR, 0))
        return total


class DelestageCountdownSensor(CoordinatorEntity, SensorEntity):
    """
    Secondes avant réarmement.
    entity_id : sensor.delestage_rearmement_dans
    """

    _attr_has_entity_name  = False
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "s"
    _attr_icon             = "mdi:timer-outline"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name      = "Délestage Réarmement dans"
        self._attr_unique_id = f"{DOMAIN}_recovery_countdown"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return self.coordinator._get_recovery_countdown()


# ══════════════════════════════════════════════════════════════════
# Sensor par équipement
# ══════════════════════════════════════════════════════════════════

class DelestageEquipmentSensor(CoordinatorEntity, SensorEntity):
    """
    Un sensor par équipement piloté.
    entity_id : sensor.delestage_equip_<entity_id>
    """

    _attr_has_entity_name = False
    _attr_icon            = "mdi:power-plug"

    def __init__(self, coordinator, entry, eq: dict):
        super().__init__(coordinator)
        self._entry    = entry
        self._eq       = eq
        self._eid      = eq.get(CONF_DEVICE_ENTITY, "")
        slug           = self._eid.replace(".", "_").replace("-", "_")
        name           = eq.get(CONF_DEVICE_NAME, self._eid)

        self._attr_name        = f"Équipement {name}"
        self._attr_unique_id   = f"{DOMAIN}_equip_{slug}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        state = self.hass.states.get(self._eid)
        return state.state if state else "inconnu"

    @property
    def extra_state_attributes(self):
        return {
            "priority":  self._eq.get(CONF_DEVICE_PRIORITY, 0),
            "power":     self._eq.get(CONF_DEVICE_FIXED_PWR, 0),
            "shed":      self._eid in self.coordinator.devices_shed,
            "entity_id": self._eid,
        }
