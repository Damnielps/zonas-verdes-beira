# Zonas verdes da Beira — plano

Produto análogo ao de Maputo (`../zonas.verdes.maputo/docs/PLANO.md`), adaptado à Beira. Pedido do autor
(11/11/2026): "elabore um produto análogo para a Cidade da Beira [...] com artigo acadêmico e site associado.
utilize o mesmo esquema de orquestração utilizado em Maputo e publique em um site separado, com DOI próprio".

## Herdado de Maputo (decidido, não reabrir)
- Artigo DOCX + PDF em ABNT; site estático (MapLibre + D3, `window.DADOS`), Ardósia, GitHub Pages, MIT, Zenodo
  vinculado ao ORCID 0000-0002-6632-3991; página do artigo no site com só o PDF para download.
- Pipeline: GeoMAD anual do Digital Earth Africa + cenas Landsat C2 do Planetary Computer para lacunas;
  Random Forest por época com rótulos de concordância (WorldCover, IO LULC, GHSL, OSM); legenda agregada
  1 construído, 2 agricultura de baixada/hortícola, 3 sequeiro/mosaico, 45 vegetação natural + zonas húmidas
  (inclui mangal), 6 água, 7 solo exposto/areia; pós-processamento `06b` (máscara de mar, janela de 3 épocas
  para construído + monotonia, suavização 2↔5); validação cega estratificada (Olofsson); métrica central
  independente da classe agrícola: fração construída dentro de perímetros independentes (baixadas DEM/TPI,
  zonas agrícolas dos planos georreferenciados), relatada como intervalo entre três estimativas
  (GHSL, bruta, pós-processada).
- Lições de Maputo: `para_3857` com no-data explícito em camadas categóricas; cache-busting `?v=` nas
  imagens; contraste das tabelas nos dois temas; ordem da cadeia 20 antes de 12; nada de afirmação
  forte ("dobrou", "dois terços") sem robustez entre as três estimativas.

## Específico da Beira (a confirmar nos levantamentos — nada disto entra no texto sem ficha)
- Cidade costeira baixa, sobre planície aluvial e mangal no estuário do Púngue; cheias e ciclones
  (Idai, março de 2019) como eixo ambiental; salinização; drenagem (rio Chiveve).
- Zonas de produção periurbana prováveis: Manga, Inhamízua, Nhangau, Munhava, Matacuane; arroz e hortícolas
  de baixada; papel do mangal e das zonas húmidas.
- Épocas: censos 1980, 1997, 2007, 2017; quinquenais até 2025; 2019/2020 (pós-Idai) se houver composição
  útil; 2026 (presente). 1980 depende de cena MSS/TM utilizável.
- Planos: período colonial (Companhia de Moçambique até 1942; planos de urbanização da Beira dos anos
  1940–1960); pós-independência; plano de estrutura / PEU municipal; Beira Masterplan 2035; planos de
  reconstrução pós-Idai. Imagens dos planos como ilustração, com citação da fonte (decisão do autor).
- Comparações: Maputo (resultado publicado), outras cidades costeiras africanas expostas a cheias,
  e os casos já fichados em Maputo.

## Orquestração (igual a Maputo)
Sessão principal Opus decide, confere e redige; `leitura` e `implementacao` em Sonnet; `mecanico` em Haiku;
`auditoria` em Opus com contexto novo. Registro em `docs/ORQUESTRACAO.md`. Lotes:
- L1 Beira: história urbana, agricultura urbana/periurbana, conflitos de uso do solo, cheias e Idai.
- L2 Planos: coloniais, pós-independência e atuais (incl. Masterplan 2035), figuras de planos.
- L3 Séries de produção e produtores (INE Sofala, Município, DPA, censos agropecuários).
- L4 Reaproveitamento: fichas gerais de Maputo + casos costeiros comparáveis.
- I1 Pipeline 01–04 (limites, composições, auxiliares, QA); I2 classificação 05–08; I3 georreferência de
  planos; I4 validação cega; I5 resultados e site; I6 artigo.

## Publicação
Repositório separado `zonas-verdes-beira` no GitHub do autor, Pages, release v1.0.0 → DOI Zenodo próprio,
com "isSupplementTo"/"references" apontando ao DOI de Maputo.
