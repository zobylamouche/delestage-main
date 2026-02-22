"""Plateforme sensor — crée toutes les entités au démarrage."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import (
    DelestageSensor,
    DelestageEquipmentSensor,
    DelestagePowerSensor,
    DelestageChargeSensor,
    DelestageCountSensor,
    DelestageShedPowerSensor,
    DelestageCountdownSensor,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Créer et enregistrer tous les sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        # Sensor principal (état + tous les attributs)
        DelestageSensor(coordinator, entry),
        # Sensors dédiés pour le dashboard
        DelestagePowerSensor(coordinator, entry),
        DelestageChargeSensor(coordinator, entry),
        DelestageCountSensor(coordinator, entry),
        DelestageShedPowerSensor(coordinator, entry),
        DelestageCountdownSensor(coordinator, entry),
    ]

    # Un sensor par équipement configuré
    for eq in coordinator.equipments:
        entities.append(DelestageEquipmentSensor(coordinator, entry, eq))

    async_add_entities(entities, True)
    _LOGGER.info(
        "Délestage : %d entité(s) créée(s) (dont %d équipement(s))",
        len(entities), len(coordinator.equipments)
    )
