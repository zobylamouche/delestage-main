from homeassistant.components.sensor import SensorEntity
from .const import *

class DelestageSensor(SensorEntity):
    """Entité qui expose l’état du délestage."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "État délestage"
        self._attr_unique_id = "delestage_state"

    @property
    def state(self):
        return self.coordinator.state

    @property
    def extra_state_attributes(self):
        return {
            ATTR_CURRENT_POWER: self.coordinator.hass.states.get(self.coordinator.power_sensor).state,
            ATTR_MAX_POWER: self.coordinator.max_power,
            ATTR_DEVICES_SHED: self.coordinator.devices_shed,
            ATTR_LAST_SHED_TIME: self.coordinator.last_shed_time,
            ATTR_LAST_RECOVERY_TIME: self.coordinator.last_recovery_time,
        }
