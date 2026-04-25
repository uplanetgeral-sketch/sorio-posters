# `_inbox/` — Drop zone para novas referências

Atalho mais rápido para adicionar uma referência à biblioteca: dropas o ficheiro aqui e processo na próxima sessão.

---

## Como usar

### Caminho 1 · Drop simples (recomendado, baixa fricção)

1. Arrasta o ficheiro PNG/JPG para esta pasta `_inbox/`
2. **(Opcional mas útil)** renomeia com hint info: `caipirinha_aprovado_evening.png`, `comporta_cafe_summer_F02.jpg`
3. **(Opcional)** cria um ficheiro `.txt` com o mesmo nome do ficheiro com 2-3 linhas de notas: por que é boa, o que admiras, contexto.

Exemplo:
```
_inbox/
├── comporta_cafe_summer_2024_F02.jpg
└── comporta_cafe_summer_2024_F02.txt    ← "Adoro a tensão entre tipografia gigante e hero pequeno. Restraint absoluto."
```

Na próxima sessão, eu (Claude) processo o inbox: extraio metadata visual, peço-te tags em falta, atribuo `ref_NNN`, movo para a pasta certa, actualizo `_index.json`. Tu validas no fim.

---

### Caminho 2 · Pasta manual completa (full control)

Se já souberes os tags todos e quiseres adicionar manualmente sem esperar sessão:

1. Cria pasta `ref_NNN_descritivo/` ao lado de `_inbox/` (NNN = próximo número livre)
2. Coloca o ficheiro como `poster.png` (ou .jpg)
3. Cria `metadata.json` baseado em `_docs/SCHEMA.md`
4. Adiciona entry em `references[]` no `_index.json`
5. Increment `stats.total_refs`
6. `git push`

---

### Caminho 3 · Boldy "Add to refs" (futuro)

Quando a Boldy estiver mais madura (Fase E+), cada poster aprovado terá um botão "Add to refs library". A Boldy preenche metadata automaticamente a partir dos params usados, tu validas e clicas. Zero fricção.

---

## O que NÃO meter aqui

- Heroes raw do Gemini (sem tipografia) — esses vão para `assets/heroes/` se forem para uso, não para refs
- Iterações intermédias / WIPs — só refs que tu consideras exemplares
- Quantidade > qualidade não é a meta. Melhor 20 refs excelentes que 200 medíocres
- Imagens com copyright dum terceiro que tencionemos REDISTRIBUIR — refs externas ficam descritas textualmente em `_index.json` com link para fonte, não embebidas

---

## Quanto tempo o `_inbox/` deve estar limpo?

Idealmente é uma queue: enches durante a semana, processo no inicio da próxima sessão Claude. Não acumula.

Se passar muito tempo sem processar, o `_inbox/` fica stale e perdes contexto sobre porque guardaste cada ref. Trata-o como inbox de email.
