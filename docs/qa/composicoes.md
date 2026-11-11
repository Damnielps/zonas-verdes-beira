# QA das composições (30 m, EPSG:32736)

Gerado por `scripts/04_qa_composicoes.py`. NaN % = fração da grade do bbox sem dado válido na banda vermelha; COUNT = número de observações por píxel (GeoMAD: banda COUNT; cena única: 1; 2026: observações válidas). Coluna Água: sobre a máscara de água do WorldCover 2020 (classe 80: mar, estuário, rios), % de píxeis sem dado e % com refletância vermelha > 0,12 (indício de nuvem/espuma/sedimento, lição de Maputo: nuvem sobre o mar virou 'construído'); é diagnóstico, não máscara.

| Época | Fonte | Sensor | Datas | NaN % | COUNT mediana | Água: NaN % / vermelho>0,12 % | Substituição / notas |
|---|---|---|---|---|---|---|---|
| 1979 | Planetary Computer landsat-c2-l1 LM02_L1TP_179074_19790829_02_T2 (Tier 2) (LM02_L1TP_179074_19790829_02_T2) | Landsat 2 MSS (60 m) | 1979-08-29 | 0.00 | 1 | 0.0 / 0.7 | TOA, (M*DN+A)/sin(elev solar); verde=B4, vermelho=B5, nir=B7 (0,8-1,1um; B6 0,7-0,8um nao usada); 60 m -> grade 30 m por reamostragem bilinear; píxeis com DN<70% ou >135% da mediana vertical de 6 linhas vizinhas (linhas de perda de dados/picos do MSS) substituídos por essa mediana; blue/swir ausentes. Cena de 29/ago/1979 (0% nuvem) como proxy do censo de 1980 |
| 1985 | Planetary Computer landsat-c2-l2 LT05_L2SP_167074_19840601_02_T1 (LT05_L2SP_167074_19840601_02_T1) | landsat-5 | 1984-06-01 | 1.07 | 1 | 0.3 / 1.6 | GeoMAD 1985 inexistente (sem observações no bbox; a coleção gm_ls5_ls7_annual vazia em 1985); substituído por TM de 1984-06-01 (nuvem/sombra 1,1% no bbox; única cena L2 de estação seca de 1984-85; alternativa 1986-05-06 0% descartada por distar mais de 1985). ~1% do bbox mascarado como nuvem/sombra (NE) e névoa fina residual sobre o mar a E/NE; 1984 é o ano mais próximo com cena de estação seca de baixa nebulosidade |
| 1990 | Digital Earth Africa gm_ls5_ls7_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (ae45182c-de73-5616-8389-a5639bac6ccf,d5527e05-c7e4-509d-a46f-c0a491134def) | Landsat 5/7 TM/ETM+ | 1990-01-01/1990-12-31 | 0.57 | 3 | 0.0 / 1.1 | COUNT mediana 3; ~0,6% do bbox sem dado (nuvens mascaradas, manchas no NE; locais distintos dos de 1985); água do estuário/mar com blocos de turbidez distintos entre datas (mosaico de poucas observações) |
| 1995 | Digital Earth Africa gm_ls5_ls7_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (15c1726b-4a99-5a4c-87d3-fd057332ee8d,f6274d4a-de22-5697-875c-b985fcb240a0) | Landsat 5/7 TM/ETM+ | 1995-01-01/1995-12-31 | 0.00 | 7 | 0.0 / 0.7 | - |
| 1997 | Digital Earth Africa gm_ls5_ls7_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (0b695aee-a754-5000-86c1-02fde4da1904,b57a7de2-cb4b-52b4-9c1a-8e269943c709) | Landsat 5/7 TM/ETM+ | 1997-01-01/1997-12-31 | 0.02 | 5 | 0.0 / 0.9 | - |
| 2000 | Digital Earth Africa gm_ls5_ls7_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (0d62bbe9-e436-54ff-a46b-668acd5930f2,3ea25163-e473-5c6b-8e3a-c9e336ff4fd0) | Landsat 5/7 TM/ETM+ | 2000-01-01/2000-12-31 | 0.00 | 7 | 0.0 / 1.0 | - |
| 2005 | Planetary Computer landsat-c2-l2 LT05_L2SP_167074_20051001_02_T1 (LT05_L2SP_167074_20051001_02_T1) | landsat-5 | 2005-10-01 | 0.01 | 1 | 0.0 / 1.6 | GeoMAD 2005 rejeitado (faixas SLC-off do Landsat 7 visíveis sobre o mar/estuário); substituído por TM de 2005-10-01 (nuvem/sombra 0% no bbox).  |
| 2007 | Planetary Computer landsat-c2-l2 LT05_L2SP_167074_20070820_02_T1 (LT05_L2SP_167074_20070820_02_T1) | landsat-5 | 2007-08-20 | 0.02 | 1 | 0.0 / 0.6 | GeoMAD 2007 rejeitado (faixas SLC-off do Landsat 7 visíveis sobre o mar/estuário); substituído por TM de 2007-08-20 (nuvem/sombra 0% no bbox).  |
| 2010 | Digital Earth Africa gm_ls5_ls7_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (2dd4b685-e070-549b-927a-c9a26c31ae17,c43be0a0-3642-5696-8735-cd3af5e73d59) | Landsat 5/7 TM/ETM+ | 2010-01-01/2010-12-31 | 0.00 | 7 | 0.0 / 2.2 | GeoMAD (mistura TM/ETM+ SLC-off, COUNT mediana 7): faixas SLC-off residuais, visíveis sobretudo sobre o mar/estuário, terra sem faixas evidentes; tentativas de substituição (TM 2010-05-08 + preenchimento ETM+; mediana das cenas abr-out) foram piores (NaN e faixas na terra) e foram descartadas; tratar com máscara de mar em 06b |
| 2015 | Digital Earth Africa gm_ls8_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (04255fe4-a3d5-50e0-aff6-97495890f111,fa0e4473-c8cd-5344-95d5-7514d60bf3fb) | Landsat 8 OLI | 2015-01-01/2015-12-31 | 0.01 | 11 | 0.0 / 1.2 | - |
| 2017 | Digital Earth Africa gm_ls8_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (69d8cf65-c731-5de8-b69f-e116d26ac345,c967f8a8-75f2-5814-a29f-ba231a68853e) | Landsat 8 OLI | 2017-01-01/2017-12-31 | 0.10 | 10 | 0.2 / 0.8 | - |
| 2019 | Digital Earth Africa gm_ls8_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (8d237338-0d34-553e-86df-796c533ff54c,c2a9ebc8-e6ad-5a06-9de5-2b700950f3d2) | Landsat 8 OLI | 2019-01-01/2019-12-31 | 0.00 | 14 | 0.0 / 1.0 | - |
| 2020 | Digital Earth Africa gm_ls8_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (c16b3ef7-bb41-5fbb-b421-36299fdf0c3a,d8b5eb2c-2dba-5567-98ab-da38e1eb393e) | Landsat 8 OLI | 2020-01-01/2020-12-31 | 0.00 | 9 | 0.0 / 0.8 | - |
| 2025 | Digital Earth Africa gm_ls8_ls9_annual v1.0.0 tiles x215y051+x216y051 (mosaico) (7bc6f898-d5a4-57ab-8158-7dabd961fc04,b29e54ad-6162-5e1e-a2fb-45ac46cfc64c) | Landsat 8/9 OLI | 2025-01-01/2025-12-31 | 0.00 | 15 | 0.0 / 0.6 | - |
| 2026 | Planetary Computer landsat-c2-l2, mediana de 12 cenas (05-09/2026), p167 r074, nuvem<30%, QA_PIXEL (LC08_L2SP_167074_20260504_02_T1,LC08_L2SP_167074_20260520_02_T1,LC09_L2SP_167074_20260528_02_T1,LC08_L2SP_167074_20260605_02_T1,LC09_L2SP_167074_20260613_02_T1,LC09_L2SP_167074_20260629_02_T1,LC09_L2SP_167074_20260715_02_T1,LC08_L2SP_167074_20260723_02_T1,LC09_L2SP_167074_20260731_02_T1,LC09_L2SP_167074_20260816_02_T1,LC09_L2SP_167074_20260901_02_T1,LC09_L2SP_167074_20260917_02_T1) | landsat-8 + landsat-9 | 2026-05-04/2026-09-17 | 0.00 | 11 | 0.0 / 0.7 | - |

