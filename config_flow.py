import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from .const import (
    DOMAIN,
    CONF_POWER_SENSOR,
    CONF_MAX_POWER,
    CONF_RECOVERY_DELAY,
    CONF_REARM_MARGIN,
    CONF_EQUIPMENTS,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ENTITY,
    CONF_DEVICE_PRIORITY,
    CONF_DEVICE_POWER_MODE,
    CONF_DEVICE_FIXED_PWR,
    CONF_DEVICE_PWR_SENSOR,
)


class DelestageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration initiale."""

    VERSION = 1

    @staticmethod
    @config_entries.HANDLERS.register(DOMAIN)
    def async_get_options_flow(config_entry):
        """Retourne le flux d'options."""
        return DelestageOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Validation : vérifier que le capteur existe
            if self.hass.states.get(user_input[CONF_POWER_SENSOR]) is None:
                errors[CONF_POWER_SENSOR] = "entity_not_found"
            else:
                return self.async_create_entry(
                    title="Délestage Électrique",
                    data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_POWER_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_MAX_POWER, default=6000): NumberSelector(
                    NumberSelectorConfig(min=100, max=50000, step=100, unit_of_measurement="W", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_RECOVERY_DELAY, default=60): NumberSelector(
                    NumberSelectorConfig(min=10, max=3600, step=10, unit_of_measurement="s", mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_REARM_MARGIN, default=200): NumberSelector(
                    NumberSelectorConfig(min=0, max=2000, step=50, unit_of_measurement="W", mode=NumberSelectorMode.BOX)
                ),
            }),
            errors=errors,
        )


class DelestageOptionsFlowHandler(config_entries.OptionsFlow):
    """Flux d'options pour gérer les équipements à délester."""

    def __init__(self):
        self._equipments = []

    async def async_step_init(self, user_input=None):
        """Menu principal des options."""
        # Récupère la liste existante
        self._equipments = list(
            self.config_entry.options.get(CONF_EQUIPMENTS, [])
        )

        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add()
            elif action == "remove":
                return await self.async_step_remove()
            elif action == "save":
                return self.async_create_entry(
                    title="",
                    data={CONF_EQUIPMENTS: self._equipments}
                )

        # Résumé des équipements configurés
        summary = "\n".join(
            f"• {eq[CONF_DEVICE_NAME]} — priorité {eq[CONF_DEVICE_PRIORITY]} — {eq[CONF_DEVICE_FIXED_PWR if eq[CONF_DEVICE_POWER_MODE] == 'fixed' else CONF_DEVICE_PWR_SENSOR]} W"
            for eq in self._equipments
        ) or "Aucun équipement configuré"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="add"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "add",    "label": "➕ Ajouter un équipement"},
                            {"value": "remove", "label": "🗑️ Supprimer un équipement"},
                            {"value": "save",   "label": "💾 Sauvegarder et fermer"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            description_placeholders={"equipments": summary},
        )

    async def async_step_add(self, user_input=None):
        """Formulaire d'ajout d'un équipement."""
        errors = {}

        if user_input is not None:
            # Validation
            entity_id = user_input[CONF_DEVICE_ENTITY]
            if self.hass.states.get(entity_id) is None:
                errors[CONF_DEVICE_ENTITY] = "entity_not_found"
            else:
                self._equipments.append({
                    CONF_DEVICE_NAME:      user_input[CONF_DEVICE_NAME],
                    CONF_DEVICE_ENTITY:    user_input[CONF_DEVICE_ENTITY],
                    CONF_DEVICE_PRIORITY:  int(user_input[CONF_DEVICE_PRIORITY]),
                    CONF_DEVICE_POWER_MODE: user_input[CONF_DEVICE_POWER_MODE],
                    CONF_DEVICE_FIXED_PWR: int(user_input.get(CONF_DEVICE_FIXED_PWR, 0)),
                    CONF_DEVICE_PWR_SENSOR: user_input.get(CONF_DEVICE_PWR_SENSOR, ""),
                })
                # Retour au menu principal
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_NAME): TextSelector(),
                vol.Required(CONF_DEVICE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain=["switch", "climate", "input_boolean"])
                ),
                vol.Required(CONF_DEVICE_PRIORITY, default=1): NumberSelector(
                    NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_DEVICE_POWER_MODE, default="fixed"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "fixed",  "label": "⚡ Puissance fixe (W)"},
                            {"value": "sensor", "label": "📡 Capteur de puissance"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_DEVICE_FIXED_PWR, default=1000): NumberSelector(
                    NumberSelectorConfig(min=0, max=10000, step=50, unit_of_measurement="W", mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_DEVICE_PWR_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            }),
            errors=errors,
        )

    async def async_step_remove(self, user_input=None):
        """Formulaire de suppression d'un équipement."""
        errors = {}

        if not self._equipments:
            return await self.async_step_init()

        if user_input is not None:
            name_to_remove = user_input.get("device_to_remove")
            self._equipments = [
                eq for eq in self._equipments
                if eq[CONF_DEVICE_NAME] != name_to_remove
            ]
            return await self.async_step_init()

        options = [
            {"value": eq[CONF_DEVICE_NAME], "label": f"{eq[CONF_DEVICE_NAME]} (priorité {eq[CONF_DEVICE_PRIORITY]})"}
            for eq in self._equipments
        ]

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({
                vol.Required("device_to_remove"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            errors=errors,
        )
