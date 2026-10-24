"""Zoraxy switches."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from . import ZoraxyDataUpdateCoordinator
from .api import ZoraxyError
from .const import DOMAIN
from .entity import ZoraxyEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZoraxyHttpsRedirectSwitch(coordinator, entry),
            ZoraxyPort80Switch(coordinator, entry),
            ZoraxyDevModeSwitch(coordinator, entry),
        ]
    )


class ZoraxyBaseSwitch(ZoraxyEntity, SwitchEntity):
    _platform = "switch"

    def _option(self, key: str) -> bool:
        """Read a flag of the proxy options, as the binary sensors do."""
        status = self._data().get("proxy_status", {})
        option = status.get("Option", {}) if isinstance(status, dict) else {}
        return bool((option or {}).get(key, False))

    async def _set(self, endpoint: str, enable: bool) -> None:
        try:
            await self.coordinator.client.command(endpoint, fields={"enable": "true" if enable else "false"})
        except ZoraxyError as err:
            raise HomeAssistantError(f"Zoraxy: {err}") from err
        await self.coordinator.async_request_refresh()


class ZoraxyHttpsRedirectSwitch(ZoraxyBaseSwitch):
    _attr_translation_key = "https_redirect"
    _legacy_name = "Zoraxy - Redirection HTTPS"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_https_redirect"

    @property
    def is_on(self):
        return self._option("ForceHttpsRedirect")

    async def async_turn_on(self, **_):
        await self._set("/api/proxy/useHttpsRedirect", True)

    async def async_turn_off(self, **_):
        await self._set("/api/proxy/useHttpsRedirect", False)


class ZoraxyPort80Switch(ZoraxyBaseSwitch):
    _attr_translation_key = "port_80"
    _legacy_name = "Zoraxy - Écoute port 80"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_port80"

    @property
    def is_on(self):
        return self._option("ListenOnPort80")

    async def async_turn_on(self, **_):
        await self._set("/api/proxy/listenPort80", True)

    async def async_turn_off(self, **_):
        await self._set("/api/proxy/listenPort80", False)


class ZoraxyDevModeSwitch(ZoraxyBaseSwitch):
    _attr_translation_key = "development_mode"
    _legacy_name = "Zoraxy - Mode développement"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_dev_mode"

    @property
    def is_on(self):
        return self._option("NoCache")

    async def async_turn_on(self, **_):
        await self._set("/api/proxy/developmentMode", True)

    async def async_turn_off(self, **_):
        await self._set("/api/proxy/developmentMode", False)
