"""Zoraxy certificate renewal buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from . import ZoraxyDataUpdateCoordinator
from .const import safe_domain
from .entity import ZoraxyDomainEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = entry.runtime_data
    async_add_entities([ZoraxyCertRenewButton(coordinator, entry, d) for d in coordinator.data.get("cert_list", [])])


class ZoraxyCertRenewButton(ZoraxyDomainEntity, ButtonEntity):
    """ACME renewal button for one certificate."""

    _attr_translation_key = "renew"
    _platform = "button"
    _legacy_name = "Zoraxy - Renouveler {domain}"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_renew_{safe_domain(self._domain)}"

    async def async_press(self):
        # Raises HomeAssistantError on failure, so the caller (and the card) sees it.
        await self.coordinator.renew_certificate(self._domain)
        await self.coordinator.async_request_refresh()
