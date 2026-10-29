"""Zoraxy binary sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from . import ZoraxyDataUpdateCoordinator
from .const import EXPIRY_WARNING_DAYS, safe_domain
from .entity import ZoraxyDomainEntity, ZoraxyEntity, async_track_cert_entities


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        [
            ZoraxyProxyRunningBinarySensor(coordinator, entry),
            ZoraxyTLSEnabledBinarySensor(coordinator, entry),
            ZoraxyHttpsRedirectBinarySensor(coordinator, entry),
            ZoraxyPort80BinarySensor(coordinator, entry),
            ZoraxyDevModeBinarySensor(coordinator, entry),
            *async_track_cert_entities(
                coordinator,
                entry,
                async_add_entities,
                lambda d: [ZoraxyCertExpiringBinarySensor(coordinator, entry, d)],
            ),
        ]
    )


class ZoraxyBaseBinarySensor(ZoraxyEntity, BinarySensorEntity):
    _platform = "binary_sensor"

    def _option(self) -> dict:
        status = self._data().get("proxy_status", {})
        # "Option": null must not break the state: fall back to no option, as switch.py does.
        return (status.get("Option") or {}) if isinstance(status, dict) else {}


# ── System sensors ───────────────────────────────────────────────────────────


class ZoraxyProxyRunningBinarySensor(ZoraxyBaseBinarySensor):
    _attr_translation_key = "proxy_running"
    _legacy_name = "Zoraxy - Proxy actif"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_proxy_running"

    @property
    def is_on(self):
        return bool(self._option())


class ZoraxyTLSEnabledBinarySensor(ZoraxyBaseBinarySensor):
    _attr_translation_key = "tls_enabled"
    _legacy_name = "Zoraxy - TLS activé"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_tls_enabled"

    @property
    def is_on(self):
        return bool(self._option().get("UseTls", False))


class ZoraxyHttpsRedirectBinarySensor(ZoraxyBaseBinarySensor):
    _attr_translation_key = "https_redirect"
    _legacy_name = "Zoraxy - Redirection HTTPS"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_https_redirect"

    @property
    def is_on(self):
        return bool(self._option().get("ForceHttpsRedirect", False))


class ZoraxyPort80BinarySensor(ZoraxyBaseBinarySensor):
    _attr_translation_key = "port_80"
    _legacy_name = "Zoraxy - Écoute port 80"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_listen_port80"

    @property
    def is_on(self):
        return bool(self._option().get("ListenOnPort80", False))


class ZoraxyDevModeBinarySensor(ZoraxyBaseBinarySensor):
    _attr_translation_key = "development_mode"
    _legacy_name = "Zoraxy - Mode développement"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_dev_mode"

    @property
    def is_on(self):
        return bool(self._option().get("NoCache", False))


# ── Per-certificate sensors ────────────────────────────────────────────────────


class ZoraxyCertExpiringBinarySensor(ZoraxyDomainEntity, ZoraxyBaseBinarySensor):
    """On when the certificate expires in less than EXPIRY_WARNING_DAYS days."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "certificate_expiring"
    _legacy_name = "Zoraxy - Cert expirant {domain}"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_cert_expiring_{safe_domain(self._domain)}"

    @property
    def is_on(self):
        expiry_str = self._data().get("cert_expiry", {}).get(self._domain)
        if not expiry_str:
            return None
        try:
            expiry = datetime.fromisoformat(expiry_str)
            # TypeError: a naive NotAfter can't be compared with an aware now().
            return expiry < datetime.now(UTC) + timedelta(days=EXPIRY_WARNING_DAYS)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self):
        return {
            "domain": self._domain,
            "expires": self._data().get("cert_expiry", {}).get(self._domain, "?"),
            "warning_days": EXPIRY_WARNING_DAYS,
        }
