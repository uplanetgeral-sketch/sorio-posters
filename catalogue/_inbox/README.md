# `_inbox/` · Drop zone para object sheets de produtos novos

Aqui é onde dropas object sheets PNG de produtos que ainda não estão no catálogo.

---

## Como usar

1. Cria object sheet do produto (via Boldy `Object Sheet` button OU Gemini directo com o prompt em `bolder-creative-studio/main.js`)
2. Arrasta o PNG para esta pasta `_inbox/`
3. **Renomeia** para o slug do produto: `caipirinha_maracuja.png`, `mojito.png`, `philly_cheesesteak.png`
4. **(Opcional)** cria `<slug>.txt` ao lado com 2-3 linhas de notas: contexto, intenção, anomalias
5. Próxima sessão Claude: dizer `processa o catalogue inbox`

Eu corro Claude Vision sobre cada object sheet, extraio:
- Ingredientes visíveis e provável composição
- Garnish inside vs outside
- Cores dominantes
- Lighting / mood inferido
- Subject position

Pergunto-te os campos editoriais que Vision não infere (mood preferido, selo recommendation, claims). Crio `produtos/<slug>/` completo. Tu validas no fim.

---

## Alternativa rápida (sem esperar sessão)

Corre tu o script:

```bash
cd /Users/goncalocarvoeirasimac/Desktop/CREATIVE\ STUDIO/CLIENTES/SO\ RIO/sorio-posters
python3 catalogue/_scripts/ingest_object_sheet.py catalogue/_inbox/<slug>.png
```

(Requer `pip install anthropic` + `ANTHROPIC_API_KEY` env var).

---

## O que NÃO meter aqui

- Heroes raw (sem grelha 2×3) — esses são `approved_heroes/` dentro do produto, não object sheets
- PNGs de outros clientes — se aparecer aqui, é provavelmente erro de drop
- Imagens > 5MB — comprimir antes (Boldy auto-comprime ao gerar)

---

## Object Sheet · estrutura esperada

Grelha 2×3 (6 cells totais):

```
┌──────────┬──────────┐
│ Cenital  │ 3/4 Front│   cells 1-2: ângulos
│ 0°       │ 35°      │
├──────────┼──────────┤
│ Side     │ High     │   cells 3-4: ângulos
│ 90°      │ 65°      │
├──────────┼──────────┤
│ Detail   │ Detail   │   cells 5-6: close-ups COM contexto
│ texture  │ context  │   (não ingredientes isolados em branco)
└──────────┴──────────┘
```

PNG ~1024×1536 px ideal. JPG aceite.
