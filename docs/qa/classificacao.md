# QA da classificação (30 m, EPSG:32736) — Beira

Gerado por `scripts/08_qa_classificacao.py` a partir de `05_rotulos.py`, `06_classificar.py`, `06b_consistencia.py`, `07_areas_transicoes.py`, `07b/07c`. Números lidos de `dados/proc/class/oob.json`, `dados/proc/rotulos/rotulos_resumo.json`, `dados/proc/class_final/consistencia.json` e `dados/proc/areas/`. A seção 8 (validação cega de 2020) é anexada por `11_avaliacao_exatidao.py` quando existir `dados/proc/validacao/rotulos_2020.csv`.

## 1. Rótulos de treino

### 1.1 Âncora 2020 e regras

- Construído: WorldCover 2021 = 50 E IO LULC 2020 = Built E GHSL-BUILT-S 2020 ≥ 2000 m² por célula de 100 m.
- Árvore/arbusto e mangal (45): (WC 10 E IO Trees E GHSL < 500) OU WC 95 (mangal; subclasse 41 na coluna `sub`); nunca agricultura.
- Agricultura: polígonos OSM `farmland`, `allotments`, `greenhouse_horticulture` OU (WC 2021 = 40 ou WC 2020 = 40) E IO = Crops ou Flooded vegetation (arrozal inundado é rotulado `flooded vegetation` pelo IO LULC; Siueia et al. 2025, tab. 1), com GHSL ≤ 500 e fora de WC 95.
- Divisão 2 × 3: classe 2 se altitude ≤ 8 m E TPI < 0, ou a ≤ 100 m de zona húmida OSM de água doce (`tidalflat` e `mangrove` excluídos); caso contrário classe 3.
- Herbácea/húmida natural (5): (WC 2021 = 90 E WC 2020 = 90 E IO Flooded vegetation ou Rangeland) OU (WC 30 em 2020 e 2021 E IO Rangeland), com GHSL < 500, fora de agricultura e de mangal. A exigência de concordância entre as duas versões do WorldCover evita rotular como zona húmida natural o arrozal, que alterna 30/40/90 entre versões.
- Água: WC 80 em 2020 e 2021 E IO Water. Solo exposto: WC 60 E IO Bare.
- Píxeis que cumprem mais de uma regra foram descartados (9 px); máscaras erodidas em 1 píxel (3×3); classes sem erosão: nenhuma.
- Reserva de até 6000 pontos por classe (`pool_2020.parquet`); âncora `treino_2020` com até 1500 por classe. Pontos na reserva: {'1': 6000, '2': 1081, '3': 3369, '4': 6000, '5': 6000, '6': 6000, '7': 961}; na âncora: {'1': 1500, '2': 1081, '3': 1500, '4': 1500, '5': 1500, '6': 1500, '7': 961}.
- Píxeis brutos por classe antes da erosão: 1: 50,387, 2: 6,192, 3: 7,808, 4: 95,293, 5: 540,350, 6: 593,070, 7: 4,782.

**Mangal de referência** (usado em 06 para 1979 e em 07b/07c): WorldCover 2020 (classe 95) e Global Mangrove Watch v3, extensão de 1996 (Zenodo, doi 10.5281/zenodo.6894273, CC BY 4.0; baixado de `zenodo.org/api/records/6894273`, tiles GMW_S19/S20 × E034/E035). Píxeis de 30 m: WorldCover 94,159; GMW 1996 66,267; interseção 56,765; união 103,661. O GMW 1996 não rotula 2020 (pode ter sido convertido depois); serve como máscara de referência.

### 1.2 Propagação temporal

Ângulo espectral entre o vetor 2020 e o da época t em (verde, vermelho, NIR, SWIR1, SWIR2; 1979: verde, vermelho, NIR), calculado sobre pseudo-invariantes: 1000 pontos de água profunda (WC 80 E IO água, erodida 3 px) e 325 pontos do núcleo construído antigo (GHSL 1975 ≥ 5000 e GHSL 2020 ≥ 5000 nos postos Urbano 1 e 2, erodido). Consistência com GHSL(t) (ano GHSL mais próximo): construído exige ≥ 2000; agricultura, árvore e herbácea exigem < 500.

