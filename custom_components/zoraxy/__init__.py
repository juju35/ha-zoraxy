"""Zoraxy integration for Home Assistant."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, safe_domain

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CSRF_META_RE = re.compile(r'<meta\s+name="zoraxy\.csrf\.Token"\s+content="([^"]+)"')

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = ZoraxyDataUpdateCoordinator(
        hass,
        host=entry.data["host"].rstrip("/"),
        username=entry.data["username"],
        password=entry.data["password"],
        update_interval=timedelta(seconds=entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
    )
    await coordinator.async_config_entry_first_refresh()
    await _cleanup_stale_entities(hass, entry, coordinator.data.get("cert_list", []))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Action: enable or disable a proxy rule ────────────────────────────
    async def handle_toggle_proxy_rule(call: ServiceCall) -> None:
        domain_name: str = call.data.get("domain", "")
        enable: bool | None = call.data.get("enable")  # True = enable, False = disable, None = toggle
        if not domain_name:
            _LOGGER.error("Zoraxy toggle_proxy_rule: missing 'domain'")
            return
        # Find the rule in the current data to know its state
        proxy_list = (coordinator.data or {}).get("proxy_list", [])
        current_disabled = next(
            (r.get("Disabled", False) for r in proxy_list if r.get("RootOrMatchingDomain") == domain_name),
            None,
        )
        if current_disabled is None:
            _LOGGER.error("Zoraxy toggle_proxy_rule: domain '%s' not found", domain_name)
            return
        # enable=None toggles (enable a disabled rule), otherwise set as asked
        should_enable = current_disabled if enable is None else enable
        set_value = "true" if should_enable else "false"
        result = await coordinator._fetch(
            "/api/proxy/toggle",
            method="POST",
            fields={"ep": domain_name, "enable": set_value},
        )
        _LOGGER.debug("Zoraxy toggle_proxy_rule '%s' enable=%s → %s", domain_name, set_value, result)
        await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "toggle_proxy_rule"):
        hass.services.async_register(DOMAIN, "toggle_proxy_rule", handle_toggle_proxy_rule)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if coordinator := hass.data.get(DOMAIN, {}).get(entry.entry_id):
        await coordinator.async_close()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class ZoraxyDataUpdateCoordinator(DataUpdateCoordinator):
    """Zoraxy coordinator.

    The Zoraxy session expires after about an hour. Zoraxy then answers with a 307
    redirect to /login.html, detected by checking the final URL of the response once
    the redirects are followed (allow_redirects=True by default).
    """

    def __init__(self, hass, host, username, password, update_interval):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.host = host
        self.username = username
        self.password = password
        self._logged_in = False
        self._csrf_token: str | None = None
        self._acme_email: str | None = None
        self._acme_ca: str = "Let's Encrypt"
        self._session: aiohttp.ClientSession | None = None
        self._make_session()

    def _make_session(self) -> None:
        """Create a fresh HTTP session."""
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )

    async def async_close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _session_expired(self, resp: aiohttp.ClientResponse) -> bool:
        """Tell whether the session expired from the final URL after redirects."""
        # Zoraxy redirects to /login.html when the session expires
        return "login" in str(resp.url)

    async def _get_csrf_token(self) -> str | None:
        """Read the CSRF token from login.html."""
        try:
            async with asyncio.timeout(10):
                # allow_redirects=True follows the 307 / → /login.html
                resp = await self._session.get(f"{self.host}/login.html", allow_redirects=True)
            m = CSRF_META_RE.search(await resp.text())
            if m:
                return m.group(1)
            _LOGGER.warning("Zoraxy: CSRF token not found in login.html")
        except Exception as err:
            _LOGGER.error("Zoraxy: could not read the CSRF token: %s", err)
        return None

    async def _login(self) -> bool:
        """Create a fresh session and log in."""
        # Close the old session and create a new one (no stale expired cookies)
        await self.async_close()
        self._make_session()
        self._logged_in = False
        self._csrf_token = None

        csrf_token = await self._get_csrf_token()
        if not csrf_token:
            return False

        try:
            async with asyncio.timeout(10):
                resp = await self._session.post(
                    f"{self.host}/api/auth/login",
                    headers={
                        "X-CSRF-Token": csrf_token,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data=urlencode({"username": self.username, "password": self.password}),
                    allow_redirects=True,
                )
            text = await resp.text()
            if resp.status == 200 and "error" not in text.lower():
                self._logged_in = True
                self._csrf_token = csrf_token
                _LOGGER.debug("Zoraxy: logged in")
                return True
            _LOGGER.warning("Zoraxy: login refused (HTTP %s): %s", resp.status, text[:200])
        except aiohttp.ClientConnectorError as err:
            raise UpdateFailed(f"Cannot reach Zoraxy ({self.host}): {err}") from err
        except Exception as err:
            _LOGGER.error("Zoraxy: login error: %s", err)
        self._logged_in = False
        return False

    async def _fetch(self, endpoint: str, method: str = "GET", fields: dict | None = None, _retry: bool = True):
        """Call the Zoraxy API, logging in again when the session expired."""
        try:
            async with asyncio.timeout(15):
                if method == "GET":
                    resp = await self._session.get(
                        f"{self.host}{endpoint}",
                        params=fields,
                        allow_redirects=True,
                    )
                else:
                    resp = await self._session.post(
                        f"{self.host}{endpoint}",
                        headers={
                            "X-CSRF-Token": self._csrf_token or "",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                        data=urlencode(fields or {}),
                        allow_redirects=True,
                    )

            # Expired session → Zoraxy redirects to /login.html
            if resp.status in (401, 403) or self._session_expired(resp):
                _LOGGER.debug("Zoraxy: session expired on %s, logging in again", endpoint)
                self._logged_in = False
                if _retry and await self._login():
                    return await self._fetch(endpoint, method, fields, _retry=False)
                return None

            if resp.status == 200:
                # HTML means the redirect to the login page was followed
                ctype = resp.headers.get("Content-Type", "")
                if "text/html" in ctype:
                    _LOGGER.debug("Zoraxy: HTML received on %s (expired session?), logging in again", endpoint)
                    self._logged_in = False
                    if _retry and await self._login():
                        return await self._fetch(endpoint, method, fields, _retry=False)
                    return None
                return await resp.json(content_type=None)

        except Exception as err:
            _LOGGER.debug("Zoraxy: API error on %s: %s", endpoint, err)
        return None

    async def renew_certificate(self, domain: str) -> bool:
        if not self._acme_email:
            _LOGGER.error("Zoraxy: ACME email not available")
            return False
        try:
            async with asyncio.timeout(120):
                resp = await self._session.get(
                    f"{self.host}/api/acme/obtainCert",
                    params={
                        "domains": domain,
                        "filename": domain,
                        "email": self._acme_email,
                        "ca": self._acme_ca,
                        "dns": "false",
                    },
                    headers={"X-CSRF-Token": self._csrf_token or ""},
                    allow_redirects=True,
                )
            text = await resp.text()
            _LOGGER.info("Zoraxy: renewal of %s → %s", domain, text[:100])
            return resp.status == 200 and "error" not in text.lower()
        except Exception as err:
            _LOGGER.error("Zoraxy: renewal of %s failed: %s", domain, err)
            return False

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

    async def _async_update_data(self) -> dict:
        if not self._logged_in:
            _LOGGER.debug("Zoraxy: no session, logging in")
            if not await self._login():
                raise UpdateFailed("Zoraxy login failed")

        proxy_status = await self._fetch("/api/proxy/status")
        host_rules, root_rules = await asyncio.gather(
            self._fetch("/api/proxy/list", method="POST", fields={"type": "host"}),
            self._fetch("/api/proxy/list", method="POST", fields={"type": "root"}),
        )
        cert_list, redirect_list, access_rules, acme_email, acme_ca = await asyncio.gather(
            self._fetch("/api/cert/list"),
            self._fetch("/api/redirect/list"),
            self._fetch("/api/access/list"),
            self._fetch("/api/acme/autoRenew/email"),
            self._fetch("/api/acme/autoRenew/ca"),
        )

        if isinstance(acme_email, str):
            self._acme_email = acme_email.strip('"')
        if isinstance(acme_ca, str):
            self._acme_ca = acme_ca.strip('"') or "Let's Encrypt"

        proxy_list = []
        if isinstance(host_rules, list):
            proxy_list.extend(host_rules)
        if isinstance(root_rules, list):
            proxy_list.extend(root_rules)

        return {
            "proxy_status": proxy_status or {},
            "proxy_list": proxy_list,
            "cert_list": cert_list if isinstance(cert_list, list) else [],
            "redirect_list": redirect_list if isinstance(redirect_list, list) else [],
            "access_rules": access_rules if isinstance(access_rules, list) else [],
            "cert_expiry": self._extract_cert_expiry(proxy_status or {}),
        }
