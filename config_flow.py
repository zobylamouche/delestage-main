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
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return DelestageOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            sensor = user_input.get(CONF_POWER_SENSOR, "")
            if not sensor:
                errors[CONF_POWER_SENSOR] = "entity_not_found"
            else:
                return self.async_create_entry(
                    title="Délestage Électrique",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_POWER_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["sensor", "input_number"])
                ),
                vol.Required(CONF_MAX_POWER, default=6000): NumberSelector(
                    NumberSelectorConfig(
                        min=1000, max=50000, step=100,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="W",
                    )
                ),
                vol.Required(CONF_RECOVERY_DELAY, default=300): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=3600, step=10,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(CONF_REARM_MARGIN, default=500): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=5000, step=50,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="W",
                    )
                ),
            }),
        )


class DelestageOptionsFlow(config_entries.OptionsFlow):

    def __init__(self, config_entry):
        self._config_entry = config_entry
        cfg = {**config_entry.data, **config_entry.options}
        self._equipments = list(cfg.get(CONF_EQUIPMENTS, []))
        self._settings = {
            CONF_POWER_SENSOR:   cfg.get(CONF_POWER_SENSOR),
            CONF_MAX_POWER:      cfg.get(CONF_MAX_POWER),
            CONF_RECOVERY_DELAY: cfg.get(CONF_RECOVERY_DELAY),
            CONF_REARM_MARGIN:   cfg.get(CONF_REARM_MARGIN),
        }

    def _build_options(self):
        return {
            **self._settings,
            CONF_EQUIPMENTS: self._equipments,
        }

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add()
            elif action == "remove":
                return await self.async_step_remove()
            elif action == "settings":
                return await self.async_step_settings()
            elif action == "save":
                return self.async_create_entry(title="", data=self._build_options())

        if self._equipments:
            summary = "\n".join(
                f"• {eq[CONF_DEVICE_NAME]} | priorité {eq[CONF_DEVICE_PRIORITY]} | {eq.get(CONF_DEVICE_FIXED_PWR, '?')} W"
                for eq in sorted(self._equipments, key=lambda e: e[CONF_DEVICE_PRIORITY])
            )
        else:
            summary = "Aucun équipement configuré."

        actions = [
            {"value": "add",      "label": "➕ Ajouter un équipement"},
            {"value": "settings", "label": "⚙️ Modifier les paramètres"},
            {"value": "save",     "label": "💾 Sauvegarder et fermer"},
        ]
        if self._equipments:
            actions.insert(1, {"value": "remove", "label": "🗑️ Supprimer un équipement"})

        return self.async_show_form(
            step_id="init",
            description_placeholders={"equipments": summary},
            data_schema=vol.Schema({
                vol.Required("action"): SelectSelector(
                    SelectSelectorConfig(
                        options=actions,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_add(self, user_input=None):
        errors = {}

        if user_input is not None:
            entity_id = user_input.get(CONF_DEVICE_ENTITY, "")
            name = user_input.get(CONF_DEVICE_NAME, "").strip()

            if not name:
                errors[CONF_DEVICE_NAME] = "required"
            elif not entity_id:
                errors[CONF_DEVICE_ENTITY] = "entity_not_found"
            else:
                self._equipments.append({
                    CONF_DEVICE_NAME:       name,
                    CONF_DEVICE_ENTITY:     entity_id,
                    CONF_DEVICE_PRIORITY:   int(user_input.get(CONF_DEVICE_PRIORITY, 1)),
                    CONF_DEVICE_POWER_MODE: user_input.get(CONF_DEVICE_POWER_MODE, "fixed"),
                    CONF_DEVICE_FIXED_PWR:  int(user_input.get(CONF_DEVICE_FIXED_PWR, 0)),
                    CONF_DEVICE_PWR_SENSOR: user_input.get(CONF_DEVICE_PWR_SENSOR, ""),
                })
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_NAME): TextSelector(),
                vol.Required(CONF_DEVICE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain=["switch", "input_boolean", "light", "climate"])
                ),
                vol.Required(CONF_DEVICE_PRIORITY, default=1): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=100, step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_DEVICE_POWER_MODE, default="fixed"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "fixed",  "label": "Puissance fixe"},
                            {"value": "sensor", "label": "Capteur de puissance"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_DEVICE_FIXED_PWR, default=0): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=20000, step=50,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="W",
                    )
                ),
                vol.Optional(CONF_DEVICE_PWR_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=["sensor"])
                ),
            }),
        )

    async def async_step_remove(self, user_input=None):
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
            {
                "value": eq[CONF_DEVICE_NAME],
                "label": f"{eq[CONF_DEVICE_NAME]} (priorité {eq[CONF_DEVICE_PRIORITY]}) — {eq.get(CONF_DEVICE_FIXED_PWR, '?')} W",
            }
            for eq in sorted(self._equipments, key=lambda e: e[CONF_DEVICE_PRIORITY])
        ]

        return self.async_show_form(
            step_id="remove",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required("device_to_remove"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
        )

    async def async_step_settings(self, user_input=None):
        errors = {}

        if user_input is not None:
            sensor = user_input.get(CONF_POWER_SENSOR, "")
            if not sensor:
                errors[CONF_POWER_SENSOR] = "entity_not_found"
            else:
                self._settings = {
                    CONF_POWER_SENSOR:   sensor,
                    CONF_MAX_POWER:      user_input[CONF_MAX_POWER],
                    CONF_RECOVERY_DELAY: user_input[CONF_RECOVERY_DELAY],
                    CONF_REARM_MARGIN:   user_input[CONF_REARM_MARGIN],
                }
                return await self.async_step_init()

        return self.async_show_form(
            step_id="settings",
            errors=errors,
            data_schema=vol.Schema({
                vol.Required(
                    CONF_POWER_SENSOR,
                    default=self._settings.get(CONF_POWER_SENSOR, ""),
                ): EntitySelector(
                    EntitySelectorConfig(domain=["sensor", "input_number"])
                ),
                vol.Required(
                    CONF_MAX_POWER,
                    default=self._settings.get(CONF_MAX_POWER, 6000),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1000, max=50000, step=100,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="W",
                    )
                ),
                vol.Required(
                    CONF_RECOVERY_DELAY,
                    default=self._settings.get(CONF_RECOVERY_DELAY, 300),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=3600, step=10,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    CONF_REARM_MARGIN,
                    default=self._settings.get(CONF_REARM_MARGIN, 500),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=5000, step=50,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="W",
                    )
                ),
            }),
        )
