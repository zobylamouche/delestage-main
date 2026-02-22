"""Entité principale exposant l'état du délestage."""
from __future__ import annotations
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_CURRENT_POWER,
    ATTR_MAX_POWER,
    ATTR_DEVICES_SHED,
    ATTR_LAST_SHED_TIME,
    ATTR_LAST_RECOVERY_TIME,
    ATTR_RECOVERY_REMAINING,
    STATE_IDLE,
    STATE_SHEDDING,
    STATE_RECOVERING,
)
from .coordinator import DelestageCoordinator


class DelestageSensor(CoordinatorEntity, SensorEntity):
    """
    Sensor principal du délestage.

    Hérite de CoordinatorEntity → mise à jour automatique
    à chaque appel de coordinator.async_set_updated_data().

    États retournés :
      idle       → fonctionnement normal
      shedding   → délestage actif
      recovering → attente avant réarmement
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DelestageCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialiser le sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "État délestage"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_state"
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> str:
        """État courant du délestage."""
        return self.coordinator.delestage_state

    @property
    def icon(self) -> str:
        """Icône adaptée à l'état."""
        icons = {
            STATE_SHEDDING:   "mdi:lightning-bolt-off",
            STATE_RECOVERING: "mdi:timer-sand",
            STATE_IDLE:       "mdi:lightning-bolt",
        }
        return icons.get(self.coordinator.delestage_state, "mdi:lightning-bolt")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Attributs exposés dans HA pour les automatisations et l'UI.
        Accessibles via {{ state_attr('sensor.etat_delestage', 'current_power') }}
        """
        coord = self.coordinator
        power_state = self.hass.states.get(coord.power_sensor)

        return {
            ATTR_CURRENT_POWER:      coord.current_power,
            ATTR_MAX_POWER:          coord.max_power,
            ATTR_DEVICES_SHED:       coord.devices_shed,
            ATTR_LAST_SHED_TIME:     (
                coord.last_shed_time.isoformat()
                if coord.last_shed_time else None
            ),
            ATTR_LAST_RECOVERY_TIME: (
                coord.last_recovery_time.isoformat()
                if coord.last_recovery_time else None
            ),
            ATTR_RECOVERY_REMAINING: round(coord.recovery_remaining, 0),
            "nb_equipements_coupes": len(coord.devices_shed),
            "capteur_puissance":     coord.power_sensor,
        }
