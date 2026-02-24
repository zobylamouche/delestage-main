"""Coordinateur de délestage électrique."""
import logging
from datetime import timedelta, datetime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from .const import *

_LOGGER = logging.getLogger(__name__)


class DelestageCoordinator(DataUpdateCoordinator):
    """Logique centrale de délestage."""

    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(
            hass,
            _LOGGER,
            name="Delestage Coordinator",
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.state = STATE_IDLE
        self.devices_shed = []
        self.last_shed_time = None
        self.last_recovery_time = None
        self._recovery_start = None
        self._unsub_tracker = None
        self._reload_config()
        # Variable pour activer/désactiver le délestage (prise depuis les options)
        self.enable_shedding = self.entry.options.get("enable_shedding", True)

    # ──────────────────────────────────────────────────────────────
    # Configuration
    # ──────────────────────────────────────────────────────────────

    def _reload_config(self):
        """Recharge la config depuis data + options."""
        cfg = {**self.entry.data, **self.entry.options}
        self.power_sensor   = cfg.get(CONF_POWER_SENSOR, "")
        self.max_power      = float(cfg.get(CONF_MAX_POWER, 6000))
        self.recovery_delay = float(cfg.get(CONF_RECOVERY_DELAY, 300))
        self.rearm_margin   = float(cfg.get(CONF_REARM_MARGIN, 0))
        self.equipments     = sorted(
            cfg.get(CONF_EQUIPMENTS, []),
            key=lambda e: int(float(e.get(CONF_DEVICE_PRIORITY, 99)))
        )
        self.enable_shedding = cfg.get("enable_shedding", True)
        _LOGGER.debug(
            "Config rechargée — capteur: %s | max: %.0f W | équipements: %d",
            self.power_sensor, self.max_power, len(self.equipments)
        )

    # ──────────────────────────────────────────────────────────────
    # Setup / Teardown
    # ──────────────────────────────────────────────────────────────

    async def async_setup(self):
        """Abonnement temps réel au capteur de puissance."""
        if self._unsub_tracker:
            self._unsub_tracker()
        if self.power_sensor:
            self._unsub_tracker = async_track_state_change_event(
                self.hass, [self.power_sensor], self._power_changed
            )
            _LOGGER.debug("Tracker abonné sur %s", self.power_sensor)

    async def async_unload(self):
        """Désabonnement."""
        if self._unsub_tracker:
            self._unsub_tracker()
            self._unsub_tracker = None

    # ──────────────────────────────────────────────────────────────
    # Helpers internes
    # ──────────────────────────────────────────────────────────────

    def _get_recovery_countdown(self):
        """Secondes restantes avant réarmement."""
        if self._recovery_start is None:
            return None
        elapsed = (datetime.now() - self._recovery_start).total_seconds()
        return max(0, round(self.recovery_delay - elapsed))

    def _get_device_power(self, eq: dict) -> float:
        """Puissance réelle d'un équipement."""
        entity_id = eq.get(CONF_DEVICE_ENTITY, "")
        mode = eq.get(CONF_DEVICE_POWER_MODE, "fixed")

        if mode == "sensor":
            sensor_id = eq.get(CONF_DEVICE_PWR_SENSOR, "")
            if sensor_id:
                s = self.hass.states.get(sensor_id)
                if s and s.state not in ("unavailable", "unknown", None):
                    try:
                        return float(s.state)
                    except (ValueError, TypeError):
                        pass
            return 0.0
        else:
            # Puissance fixe — retourne 0 si l'équipement est éteint
            s = self.hass.states.get(entity_id)
            if s and s.state not in ("off", "unavailable", "unknown"):
                try:
                    return float(eq.get(CONF_DEVICE_FIXED_PWR, 0))
                except (ValueError, TypeError):
                    return 0.0
            return 0.0

    def _build_data(self, current_power: float) -> dict:
        """Construit le dict de données exposé aux sensors."""
        shed_power = 0.0
        all_devices = []

        for eq in self.equipments:
            entity_id = eq.get(CONF_DEVICE_ENTITY, "")
            is_shed = entity_id in self.devices_shed
            power = self._get_device_power(eq)
            s = self.hass.states.get(entity_id)

            if is_shed:
                shed_power += float(eq.get(CONF_DEVICE_FIXED_PWR, 0))

            all_devices.append({
                "name":      eq.get(CONF_DEVICE_NAME, entity_id),
                "entity_id": entity_id,
                "priority":  int(float(eq.get(CONF_DEVICE_PRIORITY, 99))),
                "power":     power,
                "status":    s.state if s else "inconnu",
                "shed":      is_shed,
            })

        return {
            "state":               self.state,
            "current_power":       current_power,
            "max_power":           self.max_power,
            "charge_percent":      round((current_power / self.max_power) * 100, 1)
                                   if self.max_power else 0,
            "devices_shed":        self.devices_shed,
            "devices_shed_count":  len(self.devices_shed),
            "total_power_shed":    shed_power,
            "recovery_countdown":  self._get_recovery_countdown(),
            "last_shed_time":      str(self.last_shed_time)
                                   if self.last_shed_time else None,
            "last_recovery_time":  str(self.last_recovery_time)
                                   if self.last_recovery_time else None,
            "all_devices":         all_devices,
        }

    # ──────────────────────────────────────────────────────────────
    # Polling + temps réel
    # ──────────────────────────────────────────────────────────────

    async def _async_update_data(self):
        """Polling toutes les 5 s."""
        s = self.hass.states.get(self.power_sensor)
        if s is None or s.state in ("unavailable", "unknown"):
            return self._build_data(0.0)
        try:
            current_power = float(s.state)
        except (ValueError, TypeError):
            return self._build_data(0.0)

        await self._delestage_logic(current_power)
        return self._build_data(current_power)

    async def _power_changed(self, event):
        """Callback temps réel sur changement de puissance."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unavailable", "unknown"):
            return
        try:
            current_power = float(new_state.state)
        except (ValueError, TypeError):
            return
        await self._delestage_logic(current_power)
        self.async_set_updated_data(self._build_data(current_power))

    # ──────────────────────────────────────────────────────────────
    # Logique de délestage
    # ──────────────────────────────────────────────────────────────

    async def _delestage_logic(self, current_power: float):
        """Décision : délester ou réarmer."""
        _LOGGER.debug(
            "Puissance: %.0f W / seuil: %.0f W / état: %s | Délestage activé: %s",
            current_power, self.max_power, self.state, self.enable_shedding
        )

        if not self.enable_shedding:
            # Si le délestage est désactivé, on ne coupe rien et on réarme tout si besoin
            if self.devices_shed:
                _LOGGER.info("Délestage désactivé : réarmement de tous les équipements si besoin.")
                await self._recover_devices(current_power)
            self.state = STATE_IDLE
            self._recovery_start = None
            return

        # ── Délestage nécessaire ───────────────────────────────
        if current_power > self.max_power:
            if self.state == STATE_RECOVERING:
                self._recovery_start = None
                self.state = STATE_SHEDDING

            await self._shed_devices(current_power)

        # ── En dessous du seuil → réarmement ──────────────────
        elif self.state == STATE_SHEDDING and self.devices_shed:
            threshold = self.max_power - self.rearm_margin
            if current_power <= threshold:
                if self._recovery_start is None:
                    self._recovery_start = datetime.now()
                    self.state = STATE_RECOVERING
                    _LOGGER.info(
                        "Délai de réarmement démarré (%.0f s)", self.recovery_delay
                    )
                elif (datetime.now() - self._recovery_start).total_seconds() \
                        >= self.recovery_delay:
                    await self._recover_devices(current_power)

        # ── Récupération en cours : vérifier le délai ─────────
        elif self.state == STATE_RECOVERING:
            if self._recovery_start and \
               (datetime.now() - self._recovery_start).total_seconds() \
               >= self.recovery_delay:
                await self._recover_devices(current_power)

        # ── Idle propre ───────────────────────────────────────
        elif not self.devices_shed:
            self.state = STATE_IDLE
            self._recovery_start = None

    # ──────────────────────────────────────────────────────────────
    # Délestage
    # ──────────────────────────────────────────────────────────────

    async def _shed_devices(self, current_power: float):
        """Coupe les équipements par ordre de priorité jusqu'à repasser sous le seuil."""
        for eq in self.equipments:  # déjà trié par priorité
            if current_power <= self.max_power:
                break

            entity_id = eq.get(CONF_DEVICE_ENTITY, "")
            if entity_id in self.devices_shed:
                continue

            s = self.hass.states.get(entity_id)
            if s is None or s.state in ("off", "unavailable", "unknown"):
                continue

            await self._turn_off(entity_id)
            self.devices_shed.append(entity_id)
            _LOGGER.info(
                "Délestage : %s (priorité %s) — %.0f W",
                entity_id,
                eq.get(CONF_DEVICE_PRIORITY),
                current_power,
            )

            # Relire la puissance après coupure
            s2 = self.hass.states.get(self.power_sensor)
            if s2 and s2.state not in ("unavailable", "unknown"):
                try:
                    current_power = float(s2.state)
                except (ValueError, TypeError):
                    pass

        self.state = STATE_SHEDDING
        self.last_shed_time = datetime.now()

    # ──────────────────────────────────────────────────────────────
    # Réarmement
    # ──────────────────────────────────────────────────────────────

    async def _recover_devices(self, current_power: float):
        """Rallume les équipements dans l'ordre inverse de priorité."""
        recovered = []

        for entity_id in reversed(list(self.devices_shed)):
            await self._turn_on(entity_id)

            s = self.hass.states.get(self.power_sensor)
            try:
                current_power = float(s.state) if s else current_power
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
    # Helpers turn_on / turn_off
    # ──────────────────────────────────────────────────────────────

    async def _turn_off(self, entity_id: str):
        domain = entity_id.split(".")[0]
        _LOGGER.info(f"[Délestage] Désactivation demandée pour {entity_id} (domain: {domain})")
        await self.hass.services.async_call(
            domain, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        _LOGGER.info(f"[Délestage] Désactivation effectuée pour {entity_id}")

    async def _turn_on(self, entity_id: str):
        domain = entity_id.split(".")[0]
        _LOGGER.info(f"[Délestage] Activation demandée pour {entity_id} (domain: {domain})")
        await self.hass.services.async_call(
            domain, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        _LOGGER.info(f"[Délestage] Activation effectuée pour {entity_id}")
