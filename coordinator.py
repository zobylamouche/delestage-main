import logging
from datetime import timedelta, datetime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from .const import *

_LOGGER = logging.getLogger(__name__)


class DelestageCoordinator(DataUpdateCoordinator):
    """Logique de délestage électrique."""

    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="Delestage Coordinator",
                _LOGGER.warning("[Delestage] async_setup: power_sensor=%s", self.power_sensor)
                if not self.power_sensor:
        )
        self.entry = entry
        self.state = STATE_IDLE
                _LOGGER.warning("[Delestage] Abonnement à state_changed pour %s", self.power_sensor)
        self.devices_shed = []
        self.last_shed_time = None
        self.last_recovery_time = None
        self._recovery_start = None
        self._reload_config()

    # ──────────────────────────────────────────────────────────────
    # Configuration
    # ──────────────────────────────────────────────────────────────

                _LOGGER.warning("[Delestage] _on_power_change: entity_id=%s, current_power=%.0f", entity_id, current_power)
    def _reload_config(self):
        """Recharge la config depuis data + options."""
        cfg = {**self.entry.data, **self.entry.options}
        self.power_sensor   = cfg.get(CONF_POWER_SENSOR, "")
                _LOGGER.warning("[Delestage] _delestage_logic: state=%s, current_power=%.0f", self.state, current_power)
        self.max_power      = float(cfg.get(CONF_MAX_POWER, 6000))
        self.recovery_delay = float(cfg.get(CONF_RECOVERY_DELAY, 300))
                        _LOGGER.warning("[Delestage] Déclenchement délestage: current_power=%.0f > max_power=%.0f", current_power, self.max_power)
        self.rearm_margin   = float(cfg.get(CONF_REARM_MARGIN, 0))
        self.equipments     = cfg.get(CONF_EQUIPMENTS, [])
        _LOGGER.warning("[Delestage] _reload_config: power_sensor=%s, max_power=%.0f, recovery_delay=%.0f, rearm_margin=%.0f, nb_equipments=%d", self.power_sensor, self.max_power, self.recovery_delay, self.rearm_margin, len(self.equipments))
        for idx, eq in enumerate(self.equipments):
                            _LOGGER.warning("[Delestage] Début réarmement: current_power=%.0f < max_power-marge=%.0f", current_power, self.max_power - self.rearm_margin)
            _LOGGER.warning("[Delestage] Equipement #%d: %s", idx+1, eq)
        _LOGGER.debug(
                            _LOGGER.warning("[Delestage] Réarmement effectif après %.0f s", self.recovery_delay)
            "Config rechargée — capteur: %s | max: %.0f W | équipements: %d",
            self.power_sensor, self.max_power, len(self.equipments)
        )

    def _get_recovery_countdown(self):
        """Secondes restantes avant réarmement."""
                _LOGGER.warning("[Delestage] _shed_devices: current_power=%.0f, max_power=%.0f", current_power, self.max_power)
        if self._recovery_start is None:
            return None
        elapsed = (datetime.now() - self._recovery_start).total_seconds()
        remaining = self.recovery_delay - elapsed
        return max(0, round(remaining))

    # ──────────────────────────────────────────────────────────────
    # Setup
    # ──────────────────────────────────────────────────────────────

                    _LOGGER.warning("[Delestage] Coupure: %s (%.0f W)", eq["entity_id"], eq_power)
    async def async_setup(self):
        """Abonnement au capteur de puissance."""
        if not self.power_sensor:
            _LOGGER.error("Aucun capteur de puissance configuré !")
                        _LOGGER.warning("[Delestage] Puissance après coupure: %.0f W", current_power - shed_power)
            return
        async_track_state_change_event(
            self.hass,
            [self.power_sensor],
            self._power_changed,
        )
        self.entry.async_on_unload(
                _LOGGER.warning("[Delestage] _recover_devices: devices_shed=%s", self.devices_shed)
            self.entry.add_update_listener(self._options_updated)
        )
        _LOGGER.info("Délestage démarré — capteur: %s", self.power_sensor)

    async def _options_updated(self, hass, entry):
        """Appelé quand les options changent."""
        self._reload_config()
        _LOGGER.info(
                    _LOGGER.warning("[Delestage] Rallumage: %s, current_power=%.0f", entity_id, current_power)
            "Options mises à jour — %d équipement(s) configuré(s)",
                        _LOGGER.warning("[Delestage] Puissance trop élevée après rallumage: %.0f W", current_power)
            len(self.equipments)
        )
        self.async_update_listeners()

    # ──────────────────────────────────────────────────────────────
    # Logique principale
    # ──────────────────────────────────────────────────────────────

    async def _async_update_data(self):
        """Appelé par le coordinator toutes les 5s (polling de secours)."""
                _LOGGER.warning("[Delestage] _turn_off: %s", entity_id)
        state = self.hass.states.get(self.power_sensor)
        if state is None:
            return self.data
        try:
            current_power = float(state.state)
                _LOGGER.warning("[Delestage] _turn_on: %s", entity_id)
        except (ValueError, TypeError):
            return self.data
        await self._delestage_logic(current_power)
        return {
            "state":        self.state,
            "devices_shed": self.devices_shed,
        }

    async def _power_changed(self, event):
        """Callback temps réel sur changement de puissance."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        try:
            current_power = float(new_state.state)
        except (ValueError, TypeError):
            return
        await self._delestage_logic(current_power)

    async def _delestage_logic(self, current_power: float):
        """Décision : délester ou réarmer."""
        _LOGGER.debug("Puissance: %.0f W / seuil: %.0f W", current_power, self.max_power)

        if current_power > self.max_power:
            if self.state != STATE_SHEDDING:
                _LOGGER.warning("Seuil dépassé (%.0f W) — délestage !", current_power)
            self._recovery_start = None
            await self._shed_devices(current_power)

        elif current_power < (self.max_power - self.rearm_margin):
            if self.state == STATE_SHEDDING and self.devices_shed:
                if self._recovery_start is None:
                    self._recovery_start = datetime.now()
                    self.state = STATE_RECOVERING
                    _LOGGER.info(
                        "Puissance OK (%.0f W) — réarmement dans %.0f s",
                        current_power, self.recovery_delay
                    )
            elif self.state == STATE_RECOVERING:
                if self._get_recovery_countdown() == 0:
                    await self._recover_devices(current_power)

        self.async_update_listeners()

    # ──────────────────────────────────────────────────────────────
    # Délestage
    # ──────────────────────────────────────────────────────────────

    async def _shed_devices(self, current_power: float):
        """Coupe les équipements par priorité jusqu'à repasser sous le seuil."""
        if not self.equipments:
            _LOGGER.warning("Aucun équipement configuré pour le délestage !")
            return

        sorted_eq = sorted(self.equipments, key=lambda e: e[CONF_DEVICE_PRIORITY])
        shed_power = 0

        for eq in sorted_eq:
            entity_id = eq[CONF_DEVICE_ENTITY]

            if entity_id in self.devices_shed:
                shed_power += float(eq.get(CONF_DEVICE_FIXED_PWR, 0))
                continue

            state = self.hass.states.get(entity_id)
            if state and state.state in ("off", "unavailable", "unknown"):
                continue

            if eq.get(CONF_DEVICE_POWER_MODE) == "sensor":
                sensor = self.hass.states.get(eq.get(CONF_DEVICE_PWR_SENSOR, ""))
                try:
                    eq_power = float(sensor.state) if sensor else 0
                except (ValueError, TypeError):
                    eq_power = 0
            else:
                eq_power = float(eq.get(CONF_DEVICE_FIXED_PWR, 0))

            await self._turn_off(entity_id)
            self.devices_shed.append(entity_id)
            shed_power += eq_power

            _LOGGER.info(
                "Délestage : %s coupé (%.0f W) | économie cumulée: %.0f W",
                eq.get(CONF_DEVICE_NAME, entity_id), eq_power, shed_power
            )

            if (current_power - shed_power) <= self.max_power:
                break

        self.state = STATE_SHEDDING
        self.last_shed_time = datetime.now()

    # ──────────────────────────────────────────────────────────────
    # Réarmement
    # ──────────────────────────────────────────────────────────────

    async def _recover_devices(self, current_power: float):
        """Rallume les équipements dans l'ordre inverse."""
        self.state = STATE_RECOVERING
        self.async_update_listeners()

        recovered = []
        for entity_id in reversed(list(self.devices_shed)):
            await self._turn_on(entity_id)

            sensor_state = self.hass.states.get(self.power_sensor)
            try:
                current_power = float(sensor_state.state) if sensor_state else 0
            except (ValueError, TypeError):
                pass

            if current_power > self.max_power:
                await self._turn_off(entity_id)
                _LOGGER.warning(
                    "Réarmement annulé pour %s : %.0f W > seuil %.0f W",
                    entity_id, current_power, self.max_power
                )
                break

            recovered.append(entity_id)
            _LOGGER.info("Réarmement OK : %s", entity_id)

        self.devices_shed = [d for d in self.devices_shed if d not in recovered]
        self.last_recovery_time = datetime.now()
        self._recovery_start = None
        self.state = STATE_IDLE if not self.devices_shed else STATE_SHEDDING

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    async def _turn_off(self, entity_id: str):
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(
            domain, "turn_off", {"entity_id": entity_id}, blocking=True
        )

    async def _turn_on(self, entity_id: str):
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(
            domain, "turn_on", {"entity_id": entity_id}, blocking=True
        )
