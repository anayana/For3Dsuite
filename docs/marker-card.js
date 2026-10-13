// marker-card.js -- gemeinsames Marker-Schema + Info-Karte fuer scene.html
// (Panorama) und splat.html (Gaussian Splatting).
//
// Einheitliches Schema (CLAUDE_CODE_UEBERGABE.md, Aufgabe A):
//
//   { id, anchor: {type:'pano', yaw, pitch, xyz?} | {type:'3d', pos:[x,y,z]},
//     title, text, media:[{type:'video'|'image'|'audio', src, poster?, caption?,
//     credit?, alt?}], links:[{label, url}], time:{from, to, phase},
//     provenance, rights:{consent, license}, attributes:{}, demo }
//
// normalizeMarker() liest alte UND neue Marker. Sie ist nicht-destruktiv: alle
// vorhandenen Felder bleiben, die Schema-Felder kommen dazu, und die alten
// Namen (yaw/pitch/xyz/pos/label) werden aus `anchor` bzw. `title` gefuellt.
// So laeuft der bestehende Viewer-Code (Hotspots, Punktwolke, Baum-Datenblatt,
// Themen-Panels ueber `kind`) unveraendert weiter -- auch fuer Marker, die nur
// noch im neuen Schema gespeichert sind. Gegenstueck in Python:
// platform/app/marker_schema.py.

const num = (v) => typeof v === 'number' && Number.isFinite(v);
const vec3 = (v) => Array.isArray(v) && v.length === 3 && v.every(num);

function legacyAnchor(m) {
  if (num(m.yaw) && num(m.pitch)) {
    const a = { type: 'pano', yaw: m.yaw, pitch: m.pitch };
    if (vec3(m.xyz)) a.xyz = m.xyz;            // Lage in der Punktwolke (3D-Ansicht)
    return a;
  }
  if (vec3(m.pos)) return { type: '3d', pos: m.pos };
  return null;
}

function legacyMedia(m) {
  // Alt: hoechstens ein Medium je Marker, Video vor Bild (wie im alten splat.html)
  const it = m.video ? { type: 'video', src: m.video }
    : m.image ? { type: 'image', src: m.image } : null;
  if (!it) return [];
  if (m.poster) it.poster = m.poster;
  if (m.caption) it.caption = m.caption;
  if (m.credit) it.credit = m.credit;
  return [it];
}

const MEDIA_TYPES = new Set(['video', 'image', 'audio']);
const okLink = (l) => l && typeof l.url === 'string' && safeUrl(l.url);

export function normalizeMarker(m) {
  m = m || {};
  const n = { ...m };
  const anchor = (m.anchor && typeof m.anchor === 'object') ? { ...m.anchor } : legacyAnchor(m);
  n.anchor = anchor;
  if (anchor && anchor.type === 'pano') {
    n.yaw = anchor.yaw; n.pitch = anchor.pitch;
    if (vec3(anchor.xyz)) n.xyz = anchor.xyz;
  } else if (anchor && anchor.type === '3d') {
    n.pos = anchor.pos;
  }
  n.title = m.title != null ? m.title : (m.label != null ? m.label : '');
  if (m.label == null && m.title != null) n.label = m.title;
  n.text = typeof m.text === 'string' ? m.text : '';
  n.media = (Array.isArray(m.media) ? m.media : legacyMedia(m))
    .filter(it => it && MEDIA_TYPES.has(it.type) && typeof it.src === 'string'
                  && safeMediaUrl(it.src));
  n.links = (Array.isArray(m.links) ? m.links : Array.isArray(m.sources) ? m.sources : [])
    .filter(okLink);
  n.attributes = m.attributes || {};
  n.demo = !!m.demo;
  return n;
}

// Marker, die eine Medien-/Text-Karte oeffnen (statt Baum-Datenblatt oder
// Themen-Panel): ohne `kind`, kein Portal, mit Text, Medium oder Link.
export function hasCardContent(n) {
  return !n.kind && n.type !== 'portal'
    && !!(n.text || n.media.length || n.links.length);
}

// Symbol fuer Pins: explizites `icon`, sonst nach erstem Medium.
export function markerIcon(n, fallback = '📍') {
  if (n.icon) return n.icon;
  const t = n.media[0] && n.media[0].type;
  return t === 'video' ? '🎬' : t === 'audio' ? '🔊' : t === 'image' ? '🖼️'
    : n.text ? '💬' : fallback;
}

// ---- sichere Ausgabe --------------------------------------------------------

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ESC[c]);

// Nur http(s), mailto und relative Pfade -- kein javascript:, data: o. ae.
export function safeUrl(u) {
  if (typeof u !== 'string') return '';
  const s = u.trim();
  if (!s) return '';
  if (/^(https?:|mailto:)/i.test(s)) return s;
  if (/^[a-z][a-z0-9+.-]*:/i.test(s) || /[\u0000-\u001f]/.test(s)) return '';
  return s;
}