**Desvios documentados.** (i) O limiar das classes construído, 2 e 3 sai dos invariantes de núcleo construído no percentil 20 e sobe para 50 e 80 só enquanto alguma classe retiver menos de min(150; 50% do pool) pontos. (ii) Vegetação natural (4, 5) e solo exposto (7) usam o percentil 95 dos mesmos invariantes: com o limiar estrito, as cenas de estação seca (2005 e 2007) perderam grande parte da vegetação seca ou queimada da amostra de treino e o RF a classificava como construído (2005 bruto: 232 mil píxeis construídos contra 115 mil depois da correção). (iii) A água não usa ângulo: um ponto da reserva de água só entra se, na época t, MNDWI (verde−SWIR1; NDWI verde−NIR em 1979) > 0 e NIR < 0,15, isto é, por índice e não por cor (turbidez do Púngue).

| época | bandas | percentil (terra) | limiar terra (rad) | limiar natural p95 (rad) |
|---|---|---|---|---|
| 1979 | green,red,nir | 80 | 0.2102 | 0.2574 |
| 1985 | green,red,nir,swir1,swir2 | 50 | 0.1335 | 0.2999 |
| 1990 | green,red,nir,swir1,swir2 | 50 | 0.1090 | 0.2838 |
| 1995 | green,red,nir,swir1,swir2 | 20 | 0.0531 | 0.2511 |
| 1997 | green,red,nir,swir1,swir2 | 50 | 0.0884 | 0.2100 |
| 2000 | green,red,nir,swir1,swir2 | 50 | 0.0882 | 0.2364 |
| 2005 | green,red,nir,swir1,swir2 | 80 | 0.0939 | 0.1352 |
| 2007 | green,red,nir,swir1,swir2 | 50 | 0.0646 | 0.1439 |
| 2010 | green,red,nir,swir1,swir2 | 50 | 0.0647 | 0.2149 |
| 2015 | green,red,nir,swir1,swir2 | 50 | 0.0432 | 0.0981 |
| 2017 | green,red,nir,swir1,swir2 | 80 | 0.0984 | 0.1401 |
| 2019 | green,red,nir,swir1,swir2 | 80 | 0.0224 | 0.0384 |
| 2025 | green,red,nir,swir1,swir2 | 80 | 0.0649 | 0.0914 |
| 2026 | green,red,nir,swir1,swir2 | 80 | 0.0679 | 0.1051 |

Pontos de treino por época e classe (após propagação; limite 1 500 por classe e época):

| época | cl 1 | cl 2 | cl 3 | cl 4 | cl 5 | cl 6 | cl 7 |
|---|---|---|---|---|---|---|---|
| 1979 | 1500 | 0 | 3288 | 0 | 0 | 1500 | 539 |
| 1985 | 1338 | 182 | 516 | 1500 | 1500 | 1500 | 471 |
| 1990 | 1399 | 280 | 506 | 1477 | 1307 | 1460 | 387 |
| 1995 | 680 | 274 | 686 | 1500 | 1500 | 1499 | 490 |
| 1997 | 1499 | 473 | 1500 | 1491 | 1468 | 1500 | 374 |
| 2000 | 1500 | 193 | 1500 | 1500 | 1500 | 1500 | 400 |
| 2005 | 1500 | 264 | 171 | 1500 | 1036 | 1500 | 469 |
| 2007 | 1500 | 212 | 396 | 1500 | 1500 | 1500 | 381 |
| 2010 | 1489 | 404 | 1184 | 1500 | 1500 | 1499 | 588 |
| 2015 | 1500 | 281 | 631 | 1500 | 1500 | 1467 | 673 |
| 2017 | 1500 | 277 | 1500 | 1500 | 1500 | 1463 | 813 |
| 2019 | 1500 | 53 | 279 | 789 | 1500 | 1500 | 792 |
| 2020 | 1500 | 1081 | 1500 | 1500 | 1500 | 1500 | 961 |
| 2025 | 1500 | 237 | 1221 | 1500 | 1500 | 1500 | 784 |
| 2026 | 1500 | 224 | 1165 | 1500 | 1500 | 1500 | 748 |

## 2. Reprodução dos rótulos (OOB e validação cruzada em blocos de 3 km)

