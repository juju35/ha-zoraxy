// Unit tests for the card: the card file is evaluated with stubs, no browser needed.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(
  new URL('../custom_components/zoraxy/frontend/zoraxy-card.js', import.meta.url),
  'utf8',
);
const context = {
  HTMLElement: class {
    attachShadow() {
      this.shadowRoot = {
        innerHTML: '',
        querySelector: () => null,
        querySelectorAll: () => [],
        getElementById: () => null,
        addEventListener() {},
      };
      return this.shadowRoot;
    }
  },
  // get() returning true: the define() calls at the bottom of the file are skipped.
  customElements: { get: () => true, define() {} },
  window: { customCards: [] },
  document: { createElement: () => ({}), addEventListener() {}, removeEventListener() {} },
  navigator: { language: 'en' },
  CustomEvent: class {
    constructor(type, init) {
      this.type = type;
      this.detail = init?.detail;
    }
  },
  console,
  Date,
  Infinity,
};
vm.createContext(context);
vm.runInContext(
  `${source}\nthis.zx = { ZoraxyCard, ZoraxyMiniCard, ZoraxyCardEditor, ZoraxyMiniCardEditor, zoraxyEsc, zoraxySafeUrl, ZORAXY_CARD_VERSION };`,
  context,
);
const { ZoraxyCard, ZoraxyMiniCard, ZoraxyCardEditor, ZoraxyMiniCardEditor, zoraxyEsc, zoraxySafeUrl, ZORAXY_CARD_VERSION } = context.zx;

const PREFIX = 'zoraxy_reverse_proxy_zoraxy';
const isoInDays = (n) => new Date(Date.now() + n * 86400000 + 3600000).toISOString();

// A card wired to a fake hass, enough for the HTML builders.
function makeCard(states = {}, Cls = ZoraxyCard, config = {}) {
  const card = new Cls();
  card._config = config;
  card._hass = { states, locale: { language: 'en' }, entities: undefined };
  return card;
}

test('zoraxyEsc escapes HTML and attribute characters', () => {
  assert.equal(zoraxyEsc(`<img src=x onerror="a">&'`), '&lt;img src=x onerror=&quot;a&quot;&gt;&amp;&#39;');
  assert.equal(zoraxyEsc(null), '');
  assert.equal(zoraxyEsc(0), '0');
});

test('zoraxySafeUrl only keeps http(s) URLs', () => {
  assert.equal(zoraxySafeUrl('https://zoraxy.local:8000'), 'https://zoraxy.local:8000');
  assert.equal(zoraxySafeUrl('  http://a '), 'http://a');
  assert.equal(zoraxySafeUrl('javascript:alert(1)'), '');
  assert.equal(zoraxySafeUrl('data:text/html,x'), '');
  assert.equal(zoraxySafeUrl(undefined), '');
});

test('card version is the manifest version', () => {
  const manifest = JSON.parse(
    readFileSync(new URL('../custom_components/zoraxy/manifest.json', import.meta.url), 'utf8'),
  );
  assert.equal(ZORAXY_CARD_VERSION, manifest.version);
});

test('I18N locales all carry the same keys', () => {
  const langs = Object.keys(ZoraxyCard.I18N);
  assert.ok(langs.includes('fr') && langs.includes('en'));
  const reference = Object.keys(ZoraxyCard.I18N.en).sort();
  for (const lang of langs) {
    assert.deepEqual(Object.keys(ZoraxyCard.I18N[lang]).sort(), reference, `keys of ${lang}`);
  }
});

test('_t falls back to English, then to the key', () => {
  const card = makeCard();
  card._hass.locale.language = 'de';
  assert.equal(card._t('rules'), ZoraxyCard.I18N.en.rules);
  assert.equal(card._t('no_such_key'), 'no_such_key');
  card._hass.locale.language = 'fr-CA';
  assert.equal(card._t('rules'), ZoraxyCard.I18N.fr.rules);
});

