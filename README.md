# Zonas verdes da Beira (1985–2026): agricultura urbana, baixadas e expansão construída

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24147238.svg)](https://doi.org/10.5281/zenodo.24147238)

Site: https://damnielps.github.io/zonas-verdes-beira/ · Repositório: https://github.com/Damnielps/zonas-verdes-beira

Artigo científico e site interativo sobre a evolução das baixadas, mangais e áreas de agricultura urbana e periurbana da Cidade da Beira, Moçambique. O projeto combina a história dos planos urbanísticos (do anteprojeto de 1943 ao Masterplan 2035) e dos conflitos de uso do solo com um painel de 15 épocas de imagens Landsat (1979–2026), classificado por Random Forest, avaliado por amostra cega e cruzado com perímetros independentes da classificação agrícola. É o projeto irmão de [Zonas verdes de Maputo](https://doi.org/10.5281/zenodo.24141821), com o mesmo método.

## Entregas

- Artigo: `artigo/artigo.pdf` e `artigo/artigo.docx` (ABNT); texto-fonte em `artigo/artigo.md` e `artigo/artigo_final.md`.
- Site estático interativo: `site/` (servir localmente com `python3 -m http.server --directory site`).
- Dados abertos agregados: `site/dados/`.

## Principais resultados

Números lidos de `artigo/valores.json`. Intervalo entre três estimativas (GHSL, classificação bruta e pós-processada), que não são independentes entre si: a bruta e a pós-processada vêm do mesmo modelo, e o GHSL orientou os rótulos de treino. Médias de dois períodos, 1985–1997 e 2017–2025.

- Fração construída do município: de 1,5–6,1% para 4,1–13,1% (fator 1,9 a 2,8).
- Fração construída das baixadas (altitude ≤ 8 m, relevo côncavo; 18.797 ha): de 1,5–6,0% para 4,0–13,1% (fator 2,0 a 3,1); robusto aos limiares de 6 e 10 m.
- Mangal de referência: sem aumento detectável da construção (GHSL 0,0% → 0,0%; classificação bruta 3,5% → 2,1%).
- Validação cega (2020, n = 280, rotulagem por agente automático, 56% de baixa confiança): o construído tem exatidão do usuário 0,78 e do produtor 0,36 (subestimado); a agricultura de baixada tem exatidão do usuário 0,02 e não é usada como métrica. Revisão humana pendente.
- Não há séries abertas de produtores ou de produção agrícola urbana para a cidade.

## Reproduzir

Requer `uv` e Python 3.14. `dados/raw/` não é versionado.

```bash
bash scripts/00_ambiente.sh
bash scripts/rodar_cadeia.sh
```

A cadeia roda 01–08, 10, 11, 20, 12 e 21 nesta ordem. A rotulagem cega (`dados/proc/validacao/rotulos_2020.csv`) é insumo externo de `scripts/11_avaliacao_exatidao.py`.

## Limitações

Ver `docs/PENDENCIAS.md`. Em resumo: a área de estudo cobre 94% do polígono municipal; a validação refere-se a 2020 e foi feita por agente automático, com 56% de rótulos de baixa confiança; a classe de agricultura de baixada não é confiável a 30 m; textos integrais do PEU 2022, do Masterplan 2035 e do PDNA 2019 e as séries do INE não foram obtidos em acesso aberto.

## Como citar

PESSINI SOBREIRA, Daniel. *Zonas verdes da Beira (1985–2026): agricultura urbana, baixadas e expansão construída*. Zenodo, 2026. DOI: 10.5281/zenodo.24147238. Disponível em: https://doi.org/10.5281/zenodo.24147238. Ver `CITATION.cff`.

## Licença e créditos

Código sob licença MIT (`LICENSE`). Imagens de terceiros (planos e mapas históricos) e dados de terceiros não são cobertos pela MIT; fontes, autores, detentores e situação de direitos em `CREDITOS.md`.

## Orquestração

Sessão principal decide e redige; implementação e leitura em modelos intermediários; tarefas mecânicas em modelo leve; auditoria com contexto novo. Registro em `docs/ORQUESTRACAO.md`.
