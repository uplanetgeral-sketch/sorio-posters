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
    } else if (data.type === 'editor:disable_overlay_mode') {
      // Captura: re-aplica clipping/overflow para mostrar versão FINAL renderizada
      _restoreClippingForCapture();
    } else if (data.type === 'editor:enable_overlay_mode') {
      // Volta a desactivar clipping para o user continuar a editar com hero inteiro
      _stripClippingForEditorMode();
    }
  }

  // Guarda os styles originais antes de stripar — para podermos restaurar depois.
  var _originalClippingStyles = new Map();

  function _stripClippingForEditorMode() {
    // Estratégia mais agressiva — apanha qualquer elemento com clip-path,
    // mask, ou overflow:hidden, independente do tamanho.
    var allEls = document.querySelectorAll('*');
    allEls.forEach(function (el) {
      var style = window.getComputedStyle(el);
      var hasClip = style.clipPath && style.clipPath !== 'none' && style.clipPath !== 'normal';
      var hasMask = style.mask && style.mask !== 'none' && style.mask !== 'normal';
      var hasOverflow = (style.overflow === 'hidden' || style.overflowX === 'hidden' || style.overflowY === 'hidden');
      if (hasClip || hasMask || hasOverflow) {
        if (!_originalClippingStyles.has(el)) {
          _originalClippingStyles.set(el, {
            clipPath: el.style.clipPath,
            webkitClipPath: el.style.webkitClipPath,
            mask: el.style.mask,
            overflow: el.style.overflow,
            overflowX: el.style.overflowX,
            overflowY: el.style.overflowY,
          });
        }
        if (hasClip) { el.style.clipPath = 'none'; el.style.webkitClipPath = 'none'; }
        if (hasMask) { el.style.mask = 'none'; }
        if (hasOverflow) { el.style.overflow = 'visible'; el.style.overflowX = 'visible'; el.style.overflowY = 'visible'; }
      }
    });
    document.documentElement.classList.add('editor-mode');
  }

  function _restoreClippingForCapture() {
    _originalClippingStyles.forEach(function (orig, el) {
      el.style.clipPath = orig.clipPath || '';
      el.style.webkitClipPath = orig.webkitClipPath || '';
      el.style.mask = orig.mask || '';
      el.style.overflow = orig.overflow || '';
      el.style.overflowX = orig.overflowX || '';
      el.style.overflowY = orig.overflowY || '';
    });
    document.documentElement.classList.remove('editor-mode');
    // Não limpa _originalClippingStyles — assim podemos re-aplicar editor mode depois
  }

  window.applyEditor = function applyEditor(opts) {
    const p = opts.p;
    const layers = opts.layers || [];

    // Editor mode flag — quando carregado com `?editor_mode=1`, desactiva
    // clipping/overflow para o user ver hero INTEIRO. Ver _stripClippingForEditorMode().
    // Aplicação é feita após paint (setTimeout 0) para apanhar styles inline
    // setados pelo template script.
    if (p.get('editor_mode') === '1') {
      setTimeout(_stripClippingForEditorMode, 0);
    }

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

    // Esperar bboxes válidos: todas as <img> dos layers têm de estar `.complete`,
    // e fonts ready (para text layers calcularem altura correctamente).
    // Sem isto, o snapshot é capturado com height=0 nas imgs ainda a carregar
    // (problema clássico: logo/selo não-clicáveis no editor).
    var imgEls = layers
      .map(findLayerEl)
      .filter(function (el) { return el && el.tagName === 'IMG'; });
    var pImgs = imgEls.map(function (img) {
      if (img.complete && img.naturalWidth > 0) return Promise.resolve();
      return new Promise(function (resolve) {
        img.addEventListener('load', resolve, { once: true });
        img.addEventListener('error', resolve, { once: true });
        // Safety timeout — mesmo que a img falhe, não bloquear o editor
        setTimeout(resolve, 1500);
      });
    });
    var pFonts = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();

    Promise.all([Promise.all(pImgs), pFonts]).then(function () {
      // Esperar 1 raf adicional para layout estabilizar
      requestAnimationFrame(function () {
        postToParent({ type: 'editor:ready', layers: snapshot() });
      });
    });
  };

  // Helper para uso em consola / debug
  window.__editorState = function () { return snapshot(); };
})();
