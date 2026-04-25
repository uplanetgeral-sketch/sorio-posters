// _shared/editor.js · Layer transform + z-index + colour + interactive postMessage protocol.
//
// Para usar num template:
//   1. Adicionar data-layer="<name>" a cada elemento editável
//      (hero / title / accent / info_top / info_bottom / logo / selo)
//   2. No fim do <script>, chamar:
//        applyEditor({ canvasW, canvasH, p, layers });
//      onde `layers` é a lista de layer-ids relevantes para este template.
//
// PARAMS lidos do URL (por layer):
//   <layer>_x          offset horizontal (px) relativo à posição base, default 0
//   <layer>_y          offset vertical (px) relativo à posição base, default 0
//   <layer>_rotation   graus, default 0
//   <layer>_scale      multiplicador, default 1.0
//   z_<layer>          z-index numérico (override CSS), default mantém actual
//   <layer>_color      override de cor para text layers (CSS color string)
//
// POSTMESSAGE PROTOCOL:
//   ➜ Parent → iframe:
//     { type: "editor:transform", layer, x?, y?, rotation?, scale? }   live update visual
//     { type: "editor:set_param", key, value }                         actualiza param no DOM
//     { type: "editor:request_state" }                                 pede snapshot dos layers
//   ➜ Iframe → parent:
//     { type: "editor:ready", layers: [...] }                          enviado on load
//     { type: "editor:state", layers: [...] }                          resposta a request_state
//
// Cada item de `layers` no postMessage tem:
//   { id, selector, bbox: {x, y, w, h}, transform: {x, y, rotation, scale}, z }

(function () {
  'use strict';

  // Estado mutável por layer — guardamos o transform actual para podermos diff-update.
  const layerState = {}; // { hero: { x, y, rotation, scale, baseRect, el }, ... }

  function num(p, k, d) {
    const v = p.get(k);
    if (v === null || v === '') return d;
    const n = parseFloat(v);
    return isNaN(n) ? d : n;
  }

  function findLayerEl(layerId) {
    // Tenta data-layer primeiro, depois IDs comuns (com fallback de hyphen vs underscore)
    return (
      document.querySelector('[data-layer="' + layerId + '"]') ||
      document.getElementById(layerId) ||
      document.getElementById(layerId.replace(/_/g, '-')) ||
      document.querySelector('.' + layerId)
    );
  }

  function applyTransform(el, t) {
    // Combina translate + rotate + scale numa única transform CSS
    // Mantém transforms pré-existentes (e.g. translate(-50%, -50%) do branding.js)
    // Para isto, anotamos a base no dataset.
    if (!el.dataset.baseTransform) {
      el.dataset.baseTransform = el.style.transform || '';
    }
    const base = el.dataset.baseTransform;
    const tx = (t.x || 0) + 'px';
    const ty = (t.y || 0) + 'px';
    const rot = (t.rotation || 0) + 'deg';
    const sc = t.scale || 1;
    const editor = 'translate(' + tx + ', ' + ty + ') rotate(' + rot + ') scale(' + sc + ')';
    el.style.transform = (base ? base + ' ' : '') + editor;
    el.style.transformOrigin = 'center center';
  }

  function applyColor(el, color) {
    if (!color) return;
    el.style.color = color;
  }

  function applyZIndex(el, z) {
    if (z === null || z === undefined || z === '') return;
    const n = parseInt(z, 10);
    if (!isNaN(n)) el.style.zIndex = n;
  }

  function captureBBox(el) {
    if (!el || !el.getBoundingClientRect) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
  }

  function snapshot() {
    const items = [];
    Object.keys(layerState).forEach(function (id) {
      const s = layerState[id];
      if (!s.el) return;
      items.push({
        id: id,
        bbox: captureBBox(s.el),
        transform: { x: s.x || 0, y: s.y || 0, rotation: s.rotation || 0, scale: s.scale || 1 },
        z: s.el.style.zIndex || window.getComputedStyle(s.el).zIndex || 'auto',
        color: s.el.style.color || null,
      });
    });
    return items;
  }

  function postToParent(msg) {
    if (window.parent && window.parent !== window) {
      try { window.parent.postMessage(msg, '*'); } catch (e) { /* ignore */ }
    }
  }

  function handleParentMessage(ev) {
    const data = ev && ev.data;
    if (!data || typeof data !== 'object' || !data.type) return;
    if (data.type === 'editor:transform' && data.layer) {
      const s = layerState[data.layer];
      if (!s || !s.el) return;
      if (typeof data.x === 'number') s.x = data.x;
      if (typeof data.y === 'number') s.y = data.y;
      if (typeof data.rotation === 'number') s.rotation = data.rotation;
      if (typeof data.scale === 'number') s.scale = data.scale;
      applyTransform(s.el, s);
    } else if (data.type === 'editor:set_param' && data.key) {
      const el = findLayerEl(data.key);
      if (el && typeof data.value === 'string') {
        if (el.tagName === 'IMG') {
          el.src = data.value;
        } else if (data.key === 'hero') {
          // Hero é div com background-image — Boldy injecta data URL para evitar CORS
          el.style.backgroundImage = 'url("' + data.value + '")';
        } else {
          el.textContent = data.value;
        }
      }
    } else if (data.type === 'editor:set_hero' && typeof data.dataUrl === 'string') {
      const heroEl = findLayerEl('hero');
      if (heroEl) heroEl.style.backgroundImage = 'url("' + data.dataUrl + '")';
    } else if (data.type === 'editor:request_state') {
      postToParent({ type: 'editor:state', layers: snapshot() });
    }
  }

  window.applyEditor = function applyEditor(opts) {
    const p = opts.p;
    const layers = opts.layers || [];

    layers.forEach(function (layerId) {
      const el = findLayerEl(layerId);
      if (!el) {
        // Aviso silencioso — alguns templates podem não ter todos os layers
        return;
      }
      // Garantir data-layer no DOM (caso template ainda não tenha)
      if (!el.dataset.layer) el.dataset.layer = layerId;

      const t = {
        el: el,
        x: num(p, layerId + '_x', 0),
        y: num(p, layerId + '_y', 0),
        rotation: num(p, layerId + '_rotation', 0),
        scale: num(p, layerId + '_scale', 1),
      };
      layerState[layerId] = t;

      // Color (text layers)
      const color = p.get(layerId + '_color');
      if (color) applyColor(el, color);

      // Z-index
      const z = p.get('z_' + layerId);
      if (z !== null && z !== '') applyZIndex(el, z);

      // Transform — só aplica se houver mexidela do default
      const hasOffset = t.x !== 0 || t.y !== 0 || t.rotation !== 0 || (t.scale !== 1 && t.scale !== 1.0);
      if (hasOffset) applyTransform(el, t);
    });

    // Listener para o parent (Boldy)
    window.addEventListener('message', handleParentMessage, false);

    // Esperar próximo tick para que layout esteja estável antes de capturar bboxes
    setTimeout(function () {
      postToParent({ type: 'editor:ready', layers: snapshot() });
    }, 50);
  };

  // Helper para uso em consola / debug
  window.__editorState = function () { return snapshot(); };
})();
