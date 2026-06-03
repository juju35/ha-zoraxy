"""Switches pour Zoraxy."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_INFO_BASE
from . import ZoraxyDataUpdateCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ZoraxyHttpsRedirectSwitch(coordinator, entry),
        ZoraxyPort80Switch(coordinator, entry),
        ZoraxyDevModeSwitch(coordinator, entry),
    ])


class ZoraxyBaseSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator: ZoraxyDataUpdateCoordinator, entry):
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        return {**DEVICE_INFO_BASE, "identifiers": {(DOMAIN, self._entry.entry_id)}, "configuration_url": self._entry.data["host"]}

    def _bool_val(self, key: str) -> bool:
        """Lit une valeur booléenne depuis les données du coordinateur."""
        val = (self.coordinator.data or {}).get(key)
        return val.get("enabled", val.get("value", False)) if isinstance(val, dict) else bool(val)

    async def _set(self, endpoint: str, enable: bool) -> None:
        await self.coordinator._fetch(endpoint, method="POST", fields={"enable": "true" if enable else "false"})
        await self.coordinator.async_request_refresh()


class ZoraxyHttpsRedirectSwitch(ZoraxyBaseSwitch):
    _attr_name = "Zoraxy - Redirection HTTPS"
    _attr_icon = "mdi:lock-check"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_switch_https_redirect"

    @property
    def is_on(self): return self._bool_val("https_redirect")

    async def async_turn_on(self, **_): await self._set("/api/proxy/useHttpsRedirect", True)
    async def async_turn_off(self, **_): await self._set("/api/proxy/useHttpsRedirect", False)


class ZoraxyPort80Switch(ZoraxyBaseSwitch):
    _attr_name = "Zoraxy - Écoute port 80"
    _attr_icon = "mdi:web"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_switch_port80"

    @property
    def is_on(self): return self._bool_val("listen_port80")

    async def async_turn_on(self, **_): await self._set("/api/proxy/listenPort80", True)
    async def async_turn_off(self, **_): await self._set("/api/proxy/listenPort80", False)


class ZoraxyDevModeSwitch(ZoraxyBaseSwitch):
    _attr_name = "Zoraxy - Mode développement"
    _attr_icon = "mdi:code-braces"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_switch_dev_mode"

    @property
    def is_on(self): return self._bool_val("development_mode")

    async def async_turn_on(self, **_): await self._set("/api/proxy/developmentMode", True)
    async def async_turn_off(self, **_): await self._set("/api/proxy/developmentMode", False)
