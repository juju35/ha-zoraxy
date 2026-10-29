"""Tests for the Zoraxy integration."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.zoraxy.api import ZoraxyClient
from custom_components.zoraxy.const import DOMAIN

HOST = "http://zoraxy.local:8000"
P = "zoraxy_reverse_proxy_zoraxy"
LOGIN_PAGE = '<html><head><meta name="zoraxy.csrf.Token" content="tok123"></head></html>'
PROXY_STATUS = {
    "Option": {
        "Port": 443,
        "UseTls": True,
        "ForceHttpsRedirect": True,
        "ListenOnPort80": False,
        "NoCache": True,
        "TlsManager": {
            "LoadedCerts": [
                {"PriKey": "a.key", "Cert": {"DNSNames": ["a.example.org"], "NotAfter": "2099-01-01T00:00:00Z"}}
            ]
        },
    }
}
HOST_RULES = [
    {
        "RootOrMatchingDomain": "app.example.org",
        "Disabled": False,
        "ActiveOrigins": [{"OriginIpOrDomain": "10.0.0.2:80"}],
    }
]
DATA = {"host": HOST, "username": "admin", "password": "secret", "scan_interval": 30, "verify_ssl": True}


def mock_zoraxy(aioclient_mock, *, status=PROXY_STATUS, rules=HOST_RULES, certs=None):
    """Register a working Zoraxy on aioclient_mock."""
    aioclient_mock.get(f"{HOST}/login.html", text=LOGIN_PAGE)
    aioclient_mock.post(f"{HOST}/api/auth/login", text="OK")
    if isinstance(status, int):
        aioclient_mock.get(f"{HOST}/api/proxy/status", status=status, text="boom")
    else:
        aioclient_mock.get(f"{HOST}/api/proxy/status", json=status)

    async def proxy_list(method, url, data):
        return AiohttpClientMockResponse(method, url, json=rules if "type=host" in data else [])

    aioclient_mock.post(f"{HOST}/api/proxy/list", side_effect=proxy_list)
    if isinstance(certs, int):
        aioclient_mock.get(f"{HOST}/api/cert/list", status=certs, text="boom")
    else:
        aioclient_mock.get(f"{HOST}/api/cert/list", json=["a.example.org"] if certs is None else certs)
    aioclient_mock.get(f"{HOST}/api/redirect/list", json=[])
    aioclient_mock.get(f"{HOST}/api/access/list", json=[])
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/email", json="me@example.org")
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/ca", json="Let's Encrypt")


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=HOST, version=1, minor_version=2)
    entry.add_to_hass(hass)
    return entry


async def _setup(hass, entry):
    assert await async_setup_component(hass, "http", {})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _calls(aioclient_mock, path, method="post"):
    return [c for c in aioclient_mock.mock_calls if c[0].lower() == method and str(c[1]).startswith(f"{HOST}{path}")]


# ── Setup and entities ────────────────────────────────────────────────────────


async def test_setup_and_unload(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"sensor.{P}_regles_proxy").state == "1"
    assert hass.states.get(f"binary_sensor.{P}_proxy_actif").state == "on"
    assert hass.states.get(f"sensor.{P}_cert_a_example_org") is not None
    # The login sent the CSRF token taken from the login page.
    _, _, data, headers = _calls(aioclient_mock, "/api/auth/login")[0]
    assert headers["X-CSRF-Token"] == "tok123"
    assert "password=secret" in data

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_entities_share_one_device(hass, aioclient_mock, entry):
    """Every entity is attached to the same Zoraxy device, which links to the Zoraxy address."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    device_ids = {e.device_id for e in entities}
    assert entities and len(device_ids) == 1
    # By id, not async_get_device (deprecated in 2026.8, async_get_device_by_identifier is too recent for 2024.12).
    device = dr.async_get(hass).async_get(device_ids.pop())
    assert device is not None
    assert (DOMAIN, entry.entry_id) in device.identifiers
    assert (device.name, device.manufacturer, device.model) == ("Zoraxy Reverse Proxy", "tobychui", "Zoraxy")
    assert device.configuration_url == HOST


