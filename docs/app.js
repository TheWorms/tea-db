'use strict';
/* Théothèque : consultation du catalogue (docs/thes.json, copié dans catalogue.js).
   Règles : FORMAT.md, sections « Volume d'eau » et « Infusion à froid ». */
(() => {
  const TEAS = window.theothequeCatalogue;
  const VOL = window.theothequeVolume;
  const BY = Object.fromEntries(TEAS.map(t => [t.id, t]));
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  let store;
  try { store = window.localStorage; store.getItem('x'); } catch (_) { store = null; }
  const get = k => { try { return store ? store.getItem(k) : null; } catch (_) { return null; } };
  const set = (k, v) => { try { if (store) store.setItem(k, v); return Boolean(store); } catch (_) { return false; } };

  /* ---------- Textes ---------- */
  const T = {
    fr: {
      autre: 'English', autreTitre: 'Switch to English',
      lede: n => `${n} thés et tisanes : dose, température et durée d'infusion, avec une recette à froid pour les thés. Recettes établies à partir de plusieurs maisons de thé (médiane), source sur chaque fiche.`,
      recherche: 'Chercher un thé…', toutes: 'Toutes', familles: 'Familles',
      filtreFroid: 'Infusion à froid', vueTel: 'Vue téléphone',
      compte: n => `${n} fiche${n > 1 ? 's' : ''}`,
      theme: { auto: 'Thème : auto', light: 'Thème : clair', dark: 'Thème : sombre' },
      fam: { green: 'Thé vert', black: 'Thé noir', white: 'Thé blanc', oolong: 'Oolong', yellow: 'Thé jaune', pu_erh: 'Pu-erh', dark: 'Thé sombre', herbal: 'Tisane', matcha: 'Matcha', cold: 'Thé glacé' },
      fiab: { legacy_referenced: 'Recette sourcée', family_default: 'Estimation de famille' },
      theine: { oui: 'Théine', non: 'Sans théine', inconnu: 'Théine : inconnue' },
      froidPossible: 'Froid possible', precaution: 'Précaution', voirPaquet: 'Voir le paquet',
      ambiante: 'ambiante', fouetter: 'à fouetter', a: 'à',
      fermer: 'Fermer', chaud: 'Chaud', froid: 'Froid', preparation: 'Préparation', volume: 'Eau',
      choisir: 'Choisir un volume', the: 'de thé', temperature: 'température', duree: 'durée',
      frigo: 'réfrigérateur', choisirAvant: 'choisir le volume',
      aideVolume: 'Volumes de la machine BRU : 100 à 350 ml. Le dernier choix est retenu sur cet appareil.',
      aideVolumeSession: 'Volumes de la machine BRU : 100 à 350 ml. Ce navigateur ne permet pas de retenir le choix : il vaut pour cette visite.',
      noteFroid: 'Au réfrigérateur, hors machine : mettre le thé et l\'eau froide dans une carafe fermée.',
      noteTisane: 'Tisane : toujours à l\'eau bouillante. Pour la boire froide, l\'infuser à chaud puis la laisser refroidir.',
      base: (g, ml) => `recette de base ${g} g pour ${ml} ml`, baseFroid: (g, ml) => `à froid ${g} g pour ${ml} ml`,
      source: 'source', autresNoms: 'Autres noms', photo: 'Photo', illustration: 'Illustration',
      langueContenu: '',
      pied: 'Données : <a href="thes.json">thes.json</a> · Code sous licence MIT, catalogue sous CC BY 4.0, photos sous la licence de leur auteur · <a href="https://github.com/TheWorms/tea-db">Dépôt GitHub</a>',
    },
    en: {
      autre: 'Français', autreTitre: 'Passer en français',
      lede: n => `${n} teas and herbal infusions: dose, water temperature and steeping time, with a cold brew recipe for teas. Recipes are the median of several tea houses, with the source on each entry.`,
      recherche: 'Search a tea…', toutes: 'All', familles: 'Families',
      filtreFroid: 'Cold brew', vueTel: 'Phone view',
      compte: n => `${n} entr${n > 1 ? 'ies' : 'y'}`,
      theme: { auto: 'Theme: auto', light: 'Theme: light', dark: 'Theme: dark' },
      fam: { green: 'Green tea', black: 'Black tea', white: 'White tea', oolong: 'Oolong', yellow: 'Yellow tea', pu_erh: 'Pu-erh', dark: 'Dark tea', herbal: 'Herbal infusion', matcha: 'Matcha', cold: 'Iced tea' },
      fiab: { legacy_referenced: 'Sourced recipe', family_default: 'Family estimate' },
      theine: { oui: 'Caffeine', non: 'Caffeine-free', inconnu: 'Caffeine: unknown' },
      froidPossible: 'Cold brew', precaution: 'Caution', voirPaquet: 'See the package',
      ambiante: 'room temperature', fouetter: 'whisk', a: 'to',
      fermer: 'Close', chaud: 'Hot', froid: 'Cold', preparation: 'Method', volume: 'Water',
      choisir: 'Choose a volume', the: 'of tea', temperature: 'temperature', duree: 'time',
      frigo: 'fridge', choisirAvant: 'choose the volume',
      aideVolume: 'BRU machine volumes: 100 to 350 ml. Your last choice is remembered on this device.',
      aideVolumeSession: 'BRU machine volumes: 100 to 350 ml. This browser cannot remember the choice: it applies to this visit only.',
      noteFroid: 'In the fridge, not in the machine: put the tea and cold water in a closed jug.',
      noteTisane: 'Herbal infusion: always use boiling water. To drink it cold, brew it hot, then let it cool.',
      base: (g, ml) => `base recipe ${g} g for ${ml} ml`, baseFroid: (g, ml) => `cold ${g} g for ${ml} ml`,
      source: 'source', autresNoms: 'Other names', photo: 'Photo', illustration: 'Illustration',
      langueContenu: 'Names, descriptions and cautions are in French.',
      pied: 'Data: <a href="thes.json">thes.json</a> · Code under the MIT licence, catalogue under CC BY 4.0, photos under their author\'s licence · <a href="https://github.com/TheWorms/tea-db">GitHub repository</a>',
    },
  };
  const urlLang = new URLSearchParams(location.search).get('lang');
  let lang = ['fr', 'en'].includes(urlLang) ? urlLang : get('theotheque.langue') ||
    ((navigator.language || 'fr').toLowerCase().startsWith('fr') ? 'fr' : 'en');
  if (!T[lang]) lang = 'fr';
  const L = () => T[lang];
  const nf = () => new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-GB', { maximumFractionDigits: 1 });

  /* ---------- Mise en forme ---------- */
  function dur(s) {
    if (s < 60) return `${s} s`;
    const m = Math.floor(s / 60), r = s % 60;
    return r ? `${m} min ${r} s` : `${m} min`;
  }
  function hotDuration(t) {
    if (t.duree_s === 0) return L().fouetter;
    return t.duree_max_s != null && t.duree_max_s !== t.duree_s ? `${dur(t.duree_s)} ${L().a} ${dur(t.duree_max_s)}` : dur(t.duree_s);
  }
  function coldDuration(f) {
    const h = s => nf().format(s / 3600);
    return f.duree_max_s != null && f.duree_max_s !== f.duree_s ? `${h(f.duree_s)} ${L().a} ${h(f.duree_max_s)} h` : `${h(f.duree_s)} h`;
  }
  const temp = t => t.temperature_c == null ? L().ambiante : `${t.temperature_c} °C`;
  const hasCold = t => t.famille !== 'herbal' && Boolean(t.froid);

  /* ---------- Illustration de famille (sans photo) ---------- */
  const COLORS = { green: '#5d8a3a', black: '#6e3524', white: '#b3a784', oolong: '#a8692c', yellow: '#c09619', pu_erh: '#5b3c2a', dark: '#4c4636', herbal: '#8b4f7a', matcha: '#6c9f35', cold: '#3c84a1' };
  function illus(fam) {
    const c = COLORS[fam] || '#777';
    const motif = {
      herbal: '<g fill="#fff" fill-opacity=".85"><circle cx="150" cy="92" r="16"/><circle cx="150" cy="58" r="20" fill-opacity=".55"/><circle cx="182" cy="82" r="20" fill-opacity=".55"/><circle cx="170" cy="120" r="20" fill-opacity=".55"/><circle cx="130" cy="120" r="20" fill-opacity=".55"/><circle cx="118" cy="82" r="20" fill-opacity=".55"/></g>',
      cold: '<g fill="none" stroke="#fff" stroke-opacity=".85" stroke-width="5"><path d="M122 40h56l-8 104h-40z"/></g><g fill="#fff" fill-opacity=".6"><rect x="134" y="70" width="16" height="16" rx="3"/><rect x="152" y="88" width="14" height="14" rx="3"/><rect x="136" y="104" width="14" height="14" rx="3"/></g>',
      matcha: '<circle cx="150" cy="96" r="44" fill="#fff" fill-opacity=".25"/><circle cx="150" cy="96" r="30" fill="#fff" fill-opacity=".55"/>',
    }[fam] || `<g fill="#fff"><path d="M150 36c34 18 44 62 0 116-44-54-34-98 0-116z" fill-opacity=".8"/><path d="M150 52v96" stroke="${c}" stroke-width="4" fill="none"/></g><path d="M205 70c20 10 24 34 0 62-24-28-20-52 0-62z" fill="#fff" fill-opacity=".35"/>`;
    return `<svg viewBox="0 0 300 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="300" height="200" fill="${c}"/><path d="M0 200L300 0V200z" fill="#fff" fill-opacity=".1"/>${motif}</svg>`;
  }
  const picture = (t, lazy) => illus(t.famille) +
    (t.photo ? `<img src="${esc(t.photo)}" alt="${esc(t.nom)}"${lazy ? ' loading="lazy"' : ''} onerror="this.remove()">` : '');

  /* ---------- Grille ---------- */
  const grid = $('grid');
  function cardHTML(t) {
    const tags = [`<span class="pill ${t.fiabilite === 'family_default' ? 'r-est' : 'r-src'}">${esc(L().fiab[t.fiabilite] || t.fiabilite)}</span>`];
    if (hasCold(t)) tags.push(`<span class="pill p-cold">${esc(L().froidPossible)}</span>`);
    if (t.precaution) tags.push(`<span class="pill p-warn">${esc(L().precaution)}</span>`);
    if (t.a_revoir) tags.push(`<span class="pill p-warn">${esc(L().voirPaquet)}</span>`);
    return `<div class="pic">${picture(t, true)}<span class="fam">${esc(L().fam[t.famille] || t.famille)}</span></div>
      <div class="credit">${esc(t.photo_credit || '')}</div>
      <div class="body">
        <div class="name">${esc(t.nom)}</div>
        <div class="origin">${esc(t.origine || '')}</div>
        <div class="recipe">${esc(temp(t))} · ${esc(hotDuration(t))}</div>
        <div class="notes">${esc(t.notes || '')}</div>
        <div class="tags">${tags.join('')}</div>
      </div>`;
  }
  function renderGrid() {
    grid.replaceChildren(...TEAS.map(t => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'card'; b.id = 'c-' + t.id; b.dataset.id = t.id;
      b.setAttribute('aria-label', t.nom);
      b.innerHTML = cardHTML(t);
      return b;
    }));
    filter();
  }

  /* ---------- Filtres ---------- */
  let famSel = '';
  const index = Object.fromEntries(TEAS.map(t => [t.id, norm([t.nom, t.nom_complet, ...(t.alias || []), t.origine, t.id].join(' '))]));
  function renderChips() {
    const fams = Object.keys(T.fr.fam).filter(k => TEAS.some(t => t.famille === k));
    $('fams').setAttribute('aria-label', L().familles);
    $('fams').innerHTML = [['', L().toutes], ...fams.map(k => [k, L().fam[k]])]
      .map(([k, v]) => `<button class="chip" type="button" data-f="${k}" aria-pressed="${k === famSel}">${esc(v)}</button>`).join('');
  }
  function filter() {
    const q = norm($('q').value).trim(), cold = $('cold-only').checked;
    let n = 0;
    for (const t of TEAS) {
      const ok = (!famSel || t.famille === famSel) && (!cold || hasCold(t)) && (!q || index[t.id].includes(q));
      $('c-' + t.id).hidden = !ok; n += ok;
    }
    $('count').textContent = L().compte(n);
  }
  $('fams').addEventListener('click', e => {
    const b = e.target.closest('.chip'); if (!b) return;
    famSel = b.dataset.f;
    $('fams').querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', String(c === b)));
    filter();
  });
  $('q').addEventListener('input', filter);
  $('cold-only').addEventListener('change', filter);
  $('phone').addEventListener('change', e => document.body.classList.toggle('phone', e.target.checked));

  /* ---------- Fiche ---------- */
  const dlg = $('detail');
  let volume = VOL.load(store);
  let mode = 'hot';
  function openDetail(id) {
    const t = BY[id]; if (!t) return;
    dlg.dataset.id = id; mode = 'hot';
    const cold = hasCold(t);
    const credit = t.photo ? `<div class="credit">${esc(t.photo_exacte ? L().photo : L().illustration)} · ${esc(t.photo_credit || '')}</div>` : '';
    dlg.innerHTML = `<div class="d-pic">${picture(t, false)}<button class="close" type="button">${esc(L().fermer)}</button></div>${credit}
      <div class="d-body">
        <div><h2 id="d-title">${esc(t.nom_complet || t.nom)}</h2>
          <div class="meta">${esc(L().fam[t.famille] || t.famille)}${t.origine ? ' · ' + esc(t.origine) : ''}</div></div>
        <p style="margin:0">${esc(t.notes || '')}</p>
        ${L().langueContenu ? `<div class="small">${esc(L().langueContenu)}</div>` : ''}
        ${t.a_revoir ? `<div class="reviewbox" id="a-revoir">${esc(t.a_revoir)}</div>` : ''}
        <div class="calc">
          <div class="calc-row">
            ${cold ? `<div class="seg" role="group" aria-label="${esc(L().preparation)}"><button type="button" id="mode-hot" aria-pressed="true">${esc(L().chaud)}</button><button type="button" id="mode-cold" aria-pressed="false">${esc(L().froid)}</button></div>` : ''}
            <label for="volume">${esc(L().volume)} <select id="volume"><option value="">${esc(L().choisir)}</option>${VOL.values.map(v => `<option value="${v}">${v} ml</option>`).join('')}</select></label>
          </div>
          <div class="big">
            <div><span id="grams"></span><small>${esc(L().the)}</small></div>
            <div><span id="temp"></span><small id="temp-label"></small></div>
            <div><span id="time"></span><small>${esc(L().duree)}</small></div>
          </div>
          <div class="small" id="volume-help">${esc(store ? L().aideVolume : L().aideVolumeSession)}</div>
          <div class="note" id="cold-note" hidden>${esc(L().noteFroid)}</div>
          ${t.famille === 'herbal' ? `<div class="note" id="herbal-note">${esc(L().noteTisane)}</div>` : ''}
          <div class="small"><span class="pill ${t.fiabilite === 'family_default' ? 'r-est' : 'r-src'}">${esc(L().fiab[t.fiabilite] || t.fiabilite)}</span>
            · <span id="base"></span>${/^https?:\/\//i.test(t.source || '') ? ` · <a href="${esc(t.source)}" target="_blank" rel="noopener noreferrer">${esc(L().source)}</a>` : ''}</div>
        </div>
        <div class="tags"><span class="pill p-mute">${esc(L().theine[t.theine] || t.theine)}</span></div>
        ${t.precaution ? `<div class="warnbox" id="precaution">${esc(t.precaution)}</div>` : ''}
        ${t.alias && t.alias.length ? `<div class="small">${esc(L().autresNoms)} : ${esc(t.alias.join(' · '))}</div>` : ''}
        <div class="small">id : <code>${esc(t.id)}</code></div>
      </div>`;
    const sel = dlg.querySelector('#volume');
    sel.value = volume ? String(volume) : '';
    sel.addEventListener('change', () => {
      const v = Number(sel.value);
      if (VOL.valid(v)) { volume = v; VOL.save(store, v); }
      update(t);
    });
    if (cold) {
      dlg.querySelector('#mode-hot').addEventListener('click', () => { mode = 'hot'; update(t); });
      dlg.querySelector('#mode-cold').addEventListener('click', () => { mode = 'cold'; update(t); });
    }
    dlg.querySelector('.close').addEventListener('click', closeDetail);
    update(t);
    if (!dlg.open) dlg.showModal();
    if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
  }
  function update(t) {
    const isCold = mode === 'cold' && hasCold(t);
    const r = isCold ? t.froid : t;
    const grams = volume ? VOL.dose(r, volume) : null;
    dlg.querySelector('#grams').textContent = grams == null ? '—' : `${nf().format(grams)} g`;
    dlg.querySelector('#grams').title = grams == null ? L().choisirAvant : '';
    dlg.querySelector('#temp').textContent = isCold ? L().frigo : temp(t);
    dlg.querySelector('#temp-label').textContent = L().temperature;
    dlg.querySelector('#time').textContent = isCold ? coldDuration(t.froid) : hotDuration(t);
    dlg.querySelector('#base').textContent = isCold ? L().baseFroid(nf().format(t.froid.the_g), t.froid.eau_ml) : L().base(nf().format(t.the_g), t.eau_ml);
    dlg.querySelector('#cold-note').hidden = !isCold;
    const h = dlg.querySelector('#mode-hot'), c = dlg.querySelector('#mode-cold');
    if (h) { h.setAttribute('aria-pressed', String(!isCold)); c.setAttribute('aria-pressed', String(isCold)); }
  }
  grid.addEventListener('click', e => { const c = e.target.closest('.card'); if (c) openDetail(c.dataset.id); });
  function clearHash() { if (location.hash) history.replaceState(null, '', location.pathname + location.search); }
  function closeDetail() { clearHash(); dlg.close(); }
  dlg.addEventListener('click', e => { if (e.target === dlg) closeDetail(); });
  dlg.addEventListener('close', clearHash);
  window.addEventListener('hashchange', () => { const id = decodeURIComponent(location.hash.slice(1)); if (BY[id]) openDetail(id); });

  /* ---------- Thème et langue ---------- */
  const themes = ['auto', 'light', 'dark'];
  let theme = themes.includes(get('theotheque.theme')) ? get('theotheque.theme') : 'auto';
  function applyTheme() {
    if (theme === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
    $('theme').textContent = L().theme[theme];
  }
  $('theme').addEventListener('click', () => {
    theme = themes[(themes.indexOf(theme) + 1) % themes.length]; set('theotheque.theme', theme); applyTheme();
  });
  function applyLang() {
    document.documentElement.lang = lang;
    $('lang').textContent = L().autre; $('lang').title = L().autreTitre;
    $('lede').textContent = L().lede(TEAS.length);
    $('q').placeholder = L().recherche; $('q').setAttribute('aria-label', L().recherche);
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = L()[el.dataset.i18n]; });
    $('footer').innerHTML = L().pied;
    applyTheme(); renderChips(); renderGrid();
    if (dlg.open) openDetail(dlg.dataset.id);
  }
  $('lang').addEventListener('click', () => {
    lang = lang === 'fr' ? 'en' : 'fr'; set('theotheque.langue', lang);
    const u = new URL(location.href); u.searchParams.delete('lang'); history.replaceState(null, '', u);
    applyLang();
  });

  applyLang();
  const start = decodeURIComponent(location.hash.slice(1));
  if (BY[start]) openDetail(start);
})();
