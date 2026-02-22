import logging
from datetime import timedelta, datetime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers import entity_registry
from homeassistant.const import STATE_ON, STATE_OFF
from .const import *

_LOGGER = logging.getLogger(__name__)

class DelestageCoordinator(DataUpdateCoordinator):
    """Logique de délestage."""

    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="Delestage Coordinator",
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.power_sensor = entry.data[CONF_POWER_SENSOR]
        self.max_power = entry.data[CONF_MAX_POWER]
        self.recovery_delay = entry.data[CONF_RECOVERY_DELAY]
        self.rearm_margin = entry.data.get(CONF_REARM_MARGIN, 0)
        self.equipments = entry.options.get(CONF_EQUIPMENTS, [])
        self.state = STATE_IDLE
        self.devices_shed = []
        self.last_shed_time = None
        self.last_recovery_time = None
        self._recovery_start = None

    async def async_setup(self):
        """Initialisation : abonne-toi au capteur de puissance."""
        async_track_state_change(
            self.hass, self.power_sensor, self._power_changed
        )

    async def _power_changed(self, entity_id, old_state, new_state):
        """Callback sur changement de puissance."""
        try:
            current_power = float(new_state.state)
        except (ValueError, TypeError):
            return

        await self._delestage_logic(current_power)

    async def _delestage_logic(self, current_power):
        """Logique principale de délestage."""
        if self.state == STATE_IDLE:
            if current_power > self.max_power:
                await self._shed_devices(current_power)
        elif self.state == STATE_SHEDDING:
            if current_power < self.max_power - self.rearm_margin:
                if not self._recovery_start:
                    self._recovery_start = datetime.now()
                elif (datetime.now() - self._recovery_start).total_seconds() >= self.recovery_delay:
                    await self._recover_devices(current_power)
            else:
                self._recovery_start = None

    async def _shed_devices(self, current_power):
        """Coupe les équipements selon priorité."""
        excess = current_power - self.max_power
        sorted_equipments = sorted(self.equipments, key=lambda e: e["priority"])
        shed_power = 0
        self.devices_shed = []
        for eq in sorted_equipments:
            if eq["power_mode"] == "fixed":
                eq_power = eq["fixed_power"]
            else:
                sensor_state = self.hass.states.get(eq["power_sensor"])
                eq_power = float(sensor_state.state) if sensor_state else 0
            await self._turn_off(eq["entity_id"])
            self.devices_shed.append(eq["entity_id"])
            shed_power += eq_power
            if current_power - shed_power < self.max_power:
                break
        self.state = STATE_SHEDDING
        self.last_shed_time = datetime.now()
        self._recovery_start = None

    async def _recover_devices(self, current_power):
        """Rallume les équipements délestés (ordre inverse)."""
        for entity_id in reversed(self.devices_shed):
            await self._turn_on(entity_id)
            # Vérifie la puissance après chaque rallumage
            sensor_state = self.hass.states.get(self.power_sensor)
            try:
                current_power = float(sensor_state.state)
            except (ValueError, TypeError):
                continue
            if current_power > self.max_power:
                await self._turn_off(entity_id)
                break
        self.state = STATE_RECOVERING
        self.last_recovery_time = datetime.now()
        self.devices_shed = []
        self._recovery_start = None
        self.state = STATE_IDLE

    async def _turn_off(self, entity_id):
        """Coupe un équipement."""
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(domain, "turn_off", {"entity_id": entity_id})

    async def _turn_on(self, entity_id):
        """Rallume un équipement."""
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(domain, "turn_on", {"entity_id": entity_id})
