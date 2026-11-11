# Zonas verdes da Beira — regras do projeto

Artigo científico (DOCX + PDF, ABNT) e site estático interativo sobre a evolução das zonas verdes
(agricultura urbana e periurbana, machambas de baixada, mangal) da Cidade da Beira, Moçambique, 1985–2026.
Projeto análogo a `../zonas.verdes.maputo/` (publicado com DOI 10.5281/zenodo.24141821): mesma
metodologia, mesma orquestração, repositório, site e DOI próprios. Plano: `docs/PLANO.md`.

## Integridade científica (inegociável)
- Nenhuma referência, número, data, artigo de lei ou citação entra no artigo ou no site sem fonte
  aberta e conferida nesta pesquisa. Nada de memória. Cada fonte tem linha em `fontes/ref_*.csv`
  (coluna `status`: VERIFICADO / PARCIAL / NAO_VERIFICADO) e, se usada no texto, ficha em
  `fontes/fichas/<chave>.md` com página/tabela de cada número e citação.
- Fichas reaproveitadas do projeto de Maputo (literatura geral sobre agricultura urbana africana,
  dados, métodos) podem ser copiadas de `../zonas.verdes.maputo/fontes/fichas/` com o mesmo status;
  o resultado do projeto de Maputo é citado como obra publicada (DOI acima).
- Citações literais curtas (≤ 15 palavras), entre aspas, com página.
- Todo número de séries vai para `fontes/series_producao.csv` com fonte, página, ano e definição
  espacial. Definições divergentes não se somam nem se comparam sem nota.
- Números de resultados do artigo e do site são lidos de `dados/proc/resultados.json` /
  `artigo/valores.json`; nunca digitados à mão.
- Não contornar verificação TLS (`curl -k` proibido), paywall ou proteção anti-robô. Se um site
  falhar, registrar e usar espelho.

## Dados
- `dados/raw/` nunca é versionado. Downloads em subpasta própria por fonte.
- Scripts numerados em `scripts/NN_nome.py`, rodam com `.venv/bin/python -I`; `scripts/rodar_cadeia.sh`
  roda tudo do zero.
- CRS de trabalho: EPSG:32736 (UTM 36S), 30 m. Área: bbox 34,72–35,10 E, −19,95 a −19,60 S
  (cobre 94% do polígono municipal de 648 km²: ficam de fora faixas nos extremos oeste e leste; o texto declara isso).

## Identidade visual (Sistema Ardósia)
- `site/assets/ardosia.css` e `scripts/ardosia_palette.py` são cópias verbatim da skill; não editar.
- Nenhum hex literal em CSS novo: usar as variáveis `--ard-*`. Tabelas e textos precisam de
  contraste nos dois temas (lição de Maputo: `td` do ardosia.css é claro só no tema claro).
- Figuras matplotlib: `from ardosia_palette import apply_ardosia; apply_ardosia()`.
- Sem emoji. Serifa no texto, sans em rótulos e eixos. Máximo seis cores categóricas.

## Direitos de imagem
- Imagens de terceiros (planos históricos, mapas antigos) ficam fora da licença MIT. Cada uma tem
  linha em `CREDITOS.md` (fonte, autor, data, detentor, situação de direitos) e legenda com autor,
  data, instituição e fonte de onde foi obtida.

## Orquestração
- Sessão principal (Opus) decide e redige; implementação e leitura em Sonnet; tarefas mecânicas em
  Haiku; auditoria em Opus com contexto novo. Agentes em `.claude/agents/`. Registro em
  `docs/ORQUESTRACAO.md`.
- Dois agentes nunca escrevem no mesmo arquivo.
