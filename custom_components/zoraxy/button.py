"""Zoraxy certificate renewal buttons."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity

from . import ZoraxyDataUpdateCoordinator
from .const import DOMAIN, safe_domain
from .entity import ZoraxyDomainEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
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
        success = await self.coordinator.renew_certificate(self._domain)
        if success:
            _LOGGER.info("Zoraxy: certificate %s renewed", self._domain)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Zoraxy: renewal of %s failed", self._domain)
