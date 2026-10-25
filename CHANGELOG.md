# Changelog

## 1.7.0

### What's new
- Mini card `custom:zoraxy-mini-card`, in the same file as the full card (no extra resource): the logo, title and status pill on one line, then chips for the active and total proxy rules, the certificates (one orange or red chip per certificate expiring within 30 days, the closest first), the inbound port, and an orange chip when the HTTPS redirect is off or the development mode on. A chip opens its entity.
- Detail button at the top right of the mini card: it switches to the full card, with the same configuration, and back; a click anywhere else on the page brings the compact view back, but not a click in a dialog opened from the card. `zoom: false` removes the button.
- Visual editor for the mini card: the full card's fields plus the detail button, in English and French.

### Maintenance
- `scripts/screenshots.py` also renders the mini card and its zoomed view, and takes `CHROMIUM_PATH` to use an installed Chromium.

## 1.6.1

### Fixes
- On Home Assistant versions before 2025.4, the card is added to the dashboard resources again instead of being loaded as an extra script.
- A re-authentication reloads the integration once instead of twice.
- The root rule is no longer requested at every update: Zoraxy never returned it in the expected form, so the request was wasted. The entities are unchanged.
- Card: a failed switch or certificate renewal no longer leaves an uncaught error in the browser console (Home Assistant still shows the error).

### Maintenance
- Tests run on Home Assistant 2026.10 and on the minimum version (2024.12), and fail on any deprecated Home Assistant call; new tests for the fixes.

## 1.6.0

### Changes
- Requires Home Assistant 2024.12 or later.
- The TLS certificate is checked, with a new **Verify the TLS certificate** option, on by default for new entries. Existing entries are migrated with it off, as before, so an HTTPS Zoraxy with a self-signed certificate keeps working: turn it on in **Configure** if your certificate is valid.
- **Configure** on the integration sets the refresh interval (10 s minimum) and the TLS verification. When Zoraxy refuses the password, Home Assistant asks for the new one.
- The entities become unavailable when Zoraxy's status cannot be read, instead of showing the proxy as stopped.
- `zoraxy.toggle_proxy_rule`: `enable` is optional (the rule is toggled when it is left out), and an unknown domain or a Zoraxy error now fails the action, so the card undoes its change.
- Card: section headers and domain links work with the keyboard (Enter, Space), and an invalid configuration shows an error on the card.

### Fixes
- The HTTPS redirect, port 80 and development mode switches show their real state and can be turned on and off: they always showed off, and the HTTPS redirect and development mode changes were ignored by Zoraxy.
- `zoraxy.toggle_proxy_rule` works again after the integration is reloaded.
- Card: rule domains, targets, redirects and certificate names are escaped, and `zoraxy_url` becomes a link only for an `http(s)://` address.
- Certificate entities are no longer deleted when the certificate list cannot be read once. The README now says to reload the integration after adding a certificate in Zoraxy.
- **Renew** logs in again when the session has expired, and reports a failure instead of only logging it.
- Requests that see an expired session together log in only once, and no connection is left open when the setup fails.
- The card redraws only when its entities change instead of every 15 s, and its height follows the open sections.

### Maintenance
- Test suite (pytest) with a test job in CI; shared `ZoraxyClient` for the coordinator and the config flow, coordinator stored on the entry.
- CI hardening: actions pinned by commit SHA, read-only token, Dependabot for actions, duplication check with PR annotations.

## 1.5.0

### Changes
- Entity names are translated (English or French, following Home Assistant) and shown under the Zoraxy Reverse Proxy device: *Proxy running* / *Proxy actif* instead of *Zoraxy - Proxy actif*. Names set by hand in Home Assistant are kept.
- Entity ids do not change. On a new install they now start with `zoraxy_reverse_proxy_zoraxy_`, the card's default `entity_prefix`, so the card works without setting it.
- Icons come from `icons.json`; the proxy icon turns off when the proxy is down.

### Maintenance
- Shared `ZoraxyEntity` base class (`entity.py`), `integration_type: hub` in the manifest.
- Removed the unused `icon.png`, `images/` and `strings.json` from the integration folder (the icons are in `brand/`, the texts in `translations/`).

## 1.4.1

### Maintenance
- Tooling only, no functional change: ruff/Biome/pre-commit, a Lint CI with duplication and dead-code checks, and internal modernizations.

