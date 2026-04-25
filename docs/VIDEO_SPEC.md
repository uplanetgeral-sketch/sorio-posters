# Boldy v3 · Video Pipeline Spec

**Status:** Backlog · scoped & ready to build após Boldy v2 image stack estabilizada
**Estimated effort:** ~28-32h distribuído em 4-5 sessões

---

## Visão geral

Estender o pipeline Boldy de imagem para vídeo curto (≤15s) com graphics integrados. Mesma filosofia: backend self-hosted, Decisor + Critic em loop, output publishable directo.

**End-to-end:**
```
Source video (MP4 ≤15s) ─┐
                         │
                         ▼
                  ffmpeg scene detection
                         │
                         ▼
                  Frames-chave (5-10 PNGs)
                         │
                         ▼
                  Vision Analyst (timeline mode) ──→ video_analysis.json
                         │
                         ▼
                  Decisor (video mode)
                  · WHEN: timestamp inicial + duration de cada elemento
                  · WHERE: safe-zone + alignment
                  · WHAT: animation preset por elemento
                         │
                         ▼
                  HTML template animado (Playwright @ 30fps)
                  → 450 PNGs com alpha (15s × 30fps)
                         │
                         ▼
                  ffmpeg overlay
                  · source video + PNG sequence
                  · preserve audio
                         │
                         ▼
                  output.mp4 H.264 1080p · publishable
```

---

## Fase 3.1 · Frame extraction + Vision timeline

### ffmpeg scene detection
```bash
ffmpeg -i source.mp4 -vf "select='gt(scene,0.4)',showinfo" \
  -vsync vfr frames/frame_%04d.png 2>&1 | grep showinfo
```

Output: 5-10 frames PNG nos cortes/zooms/transições visuais. Plus 1 frame por cada 2s sem cuts (fallback para "pull-back" gradual sem cut).

### Vision Analyst Video Mode

System prompt expandido em `critique/system_prompt_video.md`:
```
You are the Vision Analyst (Video). Receive 5-10 frames from a ≤15s video.
Output a JSON timeline:
{
  "duration_estimated_s": 14.5,
  "frames": [
    {"t_estimated": 0.0, "composition": "...", "graphics_safe_zone": "bottom-third"},
    {"t_estimated": 3.2, "composition": "...", "graphics_safe_zone": "n/a"},
    ...
  ],
  "still_windows": [
    {"start": 11.5, "end": 14.5, "composition": "stable wide", "graphics_safe_zone": "centre"}
  ],
  "dominant_palette": ["..."],
  "lighting_arc": "...",
  "best_graphic_window": {"start": 11.5, "end": 14.5}
}
```

**still_windows** = períodos onde câmara é estável + composição não muda. Esses são os melhores momentos para overlay graphics (não baralha o olhar).

### Decisor Video Mode

Inputs: product + timeline + best_graphic_window.

Output (estende output_schema.json com novos campos):
```json
{
  "video_overlay": {
    "start_at_s": 11.5,
    "end_at_s": 14.5,
    "elements": [
      {
        "param": "info_top",
        "value": "Maracujá · Lima · Cachaça · Mel",
        "appear_at_s": 11.7,
        "duration_s": 2.8,
        "animation": "fade-in",
        "exit_animation": "hold"
      },
      {
        "param": "title",
        "value": "Caipirinha de Maracujá",
        "appear_at_s": 12.0,
        "duration_s": 2.5,
        "animation": "stagger-words",
        "exit_animation": "fade-out"
      },
      ...
    ],
    "anchor_position": "bottom-center",
    "background_treatment": "subtle-darken-bottom-30pct"
  }
}
```

---

## Fase 3.2 · Template HTML animado

Templates `f02_video.html` etc. extendem os existentes com:

```css
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes staggerWord {
  /* applied to each <span> child of title */
}

.display-hero {
  opacity: 0;
  animation: fadeIn 0.8s ease-out var(--display-delay) forwards;
}
```

URL params per element:
```
&info_top_animation=fade-in
&info_top_delay=11.7
&info_top_duration=2.8
&display_animation=stagger-words
&display_delay=12.0
&display_duration=2.5
```

Playwright captura sequência:
```python
for frame_n in range(450):  # 15s * 30fps
    page.evaluate(f"document.body.style.animationDelay = '{frame_n/30}s'")
    page.screenshot(path=f"overlay_{frame_n:04d}.png", omit_background=True)
```

(Alternativa mais eficiente: usar `Page.startScreencast` + custom timing controlado via JS.)

---

## Fase 3.3 · ffmpeg compose

