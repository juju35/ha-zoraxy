"""Config flow pour l'intégration Zoraxy."""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlencode

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

CSRF_META_RE = re.compile(r'<meta\s+name="zoraxy\.csrf\.Token"\s+content="([^"]+)"')

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("host", default="http://192.168.1.253:8000"): str,
    vol.Required("username", default="admin"): str,
    vol.Required("password"): str,
    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
})


class CannotConnect(Exception):
    pass

class InvalidAuth(Exception):
    pass


async def _test_login(host: str, username: str, password: str) -> None:
    """Vérifie les identifiants en simulant le flux login CSRF de Zoraxy."""
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), cookie_jar=jar) as session:
        try:
            async with asyncio.timeout(10):
                resp = await session.get(f"{host.rstrip('/')}/login.html", allow_redirects=True)
            m = CSRF_META_RE.search(await resp.text())
            if not m:
                raise InvalidAuth("Token CSRF introuvable")

            async with asyncio.timeout(10):
                resp = await session.post(
                    f"{host.rstrip('/')}/api/auth/login",
                    headers={"X-CSRF-Token": m.group(1), "Content-Type": "application/x-www-form-urlencoded"},
                    data=urlencode({"username": username, "password": password}),
                )
            text = await resp.text()
            if resp.status != 200 or "error" in text.lower():
                raise InvalidAuth(f"Login refusé: {text[:100]}")

        except (aiohttp.ClientConnectorError, aiohttp.ServerConnectionError) as err:
            raise CannotConnect(str(err)) from err


class ZoraxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _test_login(user_input["host"], user_input["username"], user_input["password"])
                await self.async_set_unique_id(user_input["host"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Zoraxy ({user_input['host']})", data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)