## Percentis 2-98% por banda (reflectância)

| Época | Bandas |
|---|---|
| 1979 | green 0.077-0.134; red 0.058-0.118; nir 0.031-0.198 |
| 1985 | blue 0.021-0.079; green 0.038-0.111; red 0.034-0.117; nir 0.027-0.336; swir1 0.007-0.241; swir2 0.004-0.166 |
| 1990 | blue 0.028-0.084; green 0.045-0.112; red 0.034-0.115; nir 0.019-0.311; swir1 0.007-0.261; swir2 0.005-0.176 |
| 1995 | blue 0.033-0.079; green 0.051-0.107; red 0.036-0.115; nir 0.018-0.282; swir1 0.006-0.275; swir2 0.005-0.199 |
| 1997 | blue 0.034-0.079; green 0.048-0.103; red 0.032-0.116; nir 0.023-0.290; swir1 0.009-0.271; swir2 0.007-0.184 |
| 2000 | blue 0.037-0.080; green 0.052-0.105; red 0.039-0.115; nir 0.026-0.294; swir1 0.010-0.266; swir2 0.008-0.187 |
| 2005 | blue 0.039-0.083; green 0.056-0.114; red 0.041-0.130; nir 0.018-0.252; swir1 0.004-0.306; swir2 0.003-0.252 |
| 2007 | blue 0.028-0.072; green 0.044-0.107; red 0.020-0.120; nir 0.009-0.269; swir1 0.001-0.295; swir2 0.000-0.229 |
| 2010 | blue 0.039-0.088; green 0.055-0.114; red 0.038-0.128; nir 0.025-0.315; swir1 0.014-0.293; swir2 0.011-0.214 |
| 2015 | blue 0.022-0.091; green 0.047-0.116; red 0.026-0.125; nir 0.009-0.293; swir1 0.007-0.296; swir2 0.005-0.229 |
| 2017 | blue 0.018-0.077; green 0.038-0.104; red 0.016-0.112; nir 0.003-0.324; swir1 0.006-0.249; swir2 0.004-0.175 |
| 2019 | blue 0.026-0.084; green 0.048-0.115; red 0.031-0.130; nir 0.015-0.296; swir1 0.010-0.297; swir2 0.008-0.226 |
| 2020 | blue 0.018-0.086; green 0.043-0.117; red 0.021-0.132; nir 0.009-0.319; swir1 0.009-0.296; swir2 0.007-0.224 |
| 2025 | blue 0.019-0.080; green 0.038-0.110; red 0.025-0.122; nir 0.009-0.318; swir1 0.008-0.266; swir2 0.006-0.197 |
| 2026 | blue 0.020-0.077; green 0.037-0.107; red 0.009-0.121; nir 0.000-0.315; swir1 0.001-0.266; swir2 0.002-0.198 |