```bash
ffmpeg -i source.mp4 \
  -framerate 30 -i overlay_%04d.png \
  -filter_complex "[0:v][1:v]overlay=format=auto" \
  -c:v libx264 -crf 20 -preset slow -pix_fmt yuv420p \
  -c:a copy \
  -map_metadata 0 \
  output.mp4
```

Aspect ratio swap (1:1 ou 9:16):
```bash
# Crop + scale source antes de overlay
-vf "crop=ih*9/16:ih,scale=1080:1920" (9:16 vertical)
-vf "crop=ih:ih,scale=1080:1080"      (1:1 square)
```

---

## Fase 3.4 · Vision Critique para vídeo

Critique recebe **3 frames-chave do output**:
- Frame inicial overlay (t=11.5s)
- Frame mid overlay (t=13.0s)
- Frame final overlay (t=14.4s)

E avalia coerência da animação + composição em cada momento. Output schema same as image, com `video_violations` extra:

```json
{
  "video_violations": [
    {"id": "VID-01", "evidence": "Display aparece 2s antes do still window — sobreposição com motion"},
    {"id": "VID-02", "evidence": "Stagger demasiado rápido para o tom evening — recomendar 120ms entre palavras"}
  ]
}
```

---

## Animation Presets (5 curados)

1. **Fade** — `opacity 0→1`, 0.6s ease-out. Universal. Daily Drop default.
2. **Slide-up** — opacity + translateY(14px → 0), 0.7s cubic-bezier(0.2, 0.8, 0.2, 1). Editorial premium.
3. **Scale-in** — scale(0.96 → 1) + opacity, 0.6s ease-out. Subtilíssimo, premium.
4. **Stagger words** — palavra-por-palavra, 80ms delay entre cada. Editorial Kinfolk.
5. **Draw wave** — wave SVG faz `stroke-dashoffset` animation, 1.2s ease-in-out. Único Só Rio.

Decisor escolhe baseado em mood:
- evening_riverside → Slide-up (lento, contemplativo)
- aperitivo_18h → Fade (versátil)
- fresh_midday → Stagger (energético) ou Scale (clean)

---

## Custos esperados

| Operação | Custo |
|---|---|
| ffmpeg frame extract | ~0.5s, free |
| Vision Analyst video timeline (5-10 frames) | ~$0.05 |
| Decisor video mode | ~$0.02 |
| Playwright capture 450 PNGs | ~30-45s, free |
| ffmpeg compose final | ~5-15s, free |
| Vision Critique 3 keyframes | ~$0.02 |
| **TOTAL** | **~$0.10 + ~90-120s tempo** |

Cliente pode gerar 10 videos/dia por ~$1.00 em API costs.

---

## Dependencies novas

- `ffmpeg` (Homebrew: `brew install ffmpeg`) — uma vez
- `pillow` (já instalado para imagens — frame manipulation)

Sem novas deps Python além das já instaladas.

---

## Catálogo extension

`catalogue/produtos/<id>/videos/` folder pattern:
```
produtos/cloud_dance/videos/
├── source_15s_landscape.mp4
├── source_15s_landscape.json    ← timeline cached pelo Vision
└── outputs/
    ├── 20260601_120000.mp4      ← export Boldy v3
    └── ...
```

`product.json` extends with:
```json
{
  "videos": {
    "available": ["source_15s_landscape", "source_8s_close"],
    "default": "source_15s_landscape"
  }
}
```

---

## UI Boldy v3

Nova vista `Catalogue Video` ou estender `Catalogue` com toggle Image/Video:

- Cada produto tem dois modos: **Image** (Boldy v2) ou **Video** (Boldy v3)
- Drag-and-drop video file → starts pipeline
- Live progress: `[ITER 0] Frame extract · 6 frames · Vision timeline · Decisor · Render PNG seq · Compose MP4 · Critique`
- Preview MP4 player no Result panel
- Slider de animation timing: posso adiar/adiantar o WHEN do overlay
- Export: "Save as MP4" → `~/Movies/SoRio/cloud_dance_<date>.mp4`

---

## Quando arrancar

Recomendado: depois de Boldy v2 (image) estar usável diariamente — significa que tens consistentemente bons posters image-only saindo da Boldy. Provavelmente após 1-2 semanas de uso real.

Sinais de prontidão para v3:
- Boldy v2 corre stable, sem bugs no pipeline image
- Pelo menos 5+ produtos no catalogue com object_sheets + approved_heroes
- Tens apetite por experimentar com video sources reais (samples de Verão Sem Pressa shoots)

Tasks: #38 (Video v1), #39 (Animations + aspect ratios)
