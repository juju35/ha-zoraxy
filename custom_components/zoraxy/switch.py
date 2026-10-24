"""Zoraxy switches."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from . import ZoraxyDataUpdateCoordinator
from .api import ZoraxyError
from .entity import ZoraxyEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = entry.runtime_data
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

    # Zoraxy endpoint, parameter name and HTTP method: each handler reads its own (src/reverseproxy.go).
    _endpoint: str
    _field = "enable"
    _method = "POST"

    async def _set(self, enable: bool) -> None:
        try:
            await self.coordinator.client.command(
                self._endpoint, self._method, fields={self._field: "true" if enable else "false"}
            )
        except ZoraxyError as err:
            raise HomeAssistantError(f"Zoraxy: {err}") from err
        await self.coordinator.async_request_refresh()


class ZoraxyHttpsRedirectSwitch(ZoraxyBaseSwitch):
    _endpoint = "/api/proxy/useHttpsRedirect"
    _field = "set"  # PostBool(r, "set")
    _attr_translation_key = "https_redirect"
    _legacy_name = "Zoraxy - Redirection HTTPS"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_https_redirect"

    @property
    def is_on(self):
        return self._option("ForceHttpsRedirect")

    async def async_turn_on(self, **_):
        await self._set(True)

    async def async_turn_off(self, **_):
        await self._set(False)


class ZoraxyPort80Switch(ZoraxyBaseSwitch):
    _endpoint = "/api/proxy/listenPort80"
    _attr_translation_key = "port_80"
    _legacy_name = "Zoraxy - Écoute port 80"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_port80"

    @property
    def is_on(self):
        return self._option("ListenOnPort80")

    async def async_turn_on(self, **_):
        await self._set(True)

    async def async_turn_off(self, **_):
        await self._set(False)


class ZoraxyDevModeSwitch(ZoraxyBaseSwitch):
    _endpoint = "/api/proxy/developmentMode"
    _method = "GET"  # GetBool(r, "enable") reads the query string only
    _attr_translation_key = "development_mode"
    _legacy_name = "Zoraxy - Mode développement"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_switch_dev_mode"

    @property
    def is_on(self):
        return self._option("NoCache")

    async def async_turn_on(self, **_):
        await self._set(True)

    async def async_turn_off(self, **_):
        await self._set(False)
