"""Render the Zoraxy card and mini card with mock entities and save the README screenshots.

Usage: python scripts/screenshots.py  (needs `pip install playwright` and `playwright install chromium`)
The clock is frozen so certificate countdowns stay the same.
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CARD_JS = (ROOT / "custom_components/zoraxy/frontend/zoraxy-card.js").read_text()
NOW = "2026-10-20T08:30:00+02:00"
WIDTH = 410
P = "zoraxy_reverse_proxy_zoraxy"

THEMES = {
    "light": {
        "--primary-background-color": "#e8eaed",
        "--secondary-background-color": "#f2f2f2",
        "--card-background-color": "#ffffff",
        "--primary-text-color": "#212121",
        "--secondary-text-color": "#727272",
        "--divider-color": "rgba(0,0,0,.12)",
    },
    "dark": {
        "--primary-background-color": "#111111",
        "--secondary-background-color": "#282828",
        "--card-background-color": "#1c1c1c",
        "--primary-text-color": "#e1e1e1",
        "--secondary-text-color": "#9b9b9b",
        "--divider-color": "rgba(225,225,225,.12)",
    },
}
COMMON = {
    "--primary-color": "#03a9f4",
    "--info-color": "#039be5",
    "--success-color": "#43a047",
    "--warning-color": "#ffa600",
    "--error-color": "#db4437",
}

# Minimal stand-in for Home Assistant's <ha-card>.
HA_CARD = """customElements.define("ha-card", class extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML =
      "<style>:host{display:block;background:var(--card-background-color);border-radius:12px;" +
      "border:1px solid var(--divider-color);color:var(--primary-text-color);overflow:hidden}</style><slot></slot>";
  }
});"""

RULES = [
    {"domain": "ha.example.org", "target": "192.168.1.10:8123", "enabled": True},
    {"domain": "nas.example.org", "target": "192.168.1.20:9999", "enabled": True},
    {"domain": "photos.example.org", "target": "192.168.1.20:2342", "enabled": False},
]
REDIRECTS = [{"RedirectURL": "example.org", "TargetURL": "https://www.example.org", "StatusCode": 301}]
CERTS = {
    "ha_example_org": "2026-12-31T00:00:00Z",
    "nas_example_org": "2026-11-08T00:00:00Z",
    "photos_example_org": "2026-10-24T00:00:00Z",
}


def state(entity_id, value, **attributes):
    return entity_id, {"entity_id": entity_id, "state": value, "attributes": attributes}


STATES = dict(
    [
        state(f"binary_sensor.{P}_proxy_actif", "on"),
        state(f"binary_sensor.{P}_redirection_https", "on"),
        state(f"binary_sensor.{P}_ecoute_port_80", "on"),
        state(f"binary_sensor.{P}_mode_developpement", "off"),
        state(f"sensor.{P}_regles_proxy", str(len(RULES)), rules=RULES, redirects=REDIRECTS),
        state(f"sensor.{P}_regles_actives", "2"),
        state(f"sensor.{P}_certificats_tls", str(len(CERTS))),
        state(f"sensor.{P}_port_entrant", "443"),
        *[state(f"sensor.{P}_cert_{k}", v, domain=k.replace("_", ".")) for k, v in CERTS.items()],
        *[state(f"binary_sensor.{P}_cert_expirant_{k}", "on" if k.startswith("photos") else "off") for k in CERTS],
    ]
)

SHOTS = [
    {"file": "card", "theme": "light", "lang": "en", "open": ["certs"]},
    {"file": "card-dark", "theme": "dark", "lang": "en", "open": ["rules"]},
    # The mini card, and the same card zoomed in (its detail button clicked).
    {"file": "mini", "theme": "light", "lang": "en", "tag": "zoraxy-mini-card"},
    {"file": "mini-dark", "theme": "dark", "lang": "en", "tag": "zoraxy-mini-card"},
    {"file": "mini-zoom", "theme": "light", "lang": "en", "tag": "zoraxy-mini-card", "zoom": True},
    {"file": "mini-zoom-dark", "theme": "dark", "lang": "en", "tag": "zoraxy-mini-card", "zoom": True},
]


def page_html(theme):
    variables = "".join(f"{k}:{v};" for k, v in {**THEMES[theme], **COMMON}.items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  :root {{ {variables} }}
  body {{ margin: 0; padding: 16px; background: var(--primary-background-color); color: var(--primary-text-color);
         font-family: Roboto, "Segoe UI", Helvetica, Arial, sans-serif; width: {WIDTH}px; }}
</style></head><body><div id="root"></div></body></html>"""


def main():
    out_dir = ROOT / "screenshots"
    out_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        # CHROMIUM_PATH: an already installed Chromium, instead of the one `playwright install` downloads.
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        context = browser.new_context(
            device_scale_factor=2,
            viewport={"width": 1000, "height": 2400},
            timezone_id="Europe/Paris",
        )
        for shot in SHOTS:
            # A new page per capture: the card's top-level declarations would clash in a reused page.
            page = context.new_page()
            page.on("pageerror", lambda err: print(f"page error: {err}"))
            page.clock.set_fixed_time(NOW)
            page.set_content(page_html(shot["theme"]))
            page.add_script_tag(content=HA_CARD)
            page.add_script_tag(content=CARD_JS)
            page.evaluate(
                """({states, lang, open, tag, zoom}) => {
                  const el = document.createElement(tag);
                  el.setConfig({type: `custom:${tag}`, zoraxy_url: "https://proxy.example.org"});
                  el.hass = {states, language: lang, locale: {language: lang}, callService: () => Promise.resolve()};
                  document.getElementById("root").appendChild(el);
                  // A mouse click (detail: 1), so that no focus ring shows on the new button.
                  const click = (node) => node.dispatchEvent(new MouseEvent("click", {bubbles: true, composed: true, detail: 1}));
                  if (zoom) click(el.shadowRoot.querySelector(".zoom"));
                  for (const id of open) click(el.shadowRoot.querySelector(`.sec-header[data-id="${id}"]`));
                }""",
                {
                    "states": STATES,
                    "lang": shot["lang"],
                    "open": shot.get("open", []),
                    "tag": shot.get("tag", "zoraxy-card"),
                    "zoom": shot.get("zoom", False),
                },
            )
            page.wait_for_timeout(300)
            page.locator(shot.get("tag", "zoraxy-card")).screenshot(
                path=str(out_dir / f"{shot['file']}.png"), animations="disabled"
            )
            print(f"screenshots/{shot['file']}.png")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
