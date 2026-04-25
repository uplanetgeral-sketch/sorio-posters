// _shared/branding.js · Logo + selo positioning helpers usados em todos os templates F01-F10.
//
// Para usar num template:
//   1. Garante que existem #logo e #selo no DOM
//   2. No fim do script <script>, chama:
//        applyBranding({ logo, selo, canvasW, canvasH, heightScale, widthScale, p });
//      onde `p` é o URLSearchParams.
//
// Esta lib NÃO é importada via <script src="..."> — é colada inline em cada template.
// (Cloudflare Pages serve estáticos, não há bundler. Inline garante zero round-trip.)
//
// PARAMS lidos do URL:
//   logo_position: 'top-left' (default) | 'top-center' | 'top-right' | 'center-top' | 'inline-block'
//   logo_scale: 0.6..1.4, default 1.0
//   selo_position: 'top-right' (default) | 'top-left' | 'top-center' | 'bottom-right' |
//                  'bottom-left' | 'inline-stamp' | 'over-hero' | 'hidden'
//   selo_scale: 0.5..1.6, default 1.0
//
// Compatibilidade backwards: se o template já posicionou logo/selo manualmente E não há
// override no URL, applyBranding() não toca. Só override quando user/Decisor pede.

function applyBranding(opts) {
  const { canvasW, canvasH, heightScale, widthScale, p, logo, selo } = opts;

  const logoEl = document.getElementById('logo');
  const seloEl = document.getElementById('selo');
  if (!logoEl || !seloEl) return;

  const logoPos = p.get('logo_position');     // null se não passado
  const seloPos = p.get('selo_position');
  const logoScale = parseFloat(p.get('logo_scale')) || 1.0;
  const seloScale = parseFloat(p.get('selo_scale')) || 1.0;

  const sideMargin = Math.round(60 * widthScale);
  const topMargin = Math.round(60 * heightScale);

  // Logo
  if (logo) logoEl.src = logo;
  const baseLogoW = 160 * heightScale * logoScale;
  logoEl.style.width = Math.round(baseLogoW) + 'px';

  if (logoPos) {
    // Reset all position properties first
    logoEl.style.left = ''; logoEl.style.right = ''; logoEl.style.top = ''; logoEl.style.bottom = '';
    logoEl.style.transform = '';
    if (logoPos === 'top-center' || logoPos === 'center-top') {
      logoEl.style.top = topMargin + 'px';
      logoEl.style.left = '50%';
      logoEl.style.transform = 'translateX(-50%)';
    } else if (logoPos === 'top-right') {
      logoEl.style.top = topMargin + 'px';
      logoEl.style.right = sideMargin + 'px';
    } else if (logoPos === 'bottom-left') {
      logoEl.style.bottom = topMargin + 'px';
      logoEl.style.left = sideMargin + 'px';
    } else if (logoPos === 'bottom-right') {
      logoEl.style.bottom = topMargin + 'px';
      logoEl.style.right = sideMargin + 'px';
    } else if (logoPos === 'hidden') {
      logoEl.classList.add('hidden');
    } else {
      // top-left default
      logoEl.style.top = topMargin + 'px';
      logoEl.style.left = sideMargin + 'px';
    }
  }

  // Selo
  if (selo) seloEl.src = selo;
  const baseSeloSize = 170 * heightScale * seloScale;
  seloEl.style.width = Math.round(baseSeloSize) + 'px';
  seloEl.style.height = Math.round(baseSeloSize) + 'px';

  if (seloPos) {
    seloEl.style.left = ''; seloEl.style.right = ''; seloEl.style.top = ''; seloEl.style.bottom = '';
    seloEl.style.transform = '';
    if (seloPos === 'top-left') {
      seloEl.style.top = topMargin + 'px';
      seloEl.style.left = sideMargin + 'px';
    } else if (seloPos === 'top-center') {
      seloEl.style.top = topMargin + 'px';
      seloEl.style.left = '50%';
      seloEl.style.transform = 'translateX(-50%)';
    } else if (seloPos === 'bottom-right') {
      seloEl.style.bottom = Math.round(topMargin * 1.5) + 'px';
      seloEl.style.right = sideMargin + 'px';
    } else if (seloPos === 'bottom-left') {
      seloEl.style.bottom = Math.round(topMargin * 1.5) + 'px';
      seloEl.style.left = sideMargin + 'px';
    } else if (seloPos === 'over-hero') {
      // Selo grande over hero center as cover-style stamp
      seloEl.style.top = '50%';
      seloEl.style.left = '50%';
      seloEl.style.transform = 'translate(-50%, -50%)';
      // override scale for over-hero — usually larger
      const overSize = 280 * heightScale * seloScale;
      seloEl.style.width = Math.round(overSize) + 'px';
      seloEl.style.height = Math.round(overSize) + 'px';
    } else if (seloPos === 'hidden') {
      seloEl.classList.add('hidden');
    } else {
      // top-right default
      seloEl.style.top = topMargin + 'px';
      seloEl.style.right = sideMargin + 'px';
    }
  }
}