| época | n | acurácia OOB | F1 por classe (OOB) | acurácia CV blocos | principais variáveis |
|---|---|---|---|---|---|
| 1979 | 6827 | 0.980 | 1: 0.97, 3: 0.98, 6: 1.00, 7: 0.93 |  | dem (0.212), ndvi (0.168), nir (0.164) |
| 1985 | 7007 | 0.958 | 1: 0.99, 2: 0.91, 3: 0.91, 4: 0.95, 5: 0.92, 6: 1.00, 7: 0.97 |  | dem (0.164), ndvi (0.094), mndwi (0.09) |
| 1990 | 6816 | 0.964 | 1: 0.98, 2: 0.93, 3: 0.94, 4: 0.97, 5: 0.92, 6: 1.00, 7: 0.98 |  | dem (0.163), mndwi (0.118), ndvi (0.11) |
| 1995 | 6629 | 0.965 | 1: 0.95, 2: 0.97, 3: 0.95, 4: 0.97, 5: 0.94, 6: 1.00, 7: 0.95 |  | mndwi (0.126), dem (0.126), swir1 (0.119) |
| 1997 | 8305 | 0.964 | 1: 0.98, 2: 0.94, 3: 0.96, 4: 0.97, 5: 0.91, 6: 1.00, 7: 0.97 |  | mndwi (0.13), dem (0.123), ndvi (0.095) |
| 2000 | 8093 | 0.968 | 1: 0.98, 2: 0.91, 3: 0.97, 4: 0.97, 5: 0.93, 6: 1.00, 7: 0.96 | 0.918 (F1: 1: 0.94, 2: 0.36, 3: 0.92, 4: 0.95, 5: 0.84, 6: 1.00, 7: 0.91) | mndwi (0.124), dem (0.112), swir1 (0.099) |
| 2005 | 6440 | 0.965 | 1: 0.97, 2: 0.90, 3: 0.89, 4: 0.99, 5: 0.91, 6: 1.00, 7: 0.96 |  | mndwi (0.146), swir1 (0.107), swir2 (0.097) |
| 2007 | 6989 | 0.966 | 1: 0.97, 2: 0.89, 3: 0.89, 4: 0.98, 5: 0.94, 6: 1.00, 7: 0.96 |  | mndwi (0.148), swir1 (0.106), swir2 (0.096) |
| 2010 | 8164 | 0.966 | 1: 0.98, 2: 0.93, 3: 0.96, 4: 0.98, 5: 0.93, 6: 1.00, 7: 0.97 | 0.915 (F1: 1: 0.95, 2: 0.68, 3: 0.88, 4: 0.96, 5: 0.84, 6: 1.00, 7: 0.92) | mndwi (0.138), dem (0.126), swir1 (0.088) |
| 2015 | 7552 | 0.979 | 1: 0.99, 2: 0.93, 3: 0.95, 4: 0.99, 5: 0.96, 6: 1.00, 7: 0.99 |  | mndwi (0.148), dem (0.092), nir (0.084) |
| 2017 | 8553 | 0.981 | 1: 0.99, 2: 0.95, 3: 0.97, 4: 0.99, 5: 0.96, 6: 1.00, 7: 1.00 |  | mndwi (0.126), ndvi (0.123), dem (0.093) |
| 2019 | 6413 | 0.989 | 1: 1.00, 2: 0.67, 3: 0.94, 4: 1.00, 5: 0.98, 6: 1.00, 7: 1.00 |  | mndwi (0.161), nir (0.124), swir1 (0.091) |
| 2020 | 9542 | 0.975 | 1: 1.00, 2: 0.96, 3: 0.96, 4: 0.99, 5: 0.93, 6: 1.00, 7: 1.00 | 0.908 (F1: 1: 0.99, 2: 0.68, 3: 0.91, 4: 0.97, 5: 0.77, 6: 1.00, 7: 0.99) | mndwi (0.157), ndvi (0.098), nir (0.098) |
| 2025 | 8242 | 0.982 | 1: 0.99, 2: 0.94, 3: 0.97, 4: 0.98, 5: 0.96, 6: 1.00, 7: 1.00 |  | mndwi (0.166), nir (0.107), ndvi (0.096) |
| 2026 | 8137 | 0.976 | 1: 0.99, 2: 0.93, 3: 0.96, 4: 0.98, 5: 0.95, 6: 1.00, 7: 0.99 |  | mndwi (0.143), ndvi (0.102), swir1 (0.101) |

