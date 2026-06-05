"""Intégration Zoraxy pour Home Assistant — v3.3.2."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from urllib.parse import urlencode

import hashlib
import shutil
from pathlib import Path

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEVICE_INFO_BASE, safe_domain

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]

CSRF_META_RE = re.compile(r'<meta\s+name="zoraxy\.csrf\.Token"\s+content="([^"]+)"')

DYNAMIC_SUFFIXES = ("_cert_expiry_", "_cert_expiring_", "_renew_")

# Fichiers frontend à copier dans /config/www/ au démarrage
FRONTEND_FILES = ["zoraxy-card.js"]


def _get_file_hash(path: Path) -> str:
    """Retourne le hash MD5 court d'un fichier pour le cache-busting."""
    return hashlib.md5(path.read_bytes()).hexdigest()[:8]


def _deploy_frontend(hass: HomeAssistant) -> str | None:
    """Copie les fichiers JS dans /config/www/ si absents ou obsolètes.
    
    Retourne l'URL versionnée avec hash pour éviter les problèmes de cache.
    """
    src_dir = Path(__file__).parent / "www"
    dst_dir = Path(hass.config.config_dir) / "www"
    dst_dir.mkdir(exist_ok=True)

    versioned_url = None
    for filename in FRONTEND_FILES:
        src = src_dir / filename
        dst = dst_dir / filename
        if src.exists():
            if not dst.exists() or src.read_bytes() != dst.read_bytes():
                shutil.copy2(src, dst)
                _LOGGER.info("Zoraxy: frontend déployé → %s", dst)
            file_hash = _get_file_hash(dst)
            versioned_url = f"/local/{filename}?v={file_hash}"
    return versioned_url


