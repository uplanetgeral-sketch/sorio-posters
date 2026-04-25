"""
orchestrator/outpaint.py · Hero outpainting condicional via Gemini 2.5 Flash Image.

Quando o aspect ratio do hero source difere significativamente do format target
(ex: 1:1 → 9:16), o cover-crop produz resultados maus. Esta lib chama o Gemini
para outpaint inteligente: pre-compõe um canvas target-size com o source centrado
em padding off-white, e pede ao modelo para preencher as zonas vazias com
extensão coerente da cena.

Uso:
    from outpaint import maybe_outpaint, ASPECT_DELTA_THRESHOLD

    new_hero_path = maybe_outpaint(
        source_path=Path("/path/to/hero.png"),
        target_format="1080x1920",
        out_dir=run_dir,
        api_key=os.environ.get("GEMINI_API_KEY"),
        hint="Só Rio · river beach lounge · ribatejo riverside food",
    )
    # devolve o source original se delta < threshold ou api_key vazia
"""

import base64
import json
import os
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import requests
except ImportError:
    requests = None


# Cadeia de fallback de modelos Gemini com image generation.
# Diferentes contas / regiões / fases de rollout têm acesso a nomes diferentes.
# Tentamos em ordem do mais novo para o mais antigo até um devolver 200.
GEMINI_MODELS = [
    "gemini-2.5-flash-image",                    # GA (nome canónico, aka "Nano Banana")
    "gemini-2.5-flash-image-preview",            # nome alternativo em algumas docs
    "gemini-2.0-flash-preview-image-generation", # preview anterior
    "gemini-2.0-flash-exp-image-generation",     # experimental anterior
    "gemini-2.0-flash-exp",                      # experimental fallback
]
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Cache do modelo que funcionou (evita refazer fallback chain todas as chamadas)
_WORKING_MODEL = None

# Threshold em delta de aspect ratio (h/w). Se |src_aspect - target_aspect| > este valor,
# chama o outpaint. Defaults:
#   1:1 (1.00) ↔ 4:5 (1.25) · delta 0.25 — borderline, NÃO accionar (cover-crop OK)
#   1:1 (1.00) ↔ 9:16 (1.78) · delta 0.78 — accionar
#   4:5 (1.25) ↔ 9:16 (1.78) · delta 0.53 — accionar
ASPECT_DELTA_THRESHOLD = 0.30


def _log(msg):
    print(f"[OUTPAINT] {msg}", flush=True)


def get_image_dimensions(path):
    """Devolve (width, height) de PNG/JPEG/WebP. Requer PIL."""
    if not HAS_PIL:
        raise RuntimeError("PIL não instalado. `pip3 install Pillow`")
    with Image.open(path) as img:
        return img.size  # (w, h)


def parse_format(fmt_str):
    """'1080x1920' → (1080, 1920)."""
    w, h = fmt_str.lower().split("x")
    return int(w), int(h)


def aspect_delta(src_w, src_h, target_w, target_h):
    """Devolve |src_aspect - target_aspect| onde aspect = h/w."""
    src_aspect = src_h / src_w
    target_aspect = target_h / target_w
    return abs(src_aspect - target_aspect)


def _compose_canvas(source_path, target_w, target_h):
    """Pre-compõe canvas target-size com source centrado, padding em off-white SO RIO.
    Devolve PIL.Image."""
    src = Image.open(source_path).convert("RGB")
    src_w, src_h = src.size

    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        # Source mais largo que target → fit width, padding top/bottom
        new_w = target_w
        new_h = int(round(target_w / src_ratio))
    else:
        # Source mais alto que target → fit height, padding left/right
        new_h = target_h
        new_w = int(round(target_h * src_ratio))

    src_resized = src.resize((new_w, new_h), Image.LANCZOS)

    # Off-white SO RIO (#F6F1E7) — neutral, easy for Gemini to recognise as "fill this"
    canvas = Image.new("RGB", (target_w, target_h), (246, 241, 231))
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(src_resized, (paste_x, paste_y))

    pad_position = "top and bottom" if paste_y > 0 else "left and right"
    pad_pct = round(((target_h - new_h) if paste_y > 0 else (target_w - new_w)) / max(target_h, target_w) * 100)
    return canvas, pad_position, pad_pct