async def test_switches_read_proxy_options(hass, aioclient_mock, entry):
    """The switches follow proxy_status.Option, like the binary sensors (they were always off)."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert hass.states.get(f"switch.{P}_redirection_https").state == "on"
    assert hass.states.get(f"switch.{P}_ecoute_port_80").state == "off"
    assert hass.states.get(f"switch.{P}_mode_developpement").state == "on"


@pytest.mark.parametrize(
    ("entity", "path", "method", "field"),
    [
        # HandleUpdateHttpsRedirect: utils.PostBool(r, "set")
        ("redirection_https", "/api/proxy/useHttpsRedirect", "post", "set"),
        # HandleUpdatePort80Listener: utils.PostBool(r, "enable")
        ("ecoute_port_80", "/api/proxy/listenPort80", "post", "enable"),
        # HandleDevelopmentModeChange: utils.GetBool(r, "enable"), query string only
        ("mode_developpement", "/api/proxy/developmentMode", "get", "enable"),
    ],
)
@pytest.mark.parametrize("service", ["turn_on", "turn_off"])
async def test_switch_sends_the_parameter_zoraxy_reads(
    hass, aioclient_mock, entry, entity, path, method, field, service
):
    """Each switch sends the parameter its Zoraxy handler reads, with the right method and nothing else."""
    mock_zoraxy(aioclient_mock)
    getattr(aioclient_mock, method)(f"{HOST}{path}", text='"OK"')
    await _setup(hass, entry)
    await hass.services.async_call("switch", service, {"entity_id": f"switch.{P}_{entity}"}, blocking=True)

    value = "true" if service == "turn_on" else "false"
    calls = _calls(aioclient_mock, path, method)
    assert len(calls) == 1
    _, url, data, _ = calls[0]
    assert url.path == path
    if method == "get":
        assert dict(url.query) == {field: value}
        assert data is None
    else:
        assert not url.query
        assert data == f"{field}={value}"
    # No call went out with another method or parameter name.
    assert _calls(aioclient_mock, path, "get" if method == "post" else "post") == []


async def test_switch_error_is_raised(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    aioclient_mock.post(f"{HOST}/api/proxy/listenPort80", json={"error": "port in use"})
    await _setup(hass, entry)
    with pytest.raises(HomeAssistantError, match="port in use"):
        await hass.services.async_call("switch", "turn_on", {"entity_id": f"switch.{P}_ecoute_port_80"}, blocking=True)


async def test_unreachable_zoraxy_retries_setup(hass, aioclient_mock, entry):
    aioclient_mock.get(f"{HOST}/login.html", exc=aiohttp.ClientConnectionError("refused"))
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_refused_password_starts_reauth(hass, aioclient_mock, entry):
    aioclient_mock.get(f"{HOST}/login.html", text=LOGIN_PAGE)
    aioclient_mock.post(f"{HOST}/api/auth/login", text='{"error":"Invalid username or password"}')
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_login_body_mentioning_error_is_not_a_refusal(hass, aioclient_mock, entry):
    """Only a JSON {"error": ...} login body is a refusal, not any body containing the word "error"."""
    aioclient_mock.post(f"{HOST}/api/auth/login", text="OK (0 errors)")
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED


async def test_null_tls_manager_keeps_entities_available(hass, aioclient_mock, entry):
    """A Zoraxy without TLS manager data ("TlsManager": null) must not fail the whole update."""
    status = {"Option": {**PROXY_STATUS["Option"], "TlsManager": None}}
    mock_zoraxy(aioclient_mock, status=status)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"binary_sensor.{P}_proxy_actif").state == "on"


async def test_status_failure_makes_entities_unavailable(hass, aioclient_mock, entry):
    """A failed status call fails the update instead of showing the proxy as stopped."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    coordinator = entry.runtime_data
    aioclient_mock.clear_requests()
    mock_zoraxy(aioclient_mock, status=500)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert hass.states.get(f"binary_sensor.{P}_proxy_actif").state == "unavailable"


async def test_cert_list_failure_keeps_cert_entities(hass, aioclient_mock, entry):
    """A failed /api/cert/list at startup no longer removes the certificate entities."""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_cert_expiry_a_example_org",
        config_entry=entry,
        suggested_object_id=f"{P}_cert_a_example_org",
    )
    mock_zoraxy(aioclient_mock, certs=500)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_cert_expiry_a_example_org")


async def test_stale_cert_entities_removed(hass, aioclient_mock, entry):
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_cert_expiry_old_example_org", config_entry=entry)
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_cert_expiry_old_example_org") is None