test('setConfig validates the option types', () => {
  const card = new ZoraxyCard();
  assert.throws(() => card.setConfig(null), /Invalid configuration/);
  assert.throws(() => card.setConfig({ zoraxy_url: 42 }), /zoraxy_url/);
  assert.throws(() => card.setConfig({ entity_prefix: {} }), /entity_prefix/);
  card.setConfig({ zoraxy_url: 'http://zoraxy.local:8000' });
  assert.equal(card._prefix(), PREFIX);
  card.setConfig({ entity_prefix: 'zoraxy_b' });
  assert.equal(card._prefix(), 'zoraxy_b');
  const mini = new ZoraxyMiniCard();
  assert.throws(() => mini.setConfig({ zoom: 'yes' }), /zoom/);
});

test('_daysUntil handles unknown and invalid dates', () => {
  const card = makeCard();
  assert.equal(card._daysUntil(null), null);
  assert.equal(card._daysUntil('unavailable'), null);
  assert.equal(card._daysUntil('unknown'), null);
  assert.equal(card._daysUntil('garbage'), null);
  assert.equal(card._daysUntil(isoInDays(3)), 3);
  assert.equal(card._daysUntil(isoInDays(-2)), -2);
});

test('_buildRules links plain domains but not wildcard ones', () => {
  const card = makeCard();
  const html = card._buildRules([
    { domain: 'app.example.org', target: '10.0.0.2:80', enabled: true },
    { domain: '*.example.org', target: '10.0.0.3:80', enabled: false },
  ]);
  assert.match(html, /data-href="https:\/\/app\.example\.org"/);
  assert.ok(!html.includes('data-href="https://*.example.org"'), 'wildcard domain must not be a link');
  const wildcardRow = html.split('<div class="row">').find((part) => part.includes('*.example.org'));
  assert.ok(!wildcardRow.includes('domain-link'), 'wildcard domain must not look clickable');
});

test('_buildRules escapes hostile values and says when there is nothing', () => {
  const card = makeCard();
  const html = card._buildRules([{ domain: '<img src=x>', target: '"><script>', enabled: true }]);
  assert.ok(!html.includes('<img'), 'domain must be escaped');
  assert.ok(!html.includes('<script'), 'target must be escaped');
  assert.equal(card._buildRules([]), `<p class="empty">${ZoraxyCard.I18N.en.noRules}</p>`);
});

test('mini chips sort unknown-expiry certificates last', () => {
  const states = {
    [`sensor.${PREFIX}_regles_proxy`]: { state: '5', attributes: {} },
    [`sensor.${PREFIX}_regles_actives`]: { state: '4', attributes: {} },
    [`sensor.${PREFIX}_certificats_tls`]: { state: '3', attributes: {} },
    [`sensor.${PREFIX}_port_entrant`]: { state: '443', attributes: {} },
    [`binary_sensor.${PREFIX}_redirection_https`]: { state: 'on', attributes: {} },
    [`binary_sensor.${PREFIX}_mode_developpement`]: { state: 'off', attributes: {} },
    // soon.example expires first, later.example after; nodate.example has no readable date
    // but its "expiring" binary sensor is on: it must come last, not first.
    [`sensor.${PREFIX}_cert_soon_example`]: { state: isoInDays(3), attributes: { domain: 'soon.example' } },
    [`sensor.${PREFIX}_cert_later_example`]: { state: isoInDays(10), attributes: { domain: 'later.example' } },
    [`sensor.${PREFIX}_cert_nodate_example`]: { state: 'unknown', attributes: { domain: 'nodate.example' } },
    [`binary_sensor.${PREFIX}_cert_expirant_nodate_example`]: { state: 'on', attributes: {} },
  };
  const html = makeCard(states, ZoraxyMiniCard)._miniChips();
  const order = ['soon.example', 'later.example', 'nodate.example'].map((d) => html.indexOf(d));
  assert.ok(order.every((i) => i >= 0), 'every expiring certificate gets a chip');
  assert.deepEqual([...order].sort((a, b) => a - b), order, 'closest expiry first, unknown last');
});

test('the mini card editor adds zoom to the full editor schema', () => {
  const base = ZoraxyCardEditor.SCHEMA.map((f) => f.name);
  const mini = ZoraxyMiniCardEditor.SCHEMA.map((f) => f.name);
  // joined: the vm realm's arrays are not deepStrictEqual to this realm's.
  assert.equal(mini.join(), [...base, 'zoom'].join());
  assert.equal(ZoraxyMiniCardEditor.DEFAULTS.zoom, true);
});
