from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from .const import DOMAIN

class DelestageStateEntity(Entity):
    def __init__(self, coordinator):
        self._coordinator = coordinator
        self._attr_name = "État Délestage"
        self._attr_unique_id = f"{DOMAIN}_etat"
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def state(self):
        return self._coordinator.state

    @property
    def extra_state_attributes(self):
        return {
            "devices_shed": self._coordinator.devices_shed,
            "last_shed_time": str(self._coordinator.last_shed_time) if self._coordinator.last_shed_time else None,
            "last_recovery_time": str(self._coordinator.last_recovery_time) if self._coordinator.last_recovery_time else None,
        }

class DelestageEquipmentEntity(Entity):
    def __init__(self, eq, coordinator):
        self._eq = eq
        self._coordinator = coordinator
        self._attr_name = eq.get("device_name", "Equipement")
        self._attr_unique_id = f"{DOMAIN}_{eq.get('entity_id','')}_equip"
        self._attr_icon = "mdi:power-plug"

    @property
    def state(self):
        entity_id = self._eq.get("entity_id", "")
        state = self._coordinator.hass.states.get(entity_id)
        return state.state if state else "inconnu"

    @property
    def extra_state_attributes(self):
        return {
            "priority": self._eq.get("priority", 0),
            "power": self._eq.get("fixed_power", 0),
            "shed": self._eq.get("entity_id") in self._coordinator.devices_shed,
        }