**Leitura.** OOB e CV medem a reprodução dos rótulos (derivados de WorldCover, IO LULC, GHSL e OSM), não a exatidão contra verdade de campo; a exatidão está na seção 8 (validação cega de 2020). F1 da classe 2: OOB entre 0.67 e 0.97; CV em blocos 2000: 0.36, 2010: 0.68, 2020: 0.68. A queda na CV espacial indica que a classe 2 não se generaliza entre blocos de 3 km (poucos rótulos propagados, uma só âncora de ~1 100 píxeis e sobreposição espectral provável com herbácea de baixada): é a classe de menor confiabilidade.

Nota 1979: legenda reduzida (1 construído, 3 vegetação/agricultura de todo o tipo, 6 água, 7 solo exposto; 4, 5 e 45 ausentes); a classe 2 é derivada por regra de baixada fora do mangal de referência. 1979 fica fora das séries quantitativas e das regras de 06b.

## 3. Pós-processamento de consistência (06b)

Sequência: 1985, 1990, 1995, 1997, 2000, 2005, 2007, 2010, 2015, 2017, 2019, 2020, 2025, 2026 (1979 fora). Regra 0: píxel que é água em pelo menos metade das épocas é mar/estuário/leito e passa a água nas demais (elimina nuvem e névoa sobre o mar). Regra 1: construído em t só permanece se estiver construído em pelo menos 2 das 3 épocas da janela {t−1, t, t+1}; depois, monotonia (construído nunca reverte). Regra 2: tremulação 2↔5 em épocas interiores. Píxeis alterados por época e regra:

| epoca | r0_mar | r1_removidos | r1_acrescentados | r2_2↔5 | total |
|---|---|---|---|---|---|
| 1985 | 13178 | 13582 | 0 | 0 | 26760 |
| 1990 | 9158 | 36321 | 2806 | 8682 | 56807 |
| 1995 | 6023 | 4490 | 9981 | 9336 | 29830 |
| 1997 | 5691 | 14823 | 10566 | 16188 | 47267 |
| 2000 | 5253 | 8020 | 10559 | 4530 | 28333 |
| 2005 | 10212 | 42635 | 8911 | 3720 | 65461 |
| 2007 | 1843 | 16769 | 14331 | 9768 | 42680 |
| 2010 | 3366 | 9753 | 35983 | 12361 | 61425 |
| 2015 | 3136 | 9357 | 27207 | 7480 | 47166 |
| 2017 | 6693 | 10575 | 35264 | 10294 | 62761 |
| 2019 | 3285 | 2733 | 31148 | 14232 | 51374 |
| 2020 | 4274 | 4598 | 28520 | 27694 | 65080 |
| 2025 | 5664 | 3665 | 37434 | 5228 | 51839 |
| 2026 | 6294 | 12008 | 36561 | 0 | 54863 |

Construído monotônico: True (violações: 0). Hipótese não testada: o estuário do Púngue tem bancos de areia e lamaçais que podem alternar entre água e solo exposto com a maré e a data da cena; pelo critério de metade das épocas, esses píxeis ficam água em todas as épocas e a variação real de água/solo exposto no estuário fica mascarada.

## 4. Áreas (km²) no Município da Beira (07)

| época | sem dado | 1 construído | 2 agric. baixada | 3 terra firme | 6 água | 7 solo exposto | 4+5 natural |
|---|---|---|---|---|---|---|---|
| 1979 | 0.00 | 80.7 | 63.5 | 438.2 | 14.0 | 10.8 | 0.00 |
| 1985 | 10.7 | 23.5 | 14.3 | 17.8 | 14.4 | 6.75 | 519.7 |
| 1990 | 8.44 | 26.4 | 9.14 | 13.3 | 11.1 | 8.11 | 530.7 |
| 1995 | 0.00 | 28.4 | 17.3 | 20.8 | 13.4 | 10.9 | 516.3 |
| 1997 | 0.16 | 33.2 | 22.7 | 31.4 | 9.66 | 7.32 | 502.8 |
| 2000 | 0.00 | 35.8 | 5.99 | 37.3 | 8.75 | 7.97 | 511.3 |
| 2005 | 0.02 | 53.5 | 12.1 | 17.2 | 8.67 | 11.2 | 504.4 |
| 2007 | 0.15 | 55.2 | 11.3 | 18.0 | 8.02 | 5.44 | 509.1 |
| 2010 | 0.01 | 58.6 | 12.6 | 33.6 | 7.33 | 7.76 | 487.3 |
| 2015 | 0.00 | 68.0 | 14.4 | 30.7 | 5.75 | 6.90 | 481.5 |
| 2017 | 0.00 | 71.4 | 11.3 | 41.8 | 6.71 | 4.92 | 471.0 |
| 2019 | 0.00 | 77.0 | 15.4 | 22.2 | 6.04 | 5.34 | 481.1 |
| 2020 | 0.00 | 80.2 | 24.3 | 43.4 | 7.08 | 5.94 | 446.3 |
| 2025 | 0.00 | 86.2 | 16.8 | 45.4 | 8.22 | 5.73 | 444.8 |
| 2026 | 0.00 | 87.0 | 15.7 | 46.0 | 8.73 | 5.47 | 444.3 |

