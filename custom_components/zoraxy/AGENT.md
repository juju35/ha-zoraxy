# Zoraxy Integration — Agent Context

## Purpose
Home Assistant custom integration for [Zoraxy](https://github.com/tobychui/zoraxy) reverse proxy (v3.3.2+).
Polls the Zoraxy REST API and exposes entities for monitoring and control.

## Architecture

```
custom_components/zoraxy/
├── __init__.py          # Coordinator, session management, API calls
├── sensor.py            # Sensor entities (counts, expiry dates)
├── binary_sensor.py     # Binary sensors (status flags, cert expiry alerts)
├── switch.py            # Switches (HTTPS redirect, port 80, dev mode)
├── button.py            # Buttons (ACME certificate renewal per domain)
├── config_flow.py       # UI config flow (host, username, password, interval)
├── const.py             # Constants, safe_domain(), DEVICE_INFO_BASE
├── manifest.json        # HA integration manifest
├── strings.json         # FR strings (default)
├── icons.json           # MDI icon mapping per entity
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

### `ZoraxyDataUpdateCoordinator` (`__init__.py`)
- `_make_session()` — creates a fresh `aiohttp.ClientSession` with `CookieJar(unsafe=True)` (required for IP-based URLs)
- `_get_csrf_token()` — GETs login.html, extracts CSRF meta tag
- `_login()` — recreates session, gets CSRF, POSTs credentials
- `_fetch(endpoint, method, fields, _retry)` — API call with auto re-login
- `_session_expired(resp)` — detects 307→login redirect
- `_extract_cert_expiry(proxy_status)` — deduplicates LoadedCerts by PriKey
- `_async_update_data()` — parallel API calls via `asyncio.gather`
- `renew_certificate(domain)` — GET `/api/acme/obtainCert` with email/ca params

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

Dynamic entities are created per certificate (from `/api/cert/list`):
- `sensor.zoraxy_*_cert_{safe_domain}` — expiry timestamp
- `binary_sensor.zoraxy_*_cert_expirant_{safe_domain}` — expires within 30 days
- `button.zoraxy_*_renouveler_{safe_domain}` — trigger ACME renewal

`safe_domain(domain)` converts `beszel.jstephan.me` → `beszel_jstephan_me`.

Stale entities are cleaned up at startup via `_cleanup_stale_entities()` using `DYNAMIC_SUFFIXES = ("_cert_expiry_", "_cert_expiring_", "_renew_")`.

## TLS Certificate Parsing

`LoadedCerts` in `/api/proxy/status` contains the full chain per domain (leaf + intermediates + root CA), all sharing the same `PriKey` path. Deduplication by `PriKey` gives the actual count. Domain name comes from `Cert.DNSNames[0]`, expiry from `Cert.NotAfter`.

## Lovelace Custom Card (`www/zoraxy-card.js`)

Web component `<zoraxy-card>`. Key design decisions:
- **Throttled render**: full DOM rebuild max every 15s; lightweight `_updateValues()` in between to avoid collapsing open sections
- **Section state**: `_sectionOpen` dict persists open/closed state across renders
- **Auto-prefix detection**: finds `sensor.*_certificats_tls` to derive entity prefix (e.g. `zoraxy_reverse_proxy_zoraxy`)
- **I18N**: `static I18N = {fr: {...}, en: {...}}` + `_t(key)` via `hass.locale.language`
- **Static assets**: `ICONS`, `LOGO`, `BADGE_COLORS`, `CSS` are static class properties (created once)

Config YAML:
```yaml
type: custom:zoraxy-card
zoraxy_url: http://192.168.1.253:8000
# Optional: entity_prefix: zoraxy_reverse_proxy_zoraxy
```

## Known Behaviors & Quirks

- Zoraxy session TTL is ~1 hour — reconnection is automatic
- `/api/proxy/list` requires `type` param (`host` or `root`); both are fetched and merged
- `/api/acme/obtainCert` is a GET (not POST) despite being a mutation
- All POST API calls require `X-CSRF-Token` header (same token as login)
- `CookieJar(unsafe=True)` is mandatory for local IP addresses
- `asyncio.timeout` is used (Python 3.11+ native); no `async_timeout` dependency