async def _register_frontend(hass: HomeAssistant, versioned_url: str) -> None:
    """Enregistre la ressource Lovelace JS via le storage JSON de HA.

    Lit/modifie directement .storage/lovelace_resources pour ajouter
    la ressource, en s'assurant de charger les ressources existantes
    avant toute modification pour ne pas les écraser.
    """
    import json as _json
    import uuid

    base_url = versioned_url.split("?")[0]
    storage_path = Path(hass.config.config_dir) / ".storage" / "lovelace_resources"

    async def _do_register(_event=None) -> None:
        try:
            # Lire le fichier storage existant
            def _read_write() -> bool:
                data = {"version": 1, "minor_version": 1, "key": "lovelace_resources", "data": {"items": []}}

                if storage_path.exists():
                    try:
                        data = _json.loads(storage_path.read_text())
                    except Exception:
                        pass

                items = data.get("data", {}).get("items", [])

                # Chercher ressource existante
                existing = next((i for i in items if base_url in i.get("url", "")), None)

                if existing:
                    # Toujours écraser avec un nouvel id + nouvelle URL pour forcer le cache-busting
                    changed = False
                    if existing.get("url") != versioned_url or existing.get("type") != "module":
                        items.remove(existing)
                        items.append({"id": str(uuid.uuid4()), "type": "module", "url": versioned_url})
                        data["data"]["items"] = items
                        changed = True
                    if not changed:
                        return False  # Déjà à jour
                    _LOGGER.info("Zoraxy: ressource Lovelace mise à jour → %s", versioned_url)
                else:
                    items.append({"id": str(uuid.uuid4()), "type": "module", "url": versioned_url})
                    data["data"]["items"] = items
                    _LOGGER.info("Zoraxy: ressource Lovelace enregistrée → %s", versioned_url)

                storage_path.write_text(_json.dumps(data, indent=4))
                return True

            changed = await hass.async_add_executor_job(_read_write)
            if changed:
                _LOGGER.info("Zoraxy: redémarrez le navigateur pour charger la carte Lovelace")

        except Exception as err:
            _LOGGER.warning(
                "Zoraxy: enregistrement ressource Lovelace échoué (%s). "
                "Ajoutez manuellement %s dans "
                "Paramètres → Tableau de bord → Ressources (type: Module JavaScript).",
                err, versioned_url,
            )

    if hass.is_running:
        await _do_register()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _do_register)


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
        _LOGGER.info("Zoraxy: suppression entité obsolète %s", entity_id)
        registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Déployer la custom card dans /config/www/ et récupérer l'URL versionnée
    versioned_url = await hass.async_add_executor_job(_deploy_frontend, hass)

    # Enregistrer/mettre à jour la ressource Lovelace avec cache-busting
    if versioned_url:
        hass.async_create_task(_register_frontend(hass, versioned_url))

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

    # ── Service : activer/désactiver une règle proxy ───────────────────────
    async def handle_toggle_proxy_rule(call: ServiceCall) -> None:
        domain_name: str = call.data.get("domain", "")
        enable: bool | None = call.data.get("enable")  # True=activer, False=désactiver, None=toggle
        if not domain_name:
            _LOGGER.error("Zoraxy toggle_proxy_rule: paramètre 'domain' manquant")
            return
        # Trouver la règle dans les données courantes pour connaître l'état actuel
        proxy_list = (coordinator.data or {}).get("proxy_list", [])
        current_disabled = next(
            (r.get("Disabled", False) for r in proxy_list if r.get("RootOrMatchingDomain") == domain_name),
            None,
        )
        if current_disabled is None:
            _LOGGER.error("Zoraxy toggle_proxy_rule: domaine '%s' introuvable", domain_name)
            return
        # Déterminer l'action : si enable=None → toggle, sinon forcer
        if enable is None:
            should_enable = current_disabled  # actuellement désactivé → activer
        else:
            should_enable = enable
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
    """Coordinateur Zoraxy.

    La session Zoraxy expire après ~1h. Zoraxy répond alors avec un redirect
    307 vers /login.html. On détecte ça en vérifiant l'URL finale de la réponse
    après avoir suivi les redirects (allow_redirects=True par défaut).
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
        """Crée une nouvelle session HTTP propre."""
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )

    async def async_close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _session_expired(self, resp: aiohttp.ClientResponse) -> bool:
        """Détecte si la session a expiré en regardant l'URL finale après redirects."""
        # Zoraxy redirige vers /login.html quand la session expire
        return "login" in str(resp.url)

    async def _get_csrf_token(self) -> str | None:
        """Récupère le token CSRF depuis login.html."""
        try:
            async with asyncio.timeout(10):
                # allow_redirects=True : suit le 307 / → /login.html
                resp = await self._session.get(f"{self.host}/login.html", allow_redirects=True)
            m = CSRF_META_RE.search(await resp.text())
            if m:
                return m.group(1)
            _LOGGER.warning("Zoraxy: token CSRF introuvable dans login.html")
        except Exception as err:
            _LOGGER.error("Zoraxy: erreur récupération CSRF: %s", err)
        return None

    async def _login(self) -> bool:
        """Recrée une session propre et s'authentifie."""
        # Fermer l'ancienne session et en créer une nouvelle
        # (évite les cookies expirés qui traînent)
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
                _LOGGER.debug("Zoraxy: authentifié avec succès")
                return True
            _LOGGER.warning("Zoraxy: login refusé (HTTP %s): %s", resp.status, text[:200])
        except aiohttp.ClientConnectorError as err:
            raise UpdateFailed(f"Impossible de joindre Zoraxy ({self.host}): {err}") from err
        except Exception as err:
            _LOGGER.error("Zoraxy: erreur login: %s", err)
        self._logged_in = False
        return False

    async def _fetch(self, endpoint: str, method: str = "GET", fields: dict | None = None, _retry: bool = True):
        """Appel API Zoraxy avec re-login automatique si session expirée."""
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

            # Session expirée → Zoraxy redirige vers /login.html
            if resp.status in (401, 403) or self._session_expired(resp):
                _LOGGER.debug("Zoraxy: session expirée sur %s, re-login...", endpoint)
                self._logged_in = False
                if _retry and await self._login():
                    return await self._fetch(endpoint, method, fields, _retry=False)
                return None

            if resp.status == 200:
                # Vérifier qu'on n'a pas reçu du HTML (redirect suivi vers login)
                ctype = resp.headers.get("Content-Type", "")
                if "text/html" in ctype:
                    _LOGGER.debug("Zoraxy: HTML reçu sur %s (session expirée?), re-login...", endpoint)
                    self._logged_in = False
                    if _retry and await self._login():
                        return await self._fetch(endpoint, method, fields, _retry=False)
                    return None
                return await resp.json(content_type=None)

        except Exception as err:
            _LOGGER.debug("Erreur API %s: %s", endpoint, err)
        return None

    async def renew_certificate(self, domain: str) -> bool:
        if not self._acme_email:
            _LOGGER.error("Zoraxy: email ACME non disponible")
            return False
        try:
            async with asyncio.timeout(120):
                resp = await self._session.get(
                    f"{self.host}/api/acme/obtainCert",
                    params={"domains": domain, "filename": domain, "email": self._acme_email, "ca": self._acme_ca, "dns": "false"},
                    allow_redirects=True,
                )
            text = await resp.text()
            _LOGGER.info("Zoraxy: renouvellement %s → %s", domain, text[:100])
            return resp.status == 200 and "error" not in text.lower()
        except Exception as err:
            _LOGGER.error("Zoraxy: erreur renouvellement %s: %s", domain, err)
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
            _LOGGER.debug("Zoraxy: session inactive, re-login...")
            if not await self._login():
                raise UpdateFailed("Authentification Zoraxy échouée")

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
            "proxy_status":  proxy_status or {},
            "proxy_list":    proxy_list,
            "cert_list":     cert_list if isinstance(cert_list, list) else [],
            "redirect_list": redirect_list if isinstance(redirect_list, list) else [],
            "access_rules":  access_rules if isinstance(access_rules, list) else [],
            "cert_expiry":   self._extract_cert_expiry(proxy_status or {}),
        }
