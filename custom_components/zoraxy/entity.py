"""Base entity shared by the Zoraxy platforms."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import ZoraxyDataUpdateCoordinator
from .const import DEVICE_INFO_BASE, DOMAIN


class ZoraxyEntity(CoordinatorEntity[ZoraxyDataUpdateCoordinator]):
    """Zoraxy entity: translated name under the Zoraxy device.

    Up to 1.4.x the names were hard-coded in French ("Zoraxy - Règles proxy"). The entity ids built from them
    (sensor.zoraxy_reverse_proxy_zoraxy_regles_proxy…) are what the card looks for, so new installs are given the
    same ids: `_legacy_name` is the former name, `_platform` the entity domain. Existing ids stay in the registry.
    """

    _attr_has_entity_name = True
    _platform: str
    _legacy_name: str

    def __init__(self, coordinator: ZoraxyDataUpdateCoordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.entity_id = f"{self._platform}.{slugify(f'{DEVICE_INFO_BASE["name"]} {self._legacy_name}')}"
        self._attr_device_info = DeviceInfo(
            **DEVICE_INFO_BASE,
            identifiers={(DOMAIN, entry.entry_id)},
            configuration_url=entry.data["host"],
        )

    def _data(self) -> dict:
        return self.coordinator.data or {}


class ZoraxyDomainEntity(ZoraxyEntity):
    """Entity tied to one certificate domain; the domain is a placeholder of the translated name."""

    def __init__(self, coordinator: ZoraxyDataUpdateCoordinator, entry, domain_name: str) -> None:
        self._domain = domain_name
        self._legacy_name = self._legacy_name.format(domain=domain_name)
        self._attr_translation_placeholders = {"domain": domain_name}
        super().__init__(coordinator, entry)


def async_track_cert_entities(
    coordinator: ZoraxyDataUpdateCoordinator,
    entry,
    async_add_entities: Callable[[Iterable[Entity]], None],
    factory: Callable[[str], Iterable[Entity]],
) -> list[Entity]:
    """Entities of the certificates listed now; those of a certificate added later in Zoraxy follow at its update.

    Without this, a new certificate only got its entities after a reload, while the count sensor already counted it.
    """
    known: set[str] = set()

    def new_entities() -> list[Entity]:
        domains = [d for d in (coordinator.data or {}).get("cert_list", []) if isinstance(d, str) and d not in known]
        known.update(domains)
        return [entity for domain in domains for entity in factory(domain)]

    @callback
    def _check() -> None:
        if entities := new_entities():
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_check))
    return new_entities()