## Notas

- 1979 (MSS, Landsat 2; proxy do censo de 1980): sem banda azul; quick-look 'rgb' é pseudo-cor (R=vermelho, G=verde, B=verde); falsa-cor = NIR-vermelho-verde.
- Quick-looks com estiramento 2-98% por banda e por imagem; NaN em branco.
- Painel de contato: `dados/fig/qa/painel_rgb.png`.
- Grade: bbox 34,72-35,10 E, -19,95 a -19,60 S, EPSG:32736, 30 m. Tiles GeoMAD DE Africa que cobrem o bbox: x215y051 e x216y051 (mosaico por NaN-fill). Cena Landsat que cobre 100% do bbox: path/row 167/074 (167/073 cobre ~3%). GeoMAD 1985 não existe (coleção vazia); a coleção L2 do Planetary Computer começa em 1984.
- GeoMAD 2005 e 2007 (e o 2010 em menor grau) mostram faixas SLC-off do Landsat 7 sobre o mar; 2005 e 2007 foram substituídos por cena TM única; 2010 manteve o GeoMAD (alternativas pioraram a terra).
- Água (WorldCover 2020, classe 80): a coluna 'vermelho>0,12' inclui sedimento do estuário do Púngue e espuma de arrebentação, não só nuvem; é limite superior de contaminação por nuvem sobre a água.
- Cor da água varia muito entre épocas (turbidez, maré, fitoplâncton/areias submersas): efeito esperado em composições de poucas observações; a classe água deve ser definida por MNDWI/NIR, não por cor.
- Auxiliares (03): Copernicus DEM 30 m, WorldCover 2020/2021, IO LULC 2017-2023, ESA CCI LC 1995-2020, WSF Evolution, GLAD GLCLUC 2000-2020 (tile 10S_030E), GHSL built-up 1975-2025 (tile R12_C22), Sentinel-2 GeoMAD 2020 10 m (`dados/proc/s2_2020_10m.tif`).
