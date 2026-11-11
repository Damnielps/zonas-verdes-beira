"""05 - Rotulos de treino (pontos) por epoca.

Beira: ancora 2020 por concordancia WorldCover 2021 (e 2020) x IO LULC 2020 x GHSL 2020 x OSM; propagacao para as
demais epocas por distancia espectral (angulo) e consistencia com GHSL(t). Agua (classe 6) em cada epoca por
MNDWI/NIR, nao por cor (turbidez do Pungue). Mangal de referencia = WorldCover 2020 (95) uniao Global Mangrove Watch
v3 1996 (Zenodo 10.5281/zenodo.6894273, CC BY 4.0), baixado para dados/raw/gmw_v3/ se ausente.
Saidas: dados/proc/rotulos/treino_<epoca>.parquet (x, y, classe, origem, sub), pool_2020.parquet,
rotulos_resumo.json, mangal_ref.tif; figura dados/fig/class/rotulos_2v3.png.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features
from scipy import ndimage as ndi

from comum import *  # noqa

ROT = PROC / "rotulos"
FIGC = FIG / "class"
SEED = 42
N_ANCORA = 1500       # pontos por classe na ancora 2020 (spec)
N_POOL = 6000         # reserva de candidatos por classe para propagar (ver docs/qa/classificacao.md)
N_MAX_EPOCA = 1500    # maximo de pontos propagados por classe e epoca
PERC_ANG = 20         # percentil (spec) dos pontos pseudo-invariantes (nivel inicial da escada)
PERC_NATURAL = 95      # classes 4, 5 e 7 (nao construidas, nao agricolas): limiar angular no p95 dos invariantes (ver nota em docs/qa/classificacao.md)
ESCADA = [20, 50, 80]  # se o limiar p20 deixa alguma classe com poucos pontos, sobe-se a escada
MIN_RET = 150          # retencao minima por classe (ou 50 % do pool, se menor)
MIN_EROSAO = 300       # classes com menos pixeis apos erosao de 1 px ficam sem erosao
ELEV_BAIXADA = 8.0    # m (Beira: mediana do municipio ~8 m; sensibilidade 6 e 10 m em 07b)
TPI_BAIXADA = 0.0
BUF_WETLAND = 100.0   # m
GHSL_CONST = 2000.0   # m2 por celula de 100 m (>=20 %)
GHSL_AGRI = 500.0
GHSL_ANO = {1979: 1980, 1985: 1985, 1990: 1990, 1995: 1995, 1997: 1995, 2000: 2000, 2005: 2005, 2007: 2005,
            2010: 2010, 2015: 2015, 2017: 2015, 2019: 2020, 2020: 2020, 2025: 2025, 2026: 2025}
GMW_URL = "https://zenodo.org/api/records/6894273/files/gmw_v3_1996_gtiff.zip/content"
GMW_DIR = RAW / "gmw_v3"
MANGAL_REF = PROC / "rotulos" / "mangal_ref.tif"
WATER_NIR_MAX = 0.15   # agua: MNDWI (NDWI verde-NIR no MSS) > 0 e NIR < 0,15
BANDAS_ANG = ["green", "red", "nir", "swir1", "swir2"]
IDXB = {b: i for i, b in enumerate(BANDAS)}

def le(path, b=1):
    with rasterio.open(path) as s:
        return s.read(b)


def le_comp(ep):
    with rasterio.open(COMP / f"{ep}.tif") as s:
        a = s.read()
    return {b: a[i] for b, i in IDXB.items()}


def ghsl(ano):
    return le(VAL / f"ghsl_built_{ano}.tif")


def ero(m, it=1):
    return ndi.binary_erosion(m, structure=np.ones((3, 3), bool), iterations=it, border_value=0)


def rast_geom(geoms):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros(SHAPE, bool)
    return features.rasterize(((g, 1) for g in geoms), out_shape=SHAPE, transform=TRANSFORM, fill=0,
                              dtype="uint8").astype(bool)


def xy_de(idx):
    r, c = np.unravel_index(idx, SHAPE)
    x = X0 + (c + 0.5) * RES
    y = Y1 - (r + 0.5) * RES
    return x, y


def rc_de(x, y):
    c = np.floor((np.asarray(x) - X0) / RES).astype(int)
    r = np.floor((Y1 - np.asarray(y)) / RES).astype(int)
    return r, c


def amostra(mask, n, rng):
    idx = np.flatnonzero(mask.ravel())
    if len(idx) > n:
        idx = rng.choice(idx, n, replace=False)
    return np.sort(idx)


def cap(df, n):
    return pd.concat([d.sample(min(len(d), n), random_state=SEED) for _, d in df.groupby("classe")],
                     ignore_index=True)


def baixada_regra(dem, tpi, wet, lim=None):
    lim = ELEV_BAIXADA if lim is None else lim
    return ((dem <= lim) & (tpi < TPI_BAIXADA)) | wet


def osm_wet_buf():
    """Buffer de 100 m de zonas humidas OSM de agua doce (exclui tidalflat e mangrove, que nao sao baixada cultivavel)."""
    wet = gpd.read_file(PROC / "osm.gpkg", layer="osm_wetland")
    wet = wet[~wet.wetland.isin(["tidalflat", "mangrove"])]
    return rast_geom(wet.geometry.buffer(BUF_WETLAND))


def agua_indice(comp, r, c):
    """Teste de agua por indice (nao por cor): MNDWI (verde-SWIR1) se houver SWIR1 na epoca, senao NDWI (verde-NIR); NIR baixo."""
    g = comp["green"][r, c]; n = comp["nir"][r, c]; s1 = comp["swir1"][r, c]
    if np.isfinite(comp["swir1"]).mean() > 0.5:
        idx = (g - s1) / np.maximum(g + s1, 1e-6)
    else:
        idx = (g - n) / np.maximum(g + n, 1e-6)
    return np.isfinite(idx) & (idx > 0.0) & (n < WATER_NIR_MAX)


def baixa_gmw():
    """Baixa (idempotente) o GMW v3 1996 (GeoTIFF por tile) de Zenodo; devolve lista de /vsizip/ para os tiles da area."""
    import zipfile
    import requests
    GMW_DIR.mkdir(parents=True, exist_ok=True)
    z = GMW_DIR / "gmw_v3_1996_gtiff.zip"
    ok = False
    if z.exists():
        try:
            ok = zipfile.is_zipfile(z) and zipfile.ZipFile(z).testzip() is None
        except Exception:
            ok = False
    if not ok:
        log("baixando GMW v3 1996:", GMW_URL)
        with requests.get(GMW_URL, headers=HEADERS, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(z.with_suffix(".part"), "wb") as f:
                for ch in r.iter_content(1 << 20):
                    f.write(ch)
        z.with_suffix(".part").replace(z)
    else:
        log("GMW v3 1996 ja existe:", z)
    nomes = [n for n in zipfile.ZipFile(z).namelist() if n.lower().endswith(".tif")]
    sel = []
    for n in nomes:
        if "S20E034" in n or "S20E035" in n or "S19E034" in n or "S19E035" in n:
            sel.append(n)
    return z, nomes, sel


def mangal_referencia():
    """Mangal de referencia: WorldCover 2020 (95) uniao GMW v3 1996, na grade de 30 m (10 m -> 30 m: >= 50 % do pixel)."""
    if integro(MANGAL_REF):
        with rasterio.open(MANGAL_REF) as s:
            return s.read(1).astype(bool), json.loads(s.tags().get("fontes", "{}"))
    ROT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(VAL / "worldcover_2020.tif") as s:
        wc = s.read(1) == 95
    info = {"worldcover_2020_px": int(wc.sum())}
    gmw = np.zeros(SHAPE, bool)
    try:
        z, nomes, sel = baixa_gmw()
        info["gmw_tiles_no_zip"] = len(nomes)
        info["gmw_tiles_usados"] = sel
        for n in sel:
            with rasterio.open(f"/vsizip/{z}/{n}") as s:
                b = s.bounds
                if b.right < LON_MIN or b.left > LON_MAX or b.top < LAT_MIN or b.bottom > LAT_MAX:
                    continue
                gmw |= para_grade(s, resampling=Resampling.average, dtype="float32", dst_nodata=0.0, margem=600.0) >= 0.5
        info["gmw1996_px"] = int(gmw.sum()); info["gmw_fonte"] = "Zenodo 10.5281/zenodo.6894273 gmw_v3_1996_gtiff.zip (CC BY 4.0)"
    except Exception as e:  # sem GMW: so WorldCover (registrado)
        info["gmw_erro"] = repr(e)
        log("GMW indisponivel, mangal de referencia = so WorldCover 2020:", repr(e))
    ref = wc | gmw
    info["uniao_px"] = int(ref.sum()); info["intersecao_px"] = int((wc & gmw).sum())
    p = perfil(dtype="uint8", nodata=None)
    p.pop("nodata", None)
    with rasterio.open(MANGAL_REF, "w", **p) as d:
        d.write(ref.astype("uint8"), 1)
        d.update_tags(fontes=json.dumps(info))
    log("mangal de referencia:", info)
    return ref, info


def angulo(a, b):
    na = np.linalg.norm(a, axis=1); nb = np.linalg.norm(b, axis=1)
    cos = (a * b).sum(1) / np.maximum(na * nb, 1e-9)
    return np.arccos(np.clip(cos, -1, 1))


def vetor(comp, r, c, bandas):
    return np.stack([comp[b][r, c] for b in bandas], 1)


def main():
    ROT.mkdir(parents=True, exist_ok=True); FIGC.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    resumo = {"params": dict(N_ANCORA=N_ANCORA, N_POOL=N_POOL, N_MAX_EPOCA=N_MAX_EPOCA,
                             PERC_ANG=PERC_ANG, ELEV_BAIXADA=ELEV_BAIXADA, TPI_BAIXADA=TPI_BAIXADA,
                             BUF_WETLAND=BUF_WETLAND, WATER_NIR_MAX=WATER_NIR_MAX, SEED=SEED)}

    dem = le(PROC / "dem.tif"); tpi = le(PROC / "tpi.tif")
    wc = le(VAL / "worldcover_2021.tif"); wc20 = le(VAL / "worldcover_2020.tif"); io = le(VAL / "io_lulc_2020.tif")
    g20 = ghsl(2020)
    mang_ref, mang_info = mangal_referencia()
    resumo["mangal_referencia"] = mang_info
    osm = gpd.read_file(PROC / "osm.gpkg", layer="osm_agricola")
    osm = osm[osm.landuse.isin(["farmland", "allotments", "greenhouse_horticulture"])]
    osm_ag = rast_geom(osm.geometry)
    wet_buf = osm_wet_buf()
    baix = baixada_regra(np.nan_to_num(dem, nan=99), np.nan_to_num(tpi, nan=0), wet_buf)

    # ---------- ancora 2020 ----------
    g20n = np.nan_to_num(g20, nan=0)
    m = {}
    m[1] = (wc == 50) & (io == 7) & (g20n >= GHSL_CONST)
    # arvore/arbusto e mangal (45): mangal WorldCover 95 sempre aqui, nunca agricultura. O GMW 1996 (mangal_ref) nao
    # rotula 2020 (pode ter sido convertido depois); serve de mascara de referencia em 06 (1979) e 07b/07c
    m[4] = (((wc == 10) & (io == 2) & (g20n < GHSL_AGRI)) | (wc == 95)) & (g20n < GHSL_CONST)
    # agricultura: OSM agricola OU WorldCover Cropland com IO Crops OU Flooded vegetation (arrozal inundado na Beira
    # e rotulado como flooded vegetation pelo IO LULC; Siueia et al. 2025, tab. 1), fora do mangal de referencia
    agri = (osm_ag | ((np.isin(wc, (40,)) | (wc20 == 40)) & np.isin(io, (5, 4)))) & (g20n <= GHSL_AGRI) & (wc != 95) & (wc20 != 95)
    # herbacea/humida natural: exige WorldCover 2020 E 2021 concordantes (arrozal alterna 30/40/90 entre versoes)
    nat = ((wc == 90) & (wc20 == 90) & np.isin(io, (4, 11))) | ((wc == 30) & (wc20 == 30) & (io == 11))
    m[5] = nat & ~agri & ~osm_ag & (g20n < GHSL_AGRI) & (wc != 95) & (wc20 != 95)
    m[6] = (wc == 80) & (io == 1) & (wc20 == 80)
    m[7] = (wc == 60) & (io == 8)
    m[2] = agri & baix
    m[3] = agri & ~baix
    bruto = {k: int(v.sum()) for k, v in m.items()}
    soma = sum(v.astype(int) for v in m.values())
    resumo["ancora_px_bruto"] = bruto
    resumo["ancora_conflito_px"] = int((soma > 1).sum())
    resumo["ancora_sem_erosao"] = []
    for k in m:
        uni = m[k] & (soma == 1)
        er = ero(uni)
        if er.sum() < MIN_EROSAO and uni.sum() > er.sum():
            m[k] = uni  # classe com poucos pixeis: sem erosao, documentado
            resumo["ancora_sem_erosao"].append(int(k))
        else:
            m[k] = er
    resumo["ancora_px_erodido"] = {k: int(v.sum()) for k, v in m.items()}
    mang = ero((wc == 95) & (wc20 == 95))

    pool = []
    for k in range(1, 8):
        idx = amostra(m[k], N_POOL, rng)
        x, y = xy_de(idx)
        sub = np.where((k == 4) & mang.ravel()[idx], 41, 0)
        pool.append(pd.DataFrame(dict(x=x, y=y, classe=k, origem="ancora2020", sub=sub)))
    pool = pd.concat(pool, ignore_index=True)
    pool.to_parquet(ROT / "pool_2020.parquet", index=False)
    anc = cap(pool, N_ANCORA)
    anc.to_parquet(ROT / "treino_2020.parquet", index=False)
    resumo["pool_2020"] = pool.classe.value_counts().sort_index().to_dict()
    resumo["treino_2020"] = anc.classe.value_counts().sort_index().to_dict()

    plot_2v3(dem, tpi, osm_ag, wet_buf, baix, g20n)

    # ---------- pontos pseudo-invariantes ----------
    agua_prof = ero((wc == 80) & (io == 1) & (wc20 == 80), 3)
    d = gpd.read_file(PROC / "limites.gpkg", layer="distritos")
    nuc_area = rast_geom(d[d.adm3_name.isin(["Urbano 1", "Urbano 2"])].geometry)
    g75 = np.nan_to_num(ghsl(1975), nan=0)
    nucleo = ero((g75 >= 5000) & nuc_area & (g20n >= 5000))
    ia = amostra(agua_prof, 1000, rng); inn = amostra(nucleo, 1000, rng)
    resumo["invariantes"] = {"agua_profunda": int(len(ia)), "nucleo_construido_Urbano1e2": int(len(inn))}
    inv_idx = np.concatenate([ia, inn])
    inv_tipo = np.array(["agua"] * len(ia) + ["nucleo"] * len(inn))
    ri, ci = np.unravel_index(inv_idx, SHAPE)

    # ---------- propagacao por epoca ----------
    pxy = np.c_[pool.x.values, pool.y.values]
    pr, pc = rc_de(pxy[:, 0], pxy[:, 1])
    c20 = le_comp(2020)
    resumo["angulos"] = {}; resumo["contagem"] = {}
    for ep in EPOCAS:
        if ep == 2020:
            df = anc.copy()
            resumo["contagem"][ep] = df.groupby(["classe", "origem"]).size().rename("n").reset_index().to_dict("records")
            continue
        ct = le_comp(ep)
        bs = [b for b in BANDAS_ANG if np.isfinite(ct[b]).any()] if ep != 1979 else ["green", "red", "nir"]
        # limiares: percentil dos angulos dos invariantes (agua e nucleo tem distribuicoes diferentes; limiar proprio
        # para terra; a agua nao usa angulo: passa no teste de indice MNDWI/NIR da propria epoca)
        ang_inv = angulo(vetor(c20, ri, ci, bs), vetor(ct, ri, ci, bs))
        ok = np.isfinite(ang_inv)
        a = angulo(vetor(c20, pr, pc, bs), vetor(ct, pr, pc, bs))
        gt = np.nan_to_num(ghsl(GHSL_ANO[ep]), nan=0)[pr, pc]
        k = pool.classe.values
        cons = np.where(k == 1, gt >= GHSL_CONST, np.where(np.isin(k, (2, 3, 4, 5)), gt < GHSL_AGRI, True))
        # mangal de referencia pode ter sido desmatado/construido: so entra se a epoca nao o contradiz (consistencia GHSL acima)
        agua_t = agua_indice(ct, pr, pc)
        npool = pool.classe.value_counts().to_dict()
        for perc in ESCADA:
            lim_l = float(np.percentile(ang_inv[ok & (inv_tipo == "nucleo")], perc))
            lim_nat = float(np.percentile(ang_inv[ok & (inv_tipo == "nucleo")], PERC_NATURAL))
            lim_k = np.where(np.isin(k, (4, 5, 7)), lim_nat, lim_l)
            keep = np.where(k == 6, agua_t, np.isfinite(a) & (a < lim_k)) & cons
            ret = pd.Series(keep).groupby(k).sum().to_dict()
            if all(ret.get(c, 0) >= min(MIN_RET, 0.5 * n) for c, n in npool.items() if n >= 20):
                break
        resumo["angulos"][ep] = dict(bandas=bs, percentil_usado=perc, limiar_terra_rad=lim_l, limiar_natural_rad=lim_nat, perc_natural=PERC_NATURAL,
                                     p20_nucleo=float(np.percentile(ang_inv[ok & (inv_tipo == "nucleo")], 20)),
                                     retidos_por_classe={int(a_): int(b_) for a_, b_ in ret.items()})
        dfp = pool[keep].copy(); dfp["origem"] = "prop2020"
        dfp = cap(dfp, N_MAX_EPOCA)
        resumo.setdefault("propagacao_descartes", {})[ep] = dict(
            por_angulo=int((~(np.isfinite(a) & (a < lim_k))).sum()), por_ghsl=int((~cons).sum()),
            agua_reprovada_indice=int(((k == 6) & ~agua_t).sum()), pool=int(len(pool)))
        df = dfp
        df.to_parquet(ROT / f"treino_{ep}.parquet", index=False)
        resumo["contagem"][ep] = df.groupby(["classe", "origem"]).size().rename("n").reset_index().to_dict("records")
        log(ep, "p%d terra=%.4f" % (perc, lim_l), df.classe.value_counts().sort_index().to_dict())
    with open(ROT / "rotulos_resumo.json", "w") as f:
        json.dump(resumo, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    log("ok; ancora:", resumo["treino_2020"])


def plot_2v3(dem, tpi, osm_ag, wet_buf, baix, g20n):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ardosia_palette import apply_ardosia, ARDOSIA, TERRACOTA, PEDRA
    apply_ardosia()
    sel = osm_ag & (g20n <= GHSL_AGRI)
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.8))
    bins = np.arange(-2, 40, 1)
    ax[0].hist(dem[sel & baix], bins=bins, color=ARDOSIA, label="classe 2 (baixada)")
    ax[0].hist(dem[sel & ~baix], bins=bins, color=TERRACOTA, label="classe 3 (terra firme)", alpha=.9)
    ax[0].axvline(ELEV_BAIXADA, color=PEDRA, ls="--"); ax[0].set_xlabel("altitude (m)"); ax[0].set_ylabel("píxeis OSM farmland/allotments")
    ax[0].set_title("Altitude dos polígonos OSM agrícolas", fontsize=11); ax[0].legend()
    ax[1].hist(tpi[sel & baix], bins=np.arange(-8, 8, .25), color=ARDOSIA)
    ax[1].hist(tpi[sel & ~baix], bins=np.arange(-8, 8, .25), color=TERRACOTA)
    ax[1].axvline(TPI_BAIXADA, color=PEDRA, ls="--"); ax[1].set_xlabel("TPI"); ax[1].set_title("TPI", fontsize=11)
    rr, cc = np.where(sel)
    r0, r1, c0, c1 = max(rr.min() - 20, 0), rr.max() + 20, max(cc.min() - 20, 0), cc.max() + 20
    rgb = np.zeros(SHAPE + (3,)) + 0.93
    rgb[sel & baix] = (0.14, 0.25, 0.31); rgb[sel & ~baix] = (0.61, 0.36, 0.25)
    ax[2].imshow(rgb[r0:r1, c0:c1]); ax[2].set_axis_off(); ax[2].grid(False)
    ax[2].set_title("OSM agrícola: baixada (azul) / outro (terracota)", fontsize=11)
    fig.savefig(FIGC / "rotulos_2v3.png", dpi=150)
    plt.close(fig)
    resumo_pct = float((sel & baix).sum() / max(sel.sum(), 1))
    log("OSM agricola em classe 2 pela regra: %.1f%%; wetland buffer sozinho: %.1f%%" % (
        100 * resumo_pct, 100 * float((sel & wet_buf & ~((dem < ELEV_BAIXADA) & (tpi < TPI_BAIXADA))).sum() / max(sel.sum(), 1))))


if __name__ == "__main__":
    main()