Município = polígono HDX COD-AB (camada `municipio`), 607 km² na grade de 30 m (inclui água interior do estuário). 1979 aparece só por completude: legenda reduzida (3 = toda a vegetação, 45 ausente), não comparável. 1985 tem 1.8% do município sem dado (nuvens da cena de 1984). As classes 2 e 3 são menos confiáveis (ver seções 2 e 8); a classe 2 varia entre 6 e 24 km² ao longo das épocas, sem tendência monótona nem explicação documentada; ler como indicativo, não como série de agricultura real.

Figuras: `dados/fig/class/mapas_classes.png`, `area_empilhada_municipio.png`, `linhas_classe1_classe2.png`, `mapa_ano_conversao.png`, `envelopes_construido.png`.

## 5. Concordância externa do construído com o GHSL-BUILT-S

Construído nosso (classe 1) contra células GHSL ≥ 2000 m² (≥ 20% de superfície construída por célula de 100 m), ano GHSL mais próximo; `ghsl_soma_fracao` é a soma da fração construída do GHSL (mesma unidade de superfície, mas conceito diferente: superfície edificada, não ocupação por píxel de 30 m).

Classificação final, município:

| epoca | ghsl_ano | construido_km2 | ghsl_ge2000_km2 | ghsl_soma_fracao_km2 | pct_nosso_em_ghsl | pct_ghsl_no_nosso | f1 |
|---|---|---|---|---|---|---|---|
| 1979 | 1980 | 80.7 | 12.4 | 6.03 | 15.0 | 97.6 | 26.0 |
| 1985 | 1985 | 23.5 | 14.7 | 7.22 | 49.3 | 78.7 | 60.6 |
| 1990 | 1990 | 26.4 | 18.0 | 8.68 | 52.2 | 76.7 | 62.1 |
| 1995 | 1995 | 28.4 | 22.3 | 10.4 | 56.6 | 72.2 | 63.5 |
| 1997 | 1995 | 33.2 | 22.3 | 10.4 | 52.8 | 78.6 | 63.2 |
| 2000 | 2000 | 35.8 | 27.4 | 12.5 | 56.5 | 73.9 | 64.1 |
| 2005 | 2005 | 53.5 | 32.5 | 15.1 | 55.3 | 91.2 | 68.9 |
| 2007 | 2005 | 55.2 | 32.5 | 15.1 | 53.8 | 91.5 | 67.7 |
| 2010 | 2010 | 58.6 | 44.3 | 18.7 | 63.2 | 83.6 | 71.9 |
| 2015 | 2015 | 68.0 | 52.9 | 22.6 | 66.2 | 85.0 | 74.4 |
| 2017 | 2015 | 71.4 | 52.9 | 22.6 | 64.6 | 87.1 | 74.2 |
| 2019 | 2020 | 77.0 | 58.8 | 25.1 | 64.5 | 84.5 | 73.1 |
| 2020 | 2020 | 80.2 | 58.8 | 25.1 | 63.7 | 86.9 | 73.5 |
| 2025 | 2025 | 86.2 | 60.1 | 26.2 | 61.9 | 88.8 | 73.0 |
| 2026 | 2025 | 87.0 | 60.1 | 26.2 | 61.5 | 89.0 | 72.8 |

Classificação bruta, município:

