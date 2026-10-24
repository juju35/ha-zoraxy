# Zoraxy Integration — Agent Context

## Purpose
Home Assistant custom integration for [Zoraxy](https://github.com/tobychui/zoraxy) reverse proxy (v3.3.2+).
Polls the Zoraxy REST API and exposes entities for monitoring and control.

## Architecture

```
custom_components/zoraxy/
├── __init__.py          # Setup, migration, coordinator, toggle_proxy_rule service
├── api.py               # ZoraxyClient: CSRF login, session expiry, API calls
├── sensor.py            # Sensor entities (counts, expiry dates)
├── binary_sensor.py     # Binary sensors (status flags, cert expiry alerts)
├── switch.py            # Switches (HTTPS redirect, port 80, dev mode)
├── button.py            # Buttons (ACME certificate renewal per domain)
├── config_flow.py       # Config flow (host, credentials, interval, verify_ssl), reauth, options
├── const.py             # Constants, safe_domain(), DEVICE_INFO_BASE
├── entity.py            # ZoraxyEntity base: device, translated name, entity id kept from 1.4.x
├── manifest.json        # HA integration manifest
├── icons.json           # MDI icon per translation key
├── translations/
│   ├── fr.json          # French translations
│   └── en.json          # English translations
└── brand/
    ├── icon.png         # 256×256 integration icon
    ├── icon@2x.png      # 512×512 integration icon
    └── logo.png         # 512×512 logo
```

## Authentication

Zoraxy v3.3.2 uses **gorilla/csrf** protection. Login flow:

1. `GET /login.html` (follow redirects) → receives `zoraxy_csrf` cookie + extracts CSRF token from `<meta name="zoraxy.csrf.Token" content="...">`
2. `POST /api/auth/login` with:
   - Header: `X-CSRF-Token: <meta token>`
   - Header: `Content-Type: application/x-www-form-urlencoded`
   - Body: `username=...&password=...`
3. Receives session cookie `Zoraxy=...` (TTL ~1h)
4. All subsequent POST requests require `X-CSRF-Token` header

**Session expiry detection** (Zoraxy returns 307 → /login.html, not 401):
- Check if response URL contains `"login"` after redirects
- Check if response Content-Type is `text/html` instead of JSON
- On expiry: recreate session + re-login, retry once (`_retry=False` guard)

## Key Classes

### `ZoraxyClient` (`api.py`)
- Uses a Home Assistant session (`async_create_clientsession(verify_ssl=..., cookie_jar=CookieJar(unsafe=True))`, closed with the entry); the config flow uses the same client
- `login()` — clears the cookies, GETs login.html for the CSRF token, POSTs the credentials; `ZoraxyAuthError` when refused
- `fetch()` / `fetch_json()` / `command()` — API call under `asyncio.timeout`, response always released, one re-login on expiry; `command()` also fails on `{"error": ...}`
- Re-login under an `asyncio.Lock` with a generation counter, so concurrent calls log in only once
- Errors: `ZoraxyError` (unreachable, HTTP error), `ZoraxyAuthError` (credentials refused → `ConfigEntryAuthFailed`, reauth flow)

### `ZoraxyDataUpdateCoordinator` (`__init__.py`)
- `_async_update_data()` — `/api/proxy/status` is required (`UpdateFailed` otherwise, entities unavailable); the other lists keep their previous value on failure
- `cert_list_loaded` — stale certificate entities are removed only when `/api/cert/list` actually answered
- `_extract_cert_expiry(proxy_status)` — deduplicates LoadedCerts by PriKey
- `renew_certificate(domain)` — GET `/api/acme/obtainCert` with email/ca params, raises `HomeAssistantError` on failure

### Config entry
- Version 1.2: `verify_ssl` (new entries: true; entries migrated from 1.1: false, as the TLS certificate was never checked before), unique id = `normalize_host(host)`
- Options override the data: `scan_interval` (10 s minimum), `verify_ssl`; changing them reloads the entry
- `toggle_proxy_rule` is registered in `async_setup` and resolves the coordinator at each call (the one whose `proxy_list` has the domain); raises `ServiceValidationError` / `HomeAssistantError`, which the card's optimistic rollback relies on

## API Endpoints Used

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/api/auth/login` | POST | Login with CSRF token |
| `/api/proxy/status` | GET | Proxy config, TLS certs (LoadedCerts), port |
| `/api/proxy/list` | POST | `type=host` or `type=root` — proxy rules |
| `/api/cert/list` | GET | List of certificate domain names |
| `/api/redirect/list` | GET | HTTP redirections |
| `/api/access/list` | GET | Access control rules |
| `/api/acme/autoRenew/email` | GET | ACME email config |
| `/api/acme/autoRenew/ca` | GET | ACME CA config |
| `/api/acme/obtainCert` | GET | Trigger ACME renewal (params: domains, filename, email, ca, dns) |
| `/api/proxy/useHttpsRedirect` | POST | Toggle HTTPS redirect |
| `/api/proxy/listenPort80` | POST | Toggle port 80 listener |
| `/api/proxy/developmentMode` | POST | Toggle dev/no-cache mode |

## Entity Patterns

Entities use `has_entity_name` and a `translation_key` (names in `translations/en.json` and `fr.json`, icons in `icons.json`). Their suggested entity id is built from the French name they had up to 1.4.x (`_legacy_name`, e.g. `sensor.zoraxy_reverse_proxy_zoraxy_regles_proxy`), which is what the card looks for.

Dynamic entities are created per certificate (from `/api/cert/list`):
- `sensor.zoraxy_*_cert_{safe_domain}` — expiry timestamp
- `binary_sensor.zoraxy_*_cert_expirant_{safe_domain}` — expires within 30 days
- `button.zoraxy_*_renouveler_{safe_domain}` — trigger ACME renewal

`safe_domain(domain)` converts `app.example.org` → `app_example_org`.

Stale entities are cleaned up at startup via `_cleanup_stale_entities()` using `DYNAMIC_SUFFIXES = ("_cert_expiry_", "_cert_expiring_", "_renew_")`.

## TLS Certificate Parsing

`LoadedCerts` in `/api/proxy/status` contains the full chain per domain (leaf + intermediates + root CA), all sharing the same `PriKey` path. Deduplication by `PriKey` gives the actual count. Domain name comes from `Cert.DNSNames[0]`, expiry from `Cert.NotAfter`.

## Lovelace Custom Card (`frontend/zoraxy-card.js`)

Served by the integration at `/zoraxy/zoraxy-card.js` (`async_setup` registers the static path and the dashboard resource, as ha-parcel does). Versions up to 1.2.1 copied it to `/config/www/` and loaded it from `/local/zoraxy-card.js`: that copy is deleted and that resource replaced at startup.

Web component `<zoraxy-card>`. Key design decisions:
- **Render on change**: the card re-renders only when one of its entities' state objects, the language or the hour changes; the entity list is cached on `hass.entities`
- **Escaping**: every entity attribute or config value goes through `zoraxyEsc()`; `zoraxy_url` is a link only when it starts with `http://` or `https://`
- **Section state**: `_sectionOpen` dict persists open/closed state across renders
- **Entity prefix**: `entity_prefix` option, default `zoraxy_reverse_proxy_zoraxy`
- **I18N**: `static I18N = {fr: {...}, en: {...}}` + `_t(key)` via `hass.locale.language`
- **Static assets**: `ICONS`, `LOGO`, `BADGE_COLORS`, `CSS` are static class properties (created once)

Config YAML:
```yaml
type: custom:zoraxy-card
zoraxy_url: http://zoraxy.local:8000
# Optional: entity_prefix: zoraxy_reverse_proxy_zoraxy
```

## Known Behaviors & Quirks

- Zoraxy session TTL is ~1 hour — reconnection is automatic
- `/api/proxy/list` requires `type` param (`host` or `root`); both are fetched and merged
- `/api/acme/obtainCert` is a GET (not POST) despite being a mutation
- All POST API calls require `X-CSRF-Token` header (same token as login)
- `CookieJar(unsafe=True)` is mandatory for local IP addresses
- Tests: `pip install -r requirements_test.txt && pytest`
- `asyncio.timeout` is used (Python 3.11+ native); no `async_timeout` dependency