// Medienquellen: zusaetzlich eingebettete Bilder/Audio/Video (data:) und
// lokale Vorschau (blob:) -- nur fuer <img>/<audio>/<video>, nie fuer Links.
export function safeMediaUrl(u) {
  if (typeof u !== 'string') return '';
  if (/^data:(image|audio|video)\/[a-z0-9.+-]+;base64,/i.test(u) || /^blob:/i.test(u)) return u;
  return safeUrl(u);
}

// Text -> HTML: alles wird escaped; danach Markdown-Teilmenge (**fett**,
// *kursiv*, [Text](URL), Leerzeile = Absatz) und die Inline-Tags der Altdaten
// (<b>, <i>, <em>, <strong>, <br> -- ohne Attribute).
export function richText(src) {
  if (!src) return '';
  return String(src).split(/\n\s*\n/).map(par => {
    let h = esc(par.trim());
    h = h.replace(/&lt;(\/?)(b|i|em|strong)&gt;/gi, '<$1$2>')
         .replace(/&lt;br\s*\/?&gt;/gi, '<br>');
    h = h.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (all, label, url) => {
      const u = safeUrl(url.replace(/&amp;/g, '&'));
      return u ? `<a href="${esc(u)}" target="_blank" rel="noopener">${label}</a>` : label;
    });
    h = h.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
         .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>');
    return '<p>' + h.replace(/\n/g, '<br>') + '</p>';
  }).join('');
}

// ---- Bausteine (auch fuer Panels in scene.html) ---------------------------

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

export function mediaElement(it) {
  ensureStyles();
  const src = safeMediaUrl(it.src);
  if (!src) return null;
  let e;
  if (it.type === 'video') {
    e = el('video');
    e.controls = true; e.playsInline = true; e.preload = 'metadata';
    const p = safeMediaUrl(it.poster || '');
    if (p) e.poster = p;
  } else if (it.type === 'audio') {
    e = el('audio');
    e.controls = true; e.preload = 'metadata';
  } else if (it.type === 'image') {
    e = el('img');
    e.alt = it.alt || '';
  } else return null;
  e.src = src;
  return e;
}

// Medium mit eigener Bildunterschrift/Credit (zweites, drittes ... Medium)
export function mediaFigure(it) {
  const m = mediaElement(it);
  if (!m) return null;
  const f = el('figure', 'mc-fig');
  f.appendChild(m);
  if (it.caption) f.appendChild(el('figcaption', 'mc-cap', it.caption));
  if (it.credit) f.appendChild(el('div', 'mc-cred', it.credit));
  return f;
}

export function linkList(links) {
  ensureStyles();
  const box = el('div', 'mc-links');
  for (const l of links) {
    const u = safeUrl(l.url);
    if (!u) continue;
    const a = el('a', null, l.label || u);
    a.href = u; a.target = '_blank'; a.rel = 'noopener';
    box.appendChild(a);
  }
  return box.childElementCount ? box : null;
}

const PROV = { erinnert: 'erinnert', dokumentiert: 'dokumentiert',
               rekonstruiert: 'rekonstruiert', kuratiert: 'kuratiert' };

function metaLine(n) {
  const parts = [];
  const t = n.time || {};
  if (t.from != null || t.to != null) {
    parts.push(t.from != null && t.to != null && t.from !== t.to
      ? `${t.from}–${t.to}` : String(t.from != null ? t.from : t.to));
  }
  if (t.phase) parts.push(t.phase);
  if (n.provenance) parts.push(PROV[n.provenance] || n.provenance);
  if (n.demo) parts.push('Demo-Inhalt');
  return parts.length ? el('div', 'mc-meta', parts.join(' · ')) : null;
}

// ---- Karte (Overlay) --------------------------------------------------------

