"""Plateforme sensor pour le délestage électrique."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .entity import DelestageSensor, DelestageEquipmentSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Créer et enregistrer les sensors de délestage."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [DelestageSensor(coordinator, entry)]

    for eq in coordinator.equipments:
        entities.append(DelestageEquipmentSensor(coordinator, entry, eq))

    async_add_entities(entities, True)