def _call_gemini_with_model(model, body, api_key, timeout):
    """Single attempt against a specific model name. Levanta RuntimeError com info útil."""
    url = GEMINI_URL_TEMPLATE.format(model=model)
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    if not r.ok:
        try:
            err_obj = r.json().get("error", {})
            err_msg = err_obj.get("message", r.text[:200])
            err_status = err_obj.get("status", "")
        except Exception:
            err_msg = r.text[:200]
            err_status = ""
        raise RuntimeError(f"{r.status_code} {err_status}: {err_msg}")

    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        # Pode ser blocked por safety, ou modelo não devolveu nada
        prompt_feedback = data.get("promptFeedback", {})
        block_reason = prompt_feedback.get("blockReason", "unknown")
        raise RuntimeError(f"sem candidates · blockReason={block_reason} · {json.dumps(data)[:200]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    finish_reason = candidates[0].get("finishReason", "?")
    raise RuntimeError(f"sem inline_data · finishReason={finish_reason} · parts={json.dumps(parts)[:200]}")


def _call_gemini(canvas_image, prompt, api_key, timeout=90):
    """POST para Gemini com cadeia de fallback de modelos.
    Devolve bytes da imagem gerada. Cacheia o modelo que funcionou."""
    global _WORKING_MODEL

    if requests is None:
        raise RuntimeError("requests não instalado. `pip3 install requests`")

    # Encode canvas as PNG bytes → base64
    import io
    buf = io.BytesIO()
    canvas_image.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": 0.35,
        }
    }

    # Se já temos um modelo que funcionou previamente, tenta-o primeiro
    candidates = list(GEMINI_MODELS)
    if _WORKING_MODEL and _WORKING_MODEL in candidates:
        candidates.remove(_WORKING_MODEL)
        candidates.insert(0, _WORKING_MODEL)

    last_err = None
    for model in candidates:
        try:
            _log(f"trying model: {model}")
            result = _call_gemini_with_model(model, body, api_key, timeout)
            _WORKING_MODEL = model
            _log(f"model OK: {model}")
            return result
        except RuntimeError as e:
            last_err = e
            err_str = str(e)
            # Se 404 / not found → próximo modelo. Outros erros (403/quota/safety) → não vale a pena tentar mais.
            if "404" in err_str or "not found" in err_str.lower() or "is not supported" in err_str.lower():
                _log(f"  → {err_str[:120]} · próximo")
                continue
            # Outro tipo de erro — propagar imediatamente
            raise

    raise RuntimeError(f"Todos os modelos Gemini falharam. Último erro: {last_err}")


# Famílias que usam cover-crop nativo no hero element e NÃO beneficiam de outpaint.
# Em split layouts (F03) ou grid layouts (F05a/b), o hero element já tem aspect próprio
# que cover-crop preenche sem deixar margens. Outpaint nestes casos só rouba protagonismo
# ao subject ao adicionar extensão fotográfica que compete visualmente.
NO_OUTPAINT_FAMILIES = {"F03", "F05a", "F05b"}


