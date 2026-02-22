import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    NumberSelector,
    SelectSelector,
)
from .const import *

class DelestageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration initiale."""

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Delestage", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_POWER_SENSOR): EntitySelector({"domain": "sensor"}),
                vol.Required(CONF_MAX_POWER): NumberSelector({"min": 100, "max": 10000, "unit_of_measurement": "W"}),
                vol.Required(CONF_RECOVERY_DELAY): NumberSelector({"min": 10, "max": 3600, "unit_of_measurement": "s"}),
                vol.Optional(CONF_REARM_MARGIN, default=0): NumberSelector({"min": 0, "max": 1000, "unit_of_measurement": "W"}),
            }),
            errors=errors,
            description_placeholders={
                CONF_POWER_SENSOR: "Capteur qui mesure la puissance totale consommée par le logement.",
                CONF_MAX_POWER: "Au-dessus de cette puissance, certains équipements seront coupés automatiquement.",
                CONF_RECOVERY_DELAY: "Temps pendant lequel la consommation doit rester sous le seuil avant de réactiver les équipements.",
                CONF_REARM_MARGIN: "Marge de sécurité pour éviter les basculements trop fréquents.",
            },
        )

    async def async_step_options(self, user_input=None):
        """Flux d’options pour gérer les équipements à délester."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Équipements à délester", data=user_input)
        # Pour simplifier, on propose d’ajouter/modifier un équipement à la fois
        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema({
                vol.Required("entity_id"): EntitySelector({"domain": ["switch", "climate"]}),
                vol.Required("priority"): NumberSelector({"min": 1, "max": 10}),
                vol.Required("power_mode"): SelectSelector({"options": ["fixed", "sensor"]}),
                vol.Optional("fixed_power", default=0): NumberSelector({"min": 0, "max": 5000, "unit_of_measurement": "W"}),
                vol.Optional("power_sensor"): EntitySelector({"domain": "sensor"}),
            }),
            errors=errors,
            description_placeholders={
                "entity_id": "Équipement à délester (ex : switch.chauffe_eau)",
                "priority": "1 = délesté en premier",
                "power_mode": "Choisissez entre puissance fixe ou capteur.",
                "fixed_power": "Puissance estimée de l’équipement (en W)",
                "power_sensor": "Capteur de puissance associé à l’équipement",
            },
        )
