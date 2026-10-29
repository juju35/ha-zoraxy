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
  for (const lang of ['en', 'fr', 'de', 'es']) assert.ok(langs.includes(lang), `missing ${lang}`);
  const reference = Object.keys(ZoraxyCard.I18N.en).sort();
  for (const lang of langs) {
    assert.deepEqual(Object.keys(ZoraxyCard.I18N[lang]).sort(), reference, `keys of ${lang}`);
  }
});

test('every I18N key is read by the card or an editor', () => {
  // Source outside the I18N table: keys passed to _t() / t() as string literals.
  const code = source.replace(/static I18N = \{[\s\S]*?\n {2}\};\n/, '');
  const used = new Set();
  for (const call of code.matchAll(/\b_?t\(([^()]*)\)/g)) {
    for (const lit of call[1].matchAll(/["']([A-Za-z0-9_]+)["']/g)) used.add(lit[1]);
  }
  // Editor labels are built as ed_<field> and ed_<field>_helper.
  const fields = new Set(
    [ZoraxyCardEditor, ZoraxyMiniCardEditor].flatMap((E) => E.schema(() => '').map((f) => f.name)),
  );
  const unused = Object.keys(ZoraxyCard.I18N.en).filter((key) => {
    const ed = key.match(/^ed_(.+?)(_helper)?$/);
    return ed ? !fields.has(ed[1]) : !used.has(key);
  });
  assert.deepEqual(unused, []);
});

test('_t falls back to English, then to the key', () => {
  const card = makeCard();
  card._hass.locale.language = 'ja';
  assert.equal(card._t('rules'), ZoraxyCard.I18N.en.rules);
  assert.equal(card._t('no_such_key'), 'no_such_key');
  card._hass.locale.language = 'fr-CA';
  assert.equal(card._t('rules'), ZoraxyCard.I18N.fr.rules);
  card._hass.locale.language = 'de-AT';
  assert.equal(card._t('rules'), ZoraxyCard.I18N.de.rules);
  card._hass.locale.language = 'es-419';
  assert.equal(card._t('rules'), ZoraxyCard.I18N.es.rules);
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

test('mini chips show a dash, not the raw state, for unknown or unavailable values', () => {
  const states = {
    [`sensor.${PREFIX}_regles_proxy`]: { state: 'unavailable', attributes: {} },
    [`sensor.${PREFIX}_regles_actives`]: { state: 'unavailable', attributes: {} },
    [`sensor.${PREFIX}_certificats_tls`]: { state: '2', attributes: {} },
    [`sensor.${PREFIX}_port_entrant`]: { state: 'unknown', attributes: {} },
  };
  const html = makeCard(states, ZoraxyMiniCard)._miniChips();
  assert.ok(!/unknown|unavailable/.test(html), html);
  assert.match(html, /Port –/);
  assert.match(html, /–\/– rules/);
  assert.match(html, /2 certs/);
});

test('the card and the editors resolve the language the same way', () => {
  assert.equal(ZoraxyCard.langOfHass({ locale: { language: 'de-AT' }, language: 'fr' }), 'de');
  assert.equal(ZoraxyCard.langOfHass({ language: 'fr' }), 'fr');
  assert.equal(ZoraxyCard.langOfHass(undefined), 'en');
});

test('the language option wins over the Home Assistant language', () => {
  const card = makeCard({}, ZoraxyCard, { language: 'es' });
  card._hass.locale.language = 'fr';
  assert.equal(card._lang(), 'es');
  assert.equal(card._t('certsSection'), 'Certificados');
  card._config = { language: '' };
  assert.equal(card._lang(), 'fr');
  assert.equal(ZoraxyCard.langOfHass({ language: 'fr' }, { language: 'de' }), 'de');
  assert.throws(() => new ZoraxyCard().setConfig({ language: 3 }), /language must be a string/);
});

test('the editors offer the language picker, labelled in the picked language', () => {
  for (const Editor of [ZoraxyCardEditor, ZoraxyMiniCardEditor]) {
    const editor = new Editor();
    editor.appendChild = () => {};
    context.document.createElement = () => ({ addEventListener() {} });
    editor._hass = { locale: { language: 'en' } };
    editor.setConfig({ language: 'de' });
    const names = editor._form.schema.map((f) => f.name);
    assert.equal(names.at(-1), 'language');
    const picker = editor._form.schema.at(-1).selector.select.options;
    assert.deepEqual([...picker.map((o) => o.value)], ['', 'en', 'fr', 'de', 'es']);
    assert.equal(picker[0].label, ZoraxyCard.I18N.de.lang_auto);
    assert.equal(editor._form.computeLabel({ name: 'language' }), 'Sprache');
    editor.setConfig({});
    assert.equal(editor._form.computeLabel({ name: 'language' }), 'Language');
    let sent;
    editor.dispatchEvent = (ev) => { sent = ev.detail.config; };
    editor._valueChanged({ stopPropagation() {}, detail: { value: { zoraxy_url: 'http://z', language: '' } } });
    assert.deepEqual({ ...sent }, { zoraxy_url: 'http://z' });
  }
});

test('French control labels are translated', () => {
  assert.equal(ZoraxyCard.I18N.fr.httpsRedirect, 'Redirection HTTPS');
  assert.equal(ZoraxyCard.I18N.fr.devMode, 'Mode dev');
});
