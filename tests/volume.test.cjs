'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const volume = require('../docs/volume.js');
const catalogue = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/thes.json'), 'utf8'));
test('6 volumes autorisés ; tout autre volume est refusé', () => {
  assert.deepEqual(volume.values, [100, 150, 200, 250, 300, 350]);
  for (const v of [-1, 0, 50, 75, 125, 175, 249, 351, 375, 5000, NaN, Infinity, null, '', '250']) {
    assert.equal(volume.valid(v), false);
    assert.equal(volume.dose({ the_g: 3, eau_ml: 250 }, v), null);
  }
});
test('aucune présélection ; dernier choix mémorisé ; mémoire invalide ignorée', () => {
  const values = new Map();
  const storage = { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v) };
  assert.equal(volume.load(storage), null);
  assert.equal(volume.save(storage, 200), true);
  assert.equal(volume.load(storage), 200);
  assert.equal(volume.save(storage, 375), false);
  assert.equal(volume.load(storage), 200);
  for (const invalid of ['375', '251', '50', '175', '0', 'null', 'undefined', '']) {
    values.set(volume.key, invalid);
    assert.equal(volume.load(storage), null);
  }
  assert.equal(volume.load(null), null);
  assert.equal(volume.save(null, 150), false);
});
test('exemples FORMAT.md et arrondi à 0,1 g', () => {
  const tea = { the_g: 3, eau_ml: 250 };
  assert.equal(volume.dose(tea, 100), 1.2);
  assert.equal(volume.dose(tea, 150), 1.8);
  assert.equal(volume.dose(tea, 350), 4.2);
  assert.equal(volume.dose({ the_g: 3, eau_ml: 200 }, 250), 3.8);
  assert.equal(volume.dose({ the_g: 3, eau_ml: 200 }, 100), 1.5);
  assert.equal(volume.dose({ the_g: 3, eau_ml: 0 }, 150), null);
});
test('calcul sur toutes les fiches sans modifier les paramètres du catalogue', () => {
  const before = JSON.stringify(catalogue);
  for (const tea of catalogue) {
    for (const v of volume.values) {
      const dose = volume.dose(tea, v);
      assert.equal(typeof dose, 'number');
      assert.ok(Number.isFinite(dose));
      assert.ok(Math.abs(dose - tea.the_g * v / tea.eau_ml) <= 0.050000001);
    }
  }
  assert.equal(JSON.stringify(catalogue), before);
});
