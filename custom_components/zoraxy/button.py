"""Zoraxy certificate renewal buttons."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZoraxyDataUpdateCoordinator
from .const import DEVICE_INFO_BASE, DOMAIN, safe_domain

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZoraxyCertRenewButton(coordinator, entry, d) for d in coordinator.data.get("cert_list", [])])


class ZoraxyCertRenewButton(CoordinatorEntity, ButtonEntity):
    """ACME renewal button for one certificate."""

    _attr_icon = "mdi:certificate-outline"

    def __init__(self, coordinator: ZoraxyDataUpdateCoordinator, entry, domain_name: str):
        super().__init__(coordinator)
        self._entry = entry
        self._domain = domain_name

    @property
    def device_info(self):
        return {
            **DEVICE_INFO_BASE,
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "configuration_url": self._entry.data["host"],
        }

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_renew_{safe_domain(self._domain)}"

    @property
    def name(self):
        return f"Zoraxy - Renouveler {self._domain}"

    async def async_press(self):
        success = await self.coordinator.renew_certificate(self._domain)
        if success:
            _LOGGER.info("Zoraxy: certificate %s renewed", self._domain)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Zoraxy: renewal of %s failed", self._domain)