## 1.4.0

### Changes
- More compact layout with the same information, like the other ha-* cards: 12 px card padding, 36 px header icon, 16 px name and 12 px subtitle, 11 px pills, tighter tiles and sections.
- 36 px logo, lower metric tiles (16 px figures), controls and certificate rows.

## 1.3.1

### Changes
- The status pill is back on the right of the header: moving it under the title in 1.3.0 is undone.

## 1.3.0

### Changes
- The card is served by the integration at `/zoraxy/zoraxy-card.js`, like the cards of ha-parcel, ha-iptv and ha-carburants-france: nothing is copied to `/config/www/` any more. At the first start, the copy left in `/config/www/zoraxy-card.js` by the previous versions is deleted and the `/local/zoraxy-card.js` dashboard resource is replaced. If you added that resource by hand in a YAML dashboard configuration, remove it: the card is loaded anyway.
- The status pill sits under the title, as in the other ha-* cards.
- Requires Home Assistant 2024.11 or later.

### Maintenance
- Logs and code comments in English.
- The release asset is `zoraxy.zip`, holding the content of `custom_components/zoraxy/` like the other ha-* integrations.

## 1.2.1

### Changes
- Card sections fold like the other ha-* cards: the chevron turns from right (folded) to down (unfolded), and a click anywhere else on the page folds the sections back to their defaults, as in ha-carburants-france.

## 1.2.0

### Changes
- The card now follows the look of the other ha-* cards: header with logo, name, Zoraxy address and status pill; metrics and controls as theme-colored tiles; uppercase section titles with an icon.
- Status colors come from the Home Assistant theme (`--success-color`, `--warning-color`, `--error-color`) instead of fixed Tailwind colors, and the dark tiles are gone in light mode.
- Card size in the Sections view (`getGridOptions`).
- Labels that were always in French ("Règles", "Aucune règle configurée"…) now follow the language; the certificate countdown reads "12 d" in English.
- README in English, with screenshots generated by `scripts/screenshots.py`.

### Fixes
- Removed a compiled `__pycache__` file from the repository.

## 1.1.1

### Fixes
- After an update, dashboards now load the new card right away: the Lovelace resource is updated through Home Assistant instead of its storage file, which Home Assistant only read at the next restart. This is why the visual editor from 1.1.0 did not show up.

## 1.1.0

### What's new
- Visual editor for the card: Zoraxy URL and entity prefix, no YAML needed. Labels in English and French.

### Maintenance
- Releases are now published automatically from this changelog when the version is bumped.
- MIT license added.

## 1.0.11

### Maintenance
- Fixed the release workflow that builds `zoraxy-integration.zip`.

## 1.0.10

### Fixes
- Section header arrows now use MDI chevron icons, as Unicode arrows did not render on some mobile devices.

## 1.0.9

### Fixes
- Proxy rule domains now open in a new tab, which links did not do inside Home Assistant's shadow DOM.

## 1.0.8

### Changes
- Removed the proxy rules table header, so the section looks like the certificates and redirects sections.

## 1.0.7

### What's new
- Proxy rule domain names are clickable and open the service in a new tab.

## 1.0.6

### Fixes
- The certificate renewal button now works: the ACME request was sent without the CSRF token and silently redirected to the login page.

## 1.0.5

### Fixes
- The Lovelace resource gets a new ID when the card is updated, so browsers reload it instead of keeping the cached version.

## 1.0.4

### Changes
- The card now ships only inside the integration (`custom_components/zoraxy/www`); the duplicate copy at the repository root is removed.
- README updated.

## 1.0.3

### Changes
- The proxy rule toggle button shows a status dot only, without text.

## 1.0.2

### What's new
- Enable or disable a proxy rule from the card.
- `zoraxy.toggle_proxy_rule` action.

## 1.0.1

### Maintenance
- Removed the example Lovelace dashboard file.

## 1.0.0

First public release.

### What's new
- Configuration from the UI: Zoraxy address, username, password and refresh interval, with automatic re-login when the session expires.
- Sensors for proxy rules, active rules, TLS certificates, access rules and listening port.
- Per-certificate expiry sensor, "expiring within 30 days" binary sensor and ACME renewal button.
- Switches for HTTPS redirect, port 80 listener and development mode.
- `zoraxy-card` Lovelace card, deployed and registered automatically.
- English and French translations.