| epoca | construido_km2 | pct_nosso_em_ghsl | pct_ghsl_no_nosso | f1 |
|---|---|---|---|---|
| 1979 | 80.7 | 15.0 | 97.6 | 26.0 |
| 1985 | 30.7 | 39.5 | 82.4 | 53.4 |
| 1990 | 52.0 | 27.0 | 78.2 | 40.1 |
| 1995 | 23.5 | 58.4 | 61.7 | 60.0 |
| 1997 | 38.3 | 46.1 | 79.4 | 58.4 |
| 2000 | 33.5 | 53.7 | 65.8 | 59.2 |
| 2005 | 74.7 | 40.6 | 93.4 | 56.6 |
| 2007 | 56.5 | 50.8 | 88.4 | 64.5 |
| 2010 | 41.7 | 63.6 | 59.8 | 61.7 |
| 2015 | 63.3 | 69.0 | 82.6 | 75.2 |
| 2017 | 63.4 | 66.4 | 79.6 | 72.4 |
| 2019 | 65.6 | 73.1 | 81.6 | 77.1 |
| 2020 | 71.0 | 70.6 | 85.2 | 77.2 |
| 2025 | 71.0 | 72.0 | 85.0 | 78.0 |
| 2026 | 78.2 | 64.7 | 84.0 | 73.1 |

GHSL e nosso construído não medem o mesmo: o GHSL com limiar de 20% por célula de 100 m exclui o casario de baixa densidade e os bairros periféricos de caniço que a classificação de 30 m capta, de modo que o nosso construído é maior que GHSL ≥ 2000 em todas as épocas e a concordância (F1) cresce com a densificação.

## 6. Comparação com Siueia et al. (2025), IO LULC 2017–2023

Siueia et al. (2025, tab. 2, p. 90; `fontes/fichas/siueia_2025.md`) usam o IO LULC 10 m recortado ao município de 658,12 km²; as colunas `io_*_nossa_mascara` recalculam as mesmas classes IO na nossa máscara municipal (HDX COD-AB, menor), como checagem de máscara. Arrozal e agricultura inundada entram em `flooded vegetation` no IO, não em `crops`; por isso `culturas` do IO é ≈ 1% do município.

| ano | siueia_culturas_km2 | io_culturas_nossa_mascara_km2 | io_inundada_km2 | siueia_construido_km2 | io_construido_nossa_mascara_km2 | nosso_construido_km2 | nosso_classe2_km2 | nosso_classe3_km2 |
|---|---|---|---|---|---|---|---|---|
| 2017 | 8.25 | 7.79 | 23.1 | 103.8 | 101.4 | 71.4 | 11.3 | 41.8 |
| 2018 | 5.72 | 5.19 | 23.3 | 109.0 | 106.4 |  |  |  |
| 2019 | 2.70 | 2.49 | 22.9 | 106.5 | 103.4 | 77.0 | 15.4 | 22.2 |
| 2020 | 5.23 | 5.09 | 21.6 | 118.5 | 115.1 | 80.2 | 24.3 | 43.4 |
| 2021 | 6.80 | 6.20 | 29.8 | 122.7 | 119.1 |  |  |  |
| 2022 | 9.54 | 8.61 | 23.0 | 130.1 | 125.9 |  |  |  |
| 2023 | 7.06 | 6.69 | 16.3 | 125.0 | 121.4 |  |  |  |

O nosso construído (2017–2020: 71–80 km²) é inferior ao do IO LULC (101–126 km² em 2017–2023). Parte da diferença está em píxeis que o IO 2020 marca como Built e o WorldCover 2021 como herbácea (Grassland): 44 km² no município, dos quais 23% têm GHSL ≥ 20% e 32% são construído na nossa classificação de 2020. Nossa classe agrícola (2+3) é maior que `crops` do IO, que exclui o arrozal inundado (`flooded vegetation`). Sem verdade de campo não se decide qual lado erra: a validação cega de 2020 (seção 8) é o árbitro.

## 7. Perímetros fixos (07b/07c): fração construída em três estimativas

Perímetros dentro do município, sem água permanente: (a) baixadas = DEM Copernicus ≤ 8 m e TPI < 0 (sensibilidade 6 e 10 m); (b) mangal de referência = WorldCover 2020 e GMW 1996; (c) feições agrícolas OSM (farmland, paddy, allotments, greenhouse_horticulture; farmyard e orchard fora). Estimativas: GHSL (fração construída média), classificação bruta e pós-processada; ano final 2025.

