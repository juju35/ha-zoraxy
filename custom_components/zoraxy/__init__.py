"""Zoraxy integration for Home Assistant."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZoraxyAuthError, ZoraxyClient, ZoraxyError, normalize_host
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SERVICE_TOGGLE_PROXY_RULE,
    safe_domain,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
TOGGLE_PROXY_RULE_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): vol.All(cv.string, vol.Strip, vol.Length(min=1)),
        # True enables, False disables, left out toggles the rule.
        vol.Optional("enable"): cv.boolean,
    }
)

DYNAMIC_SUFFIXES = ("_cert_expiry_", "_cert_expiring_", "_renew_")

CARD_FILENAME = "zoraxy-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / CARD_FILENAME
FRONTEND_URL = f"/{DOMAIN}"
# Up to 1.2.1 the card was copied to /config/www/ and loaded from /local/.
LEGACY_CARD_URL = f"/local/{CARD_FILENAME}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the Lovelace card from the integration and add it to the dashboard resources."""
    await hass.http.async_register_static_paths([StaticPathConfig(FRONTEND_URL, str(CARD_PATH.parent), True)])
    await hass.async_add_executor_job(_remove_legacy_card_file, hass)
    await _async_register_card(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE_PROXY_RULE, _async_toggle_proxy_rule(hass), TOGGLE_PROXY_RULE_SCHEMA
    )
    return True


