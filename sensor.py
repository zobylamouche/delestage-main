"""Plateforme sensor pour le délestage électrique."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DelestageSensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Créer et enregistrer le sensor de délestage."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # Add main sensor
    entities = [DelestageSensor(coordinator, entry)]

    # Add one sensor per equipment
    for eq in coordinator.equipments:
        name = eq.get("device_name", "Equipement")
        entity_id = eq.get("entity_id", "")
        unique_id = f"{DOMAIN}_{entity_id}_equip"
        class EquipmentSensor(SensorEntity):
            def __init__(self, eq, coordinator):
                self._eq = eq
                self._coordinator = coordinator
                self._attr_name = name
                self._attr_unique_id = unique_id
                self._attr_icon = "mdi:power-plug"
            @property
            def native_value(self):
                state = self._coordinator.hass.states.get(entity_id)
                return state.state if state else "inconnu"
            @property
            def extra_state_attributes(self):
                return {
                    "priority": self._eq.get("priority", 0),
                    "power": self._eq.get("fixed_power", 0),
                    "shed": entity_id in self._coordinator.devices_shed,
                }
        entities.append(EquipmentSensor(eq, coordinator))

    async_add_entities(entities, True)

    # Register dashboard entities for Home Assistant dashboards
    from .dashboard_entity import DelestageStateEntity, DelestageEquipmentEntity
    dashboard_entities = [DelestageStateEntity(coordinator)]
    for eq in coordinator.equipments:
        dashboard_entities.append(DelestageEquipmentEntity(eq, coordinator))
    async_add_entities(dashboard_entities, True)