| perimetro | area_ha_2025 | ghsl_1985 | ghsl_2025 | bruta_1985 | bruta_2025 | final_1985 | final_2025 | var_pp_min | var_pp_max |
|---|---|---|---|---|---|---|---|---|---|
| baixada_dem<=10m_tpi<0 | 21,468.0 | 1.10 | 4.18 | 4.15 | 11.8 | 3.32 | 13.8 | 3.08 | 10.5 |
| baixada_dem<=6m_tpi<0 | 15,544.6 | 1.35 | 4.62 | 4.65 | 13.8 | 3.82 | 16.2 | 3.27 | 12.4 |
| baixada_dem<=8m_tpi<0 | 18,797.2 | 1.21 | 4.33 | 4.17 | 12.3 | 3.40 | 14.4 | 3.12 | 11.0 |
| mangal_ref_wc2020_gmw1996 | 4,677.7 | 0.02 | 0.07 | 1.44 | 0.99 | 0.85 | 4.31 | -0.45 | 3.46 |
| municipio_total | 60,232.1 | 1.22 | 4.35 | 5.18 | 11.8 | 3.97 | 14.3 | 3.13 | 10.3 |
| osm_agricola | 895.7 | 0.04 | 0.89 | 0.05 | 0.48 | 0.05 | 0.25 | 0.20 | 0.85 |

Percentuais de área construída no perímetro; `var_pp` = variação 1985→2025 em pontos percentuais (mínimo e máximo entre as três estimativas). Série completa em `dados/proc/areas/envelopes_comparacao.csv`.

Duas ressalvas. O GHSL dá níveis cerca de três vezes menores que a classificação (conceito de superfície edificada por célula de 100 m), mas a mesma direção. No mangal de referência a estimativa pós-processada cresce mais que a bruta: dos 2,240 píxeis do mangal construídos em 2025 na classificação final, 100% foram construído bruto em alguma época e 436 já eram construído em 1985; a monotonia acumula, ao longo de 14 épocas, qualquer comissão que se repita em 2 de 3 épocas. O GHSL é ≈ 0 no mangal, então a variação aí é provavelmente erro de classificação e não perda de mangal; não usar o perímetro do mangal como medida de pressão construída sem validação.

## 7.1 Frentes de conversão (agricultura → construído, 2+3 → 1)

| t0 | t1 | anos | ha_agri_para_construido | ha_agri_ano | ha_zv_para_construido |
|---|---|---|---|---|---|
| 1979 | 1985 | 6 | 135.6 | 22.6 | 25.5 |
| 1985 | 1990 | 5 | 7.11 | 1.42 | 3.78 |
| 1990 | 1995 | 5 | 8.46 | 1.69 | 0.45 |
| 1995 | 1997 | 2 | 5.13 | 2.56 | 3.15 |
| 1997 | 2000 | 3 | 39.8 | 13.3 | 33.0 |
| 2000 | 2005 | 5 | 79.4 | 15.9 | 0.54 |
| 2005 | 2007 | 2 | 3.24 | 1.62 | 1.53 |
| 2007 | 2010 | 3 | 22.6 | 7.53 | 20.9 |
| 2010 | 2015 | 5 | 73.2 | 14.6 | 31.5 |
| 2015 | 2017 | 2 | 16.9 | 8.46 | 9.99 |
| 2017 | 2019 | 2 | 114.8 | 57.4 | 59.4 |
| 2019 | 2020 | 1 | 9.09 | 9.09 | 0.45 |
| 2020 | 2025 | 5 | 139.3 | 27.9 | 60.4 |
| 2025 | 2026 | 1 | 0.00 | 0.00 | 0.00 |

Intervalos curtos amplificam as diferenças entre composições; usar os intervalos 1985→2025 e 1990→2025 (`conversao.csv`).

## 9. Problemas conhecidos

- **Cenas de estação seca (2005, 2007).** As cenas únicas de out/2005 e ago/2007 inflam o construído bruto (vegetação seca/queimada); a regra 1 da 06b remove parte e a monotonia propaga o resto. O construído final salta de 36 km² (2000) para 53 km² (2005), mais que os 5 km² de 2005 a 2010: resíduo provável de comissão em 2005.
- **1985** vem de uma cena de 1984 (GeoMAD inexistente), com ~1% de nuvens no NE (sem dado, não classificado).
- **2010** e **1990**: GeoMAD de poucas observações (faixas SLC-off do Landsat 7 / COUNT 3); o mar é corrigido pela regra 0.
- **Classe 3** mostra manchas anelares no NE do bbox (fora do perímetro urbano), de natureza não verificada (cicatrizes de queimada ou cultivo extensivo são hipóteses); a classe é indicativa.
- **Nuvem sobre o mar**: o erro conhecido de Maputo (nuvem → construído) não aparece nos mapas finais de 1985, 2000, 2019 e 2025 após a regra 0.

