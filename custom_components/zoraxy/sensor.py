"""Capteurs pour l'intégration Zoraxy."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_INFO_BASE, safe_domain
from . import ZoraxyDataUpdateCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZoraxyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        ZoraxyProxyRulesCountSensor(coordinator, entry),
        ZoraxyActiveRulesCountSensor(coordinator, entry),
        ZoraxyCertCountSensor(coordinator, entry),
        ZoraxyAccessRulesCountSensor(coordinator, entry),
        ZoraxyInboundPortSensor(coordinator, entry),
        *[ZoraxyCertExpirySensor(coordinator, entry, d) for d in coordinator.data.get("cert_list", [])],
    ]
    async_add_entities(entities)


class ZoraxyBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        return {**DEVICE_INFO_BASE, "identifiers": {(DOMAIN, self._entry.entry_id)}, "configuration_url": self._entry.data["host"]}

    def _data(self) -> dict:
        return self.coordinator.data or {}

    def _proxy_list(self) -> list:
        return self._data().get("proxy_list", [])

    def _status_option(self) -> dict:
        status = self._data().get("proxy_status", {})
        return status.get("Option", {}) if isinstance(status, dict) else {}


class ZoraxyProxyRulesCountSensor(ZoraxyBaseSensor):
    _attr_name = "Zoraxy - Règles proxy"
    _attr_icon = "mdi:router-network"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "règles"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_proxy_rules_count"

    @property
    def native_value(self): return len(self._proxy_list())

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
            {"RedirectURL": r.get("RedirectURL", "?"), "TargetURL": r.get("TargetURL", "?"), "StatusCode": r.get("StatusCode", 307)}
            for r in self._data().get("redirect_list", [])
        ]
        return {"rules": rules, "redirects": redirects}


class ZoraxyActiveRulesCountSensor(ZoraxyBaseSensor):
    _attr_name = "Zoraxy - Règles actives"
    _attr_icon = "mdi:check-network"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "actives"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_active_rules_count"

    @property
    def native_value(self): return sum(1 for r in self._proxy_list() if not r.get("Disabled", False))


class ZoraxyCertCountSensor(ZoraxyBaseSensor):
    _attr_name = "Zoraxy - Certificats TLS"
    _attr_icon = "mdi:certificate"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "certificats"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_cert_count"

    @property
    def native_value(self): return len(self._data().get("cert_list", []))

    @property
    def extra_state_attributes(self):
        expiry = self._data().get("cert_expiry", {})
        return {"certificates": [{"domain": d, "expires": expiry.get(d, "?")} for d in self._data().get("cert_list", [])]}


class ZoraxyAccessRulesCountSensor(ZoraxyBaseSensor):
    _attr_name = "Zoraxy - Règles d'accès"
    _attr_icon = "mdi:shield-account"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "règles"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_access_rules_count"

    @property
    def native_value(self): return len(self._data().get("access_rules", []))


class ZoraxyInboundPortSensor(ZoraxyBaseSensor):
    _attr_name = "Zoraxy - Port entrant"
    _attr_icon = "mdi:ethernet-cable"

    @property
    def unique_id(self): return f"{self._entry.entry_id}_inbound_port"

    @property
    def native_value(self): return self._status_option().get("Port", "?")


class ZoraxyCertExpirySensor(ZoraxyBaseSensor):
    """Date d'expiration d'un certificat spécifique."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:certificate-outline"

    def __init__(self, coordinator, entry, domain_name: str):
        super().__init__(coordinator, entry)
        self._domain = domain_name

    @property
    def unique_id(self): return f"{self._entry.entry_id}_cert_expiry_{safe_domain(self._domain)}"

    @property
    def name(self): return f"Zoraxy - Cert {self._domain}"

    @property
    def native_value(self):
        expiry_str = self._data().get("cert_expiry", {}).get(self._domain)
        if not expiry_str:
            return None
        try:
            return datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    @property
    def extra_state_attributes(self): return {"domain": self._domain}
