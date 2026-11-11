"""07 - Areas por classe/epoca/unidade, matrizes de transicao, taxas de conversao e raster de ano de conversao (Beira).

Ambitos: 'bbox' (grade inteira) e 'municipio' (poligono do Municipio da Beira, HDX COD-AB, camada `municipio`;
inclui os trechos de agua do municipio). Unidades: postos administrativos urbanos (camada `distritos`, Urbano 1-5) e
bairros (camada `bairros`). Area de cada pixel = 0,09 ha. Classe 0 = sem dado.
Entrada: --entrada (padrao class_final = saida de 06b_consistencia.py; "class" = classificacao bruta).
Saidas em dados/proc/areas/ (tabelas com legenda completa e areas_agregado_*.csv com legenda agregada:
1 Construido; 2 Agricultura de baixada/horticola; 3 Cultivo/mosaico de terra firme; 45 Vegetacao natural e zonas
humidas (4+5, inclui mangal); 6 Agua; 7 Solo exposto) e <entrada>/conversao_agri_construido.tif.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features

from comum import *  # noqa

CLS = PROC / "class_final"   # sobrescrito por --entrada
AREAS = PROC / "areas"
HA = RES * RES / 1e4
PARES_EXTRA = [(1985, 2025), (1985, 2026), (1990, 2025)]
AGR = {0: 0, 1: 1, 2: 2, 3: 3, 4: 45, 5: 45, 6: 6, 7: 7}
AGR_NOME = {0: "Sem dado", 1: "Construído", 2: "Agricultura de baixada/hortícola", 3: "Cultivo e mosaico de terra firme (indicativo)",
            45: "Vegetação natural e zonas húmidas (4+5, inclui mangal)", 6: "Água", 7: "Solo exposto, areia e praia"}
AGR_COD = [0, 1, 2, 3, 45, 6, 7]
LUT = np.array([AGR[k] for k in range(8)], dtype="uint8")
LUTI = np.array([0, 1, 2, 3, 4, 4, 5, 6], dtype="uint8")  # classe -> indice em AGR_COD


def agrega_cnt(cnt):
    """cnt (..., 8) contagens por classe -> (..., 7) por classe agregada (0,1,2,3,45,6,7)."""
    out = np.stack([cnt[..., 0], cnt[..., 1], cnt[..., 2], cnt[..., 3], cnt[..., 4] + cnt[..., 5], cnt[..., 6], cnt[..., 7]], -1)
    return out


def le(ep):
    with rasterio.open(CLS / f"{ep}.tif") as s:
        return s.read(1)


def rast_id(gdf):
    shapes = ((g, i + 1) for i, g in enumerate(gdf.geometry))
    return features.rasterize(shapes, out_shape=SHAPE, transform=TRANSFORM, fill=0, dtype="int32")


def conta_unidades(cl, ids, n):
    m = ids > 0
    cnt = np.bincount((ids[m] - 1) * 8 + cl[m], minlength=n * 8).reshape(n, 8)
    return cnt


def main():
    global CLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="class_final", help="subpasta de dados/proc com <epoca>.tif (class_final ou class)")
    args = ap.parse_args()
    CLS = PROC / args.entrada
    log("entrada:", CLS)
    AREAS.mkdir(parents=True, exist_ok=True)
    cl = {ep: le(ep) for ep in EPOCAS}
    dist = gpd.read_file(PROC / "limites.gpkg", layer="distritos").reset_index(drop=True)
    dist["adm2_name"] = dist["adm3_name"]   # posto administrativo urbano (Urbano 1-5)
    cid_ids = rast_id(dist)
    muni = gpd.read_file(PROC / "limites.gpkg", layer="municipio")
    cidade = rast_id(muni) > 0
    bairros = gpd.read_file(PROC / "limites.gpkg", layer="bairros").reset_index(drop=True)
    b_ids = rast_id(bairros)
    log("pixels municipio:", int(cidade.sum()), "ha:", round(cidade.sum() * HA), "| soma postos:", int((cid_ids > 0).sum()))

    # ---- areas por classe/epoca ----
    linhas = []; ld = []; lb = []
    for ep in EPOCAS:
        c = cl[ep]
        for amb, msk in (("bbox", np.ones(SHAPE, bool)), ("municipio", cidade)):
            cnt = np.bincount(c[msk], minlength=8)
            for k in range(8):
                linhas.append(dict(epoca=ep, ambito=amb, classe=k, ha=round(cnt[k] * HA, 2)))
        cd = conta_unidades(c, cid_ids, len(dist))
        for i, nome in enumerate(dist.adm2_name):
            for k in range(8):
                ld.append(dict(epoca=ep, unidade=nome, classe=k, ha=round(cd[i, k] * HA, 2)))
        for grupo, gdf, ids in (("bairro", bairros, b_ids),):
            cb = conta_unidades(c, ids, len(gdf))
            for i, (nome, pc) in enumerate(zip(gdf.adm4_name, gdf.adm4_pcode)):
                for k in range(8):
                    lb.append(dict(epoca=ep, grupo=grupo, unidade=nome, pcode=pc, classe=k, ha=round(cb[i, k] * HA, 2)))
    pd.DataFrame(linhas).to_csv(AREAS / "areas_classe_epoca.csv", index=False)
    pd.DataFrame(ld).to_csv(AREAS / "areas_distrito.csv", index=False)
    pd.DataFrame(lb).to_csv(AREAS / "areas_bairro.csv", index=False)

    # ---- tabelas com legenda agregada ----
    la = []; lda = []; lba = []
    for ep in EPOCAS:
        c = cl[ep]
        nota = "1979 excluida das series quantitativas (MSS, legenda reduzida: 3 = toda a vegetacao, 45 ausente)" if ep == 1979 else ""
        for amb, msk in (("bbox", np.ones(SHAPE, bool)), ("municipio", cidade)):
            cnt = agrega_cnt(np.bincount(c[msk], minlength=8))
            tot = cnt[1:].sum()
            for j, k in enumerate(AGR_COD):
                la.append(dict(epoca=ep, ambito=amb, classe_agr=k, nome=AGR_NOME[k], ha=round(cnt[j] * HA, 2),
                               pct_com_dado=round(100 * cnt[j] / tot, 3) if k else np.nan, nota=nota))
        cd = agrega_cnt(conta_unidades(c, cid_ids, len(dist)))
        for i, nome in enumerate(dist.adm2_name):
            for j, k in enumerate(AGR_COD):
                lda.append(dict(epoca=ep, unidade=nome, classe_agr=k, ha=round(cd[i, j] * HA, 2)))
        for grupo, gdf, ids in (("bairro", bairros, b_ids),):
            cb = agrega_cnt(conta_unidades(c, ids, len(gdf)))
            for i, (nome, pc) in enumerate(zip(gdf.adm4_name, gdf.adm4_pcode)):
                for j, k in enumerate(AGR_COD):
                    lba.append(dict(epoca=ep, grupo=grupo, unidade=nome, pcode=pc, classe_agr=k, ha=round(cb[i, j] * HA, 2)))
    pd.DataFrame(la).to_csv(AREAS / "areas_agregado_classe_epoca.csv", index=False)
    pd.DataFrame(lda).to_csv(AREAS / "areas_agregado_distrito.csv", index=False)
    pd.DataFrame(lba).to_csv(AREAS / "areas_agregado_bairro.csv", index=False)

    # ---- transicoes ----
    pares = [(EPOCAS[i], EPOCAS[i + 1]) for i in range(len(EPOCAS) - 1)] + PARES_EXTRA
    conv = []; agr_trans = []
    for t0, t1 in pares:
        a, b = cl[t0], cl[t1]
        rows = []
        for amb, msk in (("bbox", np.ones(SHAPE, bool)), ("municipio", cidade)):
            m = (a[msk].astype(int) * 8 + b[msk]).ravel()
            mat = np.bincount(m, minlength=64).reshape(8, 8)
            for i in range(8):
                for j in range(8):
                    rows.append(dict(ambito=amb, de=i, para=j, ha=round(mat[i, j] * HA, 2)))
            ini2 = mat[2, :].sum() * HA; ini23 = (mat[2, :].sum() + mat[3, :].sum()) * HA
            zv = mat[2, 1] * HA; ag = (mat[2, 1] + mat[3, 1]) * HA
            anos = t1 - t0
            nota = ""
            if t0 == 1979:
                nota = "1979: classe 3 = toda a vegetacao fora da baixada; agricultura 2+3 nao comparavel; usar so a classe 2"
            conv.append(dict(ambito=amb, t0=t0, t1=t1, anos=anos, consecutivo=(t1 == EPOCAS[EPOCAS.index(t0) + 1]) if t0 in EPOCAS and t1 in EPOCAS and EPOCAS.index(t1) == EPOCAS.index(t0) + 1 else False,
                             ha_agri_para_construido=round(ag, 2), ha_agri_ano=round(ag / anos, 2),
                             pct_agri_inicial=round(100 * ag / ini23, 2) if ini23 else np.nan,
                             ha_zv_para_construido=round(zv, 2), ha_zv_ano=round(zv / anos, 2),
                             pct_zv_inicial=round(100 * zv / ini2, 2) if ini2 else np.nan,
                             area_agri_inicial_ha=round(ini23, 2), area_zv_inicial_ha=round(ini2, 2), nota=nota))
        pd.DataFrame(rows).to_csv(AREAS / f"transicoes_{t0}_{t1}.csv", index=False)
        for amb, msk in (("bbox", np.ones(SHAPE, bool)), ("municipio", cidade)):
            ia = LUTI[a[msk]].astype(int); ib = LUTI[b[msk]]
            mat = np.bincount(ia * 7 + ib, minlength=49).reshape(7, 7)
            for i, ki in enumerate(AGR_COD):
                for j, kj in enumerate(AGR_COD):
                    agr_trans.append(dict(t0=t0, t1=t1, ambito=amb, de=ki, para=kj, ha=round(mat[i, j] * HA, 2)))
    pd.DataFrame(conv).to_csv(AREAS / "conversao.csv", index=False)
    pd.DataFrame(agr_trans).to_csv(AREAS / "areas_agregado_transicoes.csv", index=False)

    # ---- perda de classe 2 por bairro, 1990 -> 2025 ----
    a, b = cl[1990], cl[2025]
    lp = []
    for grupo, gdf, ids in (("bairro", bairros, b_ids),):
        for i, (nome, pc) in enumerate(zip(gdf.adm4_name, gdf.adm4_pcode)):
            m = ids == (i + 1)
            if not m.any():
                continue
            a2 = (a[m] == 2); b2 = (b[m] == 2)
            lp.append(dict(grupo=grupo, unidade=nome, pcode=pc, area_unidade_ha=round(m.sum() * HA, 1),
                           zv_1990_ha=round(a2.sum() * HA, 2), zv_2025_ha=round(b2.sum() * HA, 2),
                           variacao_liquida_ha=round((b2.sum() - a2.sum()) * HA, 2),
                           perda_bruta_ha=round((a2 & ~b2).sum() * HA, 2),
                           convertida_construido_ha=round(((a[m] == 2) & (b[m] == 1)).sum() * HA, 2),
                           ganho_bruto_ha=round((~a2 & b2).sum() * HA, 2)))
    pd.DataFrame(lp).sort_values("convertida_construido_ha", ascending=False).to_csv(AREAS / "perda_bairro.csv", index=False)

    # ---- raster do ano de conversao agricola -> construido (regra estavel) ----
    n = len(EPOCAS)
    stack = np.stack([cl[ep] for ep in EPOCAS], 0)
    estavel = np.zeros((n, ) + SHAPE, bool)  # construido neste e em todas as epocas seguintes
    acc = np.ones(SHAPE, bool)
    for i in range(n - 1, -1, -1):
        acc = acc & (stack[i] == 1)
        estavel[i] = acc
    out = np.zeros(SHAPE, "uint16")
    for i in range(1, n):
        prev = stack[i - 1]
        agri_prev = np.isin(prev, (2, 3)) if EPOCAS[i - 1] != 1979 else (prev == 2)
        m = estavel[i] & agri_prev & (out == 0)
        out[m] = EPOCAS[i]
    p = perfil(count=1, dtype="uint16", nodata=None)
    p.pop("nodata", None)
    with rasterio.open(CLS / "conversao_agri_construido.tif", "w", **{k: v for k, v in p.items() if v is not None}) as d:
        d.write(out, 1)
        d.set_band_description(1, "ano da primeira conversao estavel agricola(2/3)->construido; 0 = nenhuma")
    cnt = pd.Series(out[out > 0]).value_counts().sort_index()
    log("conversao agri->construido (px por ano):", (cnt * HA).round(0).to_dict())
    log("ok")


if __name__ == "__main__":
    main()