<!-- exatidao_2020:inicio -->
## 8. Exatidão e áreas ajustadas de 2020 (validação cega)

Gerado por `scripts/11_avaliacao_exatidao.py`. Amostra estratificada pela classe mapeada de 2020 (`class_final`), legenda agregada, rotulada às cegas por interpretação visual de chips Sentinel-2 10 m / Landsat 30 m. Pontos: 280; indeterminados excluídos: 0; sem rótulo: 0; usados: 280. Estimadores de Olofsson et al. (2014); IC 95% = ±1,96 EP. Linhas = classe mapeada, colunas = referência.

### 8.1 Âmbito: Município da Beira (polígono HDX COD-AB, com água interior)

Amostra sorteada só dentro do município; estratos com menos de 2 pontos não têm erro padrão (células vazias).

Matriz de confusão (contagem de pontos):

| mapa \ referência | 1 | 2 | 3 | 45 | 6 | 7 | total |
|---|---|---|---|---|---|---|---|
| 1 Construído | 47 | 2 | 2 | 3 | 1 | 5 | 60 |
| 2 Zonas verdes | 5 | 1 | 6 | 47 | 0 | 1 | 60 |
| 3 Sequeiro e mosaico | 7 | 0 | 26 | 2 | 0 | 5 | 40 |
| 45 Vegetação não cultivada | 14 | 0 | 17 | 25 | 0 | 4 | 60 |
| 6 Água | 0 | 0 | 0 | 7 | 18 | 5 | 30 |
| 7 Solo exposto | 0 | 0 | 0 | 0 | 0 | 30 | 30 |
| total | 73 | 3 | 51 | 84 | 19 | 50 | 280 |

Exatidão global (ponderada pela área): 47.4% ± 9.4 p.p.

| classe | área mapeada (ha) | área ajustada (ha) | IC 95% (± ha) | exatidão do usuário (%) | ± | exatidão do produtor (%) | ± |
|---|---|---|---|---|---|---|---|
| 1 Construído | 8,019 | 17,657 | 4,920 | 78.3 | 10.5 | 35.6 | 10.2 |
| 2 Zonas verdes | 2,425 | 308 | 376 | 1.7 | 3.3 | 13.1 | 27.3 |
| 3 Sequeiro e mosaico | 4,341 | 15,977 | 5,189 | 65.0 | 15.0 | 17.7 | 6.6 |
| 45 Vegetação não cultivada | 44,629 | 21,279 | 5,647 | 41.7 | 12.6 | 87.4 | 4.1 |
| 6 Água | 708 | 559 | 291 | 60.0 | 17.8 | 76.1 | 36.1 |
| 7 Solo exposto | 594 | 4,939 | 2,934 | 100.0 | 0.0 | 12.0 | 7.1 |

<!-- exatidao_2020:fim -->

<!-- sensibilidade_2020:inicio -->
## 9. Sensibilidade a rótulos de baixa confiança (validação cega de 2020)

Gerado por `scripts/11_avaliacao_exatidao.py --sem-baixa`. Os rótulos foram atribuídos por um agente automático de interpretação visual de imagens, cego ao mapa; recomenda-se revisão humana de uma subamostra. A tabela compara o conjunto completo com o conjunto sem os rótulos de confiança 'baixa'.

Distribuição da confiança dos rótulos (todos os pontos rotulados): alta 15, baixa 156, media 109.

### Município da Beira (com água interior)

| medida | todos os rótulos | sem confiança baixa |
|---|---|---|
| pontos usados | 280 | 124 |
| exatidão global (%) | 47.4 ± 9.4 | 63.6 ± 18.2 |
| UA classe 1 (construído) (%) | 78.3 ± 10.5 | 95.2 ± 6.5 |
| PA classe 1 (construído) (%) | 35.6 ± 10.2 | 40.6 ± 20.8 |
| UA classe 2 (zonas verdes) (%) | 1.7 ± 3.3 | 7.1 ± 14.0 |
| PA classe 2 (zonas verdes) (%) | 13.1 ± 27.3 | 100.0 ± 0.0 |
| área ajustada classe 2 (ha) | 308 ± 376 | 173 ± 340 |

<!-- sensibilidade_2020:fim -->
