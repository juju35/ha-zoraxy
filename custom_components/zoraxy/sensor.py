"""Zoraxy sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from . import ZoraxyDataUpdateCoordinator
from .const import safe_domain
from .entity import ZoraxyDomainEntity, ZoraxyEntity, async_track_cert_entities


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = entry.runtime_data
    entities = [
        ZoraxyProxyRulesCountSensor(coordinator, entry),
        ZoraxyActiveRulesCountSensor(coordinator, entry),
        ZoraxyCertCountSensor(coordinator, entry),
        ZoraxyAccessRulesCountSensor(coordinator, entry),
        ZoraxyInboundPortSensor(coordinator, entry),
        *async_track_cert_entities(
            coordinator, entry, async_add_entities, lambda d: [ZoraxyCertExpirySensor(coordinator, entry, d)]
        ),
    ]
    async_add_entities(entities)


class ZoraxyBaseSensor(ZoraxyEntity, SensorEntity):
    _platform = "sensor"

    def _proxy_list(self) -> list:
        return self._data().get("proxy_list", [])

    def _status_option(self) -> dict:
        status = self._data().get("proxy_status", {})
        # "Option": null must not break the state: fall back to no option, as switch.py does.
        return (status.get("Option") or {}) if isinstance(status, dict) else {}


class ZoraxyProxyRulesCountSensor(ZoraxyBaseSensor):
    _attr_translation_key = "proxy_rules"
    _legacy_name = "Zoraxy - Règles proxy"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_proxy_rules_count"

    @property
    def native_value(self):
        return len(self._proxy_list())

    @property
    def extra_state_attributes(self):
        rules = [
            {
                "domain": r.get("RootOrMatchingDomain", "?"),
                "target": r["ActiveOrigins"][0].get("OriginIpOrDomain", "?") if r.get("ActiveOrigins") else "?",
                "enabled": not r.get("Disabled", False),
                "tls": r["ActiveOrigins"][0].get("RequireTLS", False) if r.get("ActiveOrigins") else False,
            }
            for r in self._proxy_list()
        ]
        redirects = [
            {
                "RedirectURL": r.get("RedirectURL", "?"),
                "TargetURL": r.get("TargetURL", "?"),
                "StatusCode": r.get("StatusCode", 307),
            }
            for r in self._data().get("redirect_list", [])
        ]
        return {"rules": rules, "redirects": redirects}


class ZoraxyActiveRulesCountSensor(ZoraxyBaseSensor):
    _attr_translation_key = "active_rules"
    _legacy_name = "Zoraxy - Règles actives"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_active_rules_count"

    @property
    def native_value(self):
        return sum(1 for r in self._proxy_list() if not r.get("Disabled", False))


class ZoraxyCertCountSensor(ZoraxyBaseSensor):
    _attr_translation_key = "tls_certificates"
    _legacy_name = "Zoraxy - Certificats TLS"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_cert_count"

    @property
    def native_value(self):
        return len(self._data().get("cert_list", []))

    @property
    def extra_state_attributes(self):
        expiry = self._data().get("cert_expiry", {})
        return {
            "certificates": [{"domain": d, "expires": expiry.get(d, "?")} for d in self._data().get("cert_list", [])]
        }


class ZoraxyAccessRulesCountSensor(ZoraxyBaseSensor):
    _attr_translation_key = "access_rules"
    _legacy_name = "Zoraxy - Règles d'accès"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_access_rules_count"

    @property
    def native_value(self):
        return len(self._data().get("access_rules", []))


class ZoraxyInboundPortSensor(ZoraxyBaseSensor):
    _attr_translation_key = "inbound_port"
    _legacy_name = "Zoraxy - Port entrant"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_inbound_port"

    @property
    def native_value(self):
        return self._status_option().get("Port")


class ZoraxyCertExpirySensor(ZoraxyDomainEntity, ZoraxyBaseSensor):
    """Expiry date of one certificate."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "certificate"
    _legacy_name = "Zoraxy - Cert {domain}"

    @property
    def unique_id(self):
        return f"{self._entry.entry_id}_cert_expiry_{safe_domain(self._domain)}"

    @property
    def native_value(self):
        expiry_str = self._data().get("cert_expiry", {}).get(self._domain)
        if not expiry_str:
            return None
        try:
            return datetime.fromisoformat(expiry_str)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self):
        return {"domain": self._domain}
