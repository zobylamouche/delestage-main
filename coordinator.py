"""
Coordinator du délestage électrique.

Rôle : surveiller la puissance en temps réel via un listener d'état
(réactif, pas de polling), et piloter les équipements selon la logique
de délestage/récupération.
"""
import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    DOMAIN,
    CONF_POWER_SENSOR,
    CONF_MAX_POWER,
    CONF_RECOVERY_DELAY,
    CONF_REARM_MARGIN,
    CONF_EQUIPMENTS,
    CONF_DEVICE_ENTITY,
    CONF_DEVICE_PRIORITY,
    CONF_DEVICE_POWER_MODE,
    CONF_DEVICE_FIXED_PWR,
    CONF_DEVICE_PWR_SENSOR,
    STATE_IDLE,
    STATE_SHEDDING,
    STATE_RECOVERING,
)

_LOGGER = logging.getLogger(__name__)


class DelestageCoordinator(DataUpdateCoordinator):
    """
    Gère la logique de délestage.

    États possibles :
      IDLE       → puissance normale, rien à faire
      SHEDDING   → seuil dépassé, des équipements sont coupés
      RECOVERING → puissance redescendue, on attend recovery_delay
                   avant de rallumer les équipements
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialiser avec les paramètres de la config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            # Pas de polling régulier : on écoute les changements d'état
            update_interval=None,
        )
        self.entry = entry

        # ── Paramètres globaux ────────────────────────────────────
        self.power_sensor: str = entry.data[CONF_POWER_SENSOR]
        self.max_power: float = float(entry.data[CONF_MAX_POWER])
        self.recovery_delay: float = float(entry.data[CONF_RECOVERY_DELAY])
        self.rearm_margin: float = float(entry.data.get(CONF_REARM_MARGIN, 0))

        # ── État interne ──────────────────────────────────────────
        self.delestage_state: str = STATE_IDLE
        self.devices_shed: list[str] = []       # Entités actuellement délestées
        self.current_power: float = 0.0
        self.last_shed_time: datetime | None = None
        self.last_recovery_time: datetime | None = None
        self._recovery_start: datetime | None = None
        self._unsub_listener = None             # Pour annuler le listener

    @property
    def equipments(self) -> list[dict]:
        """Équipements lus depuis les options (mis à jour dynamiquement)."""
        return self.entry.options.get(CONF_EQUIPMENTS, [])

    async def async_setup(self) -> None:
        """
        Abonnement au capteur de puissance.
        Utilise async_track_state_change_event (remplace l'ancienne
        async_track_state_change qui est dépréciée depuis HA 2022).
        """
        self._unsub_listener = async_track_state_change_event(
            self.hass,
            [self.power_sensor],    # liste d'entités à surveiller
            self._handle_power_event,
        )
        _LOGGER.debug(
            "Délestage : écoute du capteur %s démarrée (seuil=%.0f W, "
            "délai=%ds, marge=%.0f W)",
            self.power_sensor, self.max_power,
            self.recovery_delay, self.rearm_margin,
        )

    async def async_shutdown(self) -> None:
        """Annuler le listener lors du déchargement de l'intégration."""
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    @callback
    def _handle_power_event(self, event) -> None:
        """
        Callback appelé à chaque changement d'état du capteur.
        Le décorateur @callback indique que c'est une fonction synchrone
        dans la boucle d'événements → on schedule la coroutine async.
        """
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        try:
            power = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Capteur %s : valeur non numérique '%s'",
                self.power_sensor, new_state.state,
            )
            return

        self.current_power = power
        # Planifier la coroutine sans bloquer le callback
        self.hass.async_create_task(self._run_delestage_logic(power))

    async def _run_delestage_logic(self, current_power: float) -> None:
        """
        Machine à états du délestage.

        IDLE     → si puissance > seuil              → délester et passer en SHEDDING
        SHEDDING → si puissance < seuil - marge      → démarrer timer de récupération
                 → si puissance remonte au-dessus    → annuler le timer
        RECOVERING → géré dans SHEDDING via _recovery_start
        IDLE/RECOVERING → fin de récupération        → passer en IDLE
        """

        if self.delestage_state == STATE_IDLE:
            if current_power > self.max_power:
                _LOGGER.info(
                    "Seuil dépassé (%.0f W > %.0f W) → délestage",
                    current_power, self.max_power,
                )
                await self._shed_devices(current_power)

        elif self.delestage_state == STATE_SHEDDING:
            threshold_recovery = self.max_power - self.rearm_margin

            if current_power < threshold_recovery:
                # Puissance redescendue : démarrer ou vérifier le timer
                if self._recovery_start is None:
                    self._recovery_start = datetime.now()
                    _LOGGER.info(
                        "Puissance sous seuil (%.0f W < %.0f W) → "
                        "timer de récupération démarré (%ds)",
                        current_power, threshold_recovery, self.recovery_delay,
                    )
                    self.delestage_state = STATE_RECOVERING
                    # Notifier les entités de l'UI
                    self.async_set_updated_data(None)
                else:
                    elapsed = (datetime.now() - self._recovery_start).total_seconds()
                    if elapsed >= self.recovery_delay:
                        _LOGGER.info(
                            "Délai de récupération écoulé (%.0fs) → réarmement",
                            elapsed,
                        )
                        await self._recover_devices(current_power)
            else:
                # Puissance encore trop haute : annuler le timer
                if self._recovery_start is not None:
                    _LOGGER.debug(
                        "Puissance remontée (%.0f W) → timer annulé", current_power
                    )
                    self._recovery_start = None
                    self.delestage_state = STATE_SHEDDING
                    self.async_set_updated_data(None)

        elif self.delestage_state == STATE_RECOVERING:
            # Vérifier si le délai est écoulé
            if self._recovery_start is not None:
                elapsed = (datetime.now() - self._recovery_start).total_seconds()
                if elapsed >= self.recovery_delay:
                    await self._recover_devices(current_power)
                elif current_power >= self.max_power:
                    # La puissance a re-dépassé le seuil pendant la récupération
                    _LOGGER.info(
                        "Puissance remontée pendant récup (%.0f W) → "
                        "retour en délestage", current_power,
                    )
                    self._recovery_start = None
                    self.delestage_state = STATE_SHEDDING
                    self.async_set_updated_data(None)

    def _get_equipment_power(self, eq: dict) -> float:
        """
        Retourner la puissance estimée d'un équipement.
        Mode 'fixed' : valeur configurée statiquement.
        Mode 'sensor' : lecture en temps réel du capteur associé.
        """
        mode = eq.get(CONF_DEVICE_POWER_MODE, "fixed")
        if mode == "sensor":
            sensor_id = eq.get(CONF_DEVICE_PWR_SENSOR)
            if sensor_id:
                state = self.hass.states.get(sensor_id)
                if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    try:
                        return float(state.state)
                    except (ValueError, TypeError):
                        pass
        return float(eq.get(CONF_DEVICE_FIXED_PWR, 0))

    async def _shed_devices(self, current_power: float) -> None:
        """
        Couper les équipements par ordre de priorité croissante
        jusqu'à ce que la puissance estimée passe sous le seuil.
        """
        excess = current_power - self.max_power
        _LOGGER.info("Excès à délester : %.0f W", excess)

        # Trier par priorité (1 = délestage en premier)
        sorted_eq = sorted(
            self.equipments,
            key=lambda e: e.get(CONF_DEVICE_PRIORITY, 99),
        )

        shed_power = 0.0
        self.devices_shed = []

        for eq in sorted_eq:
            entity_id = eq.get(CONF_DEVICE_ENTITY)
            if not entity_id:
                continue

            eq_power = self._get_equipment_power(eq)
            await self._turn_off(entity_id)
            self.devices_shed.append(entity_id)
            shed_power += eq_power

            _LOGGER.info(
                "Délestage : %s coupé (%.0f W, total délésté=%.0f W)",
                entity_id, eq_power, shed_power,
            )

            # Arrêter de délester si on a récupéré suffisamment
            if shed_power >= excess:
                break

        self.delestage_state = STATE_SHEDDING
        self.last_shed_time = datetime.now()
        self._recovery_start = None
        self.async_set_updated_data(None)

    async def _recover_devices(self, current_power: float) -> None:
        """
        Rallumer les équipements dans l'ordre inverse du délestage
        (le dernier coupé est rallumé en premier).
        On vérifie après chaque rallumage que la puissance ne re-dépasse
        pas le seuil.
        """
        _LOGGER.info("Réarmement : tentative de rallumage de %s", self.devices_shed)

        for entity_id in reversed(self.devices_shed[:]):
            await self._turn_on(entity_id)

            # Laisser le temps à l'équipement de monter en charge
            # et lire la puissance actuelle
            sensor_state = self.hass.states.get(self.power_sensor)
            if sensor_state and sensor_state.state not in (
                STATE_UNAVAILABLE, STATE_UNKNOWN
            ):
                try:
                    fresh_power = float(sensor_state.state)
                    if fresh_power > self.max_power:
                        # Puissance trop haute : recouper cet équipement
                        _LOGGER.warning(
                            "Réarmement : %s rallumé mais puissance trop haute "
                            "(%.0f W) → recoupé", entity_id, fresh_power,
                        )
                        await self._turn_off(entity_id)
                        continue
                except (ValueError, TypeError):
                    pass

            # Retirer de la liste des délestés
            if entity_id in self.devices_shed:
                self.devices_shed.remove(entity_id)
            _LOGGER.info("Réarmement : %s rallumé", entity_id)

        self.delestage_state = STATE_IDLE
        self.last_recovery_time = datetime.now()
        self._recovery_start = None
        self.devices_shed = []
        self.async_set_updated_data(None)

    async def _turn_off(self, entity_id: str) -> None:
        """Couper un équipement via son service HA."""
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(
            domain, "turn_off",
            {"entity_id": entity_id},
            blocking=False,
        )

    async def _turn_on(self, entity_id: str) -> None:
        """Rallumer un équipement via son service HA."""
        domain = entity_id.split(".")[0]
        await self.hass.services.async_call(
            domain, "turn_on",
            {"entity_id": entity_id},
            blocking=False,
        )

    @property
    def recovery_remaining(self) -> float:
        """Secondes restantes avant réarmement (0 si non applicable)."""
        if self._recovery_start is None:
            return 0.0
        elapsed = (datetime.now() - self._recovery_start).total_seconds()
        return max(0.0, self.recovery_delay - elapsed)
