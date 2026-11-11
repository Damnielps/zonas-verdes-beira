"""02 - Composições multibanda por época (30 m, EPSG:32736, reflectância 0-1) + índices. Idempotente.

Fontes: GeoMAD anual do Digital Earth Africa (tiles x215y051 + x216y051, mosaicados), Landsat C2 L2
(Planetary Computer, path/row 167/074, que cobre 100% do bbox) para substituições e 2026, e Landsat MSS
C2 L1 (Landsat 2, 179/074) para 1979 (proxy do censo de 1980).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import rasterio
import requests
import pystac_client
import planetary_computer as pc
from rasterio.warp import Resampling
from shapely.geometry import box, shape
from rasterio.windows import from_bounds, Window
import comum as c

DEA_STAC = "https://explorer.digitalearth.africa/stac/search"
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
TILES = {"x215y051", "x216y051"}
PATH, ROW = "167", "074"
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="6", GDAL_HTTP_RETRY_DELAY="3",
           CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF", GDAL_HTTP_USERAGENT=c.UA,
           GDAL_HTTP_TIMEOUT="120", GDAL_HTTP_MULTIRANGE="YES")

# ressalvas de épocas mantidas em GeoMAD
NOTAS = {
    1985: "~1% do bbox mascarado como nuvem/sombra (NE) e névoa fina residual sobre o mar a E/NE; 1984 é o ano mais próximo com cena de estação seca de baixa nebulosidade",
    1990: "COUNT mediana 3; ~0,6% do bbox sem dado (nuvens mascaradas, manchas no NE; locais distintos dos de 1985); água do estuário/mar com blocos de turbidez distintos entre datas (mosaico de poucas observações)",
    2010: "GeoMAD (mistura TM/ETM+ SLC-off, COUNT mediana 7): faixas SLC-off residuais, visíveis sobretudo sobre o mar/estuário, terra sem faixas evidentes; tentativas de substituição (TM 2010-05-08 + preenchimento ETM+; mediana das cenas abr-out) foram piores (NaN e faixas na terra) e foram descartadas; tratar com máscara de mar em 06b",
}

# mapeamento de bandas GeoMAD -> nomes harmonizados
MAPA_LS57 = {"blue": "SR_B1", "green": "SR_B2", "red": "SR_B3", "nir": "SR_B4", "swir1": "SR_B5", "swir2": "SR_B7"}
MAPA_LS89 = {"blue": "SR_B2", "green": "SR_B3", "red": "SR_B4", "nir": "SR_B5", "swir1": "SR_B6", "swir2": "SR_B7"}
GEOMAD_ESCALA = 1e-4  # DEA GeoMAD: SR em 0-10000 (conferido: mediana vermelho ~900 = 0,09)

# substituições por cena única (preenchido após inspeção visual do GeoMAD; época -> prefixo da cena)
SUBST = {
    1985: ("LT05_L2SP_167074_19840601",
           "GeoMAD 1985 inexistente (sem observações no bbox; a coleção gm_ls5_ls7_annual vazia em 1985); substituído por TM de 1984-06-01 "
           "(nuvem/sombra 1,1% no bbox; única cena L2 de estação seca de 1984-85; alternativa 1986-05-06 0% descartada por distar mais de 1985)"),
    2005: ("LT05_L2SP_167074_20051001",
           "GeoMAD 2005 rejeitado (faixas SLC-off do Landsat 7 visíveis sobre o mar/estuário); substituído por TM de 2005-10-01 (nuvem/sombra 0% no bbox)"),
    2007: ("LT05_L2SP_167074_20070820",
           "GeoMAD 2007 rejeitado (faixas SLC-off do Landsat 7 visíveis sobre o mar/estuário); substituído por TM de 2007-08-20 (nuvem/sombra 0% no bbox)"),
}


def colecao_geomad(ano):
    if ano <= 2012:
        return "gm_ls5_ls7_annual", MAPA_LS57, "Landsat 5/7 TM/ETM+"
    if ano <= 2020:
        return "gm_ls8_annual", MAPA_LS89, "Landsat 8 OLI"
    return "gm_ls8_ls9_annual", MAPA_LS89, "Landsat 8/9 OLI"


def https(href):
    return href.replace("s3://deafrica-services/", "https://deafrica-services.s3.af-south-1.amazonaws.com/")


def geomad(ano):
    col, mapa, sensor = colecao_geomad(ano)
    r = requests.post(DEA_STAC, json={"collections": [col], "bbox": list(c.BBOX_LL),
                                      "datetime": f"{ano}-01-01/{ano}-12-31", "limit": 20},
                      headers=c.HEADERS, timeout=60)
    r.raise_for_status()
    feats = [f for f in r.json()["features"] if f["properties"].get("odc:region_code") in TILES]
    got = {f["properties"]["odc:region_code"] for f in feats}
    assert got == TILES, f"tiles GeoMAD {col} {ano}: {got}"
    out = {}
    cnt = np.full(c.SHAPE, np.nan, "float32")

    def junta(dst, nome, novo):
        dst[nome] = novo if nome not in dst else np.where(np.isfinite(dst[nome]), dst[nome], novo)
    for f in feats:
        a = f["assets"]
        for nome, k in mapa.items():
            with rasterio.open(https(a[k]["href"])) as s:
                arr = c.para_grade(s, resampling=Resampling.bilinear, src_nodata=0)
            junta(out, nome, arr * GEOMAD_ESCALA)
        for nome in ("SMAD", "EMAD", "BCMAD"):
            with rasterio.open(https(a[nome]["href"])) as s:
                junta(out, nome.lower(), c.para_grade(s, resampling=Resampling.bilinear))
        with rasterio.open(https(a["COUNT"]["href"])) as s:
            cn = c.para_grade(s, resampling=Resampling.nearest)
        cnt = np.where(np.isfinite(cnt), cnt, cn)
    ok = np.isfinite(out["red"])
    out["count"] = np.where(ok, cnt, np.nan).astype("float32")
    stack = np.stack([out[b] for b in c.BANDAS]).astype("float32")
    meta = dict(fonte=f"Digital Earth Africa {col} v1.0.0 tiles {'+'.join(sorted(TILES))} (mosaico)", sensor=sensor,
                datas=f"{ano}-01-01/{ano}-12-31", item=",".join(f["id"] for f in feats),
                count_mediana_bbox_todos=float(np.nanmedian(cnt)))
    return stack, meta


# ---------------- Landsat C2 L2 (Planetary Computer) ----------------
_cat = None


def catalogo():
    global _cat
    if _cat is None:
        _cat = pystac_client.Client.open(PC_STAC, modifier=pc.sign_inplace)
    return _cat


def busca_item_l2(prefixo):
    """prefixo tipo LT05_L2SP_167078_19840601 -> item PC."""
    d = prefixo.split("_")[-1]
    data = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    res = catalogo().search(collections=["landsat-c2-l2"], bbox=list(c.BBOX_LL), datetime=f"{data}/{data}",
                            max_items=20).item_collection()
    for it in res:
        if it.id.startswith(prefixo):
            return it
    raise RuntimeError(f"item {prefixo} não encontrado no PC")


def bandas_l2(item):
    p = item.properties["platform"]
    mapa = {"blue": "blue", "green": "green", "red": "red", "nir": "nir08", "swir1": "swir16", "swir2": "swir22"}
    return mapa


def le_cena_l2(item):
    """Retorna dict banda->array reflectância (NaN mascarado por QA_PIXEL) e fração de máscara."""
    mapa = bandas_l2(item)
    with rasterio.open(item.assets["qa_pixel"].href) as s:
        qa = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", src_nodata=None, dst_nodata=1)
    qa = np.nan_to_num(qa, nan=1).astype("uint16")
    # bits: 0 fill, 1 dilated cloud, 2 cirrus, 3 cloud, 4 shadow
    ruim = (qa & 0b11111) != 0
    out = {}
    for nome, asset in mapa.items():
        with rasterio.open(item.assets[asset].href) as s:
            dn = c.para_grade(s, resampling=Resampling.bilinear, src_nodata=0)
        refl = dn * 0.0000275 - 0.2
        refl = np.where(ruim, np.nan, refl)
        refl = np.where((refl < -0.05) | (refl > 1.0), np.nan, refl)
        out[nome] = np.clip(refl, 0, 1).astype("float32")
    # qualquer banda NaN invalida todas
    inval = ~np.all([np.isfinite(out[b]) for b in out], axis=0)
    for b in out:
        out[b][inval] = np.nan
    return out, float(ruim.mean())


def nuvem_bbox(item):
    with rasterio.open(item.assets["qa_pixel"].href) as s:
        qa = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", dst_nodata=1)
    qa = np.nan_to_num(qa, nan=1).astype("uint16")
    return float(((qa & 0b11111) != 0).mean())


def empilha(d, count, extras=None):
    n = np.full(c.SHAPE, np.nan, "float32")
    lista = []
    for b in c.BANDAS:
        if b in ("blue", "green", "red", "nir", "swir1", "swir2"):
            lista.append(d[b])
        elif b == "count":
            lista.append(count.astype("float32"))
        else:
            lista.append(n)
    return np.stack(lista).astype("float32")


def cena_unica(prefixo):
    item = busca_item_l2(prefixo)
    d, frac = le_cena_l2(item)
    ok = np.isfinite(d["red"])
    cnt = np.where(ok, 1.0, np.nan)
    meta = dict(fonte=f"Planetary Computer landsat-c2-l2 {item.id}", sensor=item.properties["platform"],
                datas=item.datetime.strftime("%Y-%m-%d"), item=item.id, mascara_nuvem_sombra_frac=round(frac, 4))
    return empilha(d, cnt), meta


def composicao_mediana(ano, d0, d1, plataformas, cc_max, ids_extra=()):
    """Mediana por banda de cenas Landsat C2 L2 (path/row 167/074) no intervalo d0..d1 do ano, QA_PIXEL aplicado."""
    res = catalogo().search(collections=["landsat-c2-l2"], bbox=list(c.BBOX_LL), datetime=f"{ano}-{d0}/{ano}-{d1}",
                            query={"landsat:wrs_path": {"eq": PATH}, "landsat:wrs_row": {"eq": ROW},
                                   "eo:cloud_cover": {"lt": cc_max}, "platform": {"in": plataformas}},
                            max_items=80).item_collection()
    itens = sorted(res, key=lambda i: i.datetime)
    c.log(f"  {ano}: cenas candidatas", [i.id for i in itens])
    assert itens, f"sem cenas {ano}"
    pilhas = {b: [] for b in ("blue", "green", "red", "nir", "swir1", "swir2")}
    usadas = []
    for it in itens:
        d, frac = le_cena_l2(it)
        if np.isfinite(d["red"]).mean() < 0.2:
            c.log(f"  {ano}: descartada (quase tudo mascarado)", it.id, round(frac, 3))
            continue
        for b in pilhas:
            pilhas[b].append(d[b])
        usadas.append(it)
    med = {b: np.nanmedian(np.stack(v), axis=0).astype("float32") for b, v in pilhas.items()}
    cnt = np.isfinite(np.stack(pilhas["red"])).sum(axis=0).astype("float32")
    cnt = np.where(cnt == 0, np.nan, cnt)
    datas = [i.datetime.strftime("%Y-%m-%d") for i in usadas]
    meta = dict(fonte=f"Planetary Computer landsat-c2-l2, mediana de {len(usadas)} cenas ({d0[:2]}-{d1[:2]}/{ano}), p{PATH} r{ROW}, nuvem<{cc_max}%, QA_PIXEL",
                sensor=" + ".join(sorted({i.properties['platform'] for i in usadas})), datas=f"{min(datas)}/{max(datas)}",
                item=",".join(i.id for i in usadas), n_cenas=len(usadas))
    return empilha(med, cnt), meta


def composicao_2026():
    return composicao_mediana(2026, "05-01", "09-30", ["landsat-8", "landsat-9"], 30)


def cena_com_preenchimento(primaria, preenchimentos):
    """Cena primária; píxeis mascarados (nuvem/sombra/faixa) preenchidos com as cenas seguintes, em ordem."""
    stack, meta = cena_unica(primaria)
    d = {b: stack[c.BANDAS.index(b)].copy() for b in ("blue", "green", "red", "nir", "swir1", "swir2")}
    cnt = np.where(np.isfinite(d["red"]), 1.0, np.nan)
    usados = [meta["item"]]
    for pf in preenchimentos:
        it = busca_item_l2(pf)
        f, _ = le_cena_l2(it)
        vazio = ~np.isfinite(d["red"]) & np.isfinite(f["red"])
        for b in d:
            d[b] = np.where(vazio, f[b], d[b])
        cnt = np.where(vazio, 1.0, cnt)
        usados.append(f"{it.id}[{vazio.mean()*100:.1f}% preenchido]")
    meta = dict(meta, item=",".join(usados), fonte=meta["fonte"] + " + preenchimento " + ",".join(preenchimentos))
    return empilha(d, cnt), meta


# ---------------- MSS 1979 ----------------
MSS_ITEM = "LM02_L1TP_179074_19790829_02_T2"


def repara_linhas(x):
    """Linhas anômalas do MSS (a cena L1TP está em geometria de mapa, então as linhas de varredura saem inclinadas):
    píxeis com DN < 70% ou > 135% da mediana vertical das 6 linhas vizinhas (±3) são substituídos por essa mediana.
    Sem teste de coerência horizontal (linhas inclinadas); o custo é suavizar picos isolados de 60 m."""
    xm = np.where(x > 0, x, np.nan)
    desl = np.stack([np.roll(xm, k, axis=0) for k in (-3, -2, -1, 1, 2, 3)])
    with np.errstate(all="ignore"):
        med = np.nanmedian(desl, axis=0)
        ruim = (x > 0) & np.isfinite(med) & ((x < 0.70 * med) | (x > 1.35 * med))
    ruim[:3, :] = False; ruim[-3:, :] = False
    y = np.where(ruim, med, x)
    c.log(f"  MSS: {ruim.sum()} píxeis de linha corrigidos ({ruim.mean()*100:.3f}%)")
    return y


def mss_1979():
    res = catalogo().search(collections=["landsat-c2-l1"], ids=[MSS_ITEM]).item_collection()
    item = res[0]
    mtl = requests.get(item.assets["mtl.json"].href, timeout=60).json()["LANDSAT_METADATA_FILE"]
    sun = float(mtl["IMAGE_ATTRIBUTES"]["SUN_ELEVATION"])
    rs = mtl["LEVEL1_RADIOMETRIC_RESCALING"]
    # Landsat 2/3 MSS: B4 verde 0,5-0,6; B5 vermelho 0,6-0,7; B6 NIR 0,7-0,8; B7 NIR 0,8-1,1 um
    escolha = {"green": ("green", 4), "red": ("red", 5), "nir": ("nir09", 7)}
    saida = {}
    for nome, (asset, n) in escolha.items():
        m = float(rs[f"REFLECTANCE_MULT_BAND_{n}"]); a = float(rs[f"REFLECTANCE_ADD_BAND_{n}"])
        with rasterio.open(item.assets[asset].href) as s:
            w = from_bounds(*c.bbox_em(s.crs, 600.0), transform=s.transform).round_offsets(op="floor").round_lengths(op="ceil")
            w = w.intersection(Window(0, 0, s.width, s.height))
            arr = repara_linhas(s.read(1, window=w).astype("float32"))
            dn = c.array_para_grade(arr, s.window_transform(w), s.crs, resampling=Resampling.bilinear, src_nodata=0)
        refl = (m * dn + a) / np.sin(np.deg2rad(sun))
        saida[nome] = np.clip(refl, 0, 1).astype("float32")
        saida[nome][~np.isfinite(dn) | (dn <= 0)] = np.nan
    inval = ~np.all([np.isfinite(saida[b]) for b in saida], axis=0)
    for b in saida:
        saida[b][inval] = np.nan
    n = np.full(c.SHAPE, np.nan, "float32")
    for b in ("blue", "swir1", "swir2"):
        saida[b] = n
    cnt = np.where(np.isfinite(saida["red"]), 1.0, np.nan)
    meta = dict(fonte=f"Planetary Computer landsat-c2-l1 {item.id} (Tier 2)", sensor="Landsat 2 MSS (60 m)",
                datas=item.datetime.strftime("%Y-%m-%d"), item=item.id, sol_elevacao=sun,
                notas=("TOA, (M*DN+A)/sin(elev solar); verde=B4, vermelho=B5, nir=B7 (0,8-1,1um; B6 0,7-0,8um nao usada); "
                       "60 m -> grade 30 m por reamostragem bilinear; píxeis com DN<70% ou >135% da mediana vertical de 6 linhas vizinhas (linhas de perda de dados/picos do MSS) substituídos por essa mediana; blue/swir ausentes. "
                       "Cena de 29/ago/1979 (0% nuvem) como proxy do censo de 1980"))
    return empilha(saida, cnt), meta


# ---------------- índices ----------------
def nd(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (a - b) / (a + b)
    r = np.where(np.isfinite(r), r, np.nan)
    return r.astype("float32")


def indices(stack):
    B = dict(zip(c.BANDAS, stack))
    ndvi = nd(B["nir"], B["red"])
    ndbi = nd(B["swir1"], B["nir"])
    mndwi = nd(B["green"], B["swir1"])
    with np.errstate(divide="ignore", invalid="ignore"):
        bsi = nd(B["swir1"] + B["red"], B["nir"] + B["blue"])
    return np.stack([ndvi, ndbi, mndwi, bsi])


def estatisticas(stack):
    red = stack[c.BANDAS.index("red")]
    nan_pct = float(np.isnan(red).mean() * 100)
    cnt = stack[c.BANDAS.index("count")]
    cnt_med = float(np.nanmedian(cnt)) if np.isfinite(cnt).any() else float("nan")
    return nan_pct, cnt_med


def nuvem_sobre_agua(stack):
    """Fração de píxeis inválidos (NaN) e de 'nuvem provável' (azul alto) - diagnóstico, não máscara."""
    red = stack[c.BANDAS.index("red")]
    return float(np.isnan(red).mean() * 100)


def main():
    c.COMP.mkdir(parents=True, exist_ok=True)
    c.IDX.mkdir(parents=True, exist_ok=True)
    with rasterio.Env(**ENV):
        for ano in c.EPOCAS:
            dest = c.COMP / f"{ano}.tif"
            didx = c.IDX / f"{ano}.tif"
            if c.integro(dest) and c.integro(didx):
                c.log(ano, "já existe, pulando")
                continue
            c.log(ano, "construindo ...")
            subst = ""
            if ano == 1979:
                stack, meta = mss_1979()
            elif ano == 2026:
                stack, meta = composicao_2026()
            elif ano in SUBST:
                alvo, subst = SUBST[ano]
                if isinstance(alvo, str):
                    stack, meta = cena_unica(alvo)
                elif alvo[0] == "mediana":
                    stack, meta = composicao_mediana(ano, *alvo[1:])
                else:
                    stack, meta = cena_com_preenchimento(alvo[0], alvo[1])
            else:
                stack, meta = geomad(ano)
                nan_pct, cnt_med = estatisticas(stack)
                c.log(f"  GeoMAD {ano}: NaN {nan_pct:.1f}%, COUNT mediana (válidos) {cnt_med}, (todos) {meta['count_mediana_bbox_todos']}")
            nan_pct, cnt_med = estatisticas(stack)
            if ano in NOTAS:
                meta["notas"] = (meta.get("notas", "") + " " + NOTAS[ano]).strip()
            meta.update(epoca=ano, substituicao=subst or "nenhuma", nan_pct=round(nan_pct, 2),
                        count_mediana=cnt_med)
            c.grava(dest, stack, descricoes=c.BANDAS, tags=meta)
            c.grava(didx, indices(stack), descricoes=["ndvi", "ndbi", "mndwi", "bsi"], tags=meta)
            p2, p98 = np.nanpercentile(stack[2], [2, 98]) if np.isfinite(stack[2]).any() else (np.nan, np.nan)
            c.log(f"  gravado {dest.name}: NaN {nan_pct:.1f}%, vermelho p2/p98 {p2:.3f}/{p98:.3f}  {subst}")


if __name__ == "__main__":
    main()
