"""Capteurs binaires pour Zoraxy."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_INFO_BASE, EXPIRY_WARNING_DAYS, safe_domain
from . import ZoraxyDataUpdateCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ZoraxyProxyRunningBinarySensor(coordinator, entry),
        ZoraxyTLSEnabledBinarySensor(coordinator, entry),
        ZoraxyHttpsRedirectBinarySensor(coordinator, entry),
        ZoraxyPort80BinarySensor(coordinator, entry),
        ZoraxyDevModeBinarySensor(coordinator, entry),
        *[ZoraxyCertExpiringBinarySensor(coordinator, entry, d) for d in coordinator.data.get("cert_list", [])],
    ])


class ZoraxyBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        return {**DEVICE_INFO_BASE, "identifiers": {(DOMAIN, self._entry.entry_id)}, "configuration_url": self._entry.data["host"]}

    def _data(self) -> dict:
        return self.coordinator.data or {}

    def _option(self) -> dict:
        status = self._data().get("proxy_status", {})
        return status.get("Option", {}) if isinstance(status, dict) else {}


# ── Capteurs système ───────────────────────────────────────────────────────────

class ZoraxyProxyRunningBinarySensor(ZoraxyBaseBinarySensor):
    _attr_name = "Zoraxy - Proxy actif"
    _attr_icon = "mdi:server-network"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def unique_id(self): return f"{self._entry.entry_id}_proxy_running"

    @property
    def is_on(self): return bool(self._option())


class ZoraxyTLSEnabledBinarySensor(ZoraxyBaseBinarySensor):
    _attr_name = "Zoraxy - TLS activé"
    _attr_icon = "mdi:shield-lock"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_tls_enabled"

    @property
    def is_on(self): return bool(self._option().get("UseTls", False))


class ZoraxyHttpsRedirectBinarySensor(ZoraxyBaseBinarySensor):
    _attr_name = "Zoraxy - Redirection HTTPS"
    _attr_icon = "mdi:lock-check"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_https_redirect"

    @property
    def is_on(self): return bool(self._option().get("ForceHttpsRedirect", False))


class ZoraxyPort80BinarySensor(ZoraxyBaseBinarySensor):
    _attr_name = "Zoraxy - Écoute port 80"
    _attr_icon = "mdi:web"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_listen_port80"

    @property
    def is_on(self): return bool(self._option().get("ListenOnPort80", False))


class ZoraxyDevModeBinarySensor(ZoraxyBaseBinarySensor):
    _attr_name = "Zoraxy - Mode développement"
    _attr_icon = "mdi:code-braces"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_dev_mode"

    @property
    def is_on(self): return bool(self._option().get("NoCache", False))


# ── Capteurs par certificat ────────────────────────────────────────────────────

class ZoraxyCertExpiringBinarySensor(ZoraxyBaseBinarySensor):
    """On si le certificat expire dans moins de EXPIRY_WARNING_DAYS jours."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry, domain_name: str):
        super().__init__(coordinator, entry)
        self._domain = domain_name

    @property
    def unique_id(self): return f"{self._entry.entry_id}_cert_expiring_{safe_domain(self._domain)}"

    @property
    def name(self): return f"Zoraxy - Cert expirant {self._domain}"

    @property
    def is_on(self):
        expiry_str = self._data().get("cert_expiry", {}).get(self._domain)
        if not expiry_str:
            return None
        try:
            expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            return expiry < datetime.now(timezone.utc) + timedelta(days=EXPIRY_WARNING_DAYS)
        except ValueError:
            return None

    @property
    def extra_state_attributes(self):
        return {
            "domain": self._domain,
            "expires": self._data().get("cert_expiry", {}).get(self._domain, "?"),
            "warning_days": EXPIRY_WARNING_DAYS,
        }