def maybe_outpaint(source_path, target_format, out_dir, api_key, hint="", family=None):
    """Outpaint condicional. Devolve Path para hero (novo se outpaintou, source se não).

    Args:
        source_path (Path): hero original
        target_format (str): "WxH" do format final
        out_dir (Path): onde gravar o outpaint result
        api_key (str|None): GEMINI_API_KEY (se None ou vazio → no-op)
        hint (str): contexto extra para o prompt (ex: "ribatejo riverside · só rio")
        family (str|None): F01/F02/F03/F05a/F05b. Se for split/grid family (F03/F05a/F05b),
            outpaint é skip — essas famílias têm cover-crop nativo e outpaint reduz
            protagonismo do subject.

    Returns:
        Path: hero a usar (source ou novo outpainted)
    """
    source_path = Path(source_path)
    out_dir = Path(out_dir)

    # Skip outpaint para famílias com layout próprio (split/grid)
    if family in NO_OUTPAINT_FAMILIES:
        _log(f"Family {family} usa cover-crop nativo — skip outpaint (mantém subject protagonista)")
        return source_path

    if not api_key:
        _log("GEMINI_API_KEY ausente — skip outpaint, usar source com cover-crop")
        return source_path

    if not HAS_PIL:
        _log("PIL ausente (`pip3 install Pillow`) — skip outpaint")
        return source_path

    try:
        target_w, target_h = parse_format(target_format)
    except Exception as e:
        _log(f"Format inválido '{target_format}' — skip · {e}")
        return source_path

    try:
        src_w, src_h = get_image_dimensions(source_path)
    except Exception as e:
        _log(f"Não consegui ler dimensões '{source_path}' — skip · {e}")
        return source_path

    delta = aspect_delta(src_w, src_h, target_w, target_h)
    src_aspect = round(src_h / src_w, 2)
    tgt_aspect = round(target_h / target_w, 2)

    if delta < ASPECT_DELTA_THRESHOLD:
        _log(f"Source {src_w}×{src_h} (aspect {src_aspect}) ≈ target {target_w}×{target_h} (aspect {tgt_aspect}) · delta {delta:.2f} < {ASPECT_DELTA_THRESHOLD} — cover-crop chega, skip")
        return source_path

    _log(f"Source {src_w}×{src_h} (aspect {src_aspect}) ↔ target {target_w}×{target_h} (aspect {tgt_aspect}) · delta {delta:.2f} ≥ threshold — accionar outpaint")

    try:
        canvas_img, pad_position, pad_pct = _compose_canvas(source_path, target_w, target_h)
        _log(f"Canvas composto · padding {pad_position} (~{pad_pct}%)")
    except Exception as e:
        _log(f"ERRO compor canvas — skip · {e}")
        return source_path

    # Save canvas (debug + fallback se Gemini falhar)
    canvas_path = out_dir / f"{source_path.stem}.canvas.png"
    canvas_img.save(canvas_path)

    prompt = (
        f"You are a professional photo retoucher specialised in seamless image extension. "
        f"The image is a {target_w}×{target_h} canvas containing a real photograph centred in it, with off-white "
        f"({{R:246,G:241,B:231}}) empty padding margins on the {pad_position} (~{pad_pct}% of the canvas total). "
        f"Your task: REPLACE the off-white padding with a natural continuation of the photograph, producing a single "
        f"unified {target_w}×{target_h} photograph at the SAME resolution. The off-white is NOT part of the scene — "
        f"it is empty space to be filled.\n\n"
        f"NON-NEGOTIABLE CONSTRAINTS:\n"
        f"1. PRESERVATION — the centred photographed area must remain pixel-identical. Do not re-render, re-stylise, "
        f"or modify the dish, glassware, plating, props, or composition that exists in the source. The subject in the "
        f"middle is locked.\n"
        f"2. SEAMLESS SURFACE CONTINUITY — the surface beneath the subject (table, plate, deck, fabric) must extend "
        f"WITHOUT abrupt transitions. No hard horizontal or vertical seams between original and extended areas. The "
        f"wood grain, fabric weave, marble veining, or whatever surface is present must flow continuously into the "
        f"new region, with the SAME material, the SAME shade, the SAME texture density.\n"
        f"3. LIGHTING COHERENCE — light direction, colour temperature, intensity, shadow softness, and highlight "
        f"placement must continue exactly. No new light sources. No change in time-of-day mood. Shadows that exist "
        f"in the source must extend naturally into the new region following the same angle.\n"
        f"4. NO INVENTED SUBJECTS — do not introduce new dishes, glasses, hands, plates, faces, text, logos, or props "
        f"in the extended area. Only continue ambient context: more of the same table surface, edge of a napkin, "
        f"another out-of-focus herb sprig, additional grain/texture of the existing material, atmospheric depth.\n"
        f"5. NO STYLE SHIFT — the extended area must look like it was captured with the same camera, lens, depth-of-"
        f"field, and post-processing. Photographic, not illustrated. Same noise/grain pattern.\n"
        f"6. NO COLOUR DRIFT — match the dominant colour palette of the source. Do not introduce hues that aren't "
        f"already present in the photographed area.\n"
        f"7. OUTPUT — single unified photograph, exact {target_w}×{target_h} dimensions, no off-white residue, no "
        f"visible seams, no fade transitions."
    )
    if hint:
        prompt += f"\n\nScene context: {hint}\n"
        prompt += f"This context is for understanding the brand/setting only — do NOT add elements from the context "
        f"into the extended area. Stick rigorously to continuing what is photographed in the source."

    try:
        img_bytes = _call_gemini(canvas_img, prompt, api_key)
    except Exception as e:
        _log(f"Gemini falhou — fallback para source · {e}")
        return source_path

    # Save outpainted result
    out_path = out_dir / f"{source_path.stem}.outpainted.png"
    out_path.write_bytes(img_bytes)

    # Verify output dimensions, resize if model returned different size
    try:
        out_w, out_h = get_image_dimensions(out_path)
        if (out_w, out_h) != (target_w, target_h):
            _log(f"Gemini devolveu {out_w}×{out_h} ≠ target {target_w}×{target_h} · resize")
            with Image.open(out_path) as im:
                im_resized = im.resize((target_w, target_h), Image.LANCZOS)
                im_resized.save(out_path)
    except Exception as e:
        _log(f"WARN ao normalizar dimensões: {e}")

    # === EDGE VALIDATION ===
    # Verifica se o Gemini deixou padding off-white residual nas bordas.
    # Off-white target: rgb(246, 241, 231) com tolerância ±15.
    # Se >12% dos pixels nas bandas das bordas (5% top + 5% bottom + 5% sides) estão
    # dentro da tolerância off-white, o outpaint falhou — fallback para source.
    try:
        with Image.open(out_path) as im:
            im_rgb = im.convert("RGB")
            iw, ih = im_rgb.size
            edge_pct = 0.05  # 5% de cada lado
            band_top = max(1, int(ih * edge_pct))
            band_side = max(1, int(iw * edge_pct))

            # Sample edges (top band, bottom band, left band, right band)
            samples = []
            samples.append(im_rgb.crop((0, 0, iw, band_top)))           # top
            samples.append(im_rgb.crop((0, ih - band_top, iw, ih)))      # bottom
            samples.append(im_rgb.crop((0, 0, band_side, ih)))           # left
            samples.append(im_rgb.crop((iw - band_side, 0, iw, ih)))     # right

            target_r, target_g, target_b = 246, 241, 231
            tol = 15  # ±15 em cada canal
            offwhite_count = 0
            total_count = 0
            for s in samples:
                pixels = list(s.getdata())
                total_count += len(pixels)
                for r, g, b in pixels:
                    if (abs(r - target_r) <= tol and
                            abs(g - target_g) <= tol and
                            abs(b - target_b) <= tol):
                        offwhite_count += 1

            offwhite_ratio = offwhite_count / max(1, total_count)
            _log(f"Edge validation · off-white residual {offwhite_ratio*100:.1f}% (threshold 12%)")

            if offwhite_ratio > 0.12:
                _log(f"FAIL · Gemini deixou off-white residual nas bordas · fallback para source com cover-crop")
                # Renomear o resultado falhado para ficar como audit trail mas devolver source
                failed_path = out_dir / f"{source_path.stem}.outpainted.FAILED.png"
                out_path.rename(failed_path)
                return source_path
    except Exception as e:
        _log(f"WARN edge validation crashed: {e} · usar resultado mesmo assim")

    _log(f"Outpaint concluído · {out_path}")
    return out_path
