'use strict';
/* Parcours de docs/index.html dans Chromium (Playwright).
     node tests/browser.cjs
   Variables facultatives : PLAYWRIGHT_MODULE (chemin de playwright ou playwright-core),
   CHROMIUM_PATH (navigateur à utiliser). */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const catalogue = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/thes.json'), 'utf8'));
const pageUrl = pathToFileURL(path.resolve(__dirname, '../docs/index.html')).href;
const firstWith = pred => catalogue.find(pred);
const hotTea = firstWith(t => t.froid && t.famille !== 'herbal' && t.the_g !== t.froid.the_g);
const herbal = firstWith(t => t.famille === 'herbal');
const withCaution = firstWith(t => t.precaution);
const fmt = g => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(g) + ' g';
const dose = (r, v) => Math.round((r.the_g * v / r.eau_ml + Number.EPSILON) * 10) / 10;

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined });
  const context = await browser.newContext({ locale: 'fr-FR' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(pageUrl);
    assert.equal(await page.locator('#count').textContent(), `${catalogue.length} fiches`);
    assert.equal(await page.locator('.card').count(), catalogue.length);

    // Filtres : recherche, famille, froid.
    await page.fill('#q', 'sencha');
    const nSencha = await page.locator('.card:not([hidden])').count();
    assert.ok(nSencha > 0 && nSencha < catalogue.length);
    await page.fill('#q', '');
    await page.click('.chip[data-f="herbal"]');
    assert.equal(await page.locator('.card:not([hidden])').count(), catalogue.filter(t => t.famille === 'herbal').length);
    await page.click('.chip[data-f=""]');
    await page.check('#cold-only');
    assert.equal(await page.locator('.card:not([hidden])').count(), catalogue.filter(t => t.froid && t.famille !== 'herbal').length);
    await page.uncheck('#cold-only');

    // Fiche chaude/froide, sans présélection de volume.
    await page.click(`#c-${hotTea.id}`);
    assert.equal(await page.locator('#volume').inputValue(), '');
    assert.equal(await page.locator('#grams').textContent(), '—');
    assert.deepEqual(await page.locator('#volume option').evaluateAll(o => o.map(x => x.value)), ['', '100', '150', '200', '250', '300', '350']);
    await page.selectOption('#volume', '150');
    assert.equal(await page.locator('#grams').textContent(), fmt(dose(hotTea, 150)));
    assert.equal(await page.locator('#temp').textContent(), `${hotTea.temperature_c} °C`);
    assert.ok(await page.locator('#cold-note').isHidden());
    await page.click('#mode-cold');
    assert.equal(await page.locator('#grams').textContent(), fmt(dose(hotTea.froid, 150)));
    assert.equal(await page.locator('#temp').textContent(), 'réfrigérateur');
    assert.match(await page.locator('#time').textContent(), / h$/);
    assert.ok(await page.locator('#cold-note').isVisible());
    await page.click('#mode-hot');
    assert.equal(await page.locator('#temp').textContent(), `${hotTea.temperature_c} °C`);
    assert.ok(page.url().endsWith('#' + hotTea.id));
    await page.click('#detail .close');

    // Tisane : jamais de froid, conseil à chaud, volume repris.
    await page.click(`#c-${herbal.id}`);
    assert.equal(await page.locator('#mode-cold').count(), 0);
    assert.ok(await page.locator('#herbal-note').isVisible());
    assert.equal(await page.locator('#volume').inputValue(), '150');
    await page.click('#detail .close');

    // Précaution affichée telle quelle.
    await page.click(`#c-${withCaution.id}`);
    assert.equal(await page.locator('#precaution').textContent(), withCaution.precaution);
    await page.click('#detail .close');

    // Volume retenu après rechargement ; ancienne valeur invalide ignorée.
    await page.reload();
    await page.click(`#c-${hotTea.id}`);
    assert.equal(await page.locator('#volume').inputValue(), '150');
    await page.click('#detail .close');
    await page.evaluate(() => localStorage.setItem('theotheque.volume-eau-ml', '175'));
    await page.reload();
    await page.click(`#c-${hotTea.id}`);
    assert.equal(await page.locator('#volume').inputValue(), '');
    await page.click('#detail .close');

    // Lien direct vers une fiche.
    await page.goto(pageUrl + '#' + herbal.id);
    assert.ok(await page.locator('#detail').evaluate(d => d.open));
    await page.click('#detail .close');

    // Anglais, langue retenue, retour au français, paramètre ?lang=en.
    await page.click('#lang');
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    assert.equal(await page.locator('#count').textContent(), `${catalogue.length} entries`);
    await page.click(`#c-${hotTea.id}`);
    await page.selectOption('#volume', '250');
    await page.click('#mode-cold');
    assert.equal(await page.locator('#temp').textContent(), 'fridge');
    await page.click('#detail .close');
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    await page.click('#lang');
    assert.equal(await page.locator('html').getAttribute('lang'), 'fr');
    await page.goto(pageUrl + '?lang=en');
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');

    // Thème.
    await page.click('#theme');
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
    await page.click('#theme');
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');

    // Largeur mobile sans débordement.
    await page.setViewportSize({ width: 360, height: 740 });
    await page.goto(pageUrl);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= 360));
    await page.click(`#c-${hotTea.id}`);
    await page.click('#mode-cold');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= 360));

    // Stockage bloqué : la page reste utilisable.
    const blocked = await browser.newContext();
    await blocked.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('bloqué'); } }); });
    const p2 = await blocked.newPage();
    p2.on('pageerror', e => errors.push(e.message));
    await p2.goto(pageUrl);
    await p2.click(`#c-${hotTea.id}`);
    await p2.selectOption('#volume', '200');
    assert.equal(await p2.locator('#grams').textContent(), fmt(dose(hotTea, 200)));
    await blocked.close();

    assert.deepEqual(errors, []);
    console.log(`Navigateur : ${catalogue.length} fiches, filtres, chaud/froid, tisanes, précautions, volumes BRU, mémoire, lien direct, anglais, thème, mobile et stockage bloqué : OK.`);
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