def _remove_legacy_card_file(hass: HomeAssistant) -> None:
    """Delete the copy of the card that versions up to 1.2.1 put in /config/www/."""
    legacy = Path(hass.config.config_dir) / "www" / CARD_FILENAME
    try:
        if legacy.is_file() and "ZORAXY_CARD_VERSION" in legacy.read_text(encoding="utf-8", errors="ignore"):
            legacy.unlink()
            _LOGGER.info("Zoraxy: removed the old copy of the card in %s", legacy)
    except OSError as err:
        _LOGGER.warning("Zoraxy: could not remove the old copy of the card in %s: %s", legacy, err)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Add the card to the dashboard resources, or update it, as ha-parcel does.

    The file hash in the URL makes browsers fetch the new card after an update. The
    /local/ resource of versions up to 1.2.1 is replaced by the integration's URL.
    """
    digest = await hass.async_add_executor_job(lambda: hashlib.md5(CARD_PATH.read_bytes()).hexdigest()[:8])
    base_url = f"{FRONTEND_URL}/{CARD_FILENAME}"
    url = f"{base_url}?v={digest}"

    async def register(_event: Event | None = None) -> None:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None or getattr(lovelace, "resource_mode", "storage") != "storage":
            # Dashboards in YAML mode: resources can't be edited, load the card on every page.
            add_extra_js_url(hass, url)
            return
        try:
            if not resources.loaded:
                await resources.async_load()
                resources.loaded = True
            existing = [
                item
                for item in resources.async_items()
                if item.get("url", "").split("?")[0] in (base_url, LEGACY_CARD_URL)
            ]
            if not existing:
                await resources.async_create_item({"res_type": "module", "url": url})
                _LOGGER.info("Zoraxy card added to dashboard resources: %s", url)
            elif existing[0].get("url") != url:
                await resources.async_update_item(existing[0]["id"], {"res_type": "module", "url": url})
                _LOGGER.info("Zoraxy card resource updated: %s", url)
            for duplicate in existing[1:]:
                await resources.async_delete_item(duplicate["id"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not add the Zoraxy card to dashboard resources (%s). Add %s manually "
                "in Settings > Dashboards > Resources (JavaScript module)",
                err,
                url,
            )
            add_extra_js_url(hass, url)

    if hass.is_running:
        await register()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register)


async def _cleanup_stale_entities(hass: HomeAssistant, entry: ConfigEntry, current_certs: list[str]) -> None:
    registry = er.async_get(hass)
    current_safe = {safe_domain(d) for d in current_certs}
    to_remove = [
        e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if any(
            suffix in (e.unique_id or "") and (e.unique_id or "").split(suffix, 1)[-1] not in current_safe
            for suffix in DYNAMIC_SUFFIXES
        )
    ]
    for entity_id in to_remove:
        _LOGGER.info("Zoraxy: removing stale entity %s", entity_id)
        registry.async_remove(entity_id)


def entry_settings(entry: ConfigEntry) -> dict[str, Any]:
    """Entry data overridden by the options (scan interval, TLS verification)."""
    return {**entry.data, **entry.options}


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """1.1 → 1.2: TLS verification becomes an option.

    Up to 1.2 the certificate was never checked. Existing entries keep that (verify_ssl False) so an HTTPS Zoraxy
    with a self-signed certificate keeps working; new entries check it by default. The unique id is normalized
    like the config flow now does, unless another entry already uses that value.
    """
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        updates: dict[str, Any] = {"data": {**entry.data, CONF_VERIFY_SSL: False}, "minor_version": 2}
        unique_id = normalize_host(entry.data["host"])
        if unique_id != entry.unique_id and not any(
            e.unique_id == unique_id for e in hass.config_entries.async_entries(DOMAIN) if e is not entry
        ):
            updates["unique_id"] = unique_id
        hass.config_entries.async_update_entry(entry, **updates)
        _LOGGER.debug("Zoraxy: migrated entry %s to 1.2", entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    settings = entry_settings(entry)
    # Session owned by Home Assistant: closed when the entry unloads or its setup fails.
    session = async_create_clientsession(
        hass,
        verify_ssl=settings.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        cookie_jar=aiohttp.CookieJar(unsafe=True),
    )
    client = ZoraxyClient(session, settings["host"], settings["username"], settings["password"])
    coordinator = ZoraxyDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    if coordinator.cert_list_loaded:
        await _cleanup_stale_entities(hass, entry, coordinator.data["cert_list"])
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_toggle_proxy_rule(hass: HomeAssistant):
    """Service handler that looks up the loaded coordinators at each call, so it survives reloads."""

    async def handle(call: ServiceCall) -> None:
        domain_name: str = call.data["domain"]
        enable: bool | None = call.data.get("enable")
        coordinators: list[ZoraxyDataUpdateCoordinator] = [
            entry.runtime_data
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
        if not coordinators:
            raise ServiceValidationError("No Zoraxy instance is loaded")
        # With several Zoraxy instances, the rule belongs to the one that lists the domain.
        match = next(
            (
                (coordinator, rule)
                for coordinator in coordinators
                for rule in (coordinator.data or {}).get("proxy_list", [])
                if rule.get("RootOrMatchingDomain") == domain_name
            ),
            None,
        )
        if match is None:
            raise ServiceValidationError(f"Zoraxy proxy rule '{domain_name}' not found")
        coordinator, rule = match
        # Left out, enable toggles the rule: a disabled rule gets enabled.
        should_enable = bool(rule.get("Disabled", False)) if enable is None else enable
        set_value = "true" if should_enable else "false"
        try:
            await coordinator.client.command("/api/proxy/toggle", fields={"ep": domain_name, "enable": set_value})
        except ZoraxyError as err:
            raise HomeAssistantError(f"Zoraxy: could not change the rule '{domain_name}': {err}") from err
        _LOGGER.debug("Zoraxy toggle_proxy_rule '%s' enable=%s", domain_name, set_value)
        await coordinator.async_request_refresh()

    return handle


class ZoraxyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Zoraxy coordinator.

    The proxy status is required: when it can't be read the update fails and the entities become unavailable.
    The other lists are optional: on failure the previous value is kept.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ZoraxyClient) -> None:
        seconds = int(entry_settings(entry).get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(MIN_SCAN_INTERVAL, seconds)),
        )
        self.client = client
        self.cert_list_loaded = False
        self._acme_email: str | None = None
        self._acme_ca: str = "Let's Encrypt"

    async def renew_certificate(self, domain: str) -> None:
        """Ask Zoraxy for a new ACME certificate. Raises HomeAssistantError on failure."""
        if not self._acme_email:
            raise HomeAssistantError("Zoraxy: ACME email not available")
        try:
            await self.client.command(
                "/api/acme/obtainCert",
                method="GET",
                fields={
                    "domains": domain,
                    "filename": domain,
                    "email": self._acme_email,
                    "ca": self._acme_ca,
                    "dns": "false",
                },
                timeout=120,
            )
        except ZoraxyError as err:
            raise HomeAssistantError(f"Zoraxy: renewal of {domain} failed: {err}") from err
        _LOGGER.info("Zoraxy: certificate %s renewed", domain)

    def _extract_cert_expiry(self, proxy_status: dict) -> dict[str, str]:
        all_certs = (proxy_status.get("Option", {}) or {}).get("TlsManager", {}).get("LoadedCerts", [])
        result, seen = {}, set()
        for c in all_certs:
            pk = c.get("PriKey", "")
            if not pk or pk in seen:
                continue
            seen.add(pk)
            cert = c.get("Cert", {})
            dns = cert.get("DNSNames") or []
            if dns and (expiry := cert.get("NotAfter", "")):
                result[dns[0]] = expiry
        return result

    async def _optional(self, endpoint: str, method: str = "GET", fields: dict[str, str] | None = None) -> Any:
        """An endpoint whose failure keeps the previous data instead of failing the update."""
        try:
            return await self.client.fetch_json(endpoint, method, fields)
        except ZoraxyAuthError:
            raise
        except ZoraxyError as err:
            _LOGGER.debug("Zoraxy: API error on %s: %s", endpoint, err)
            return None

    def _previous(self, key: str) -> list:
        return (self.data or {}).get(key, [])

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            proxy_status = await self.client.fetch_json("/api/proxy/status")
            if not isinstance(proxy_status, dict):
                raise UpdateFailed("Unexpected proxy status from Zoraxy")
            # type=root answers the root object alone (zsrc/rp.go), not a rule list: only host rules are listed.
            host_rules, cert_list, redirect_list, access_rules, acme_email, acme_ca = await asyncio.gather(
                self._optional("/api/proxy/list", method="POST", fields={"type": "host"}),
                self._optional("/api/cert/list"),
                self._optional("/api/redirect/list"),
                self._optional("/api/access/list"),
                self._optional("/api/acme/autoRenew/email"),
                self._optional("/api/acme/autoRenew/ca"),
            )
        except ZoraxyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZoraxyError as err:
            raise UpdateFailed(str(err)) from err

        if isinstance(acme_email, str):
            self._acme_email = acme_email.strip('"')
        if isinstance(acme_ca, str):
            self._acme_ca = acme_ca.strip('"') or "Let's Encrypt"

        proxy_list = host_rules if isinstance(host_rules, list) else self._previous("proxy_list")

        # Only a list actually returned by Zoraxy may remove certificate entities (see async_setup_entry).
        self.cert_list_loaded = isinstance(cert_list, list)

        return {
            "proxy_status": proxy_status,
            "proxy_list": proxy_list,
            "cert_list": cert_list if self.cert_list_loaded else self._previous("cert_list"),
            "redirect_list": redirect_list if isinstance(redirect_list, list) else self._previous("redirect_list"),
            "access_rules": access_rules if isinstance(access_rules, list) else self._previous("access_rules"),
            "cert_expiry": self._extract_cert_expiry(proxy_status),
        }
