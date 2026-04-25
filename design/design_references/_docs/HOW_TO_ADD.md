# Como adicionar uma referência · 3 caminhos

---

## Caminho 1 · Drop no `_inbox/` (recomendado)

**Quando usar:** dia-a-dia, quando vês algo bom no Pinterest / packaging / projecto teu e queres guardar sem fricção.

```
1. arrastar PNG/JPG → _inbox/
2. (opcional) renomear: comporta_summer_F02.jpg
3. (opcional) escrever notas em comporta_summer_F02.txt
4. próxima sessão Claude: dizer "processa o inbox"
```

Eu (Claude) processo: extraio metadata visual, peço-te tags em falta via tool de questions, atribuo `ref_NNN`, movo para a pasta certa, actualizo `_index.json`. Tu validas no fim.

---

## Caminho 2 · Add Reference Helper script (semi-automático)

**Quando usar:** queres adicionar 1-3 refs sem esperar uma sessão Claude.

Ainda no Terminal, dentro de `sorio-posters/`:

```bash
python3 design/design_references/_scripts/add_reference.py PATH/TO/poster.png
```

O script:
1. Pergunta interactivamente: title, source, family, category, mood, tags, why_good (3-5 items)
2. Cria `ref_NNN_slug/` com o ficheiro renomeado para `poster.png`
3. Gera `metadata.json`
4. Adiciona entry em `_index.json`
5. Increment stats
6. Imprime: `git add . && git commit -m "ref: ..." && git push` para fazeres push

Tempo médio por ref: 60-90 segundos.

---

## Caminho 3 · Manual full-control

**Quando usar:** queres total controlo, ou estás a importar refs em batch.

```
1. Criar pasta ref_NNN_descritivo/ ao lado de _inbox/
2. Pôr o ficheiro como poster.png (ou .jpg)
3. Criar metadata.json baseado em SCHEMA.md
4. Adicionar entry no _index.json references[]
5. Actualizar stats
6. git push
```

---

## Caminho 4 · Boldy "Add to refs" (futuro)

**Quando vai existir:** a partir da Fase E (Vision Critique Loop) na Boldy.

Cada poster gerado e aprovado tem um botão **"Add to refs library"**. Boldy:
1. Pré-preenche family, category, mood, tags a partir dos params usados
2. Pede-te why_good em 3 linhas (input livre)
3. Atalho de tags clicáveis (não tens que digitar)
4. Submit → cria `ref_NNN/`, commita ao repo, push automático
5. Netlify rebuild ~30s depois

Zero fricção. É a meta.

---

## Numeração `ref_NNN`

`NNN` é zero-padded 3 dígitos: `ref_001`, `ref_002`, ..., `ref_099`, `ref_100`.

O próximo número livre = `_index.json/stats/total_refs + 1`.

Slug depois do número: `ref_007_caipirinha_evening_aprovado`. Snake_case, descritivo, ASCII (sem acentos).

---

## Onde os assets vivem

```
sorio-posters/
└── design/
    └── design_references/
        ├── _index.json                     ← catálogo (sempre actualizar quando adicionas)
        ├── _inbox/                         ← drop zone temporária
        ├── _docs/                          ← schema, este doc, philosophy
        ├── _scripts/                       ← add_reference.py
        ├── ref_001_*/
        │   ├── poster.png                  ← ★ obrigatório
        │   ├── thumb.jpg                   ← opcional, gerado pelo script
        │   └── metadata.json               ← ★ obrigatório
        ├── ref_002_*/
        ...
```

Tudo no repo `sorio-posters` deployed em Netlify → Decisor acessa via HTTPS em runtime.

---

## Limpeza periódica

Mensalmente:
- Revisar `_inbox/` — se ainda lá está, ou processas ou apagas
- Rodar `_scripts/audit.py` (TBD) que detecta refs sem `principle_match`, sem `why_good`, sem thumb, etc.
- Se um princípio mudar (ex: TYPO-01 ajustado), refs antigas com principle_match daquele ID ficam sinalizadas para revisão

---

## TL;DR

Se for ad-hoc → drop no `_inbox/`.
Se quiseres processar agora → script Python.
Se for em volume / com critério especial → manual.
Em breve → botão na Boldy.
