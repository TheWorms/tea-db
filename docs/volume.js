(function (root) {
  'use strict';
  const values = Object.freeze(Array.from({ length: 6 }, (_, i) => 100 + i * 50));
  const key = 'theotheque.volume-eau-ml';
  function valid(value) {
    return typeof value === 'number' && values.includes(value);
  }
  function load(storage) {
    try {
      const raw = storage.getItem(key);
      if (raw === null) return null;
      const value = Number(raw);
      return valid(value) ? value : null;
    } catch (_) { return null; }
  }
  function save(storage, value) {
    if (!valid(value)) return false;
    try { storage.setItem(key, String(value)); return true; }
    catch (_) { return false; }
  }
  function dose(tea, volume) {
    if (!valid(volume) || !Number.isFinite(tea.the_g) || tea.the_g <= 0 ||
        !Number.isFinite(tea.eau_ml) || tea.eau_ml <= 0) return null;
    return Math.round((tea.the_g * volume / tea.eau_ml + Number.EPSILON) * 10) / 10;
  }
  const api = Object.freeze({ values, key, valid, load, save, dose });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.theothequeVolume = api;
})(globalThis);
