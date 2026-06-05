class ZoraxyCard extends HTMLElement {

  // ── Statiques ──────────────────────────────────────────────────────────────

  static ICONS = {
    router:  "M10.59,13.41C11,13.8 11,14.44 10.59,14.83C10.2,15.22 9.56,15.22 9.17,14.83C7.22,12.88 7.22,9.71 9.17,7.76L12.76,4.17C14.71,2.22 17.88,2.22 19.83,4.17C21.78,6.12 21.78,9.29 19.83,11.24L18.29,12.78C18.3,12.03 18.17,11.27 17.89,10.56L18.71,9.76C19.9,8.56 19.9,6.56 18.71,5.36C17.5,4.17 15.5,4.17 14.29,5.36L10.7,8.95C9.5,10.15 9.5,12.15 10.59,13.41M13.41,9.17C13.8,8.78 14.44,8.78 14.83,9.17C16.78,11.12 16.78,14.29 14.83,16.24L11.24,19.83C9.29,21.78 6.12,21.78 4.17,19.83C2.22,17.88 2.22,14.71 4.17,12.76L5.71,11.22C5.7,11.97 5.83,12.73 6.11,13.44L5.29,14.24C4.1,15.44 4.1,17.44 5.29,18.64C6.5,19.83 8.5,19.83 9.71,18.64L13.3,15.05C14.5,13.85 14.5,11.85 13.41,10.59C13,10.2 13,9.56 13.41,9.17Z",
    lock:    "M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V10C4,8.89 4.89,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3M12,17A2,2 0 0,0 14,15A2,2 0 0,0 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17Z",
    web:     "M16.36,14C16.44,13.34 16.5,12.68 16.5,12C16.5,11.32 16.44,10.66 16.36,10H19.74C19.9,10.64 20,11.31 20,12C20,12.69 19.9,13.36 19.74,14M14.59,19.56C15.19,18.45 15.65,17.25 15.97,16H18.92C17.96,17.65 16.43,18.93 14.59,19.56M14.34,14H9.66C9.56,13.34 9.5,12.68 9.5,12C9.5,11.32 9.56,10.65 9.66,10H14.34C14.43,10.65 14.5,11.32 14.5,12C14.5,12.68 14.43,13.34 14.34,14M12,19.96C11.17,18.76 10.5,17.43 10.09,16H13.91C13.5,17.43 12.83,18.76 12,19.96M8,8H5.08C6.03,6.34 7.57,5.06 9.4,4.44C8.8,5.55 8.35,6.75 8,8M5.08,16H8C8.35,17.25 8.8,18.45 9.4,19.56C7.57,18.93 6.03,17.65 5.08,16M4.26,14C4.1,13.36 4,12.69 4,12C4,11.31 4.1,10.64 4.26,10H7.64C7.56,10.66 7.5,11.32 7.5,12C7.5,12.68 7.56,13.34 7.64,14M12,4.03C12.83,5.23 13.5,6.57 13.91,8H10.09C10.5,6.57 11.17,5.23 12,4.03M18.92,8H15.97C15.65,6.75 15.19,5.55 14.59,4.44C16.43,5.07 17.96,6.34 18.92,8M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z",
    code:    "M14.6,16.6L19.2,12L14.6,7.4L16,6L22,12L16,18L14.6,16.6M9.4,16.6L4.8,12L9.4,7.4L8,6L2,12L8,18L9.4,16.6Z",
    cert:    "M13,21L15,20L17,21V14H13M17,9V7H15V9H13V11H15V13H17V11H19V9M11,9H3V11H11M11,13H3V15H11M3,7V9H11V7",
    refresh: "M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4",
    server:  "M4,1H20A1,1 0 0,1 21,2V6A1,1 0 0,1 20,7H4A1,1 0 0,1 3,6V2A1,1 0 0,1 4,1M4,9H20A1,1 0 0,1 21,10V14A1,1 0 0,1 20,15H4A1,1 0 0,1 3,14V10A1,1 0 0,1 4,9M4,17H20A1,1 0 0,1 21,18V22A1,1 0 0,1 20,23H4A1,1 0 0,1 3,22V18A1,1 0 0,1 4,17M9,5H10V3H9V5M9,13H10V11H9V13M9,21H10V19H9V21M6,3V5H7V3H6M6,11V13H7V11H6M6,19V21H7V19H6Z",
    redirect:"M14,3L17,6H14.5C12,6 10,8 10,10.5V14.5C8.86,14.18 8,13.19 8,12V10.5C8,6.91 10.91,4 14.5,4L17,3.97L14,1M10,21L7,18H9.5C12,18 14,16 14,13.5V9.5C15.14,9.82 16,10.81 16,12V13.5C16,17.09 13.09,20 9.5,20L7,20.03L10,23",
  };

  static LOGO = `<svg viewBox="0 0 100 100" style="width:28px;height:28px;flex-shrink:0;">
    <rect width="100" height="100" rx="16" fill="#0f172a"/>
    <circle cx="50" cy="50" r="18" fill="#bfdbfe"/>
    <path d="M50 20 L44 32 L56 32 Z" fill="#bfdbfe"/>
    <path d="M50 80 L44 68 L56 68 Z" fill="#bfdbfe"/>
    <path d="M25 35 Q15 45 15 50 Q15 55 25 65" stroke="#bfdbfe" stroke-width="5" fill="none" stroke-linecap="round"/>
    <path d="M75 35 Q85 45 85 50 Q85 55 75 65" stroke="#bfdbfe" stroke-width="5" fill="none" stroke-linecap="round"/>
  </svg>`;


  static I18N = {
    fr: {
      active: "Actif", inactive: "Inactif",
      rules: "Règles", activeRules: "Actives", certs: "Certs", port: "Port",
      controls: "Contrôles", httpsRedirect: "HTTPS redirect", port80: "Port 80", devMode: "Dev mode",
      certsSection: "Certificats", proxyRules: "Règles proxy", redirections: "Redirections",
      noCerts: "Aucun certificat trouvé.", noRules: "Aucune règle configurée.", noRedirects: "Aucune redirection configurée.",
      expired: "Expiré", renew: "Renouveler",
      domain: "Domaine", target: "Cible", status: "État",
      on: "On", off: "Off",
      enableRule: "Activer", disableRule: "Désactiver",
    },
    en: {
      active: "Active", inactive: "Inactive",
      rules: "Rules", activeRules: "Active", certs: "Certs", port: "Port",
      controls: "Controls", httpsRedirect: "HTTPS redirect", port80: "Port 80", devMode: "Dev mode",
      certsSection: "Certificates", proxyRules: "Proxy rules", redirections: "Redirections",
      noCerts: "No certificate found.", noRules: "No rule configured.", noRedirects: "No redirect configured.",
      expired: "Expired", renew: "Renew",
      domain: "Domain", target: "Target", status: "Status",
      on: "On", off: "Off",
      enableRule: "Enable", disableRule: "Disable",
    },
  };

  static BADGE_COLORS = {
    green:  ["#dcfce7","#15803d"],
    red:    ["#fee2e2","#b91c1c"],
    orange: ["#fff7ed","#c2410c"],
    gray:   ["#f3f4f6","#374151"],
  };

  static CSS = `
    :host{display:block}
    ha-card{padding:16px;box-sizing:border-box}
    .header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
    .title-link{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:500;text-decoration:none;color:var(--primary-text-color)}
    .bs{display:inline-flex;align-items:center;padding:4px 10px;border-radius:16px;font-size:12px;font-weight:500}
    .ok{background:#dcfce7;color:#15803d}.err{background:#fee2e2;color:#b91c1c}
    .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin-bottom:16px}
    .metric{background:#0f172a;border-radius:10px;padding:10px 8px;text-align:center}
    .mv{font-size:22px;font-weight:600;color:#bfdbfe}
    .ml{font-size:11px;color:#93c5fd;margin-top:2px}
    .section{margin-bottom:14px}
    .sec-header{display:flex;justify-content:space-between;align-items:center;cursor:pointer;padding:8px 0;border-bottom:1px solid var(--divider-color);margin-bottom:8px}
    .sec-title{display:flex;align-items:center;gap:8px;color:var(--secondary-text-color)}
    .sec-label{font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:0.5px}
    .sec-arrow{color:var(--secondary-text-color);font-size:12px}
    .controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
    .ctrl{display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 6px;background:#0f172a;border-radius:10px;cursor:pointer;border:none;width:100%;font-family:inherit;color:var(--primary-text-color)}
    .ctrl:hover{background:var(--primary-color,#3b82f6);color:white}
    .ctrl:hover svg,.ctrl:hover .cl{fill:white;color:rgba(255,255,255,0.8)}
    .cl{font-size:11px;color:#93c5fd;text-align:center}
    .cs{font-size:11px;font-weight:500}
    .on{color:#22c55e}.off{color:#ef4444}
    .row{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--divider-color);gap:8px}
    .row-left{display:flex;align-items:center;gap:6px;min-width:0}
    .row-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
    .row-label{font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .row-sub{font-size:12px;color:var(--secondary-text-color);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .empty{color:var(--secondary-text-color);font-size:13px;padding:8px 0}
    .renew-btn{display:flex;align-items:center;justify-content:center;background:none;border:1px solid var(--divider-color);border-radius:6px;cursor:pointer;padding:4px 7px;color:var(--primary-text-color)}
    .renew-btn:hover{background:var(--primary-color,#3b82f6);color:white;border-color:transparent}
    .renew-btn:hover svg{fill:white}
    .toggle-rule-btn{display:inline-flex;align-items:center;gap:4px;background:none;border:1px solid var(--divider-color);border-radius:6px;cursor:pointer;padding:3px 8px;font-size:11px;font-weight:500;color:var(--primary-text-color);font-family:inherit;transition:background 0.15s,color 0.15s}
    .toggle-rule-btn.is-on{border-color:#15803d;color:#15803d}
    .toggle-rule-btn.is-off{border-color:#b91c1c;color:#b91c1c}
    .toggle-rule-btn:hover{background:var(--primary-color,#3b82f6);color:white;border-color:transparent}
    .toggle-rule-btn:disabled{opacity:0.5;cursor:not-allowed}
  `;

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._sectionOpen = { controls: true, certs: false, rules: false, redirects: false };
    this._rendered = false;
    this._lastRender = 0;
  }

  setConfig(config) { this._config = config; }

  set hass(hass) {
    this._hass = hass;
    const now = Date.now();
    if (!this._rendered || now - this._lastRender > 15000) {
      this._lastRender = now;
      this._rendered = true;
      this._render();
    } else {
      this._updateValues();
    }
  }

  getCardSize() { return 7; }
  static getStubConfig() { return { zoraxy_url: "http://192.168.1.253:8000" }; }

  // ── Helpers ────────────────────────────────────────────────────────────────


  _lang() {
    const lang = this._hass?.locale?.language || navigator.language || "en";
    return lang.toLowerCase().startsWith("fr") ? "fr" : "en";
  }

  _t(key) { return ZoraxyCard.I18N[this._lang()]?.[key] ?? ZoraxyCard.I18N.en[key] ?? key; }

  _prefix() { return this._config?.entity_prefix || "zoraxy_reverse_proxy_zoraxy"; }
  _state(id) { return this._hass?.states[id]?.state ?? "unavailable"; }
  _attr(id, attr) { return this._hass?.states[id]?.attributes?.[attr]; }
  _isOn(id) { return this._state(id) === "on"; }

  async _toggle(id) {
    await this._hass.callService("homeassistant", this._isOn(id) ? "turn_off" : "turn_on", { entity_id: id });
  }
  async _pressButton(id) {
    await this._hass.callService("button", "press", { entity_id: id });
  }

  async _toggleRule(domain, currentlyEnabled, btn) {
    btn.disabled = true;

    // Mise à jour optimiste immédiate du bouton
    const newEnabled = !currentlyEnabled;
    btn.className = `toggle-rule-btn ${newEnabled ? "is-on" : "is-off"}`;
    btn.dataset.ruleEnabled = String(newEnabled);
    btn.title = newEnabled ? this._t("disableRule") : this._t("enableRule");
    btn.innerHTML = newEnabled
      ? `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;"></span>${this._t("disableRule")}`
      : `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;"></span>${this._t("enableRule")}`;

    try {
      await this._hass.callService("zoraxy", "toggle_proxy_rule", {
        domain: domain,
        enable: newEnabled,
      });
      // Re-render complet après que le coordinateur HA ait rafraîchi les données
      setTimeout(() => {
        this._lastRender = 0;
        this._rendered = false;
        if (this._hass) this._render();
      }, 3000);
    } catch (e) {
      console.error("Zoraxy toggleRule error:", e);
      // Annuler la mise à jour optimiste en cas d'erreur
      this._lastRender = 0;
      this._rendered = false;
      if (this._hass) this._render();
    } finally {
      btn.disabled = false;
    }
  }

  _dot(on) {
    return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${on?"#22c55e":"#ef4444"};margin-right:6px;flex-shrink:0;"></span>`;
  }

  _badge(text, color) {
    const [bg, fg] = ZoraxyCard.BADGE_COLORS[color] || ZoraxyCard.BADGE_COLORS.gray;
    return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500;background:${bg};color:${fg};">${text}</span>`;
  }

  _daysUntil(dateStr) {
    if (!dateStr || dateStr === "unavailable" || dateStr === "unknown") return null;
    try { return Math.floor((new Date(dateStr) - new Date()) / 86400000); } catch { return null; }
  }

  _mdi(path) {
    return `<svg viewBox="0 0 24 24" style="width:20px;height:20px;fill:currentColor;flex-shrink:0;"><path d="${path}"/></svg>`;
  }

  // Ligne générique : point + label à gauche, contenu à droite
  _row(dotOn, label, right) {
    return `<div class="row">
      <div class="row-left">${this._dot(dotOn)}<span class="row-label">${label}</span></div>
      <div class="row-right">${right}</div>
    </div>`;
  }

  _section(id, title, icon, content) {
    const open = this._sectionOpen[id] === true;
    return `<div class="section">
      <div class="sec-header" data-id="${id}">
        <div class="sec-title">${this._mdi(icon)}<span class="sec-label">${title}</span></div>
        <span class="sec-arrow" data-id="${id}">${open ? "▼" : "▶"}</span>
      </div>
      <div class="sec-content" data-id="${id}" style="display:${open ? "block" : "none"};">${content}</div>
    </div>`;
  }

  // ── Builders ───────────────────────────────────────────────────────────────

  _buildRules(rules) {
    if (!rules?.length) return `<p class="empty">Aucune règle configurée.</p>`;
    return `<table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="border-bottom:1px solid var(--divider-color);">
        <th style="text-align:left;padding:5px 4px;color:var(--secondary-text-color);font-weight:500;">Domaine</th>
        <th style="text-align:left;padding:5px 4px;color:var(--secondary-text-color);font-weight:500;">Cible</th>
        <th style="text-align:center;padding:5px 4px;color:var(--secondary-text-color);font-weight:500;">État</th>
      </tr></thead>
      <tbody>${rules.map((r, i) => `<tr style="border-bottom:1px solid var(--divider-color);">
        <td style="padding:5px 4px;font-weight:500;">${r.domain}</td>
        <td style="padding:5px 4px;color:var(--secondary-text-color);font-size:12px;">${r.target}</td>
        <td style="text-align:center;padding:5px 4px;">
          <button class="toggle-rule-btn ${r.enabled ? "is-on" : "is-off"}"
            data-rule-domain="${r.domain}"
            data-rule-enabled="${r.enabled}"
            title="${r.enabled ? this._t("disableRule") : this._t("enableRule")}">
            ${r.enabled
              ? `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;"></span>${this._t("disableRule")}`
              : `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef4444;"></span>${this._t("enableRule")}`
            }
          </button>
        </td>
      </tr>`).join("")}</tbody>
    </table>`;
  }

  _buildCerts(prefix) {
    const certPrefix = `sensor.${prefix}_cert_`;
    const sensors = Object.keys(this._hass?.states || {}).filter(id => id.startsWith(certPrefix)).sort();
    if (!sensors.length) return `<p class="empty">Aucun certificat trouvé.</p>`;
    return sensors.map(sensorId => {
      const suffix    = sensorId.slice(certPrefix.length);
      const days      = this._daysUntil(this._state(sensorId));
      const isExpiring = this._isOn(`binary_sensor.${prefix}_cert_expirant_${suffix}`);
      const domain    = this._attr(sensorId, "domain") || suffix.replace(/_/g, ".");
      const btnId     = `button.${prefix}_renouveler_${suffix}`;
      let daysLabel = "?", daysColor = "gray";
      if (days !== null) {
        daysLabel = days < 0 ? this._t("expired") : `J-${days}`;
        daysColor = days < 0 || days < 7 ? "red" : days < 30 ? "orange" : "green";
      }
      const right = `${this._badge(daysLabel, daysColor)}
        <button class="renew-btn" data-entity="${btnId}" title="${this._t('renew')}">
          ${this._mdi(ZoraxyCard.ICONS.refresh)}
        </button>`;
      return this._row(!isExpiring, domain, right);
    }).join("");
  }

  _buildRedirects(redirects) {
    if (!redirects?.length) return `<p class="empty">Aucune redirection configurée.</p>`;
    return redirects.map(r => {
      const src   = r.RedirectURL || "?";
      const dst   = r.TargetURL || "?";
      const code  = r.StatusCode ? `${r.StatusCode}` : "";
      const https = dst.startsWith("https");
      const right = `<span style="font-size:11px;color:var(--secondary-text-color);">→ ${code}</span>
        <span class="row-sub" title="${dst}">${dst}</span>
        ${https ? this._mdi(ZoraxyCard.ICONS.lock) : ""}`;
      return this._row(true, src, right);
    }).join("");
  }

  // ── Update partiel (entre les re-renders complets) ─────────────────────────

  _updateValues() {
    const root = this.shadowRoot;
    if (!root?.querySelector(".mv")) return;
    const p   = this._prefix();
    const sp  = `sensor.${p}`;
    const bp  = `binary_sensor.${p}`;

    const proxyRunning = this._isOn(`${bp}_proxy_actif`);
    const bs = root.querySelector(".bs");
    if (bs) { bs.className = `bs ${proxyRunning ? "ok" : "err"}`; bs.innerHTML = `${this._dot(proxyRunning)}${proxyRunning ? this._t("active") : this._t("inactive")}`; }

    const mvs = root.querySelectorAll(".mv");
    const metrics = [`${sp}_regles_proxy`, `${sp}_regles_actives`, `${sp}_certificats_tls`, `${sp}_port_entrant`];
    mvs.forEach((el, i) => { if (metrics[i]) el.textContent = this._state(metrics[i]); });

    [["ctrl-https", `${bp}_redirection_https`], ["ctrl-port80", `${bp}_ecoute_port_80`], ["ctrl-devmode", `${bp}_mode_developpement`]].forEach(([id, entity]) => {
      const cs = root.getElementById(id)?.querySelector(".cs");
      if (cs) { const on = this._isOn(entity); cs.textContent = on ? this._t("on") : this._t("off"); cs.className = `cs ${on ? "on" : "off"}`; }
    });
  }

  // ── Render complet ─────────────────────────────────────────────────────────

  _render() {
    if (!this._hass || !this._config) return;

    const p   = this._prefix();
    const sp  = `sensor.${p}`;
    const bp  = `binary_sensor.${p}`;
    const swp = `switch.${p}`;

    const proxyRunning  = this._isOn(`${bp}_proxy_actif`);
    const httpsRedirect = this._isOn(`${bp}_redirection_https`);
    const port80        = this._isOn(`${bp}_ecoute_port_80`);
    const devMode       = this._isOn(`${bp}_mode_developpement`);
    const rulesCount    = this._state(`${sp}_regles_proxy`);
    const activeCount   = this._state(`${sp}_regles_actives`);
    const certCount     = this._state(`${sp}_certificats_tls`);
    const port          = this._state(`${sp}_port_entrant`);
    const rules         = this._attr(`${sp}_regles_proxy`, "rules") || [];
    const redirects     = this._attr(`${sp}_regles_proxy`, "redirects") || [];
    const zoraxyUrl     = this._config.zoraxy_url || "";

    const ctrl = (id, icon, label, on) => `
      <button class="ctrl" id="${id}">
        ${this._mdi(ZoraxyCard.ICONS[icon])}
        <span class="cl">${label}</span>
        <span class="cs ${on ? "on" : "off"}">${on ? this._t("on") : this._t("off")}</span>
      </button>`;

    this.shadowRoot.innerHTML = `
      <style>${ZoraxyCard.CSS}</style>
      <ha-card>
        <div class="header">
          <a class="title-link" ${zoraxyUrl ? `href="${zoraxyUrl}" target="_blank"` : ""}>
            ${ZoraxyCard.LOGO}
            <span>Zoraxy</span>
          </a>
          <span class="bs ${proxyRunning ? "ok" : "err"}">${this._dot(proxyRunning)}${proxyRunning ? this._t("active") : this._t("inactive")}</span>
        </div>

        <div class="metrics">
          <div class="metric"><div class="mv">${rulesCount}</div><div class="ml">Règles</div></div>
          <div class="metric"><div class="mv">${activeCount}</div><div class="ml">Actives</div></div>
          <div class="metric"><div class="mv">${certCount}</div><div class="ml">Certs</div></div>
          <div class="metric"><div class="mv">${port}</div><div class="ml">Port</div></div>
        </div>

        ${this._section("controls", this._t("controls"), ZoraxyCard.ICONS.server, `<div class="controls">
          ${ctrl("ctrl-https",   "lock",   this._t("httpsRedirect"), httpsRedirect)}
          ${ctrl("ctrl-port80",  "web",    this._t("port80"),        port80)}
          ${ctrl("ctrl-devmode", "code",   this._t("devMode"),       devMode)}
        </div>`)}

        ${this._section("certs",     `${this._t("certsSection")} (${certCount})`,       ZoraxyCard.ICONS.cert,     this._buildCerts(p))}
        ${this._section("rules",     `${this._t("proxyRules")} (${rules.length})`,   ZoraxyCard.ICONS.router,   this._buildRules(rules))}
        ${this._section("redirects", `${this._t("redirections")} (${redirects.length})`, ZoraxyCard.ICONS.redirect, this._buildRedirects(redirects))}
      </ha-card>`;

    // Sections collapse/expand
    this.shadowRoot.querySelectorAll(".sec-header").forEach(h => {
      h.addEventListener("click", () => {
        const id = h.dataset.id;
        const content = this.shadowRoot.querySelector(`.sec-content[data-id="${id}"]`);
        const arrow   = this.shadowRoot.querySelector(`.sec-arrow[data-id="${id}"]`);
        const open    = content.style.display !== "none";
        content.style.display = open ? "none" : "block";
        arrow.textContent = open ? "▶" : "▼";
        this._sectionOpen[id] = !open;
      });
    });

    // Switches
    [["ctrl-https", `${swp}_redirection_https`], ["ctrl-port80", `${swp}_ecoute_port_80`], ["ctrl-devmode", `${swp}_mode_developpement`]].forEach(([id, entity]) => {
      this.shadowRoot.getElementById(id)?.addEventListener("click", () => this._toggle(entity));
    });

    // Boutons renouvellement
    this.shadowRoot.querySelectorAll(".renew-btn").forEach(btn => {
      btn.addEventListener("click", async e => {
        e.stopPropagation();
        const orig = btn.innerHTML;
        btn.innerHTML = this._mdi(ZoraxyCard.ICONS.refresh);
        btn.style.color = "#f59e0b";
        btn.disabled = true;
        try {
          await this._pressButton(btn.dataset.entity);
        } finally {
          setTimeout(() => { btn.innerHTML = orig; btn.style.color = ""; btn.disabled = false; }, 3000);
        }
      });
    });

    // Boutons activation/désactivation des règles proxy
    this.shadowRoot.querySelectorAll(".toggle-rule-btn").forEach(btn => {
      btn.addEventListener("click", async e => {
        e.stopPropagation();
        const domain = btn.dataset.ruleDomain;
        const enabled = btn.dataset.ruleEnabled === "true";
        await this._toggleRule(domain, enabled, btn);
      });
    });
  }
}

customElements.define("zoraxy-card", ZoraxyCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "zoraxy-card", name: "Zoraxy Dashboard", description: "Dashboard Zoraxy", preview: true });