const CSS = `
.mc-pop { position: fixed; inset: 0; z-index: 1000; display: none; place-items: center;
  background: rgba(0,0,0,.55); backdrop-filter: blur(3px); padding: 16px; }
.mc-pop.open { display: grid; }
.mc-card { width: min(440px, 94vw); max-height: 88vh; overflow: auto; background: #0d1117;
  border: 1px solid rgba(255,255,255,.14); border-radius: 14px; color: #e6edf3;
  box-shadow: 0 22px 64px rgba(0,0,0,.62); text-align: left;
  font-family: system-ui, -apple-system, sans-serif; }
.mc-card img, .mc-card video { width: 100%; display: block; background: #000;
  max-height: 52vh; object-fit: contain; }
.mc-card .mc-body { padding: 15px 18px 18px; position: relative; }
.mc-card h2 { margin: 0 26px 9px 0; font-size: 19px; line-height: 1.25; }
.mc-card .mc-meta { margin: -3px 0 10px; font-size: 12px; color: #d2a24c; }
.mc-card p { margin: 0; font-size: 14px; line-height: 1.62; color: #cbd5e1; }
.mc-card p + p { margin-top: 10px; }
.mc-card a, .mc-links a { color: #79c0ff; }
/* Bausteine -- auch ausserhalb der Karte (Themen-Panels in scene.html) */
.mc-fig { margin: 14px 0 0; }
.mc-fig img, .mc-fig video { width: 100%; display: block; background: #000;
  max-height: 52vh; object-fit: contain; border-radius: 8px; }
.mc-fig audio, .mc-card audio { width: 100%; display: block; margin-top: 12px; }
.mc-links { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; }
.mc-cap { margin-top: 12px; font-size: 12px; font-style: italic; color: #9aa7b4; }
.mc-fig .mc-cap { margin-top: 6px; }
.mc-cred { margin-top: 6px; font-size: 11px; color: #6b7684; }
.mc-card .mc-x { position: absolute; top: 12px; right: 14px; cursor: pointer; color: #9aa7b4;
  font-size: 22px; line-height: 1; background: none; border: none; }
.mc-card .mc-x:hover { color: #e6edf3; }
`;

let pop = null, card = null, onCloseCb = null, styled = false;

function ensureStyles() {
  if (styled) return;
  styled = true;
  const st = document.createElement('style');
  st.textContent = CSS;
  document.head.appendChild(st);
}

function ensureDom() {
  ensureStyles();
  if (pop) return;
  pop = el('div', 'mc-pop');
  card = el('div', 'mc-card');
  card.setAttribute('role', 'dialog');
  card.setAttribute('aria-modal', 'true');
  pop.appendChild(card);
  document.body.appendChild(pop);
  pop.addEventListener('click', e => { if (e.target === pop) closeMarkerCard(); });
  addEventListener('keydown', e => { if (e.key === 'Escape') closeMarkerCard(); });
}

// Inhalt der Karte als Element (ohne Overlay) -- auch fuer eine Studio-Vorschau.
export function buildCard(n) {
  const frag = document.createDocumentFragment();
  const media = n.media || [];
  // Erstes Bild/Video steht randlos oben, seine Unterschrift unten in der Karte
  // (wie bisher in splat.html); weitere Medien und Audio folgen im Text.
  const hero = media[0] && media[0].type !== 'audio' ? media[0] : null;
  if (hero) { const h = mediaElement(hero); if (h) frag.appendChild(h); }
  const body = el('div', 'mc-body');
  const x = el('button', 'mc-x', '×');
  x.setAttribute('aria-label', 'Schließen');
  x.onclick = closeMarkerCard;
  body.appendChild(x);
  body.appendChild(el('h2', null, n.title || ''));
  const meta = metaLine(n);
  if (meta) body.appendChild(meta);
  body.insertAdjacentHTML('beforeend', richText(n.text) || '<p></p>');
  for (const it of media) {
    if (it === hero) continue;
    const f = it.type === 'audio' && !it.caption && !it.credit ? mediaElement(it) : mediaFigure(it);
    if (f) body.appendChild(f);
  }
  const links = linkList(n.links || []);
  if (links) body.appendChild(links);
  const cap = hero ? hero.caption : (media.length ? null : n.caption);
  const cred = hero ? hero.credit : (media.length ? null : n.credit);
  if (cap) body.appendChild(el('div', 'mc-cap', cap));
  if (cred) body.appendChild(el('div', 'mc-cred', cred));
  const lic = n.rights && n.rights.license;
  if (lic) body.appendChild(el('div', 'mc-cred', 'Lizenz: ' + lic));
  frag.appendChild(body);
  return frag;
}

export function openMarkerCard(marker, { onClose } = {}) {
  ensureDom();
  const n = normalizeMarker(marker);   // idempotent -- roh oder schon normalisiert
  stopMedia();
  card.replaceChildren(buildCard(n));
  card.scrollTop = 0;
  onCloseCb = onClose || null;
  pop.classList.add('open');
  const x = card.querySelector('.mc-x');
  if (x) x.focus({ preventScroll: true });
}

function stopMedia() {
  if (card) card.querySelectorAll('video, audio').forEach(v => v.pause());
}

export function closeMarkerCard() {
  if (!pop || !pop.classList.contains('open')) return;
  stopMedia();
  pop.classList.remove('open');
  const cb = onCloseCb;
  onCloseCb = null;
  if (cb) cb();
}

export const isMarkerCardOpen = () => !!(pop && pop.classList.contains('open'));
