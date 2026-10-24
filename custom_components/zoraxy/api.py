"""Client for the Zoraxy web API, shared by the coordinator and the config flow."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import aiohttp

_LOGGER = logging.getLogger(__name__)

CSRF_META_RE = re.compile(r'<meta\s+name="zoraxy\.csrf\.Token"\s+content="([^"]+)"')
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


class ZoraxyError(Exception):
    """Zoraxy could not be reached or answered with an error."""


class ZoraxyAuthError(ZoraxyError):
    """Zoraxy refused the credentials."""


def normalize_host(host: str) -> str:
    """Host as used for the unique id: no trailing slash, lower case."""
    return host.strip().rstrip("/").lower()


class ZoraxyClient:
    """Zoraxy web API with its CSRF login.

    The Zoraxy session expires after about an hour. Zoraxy then redirects to /login.html, detected from the final
    URL once the redirects are followed, from a 401/403, or from an HTML page where JSON was expected. The client
    logs in again once and retries. Concurrent calls that see the expiry at the same time log in only once: the
    login runs under a lock and a generation counter tells the others that a fresh session already exists.
    """

    def __init__(self, session: aiohttp.ClientSession, host: str, username: str, password: str) -> None:
        self._session = session
        self.host = host.strip().rstrip("/")
        self._username = username
        self._password = password
        self._csrf_token: str | None = None
        self._logged_in = False
        self._generation = 0
        self._lock = asyncio.Lock()

    async def _request(
        self, method: str, endpoint: str, *, timeout: float = 15, **kwargs: Any
    ) -> tuple[int, str, str, str]:
        """Send one request; return status, final URL path, content type and body.

        The body is read under the timeout and the response is always released.
        """
        try:
            async with (
                asyncio.timeout(timeout),
                self._session.request(method, f"{self.host}{endpoint}", allow_redirects=True, **kwargs) as resp,
            ):
                body = await resp.text()
                return resp.status, resp.url.path, resp.headers.get("Content-Type", ""), body
        except TimeoutError as err:
            raise ZoraxyError(f"Timeout while calling Zoraxy ({self.host})") from err
        except aiohttp.ClientError as err:
            raise ZoraxyError(f"Cannot reach Zoraxy ({self.host}): {err}") from err

    async def login(self) -> None:
        """Log in with a clean cookie jar. Raises ZoraxyAuthError when the credentials are refused."""
        self._logged_in = False
        self._csrf_token = None
        # Drop the expired cookies, the CSRF cookie comes back with the login page.
        self._session.cookie_jar.clear()

        _, _, _, page = await self._request("GET", "/login.html", timeout=10)
        match = CSRF_META_RE.search(page)
        if not match:
            raise ZoraxyError(f"No Zoraxy login page at {self.host} (CSRF token not found)")
        token = match.group(1)

        status, _, _, body = await self._request(
            "POST",
            "/api/auth/login",
            timeout=10,
            headers={"X-CSRF-Token": token, "Content-Type": FORM_CONTENT_TYPE},
            data=urlencode({"username": self._username, "password": self._password}),
        )
        if status >= 500:
            raise ZoraxyError(f"Zoraxy login failed (HTTP {status})")
        if status != 200 or "error" in body.lower():
            _LOGGER.debug("Zoraxy: login refused (HTTP %s): %s", status, body[:200])
            raise ZoraxyAuthError(f"Zoraxy refused the login (HTTP {status})")

        self._csrf_token = token
        self._logged_in = True
        self._generation += 1
        _LOGGER.debug("Zoraxy: logged in")

    async def _relogin(self, generation: int) -> None:
        """Log in again, unless another call already did since `generation`."""
        async with self._lock:
            if self._logged_in and self._generation != generation:
                return
            await self.login()

    async def ensure_logged_in(self) -> None:
        if not self._logged_in:
            await self._relogin(self._generation)

    @staticmethod
    def _expired(status: int, path: str, content_type: str) -> bool:
        return status in (401, 403) or "login" in path or (status == 200 and "text/html" in content_type)

    async def fetch(
        self, endpoint: str, method: str = "GET", fields: dict[str, str] | None = None, *, timeout: float = 15
    ) -> str:
        """Call the API and return the body, logging in again once when the session expired."""
        await self.ensure_logged_in()
        for attempt in range(2):
            generation = self._generation
            headers = {"X-CSRF-Token": self._csrf_token or ""}
            if method == "GET":
                result = await self._request("GET", endpoint, timeout=timeout, params=fields, headers=headers)
            else:
                headers["Content-Type"] = FORM_CONTENT_TYPE
                result = await self._request(
                    method, endpoint, timeout=timeout, headers=headers, data=urlencode(fields or {})
                )
            status, path, content_type, body = result
            if not self._expired(status, path, content_type):
                break
            if attempt:
                raise ZoraxyError(f"Zoraxy session expired again on {endpoint}")
            _LOGGER.debug("Zoraxy: session expired on %s, logging in again", endpoint)
            await self._relogin(generation)

        if status != 200:
            raise ZoraxyError(f"Zoraxy answered HTTP {status} on {endpoint}")
        return body

    async def fetch_json(self, endpoint: str, method: str = "GET", fields: dict[str, str] | None = None) -> Any:
        body = await self.fetch(endpoint, method, fields)
        try:
            return json.loads(body)
        except ValueError as err:
            raise ZoraxyError(f"Invalid response from Zoraxy on {endpoint}") from err

    async def command(
        self, endpoint: str, method: str = "POST", fields: dict[str, str] | None = None, *, timeout: float = 15
    ) -> None:
        """Run an action; Zoraxy reports a failure as {"error": "..."} with HTTP 200."""
        body = await self.fetch(endpoint, method, fields, timeout=timeout)
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("error"):
            raise ZoraxyError(str(data["error"]))
        if not isinstance(data, dict) and "error" in body.lower():
            raise ZoraxyError(body[:200])
