"""Zoraxy switches."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from . import ZoraxyDataUpdateCoordinator
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

    def _bool_val(self, key: str) -> bool:
        """Read a boolean from the coordinator data."""
        val = self._data().get(key)
        return val.get("enabled", val.get("value", False)) if isinstance(val, dict) else bool(val)

    async def _set(self, endpoint: str, enable: bool) -> None:
        await self.coordinator._fetch(endpoint, method="POST", fields={"enable": "true" if enable else "false"})
        await self.coordinator.async_request_refresh()


class ZoraxyHttpsRedirectSwitch(ZoraxyBaseSwitch):
    _attr_translation_key = "https_redirect"
    _legacy_name = "Zoraxy - Redirection HTTPS"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_https_redirect"

    @property
    def is_on(self):
        return self._bool_val("https_redirect")

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
        return self._bool_val("listen_port80")

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
        return self._bool_val("development_mode")

    async def async_turn_on(self, **_):
        await self._set("/api/proxy/developmentMode", True)

    async def async_turn_off(self, **_):
        await self._set("/api/proxy/developmentMode", False)
