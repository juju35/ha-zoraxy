"""Config flow for the Zoraxy integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ZoraxyAuthError, ZoraxyClient, ZoraxyError, normalize_host
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_HOST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=3600, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host", default=DEFAULT_HOST): str,
        vol.Required("username", default="admin"): str,
        vol.Required("password"): PASSWORD_SELECTOR,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): SCAN_INTERVAL_SELECTOR,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required("password"): PASSWORD_SELECTOR})


async def _validate(hass: HomeAssistant, host: str, username: str, password: str, verify_ssl: bool) -> str | None:
    """Go through Zoraxy's CSRF login; return an error key, or None when the login works."""
    session = async_create_clientsession(
        hass, verify_ssl=verify_ssl, auto_cleanup=False, cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    try:
        await ZoraxyClient(session, host, username, password).login()
    except ZoraxyAuthError:
        return "invalid_auth"
    except ZoraxyError as err:
        _LOGGER.debug("Zoraxy: cannot connect to %s: %s", host, err)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Zoraxy: unexpected error while checking %s", host)
        return "unknown"
    finally:
        # The connector is shared by Home Assistant: detach it rather than closing it.
        session.detach()
    return None


class ZoraxyConfigFlow(ConfigFlow, domain=DOMAIN):
    # 1.2: verify_ssl option, normalized unique id (see async_migrate_entry).
    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input["host"].strip().rstrip("/")
            await self.async_set_unique_id(normalize_host(host))
            self._abort_if_unique_id_configured()
            data = {
                **user_input,
                "host": host,
                CONF_SCAN_INTERVAL: int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            }
            error = await _validate(self.hass, host, data["username"], data["password"], data[CONF_VERIFY_SSL])
            if error is None:
                return self.async_create_entry(title=f"Zoraxy ({host})", data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            settings = {**entry.data, **entry.options}
            error = await _validate(
                self.hass,
                settings["host"],
                settings["username"],
                user_input["password"],
                settings.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )
            if error is None:
                return self.async_update_reload_and_abort(entry, data_updates={"password": user_input["password"]})
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"host": entry.data["host"], "username": entry.data["username"]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ZoraxyOptionsFlow()


class ZoraxyOptionsFlow(OptionsFlow):
    """Refresh interval and TLS certificate verification."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): SCAN_INTERVAL_SELECTOR,
                vol.Required(CONF_VERIFY_SSL, default=current.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
