"""
orchestrator/isolate.py · Subject isolation (background removal).

Devolve uma versão do hero com fundo transparente (PNG com alpha channel),
para usar em famílias onde o subject deve aparecer EM CIMA do type/colour
(F06 Type-as-Subject, F09 Negative Space Float, F10 Circular Frame).

Pipeline:
  1. rembg local (U-2-Net) — primário, free, ~3-5s
  2. Gemini 2.5 Flash Image — fallback se rembg falhar / não estiver instalado

Uso:
    from isolate import maybe_isolate

    iso_path = maybe_isolate(
        source_path=Path("/path/to/hero.png"),
        out_dir=run_dir,
        gemini_key=os.environ.get("GEMINI_API_KEY"),
        family="F06",  # se família não precisa, devolve source
    )
"""

import base64
import json
import os
from pathlib import Path

# rembg é optional — se não estiver instalado, fallback automático para Gemini
try:
    from rembg import remove as rembg_remove
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import requests
except ImportError:
    requests = None


# Famílias que precisam de subject isolado (PNG com alpha)
ISOLATE_FAMILIES = {"F06", "F09", "F10"}


def _log(msg):
    print(f"[ISOLATE] {msg}", flush=True)


def _isolate_via_rembg(source_path, out_path):
    """rembg local — devolve True se OK."""
    if not HAS_REMBG:
        _log("rembg não instalado (`pip3 install rembg`) — skip")
        return False
    try:
        with open(source_path, "rb") as f:
            input_bytes = f.read()
        _log(f"rembg processing {source_path.name} ({len(input_bytes)//1024}KB)...")
        output_bytes = rembg_remove(input_bytes)
        with open(out_path, "wb") as f:
            f.write(output_bytes)
        _log(f"rembg OK · output {len(output_bytes)//1024}KB · {out_path.name}")
        return True
    except Exception as e:
        _log(f"rembg falhou: {e}")
        return False


def _isolate_via_gemini(source_path, out_path, api_key):
    """Gemini fallback — usa o mesmo modelo que outpaint mas com prompt de bg removal."""
    if not api_key or requests is None:
        _log("Gemini key ausente ou requests não instalado — skip fallback")
        return False
    if not HAS_PIL:
        return False

    # Reuso do mesmo modelo + cache de outpaint
    try:
        from outpaint import GEMINI_MODELS, GEMINI_URL_TEMPLATE, _WORKING_MODEL
    except ImportError:
        GEMINI_MODELS = ["gemini-2.5-flash-image", "gemini-2.5-flash-image-preview"]
        GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        _WORKING_MODEL = None

    import io
    with Image.open(source_path) as img:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")

    prompt = (
        "Remove the background of this photograph completely. Preserve the main subject "
        "(food, drink, glass, hand holding the subject if present) with crisp edges and "
        "all internal details intact. Output: PNG with transparent alpha channel where "
        "the background was. The subject must remain photographic, full quality, no "
        "stylisation. The transparent areas must be fully transparent (alpha=0), not "
        "white, not coloured. Edges must be clean — no halo, no fringe, no remnants of "
        "the original background colour."
    )

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": 0.2,  # baixa — queremos resultado consistente, não criativo
        }
    }

    candidates = list(GEMINI_MODELS)
    if _WORKING_MODEL and _WORKING_MODEL in candidates:
        candidates.remove(_WORKING_MODEL)
        candidates.insert(0, _WORKING_MODEL)

    for model in candidates:
        url = GEMINI_URL_TEMPLATE.format(model=model)
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        try:
            _log(f"Gemini bg removal · trying {model}")
            r = requests.post(url, headers=headers, json=body, timeout=90)
            if not r.ok:
                err = ""
                try:
                    err = r.json().get("error", {}).get("message", r.text[:120])
                except Exception:
                    err = r.text[:120]
                _log(f"  {r.status_code}: {err[:100]} · próximo")
                continue
            data = r.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    img_bytes = base64.b64decode(inline["data"])
                    out_path.write_bytes(img_bytes)
                    _log(f"Gemini OK · {len(img_bytes)//1024}KB")
                    return True
            _log("Gemini sem inline_data · próximo")
        except Exception as e:
            _log(f"Gemini erro {e} · próximo")
            continue

    _log("Todos os modelos Gemini falharam")
    return False


def _validate_isolation(out_path):
    """Verifica que o resultado tem alpha channel funcional. Devolve True se OK."""
    if not HAS_PIL:
        return True  # não conseguimos verificar, assumir OK
    try:
        with Image.open(out_path) as im:
            if im.mode not in ("RGBA", "LA"):
                _log(f"WARN output não tem alpha channel (mode={im.mode})")
                return False
            # Verificar que pelo menos 5% dos pixels são transparentes
            if im.mode == "RGBA":
                alpha = im.split()[3]
                pixels = list(alpha.getdata())
                transparent_count = sum(1 for p in pixels if p < 30)
                pct = transparent_count / max(1, len(pixels))
                _log(f"Alpha validation · {pct*100:.1f}% transparent pixels")
                if pct < 0.05:
                    _log("WARN <5% transparent — bg removal may have failed")
                    return False
            return True
    except Exception as e:
        _log(f"Validation error: {e}")
        return True  # don't reject on validator failure


def maybe_isolate(source_path, out_dir, gemini_key=None, family=None, force=False):
    """Isolate subject conditionally based on family.

    Args:
        source_path (Path): hero original
        out_dir (Path): onde gravar o output isolado
        gemini_key (str|None): API key para fallback
        family (str|None): F01..F10. Se ∉ ISOLATE_FAMILIES, devolve source unless force.
        force (bool): forçar isolation independentemente da family

    Returns:
        Path: hero a usar (source ou novo isolated PNG)
    """
    source_path = Path(source_path)
    out_dir = Path(out_dir)

    if not force and family not in ISOLATE_FAMILIES:
        _log(f"Family {family} não requer isolation — usar source")
        return source_path

    if not source_path.exists():
        _log(f"Source não existe: {source_path}")
        return source_path

    out_path = out_dir / f"{source_path.stem}.isolated.png"

    # Try rembg first (free, local)
    if _isolate_via_rembg(source_path, out_path):
        if _validate_isolation(out_path):
            return out_path
        _log("rembg result failed validation — tentar Gemini fallback")

    # Fallback to Gemini
    if gemini_key:
        if _isolate_via_gemini(source_path, out_path, gemini_key):
            if _validate_isolation(out_path):
                return out_path

    _log("Isolation falhou — fallback para source (subject vai ter bg rectangular)")
    return source_path