async def test_renew_failure_is_raised(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    aioclient_mock.get(f"{HOST}/api/acme/obtainCert", json={"error": "rate limited"})
    await _setup(hass, entry)
    with pytest.raises(HomeAssistantError, match="rate limited"):
        await hass.services.async_call(
            "button", "press", {"entity_id": f"button.{P}_renouveler_a_example_org"}, blocking=True
        )


# ── toggle_proxy_rule service ─────────────────────────────────────────────────


async def test_toggle_proxy_rule_after_reload(hass, aioclient_mock, entry):
    """The service uses the coordinator loaded now, not the one of the first setup."""
    mock_zoraxy(aioclient_mock)
    aioclient_mock.post(f"{HOST}/api/proxy/toggle", text="OK")
    await _setup(hass, entry)
    first = entry.runtime_data
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data is not first

    await hass.services.async_call(
        DOMAIN, "toggle_proxy_rule", {"domain": "app.example.org", "enable": False}, blocking=True
    )
    calls = _calls(aioclient_mock, "/api/proxy/toggle")
    assert len(calls) == 1
    assert calls[0][2] == "ep=app.example.org&enable=false"


async def test_toggle_proxy_rule_without_enable_toggles(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    aioclient_mock.post(f"{HOST}/api/proxy/toggle", text="OK")
    await _setup(hass, entry)
    await hass.services.async_call(DOMAIN, "toggle_proxy_rule", {"domain": "app.example.org"}, blocking=True)
    assert _calls(aioclient_mock, "/api/proxy/toggle")[0][2] == "ep=app.example.org&enable=false"


async def test_toggle_proxy_rule_body_mentioning_error_is_not_a_failure(hass, aioclient_mock, entry):
    """Only a JSON {"error": ...} body fails a command, not any body containing the word "error"."""
    mock_zoraxy(aioclient_mock)
    aioclient_mock.post(f"{HOST}/api/proxy/toggle", text="OK, no error")
    await _setup(hass, entry)
    await hass.services.async_call(
        DOMAIN, "toggle_proxy_rule", {"domain": "app.example.org", "enable": True}, blocking=True
    )
    assert len(_calls(aioclient_mock, "/api/proxy/toggle")) == 1


async def test_toggle_proxy_rule_unknown_domain(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "toggle_proxy_rule", {"domain": "nope.example.org"}, blocking=True)


async def test_toggle_proxy_rule_zoraxy_error(hass, aioclient_mock, entry):
    """A refused change fails the call, so the card rolls its button back."""
    mock_zoraxy(aioclient_mock)
    aioclient_mock.post(f"{HOST}/api/proxy/toggle", json={"error": "endpoint not found"})
    await _setup(hass, entry)
    with pytest.raises(HomeAssistantError, match="endpoint not found"):
        await hass.services.async_call(
            DOMAIN, "toggle_proxy_rule", {"domain": "app.example.org", "enable": True}, blocking=True
        )


async def test_toggle_proxy_rule_nothing_loaded(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "toggle_proxy_rule", {"domain": "app.example.org"}, blocking=True)


# ── Client ────────────────────────────────────────────────────────────────────


async def test_concurrent_expiry_logs_in_once(hass, aioclient_mock):
    """Calls that see the expired session together log in only once."""
    logins = 0

    async def login(method, url, data):
        nonlocal logins
        logins += 1
        await asyncio.sleep(0)
        return AiohttpClientMockResponse(method, url, text="OK")

    async def endpoint(method, url, data):
        expired = logins < 2  # Requests sent with the session of the first login.
        await asyncio.sleep(0)
        if expired:
            return AiohttpClientMockResponse(
                method, url, text="<html>login</html>", headers={"Content-Type": "text/html"}
            )
        return AiohttpClientMockResponse(method, url, json=[1])

    aioclient_mock.get(f"{HOST}/login.html", text=LOGIN_PAGE)
    aioclient_mock.post(f"{HOST}/api/auth/login", side_effect=login)
    aioclient_mock.get(f"{HOST}/api/a", side_effect=endpoint)
    aioclient_mock.get(f"{HOST}/api/b", side_effect=endpoint)
    aioclient_mock.get(f"{HOST}/api/c", side_effect=endpoint)

    session = aioclient_mock.create_session(hass.loop)
    client = ZoraxyClient(session, HOST, "admin", "secret")
    await client.login()
    results = await asyncio.gather(
        client.fetch_json("/api/a"), client.fetch_json("/api/b"), client.fetch_json("/api/c")
    )
    assert results == [[1], [1], [1]]
    assert logins == 2
    await session.close()


# ── Config flow, options, reauth, migration ───────────────────────────────────


async def test_config_flow(hass, aioclient_mock):
    mock_zoraxy(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.zoraxy.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": f"{HOST}/", "username": "admin", "password": "secret"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA
    assert result["result"].unique_id == HOST
    assert result["result"].minor_version == 2


@pytest.mark.parametrize(
    ("login_page", "error"),
    [
        ({"exc": aiohttp.ClientConnectionError("refused")}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
        ({"text": "<html>no token</html>"}, "cannot_connect"),
    ],
)
async def test_config_flow_cannot_connect(hass, aioclient_mock, login_page, error):
    aioclient_mock.get(f"{HOST}/login.html", **login_page)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "username": "admin", "password": "secret"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_config_flow_invalid_auth(hass, aioclient_mock):
    aioclient_mock.get(f"{HOST}/login.html", text=LOGIN_PAGE)
    aioclient_mock.post(f"{HOST}/api/auth/login", text='{"error":"Invalid username or password"}')
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST, "username": "admin", "password": "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_duplicate(hass, aioclient_mock, entry):
    """The same host with another case or a trailing slash is the same Zoraxy."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "HTTP://Zoraxy.local:8000/", "username": "admin", "password": "secret"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 120, "verify_ssl": False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    assert coordinator.update_interval.total_seconds() == 120


async def test_scan_interval_has_a_minimum(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, "scan_interval": 0}, unique_id=HOST, minor_version=2)
    entry.add_to_hass(hass)
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert entry.runtime_data.update_interval.total_seconds() == 10


async def test_reauth_flow(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "new"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"


async def test_reauth_reloads_once(hass, aioclient_mock, entry):
    """A reauth reloads the entry once (the update listener), not twice."""
    from custom_components import zoraxy

    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    result = await entry.start_reauth_flow(hass)
    with patch("custom_components.zoraxy.async_setup_entry", wraps=zoraxy.async_setup_entry) as setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "new"})
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert setup_entry.call_count == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_reauth_after_failed_setup_reloads(hass, aioclient_mock, entry):
    """When the setup failed on the password, there is no update listener: the reauth reloads the entry itself."""
    aioclient_mock.get(f"{HOST}/login.html", text=LOGIN_PAGE)
    aioclient_mock.post(f"{HOST}/api/auth/login", text='{"error":"Invalid username or password"}')
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flow = next(f for f in hass.config_entries.flow.async_progress() if f["context"]["source"] == "reauth")
    aioclient_mock.clear_requests()
    mock_zoraxy(aioclient_mock)
    with patch("custom_components.zoraxy.config_flow._validate", return_value=None):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"password": "new"})
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.state is ConfigEntryState.LOADED


async def test_reauth_with_same_password_reloads(hass, aioclient_mock, entry):
    """An unchanged password does not fire the update listener: the reauth still reloads the entry once."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    result = await entry.start_reauth_flow(hass)
    with patch("custom_components.zoraxy.async_setup_entry", return_value=True) as setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "secret"})
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert setup_entry.call_count == 1


async def test_polling_skips_root_rule_request(hass, aioclient_mock, entry):
    """Zoraxy answers type=root with a single object, never a list: the request was wasted at each poll."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    fields = [str(call[2]) for call in _calls(aioclient_mock, "/api/proxy/list")]
    assert fields and all("type=host" in f for f in fields)
    assert hass.states.get(f"sensor.{P}_regles_proxy").state == "1"


async def test_acme_settings_polled_hourly(hass, aioclient_mock, entry):
    """The ACME auto-renew settings only feed the renewal service: read once, then at most hourly."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    coordinator = entry.runtime_data
    assert len(_calls(aioclient_mock, "/api/acme/autoRenew/email", method="get")) == 1

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(_calls(aioclient_mock, "/api/acme/autoRenew/email", method="get")) == 1
    # The settings read at the first refresh still feed the renewal service.
    assert coordinator._acme_email == "me@example.org"

    coordinator._acme_checked -= 3601  # an hour later
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(_calls(aioclient_mock, "/api/acme/autoRenew/email", method="get")) == 2


async def test_migration_keeps_tls_unchecked(hass, aioclient_mock):
    """Entries from 1.5.0 and earlier never checked the certificate: they keep verify_ssl off."""
    old = {"host": f"{HOST}/", "username": "admin", "password": "secret", "scan_interval": 30}
    entry = MockConfigEntry(domain=DOMAIN, data=old, unique_id=f"{HOST}/", version=1, minor_version=1)
    entry.add_to_hass(hass)
    mock_zoraxy(aioclient_mock)
    with patch("custom_components.zoraxy.async_create_clientsession", wraps=async_create_clientsession) as create:
        await _setup(hass, entry)
    assert entry.minor_version == 2
    assert entry.data["verify_ssl"] is False
    assert entry.unique_id == HOST
    assert create.call_args.kwargs["verify_ssl"] is False


async def test_new_entries_verify_tls(hass, aioclient_mock, entry):
    mock_zoraxy(aioclient_mock)
    with patch("custom_components.zoraxy.async_create_clientsession", wraps=async_create_clientsession) as create:
        await _setup(hass, entry)
    assert create.call_args.kwargs["verify_ssl"] is True


async def test_card_served(hass, aioclient_mock, entry, hass_client):
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    client = await hass_client()
    resp = await client.get("/zoraxy/zoraxy-card.js")
    assert resp.status == 200
    text = await resp.text()
    assert 'customElements.define("zoraxy-card"' in text
    assert 'customElements.define("zoraxy-mini-card"' in text


@pytest.mark.parametrize("as_dict", [True, False])
@pytest.mark.parametrize("key", ["mode", "resource_mode"])
async def test_card_resource_with_lovelace_data_variants(hass, aioclient_mock, entry, stub_frontend, key, as_dict):
    """Before 2025.2 hass.data["lovelace"] is a dict, then a dataclass whose `mode` field is `resource_mode` from
    2026.2."""
    assert await async_setup_component(hass, "lovelace", {})
    lovelace = hass.data["lovelace"]
    resources = lovelace["resources"] if isinstance(lovelace, dict) else lovelace.resources
    data = {key: "storage", "resources": resources, "dashboards": {}}
    hass.data["lovelace"] = data if as_dict else SimpleNamespace(**data)
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    urls = [item["url"] for item in resources.async_items()]
    assert len(urls) == 1 and urls[0].startswith("/zoraxy/zoraxy-card.js?v=")
    stub_frontend.assert_not_called()


async def test_card_resource_yaml_mode_uses_extra_js(hass, aioclient_mock, entry, stub_frontend):
    """Resources in YAML mode can't be edited: the card is loaded on every page instead."""
    from homeassistant.components.lovelace.resources import ResourceYAMLCollection

    assert await async_setup_component(hass, "lovelace", {})
    hass.data["lovelace"] = {"mode": "yaml", "resources": ResourceYAMLCollection([]), "dashboards": {}}
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    stub_frontend.assert_called_once()


# ── Review pass 2 regressions ─────────────────────────────────────────────────


async def test_acme_failure_is_retried_at_next_poll(hass, aioclient_mock, entry):
    """A failed ACME read at the first refresh does not wait an hour: the next poll reads it again."""
    mock_zoraxy(aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/email", status=500, text="boom")
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/ca", status=500, text="boom")
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    coordinator = entry.runtime_data
    assert coordinator._acme_email is None
    assert coordinator._acme_checked is None

    aioclient_mock.clear_requests()
    mock_zoraxy(aioclient_mock)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator._acme_email == "me@example.org"
    assert coordinator._acme_checked is not None


async def test_renew_reads_missing_acme_email(hass, aioclient_mock, entry):
    """With no ACME email known yet, the renewal reads it instead of failing."""
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/email", status=500, text="boom")
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/ca", status=500, text="boom")
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert entry.runtime_data._acme_email is None

    aioclient_mock.clear_requests()
    mock_zoraxy(aioclient_mock)
    aioclient_mock.get(f"{HOST}/api/acme/obtainCert", text='"OK"')
    await hass.services.async_call(
        "button", "press", {"entity_id": f"button.{P}_renouveler_a_example_org"}, blocking=True
    )
    (_, url, _, _) = _calls(aioclient_mock, "/api/acme/obtainCert", method="get")[0]
    assert url.query["email"] == "me@example.org"


async def test_renew_without_acme_email_fails(hass, aioclient_mock, entry):
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/email", status=500, text="boom")
    aioclient_mock.get(f"{HOST}/api/acme/autoRenew/ca", status=500, text="boom")
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    with pytest.raises(HomeAssistantError, match="ACME email not available"):
        await hass.services.async_call(
            "button", "press", {"entity_id": f"button.{P}_renouveler_a_example_org"}, blocking=True
        )


@pytest.mark.parametrize("loaded", [[{"PriKey": "a.key", "Cert": None}], ["junk", None], [{"PriKey": "a.key"}]])
async def test_malformed_loaded_certs_keep_entities_available(hass, aioclient_mock, entry, loaded):
    """A null Cert or a non-object entry in LoadedCerts must not fail the whole update."""
    status = {"Option": {**PROXY_STATUS["Option"], "TlsManager": {"LoadedCerts": loaded}}}
    mock_zoraxy(aioclient_mock, status=status)
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"binary_sensor.{P}_proxy_actif").state == "on"
    assert hass.states.get(f"sensor.{P}_cert_a_example_org").state == "unknown"


async def test_null_option_keeps_entities_working(hass, aioclient_mock, entry):
    """ "Option": null reads as no option in every platform instead of raising in the state properties."""
    mock_zoraxy(aioclient_mock, status={"Option": None})
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(f"binary_sensor.{P}_proxy_actif").state == "off"
    assert hass.states.get(f"binary_sensor.{P}_tls_active").state == "off"
    assert hass.states.get(f"sensor.{P}_port_entrant").state == "unknown"
    assert hass.states.get(f"switch.{P}_ecoute_port_80").state == "off"


async def test_expiry_found_by_any_san(hass, aioclient_mock, entry):
    """A certificate file named after its second SAN still gets its expiry date."""
    cert = {"DNSNames": ["example.org", "www.example.org"], "NotAfter": "2099-01-01T00:00:00Z"}
    status = {"Option": {**PROXY_STATUS["Option"], "TlsManager": {"LoadedCerts": [{"PriKey": "w.key", "Cert": cert}]}}}
    mock_zoraxy(aioclient_mock, status=status, certs=["www.example.org"])
    await _setup(hass, entry)
    assert hass.states.get(f"sensor.{P}_cert_www_example_org").state == "2099-01-01T00:00:00+00:00"
    assert hass.states.get(f"binary_sensor.{P}_cert_expirant_www_example_org").state == "off"


@pytest.mark.parametrize("reverse", [False, True])
async def test_expiry_prefers_the_certificate_named_after_the_domain(hass, aioclient_mock, entry, reverse):
    """A name covered as a secondary SAN by another certificate keeps the expiry of its own certificate."""
    apex = {"DNSNames": ["example.org", "www.example.org"], "NotAfter": "2099-01-01T00:00:00Z"}
    www = {"DNSNames": ["www.example.org"], "NotAfter": "2030-01-01T00:00:00Z"}
    loaded = [{"PriKey": "apex.key", "Cert": apex}, {"PriKey": "www.key", "Cert": www}]
    status = {"Option": {**PROXY_STATUS["Option"], "TlsManager": {"LoadedCerts": loaded[::-1] if reverse else loaded}}}
    mock_zoraxy(aioclient_mock, status=status, certs=["example.org", "www.example.org"])
    await _setup(hass, entry)
    assert hass.states.get(f"sensor.{P}_cert_example_org").state == "2099-01-01T00:00:00+00:00"
    assert hass.states.get(f"sensor.{P}_cert_www_example_org").state == "2030-01-01T00:00:00+00:00"


async def test_new_certificate_gets_entities_without_reload(hass, aioclient_mock, entry):
    """A certificate added in Zoraxy gets its sensor, binary sensor and renew button at the next update."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    assert hass.states.get(f"sensor.{P}_cert_b_example_org") is None

    aioclient_mock.clear_requests()
    mock_zoraxy(aioclient_mock, certs=["a.example.org", "b.example.org"])
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.{P}_cert_b_example_org") is not None
    assert hass.states.get(f"binary_sensor.{P}_cert_expirant_b_example_org") is not None
    assert hass.states.get(f"button.{P}_renouveler_b_example_org") is not None
    # The certificates already known are not added twice.
    registry = er.async_get(hass)
    unique_ids = [e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)]
    assert len(unique_ids) == len(set(unique_ids))


async def test_errors_are_translated(hass, aioclient_mock, entry):
    """Service and entity errors carry a translation key of the integration."""
    mock_zoraxy(aioclient_mock)
    await _setup(hass, entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "toggle_proxy_rule", {"domain": "nope.example.org"}, blocking=True)
    assert (err.value.translation_domain, err.value.translation_key) == (DOMAIN, "rule_not_found")
    assert "nope.example.org" in str(err.value)
