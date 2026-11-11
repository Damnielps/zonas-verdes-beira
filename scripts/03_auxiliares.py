"""03 - Produtos auxiliares: DEM, declive, TPI e produtos de validação, todos na grade comum. Idempotente.

Falhas de um produto não interrompem os demais; ao final lista o que falhou.
"""
import os, sys, json, zipfile, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import rasterio
import requests
import pystac_client
import planetary_computer as pc
from rasterio.warp import Resampling, reproject
from rasterio.transform import Affine
from scipy import ndimage
import comum as c

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="6", GDAL_HTTP_RETRY_DELAY="3",
           CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.zip", GDAL_HTTP_USERAGENT=c.UA, GDAL_HTTP_TIMEOUT="120")
LEG = c.VAL / "legendas.json"
FALHAS = []
cat = None


def catalogo():
    global cat
    if cat is None:
        cat = pystac_client.Client.open(PC_STAC, modifier=pc.sign_inplace)
    return cat


def legenda_set(chave, valor):
    d = json.loads(LEG.read_text()) if LEG.exists() else {}
    d[chave] = valor
    c.VAL.mkdir(parents=True, exist_ok=True)
    LEG.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def legenda_tem(chave):
    return LEG.exists() and chave in json.loads(LEG.read_text())


def yr(i):
    return int((i.datetime.isoformat() if i.datetime else i.properties['start_datetime'])[:4])


def categorico(arr_f, nd=0):
    a = np.nan_to_num(arr_f, nan=nd)
    return a.astype("uint8")


def ja(path):
    if path.exists() and c.integro(path):
        c.log("  já existe:", path.name)
        return True
    return False


def tenta(nome, fn):
    try:
        fn()
    except Exception as e:
        c.log(f"  FALHA {nome}: {e!r}")
        traceback.print_exc()
        FALHAS.append((nome, repr(e)))


# ---------------- DEM / declive / TPI ----------------
PAD = 15  # pixels de margem para a TPI


def dem():
    dem_p, dec_p, tpi_p = c.PROC / "dem.tif", c.PROC / "declive.tif", c.PROC / "tpi.tif"
    if ja(dem_p) and ja(dec_p) and ja(tpi_p):
        return
    items = catalogo().search(collections=["cop-dem-glo-30"], bbox=list(c.BBOX_LL)).item_collection()
    c.log("  DEM tiles:", [i.id for i in items])
    # grade expandida
    h, w = c.HEIGHT + 2 * PAD, c.WIDTH + 2 * PAD
    tr = Affine(c.RES, 0, c.X0 - PAD * c.RES, 0, -c.RES, c.Y1 + PAD * c.RES)
    big = np.full((h, w), np.nan, "float32")
    for it in items:
        with rasterio.open(it.assets["data"].href) as s:
            tmp = np.full((h, w), np.nan, "float32")
            b = c.bbox_em(s.crs, 1500)
            from rasterio.windows import from_bounds, Window
            win = from_bounds(*b, transform=s.transform).round_offsets(op="floor").round_lengths(op="ceil")
            win = win.intersection(Window(0, 0, s.width, s.height))
            arr = s.read(1, window=win)
            reproject(arr, tmp, src_transform=s.window_transform(win), src_crs=s.crs, dst_transform=tr,
                      dst_crs=c.CRS, resampling=Resampling.bilinear, src_nodata=s.nodata, dst_nodata=np.nan)
        big = np.where(np.isfinite(big), big, tmp)
    assert np.isfinite(big).mean() > 0.99, "DEM incompleto"
    # declive (graus) por diferenças centrais
    gy, gx = np.gradient(big, c.RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
    # TPI: elevação - média num disco de raio 300 m (10 px), sem o pixel central
    r = int(round(300 / c.RES))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    k = ((yy ** 2 + xx ** 2) <= r * r).astype("float32")
    k[r, r] = 0
    fill = np.where(np.isfinite(big), big, np.nanmean(big))
    media = ndimage.convolve(fill, k, mode="nearest") / k.sum()
    tpi = (fill - media).astype("float32")
    crop = lambda a: a[PAD:PAD + c.HEIGHT, PAD:PAD + c.WIDTH]
    c.grava(dem_p, crop(big), descricoes=["elevacao_m"], tags=dict(fonte="Copernicus DEM GLO-30 (PC cop-dem-glo-30)", nota="altura EGM2008, bilinear 1 arcsec -> 30 m"))
    c.grava(dec_p, crop(slope), descricoes=["declive_graus"], tags=dict(fonte="derivado de dem.tif", metodo="gradiente central em grade UTM 30 m"))
    c.grava(tpi_p, crop(tpi), descricoes=["tpi_300m"], tags=dict(fonte="derivado de dem.tif", metodo="elevacao - media do disco raio 300 m (10 px) excluindo centro"))
    c.log("  DEM min/max", np.nanmin(crop(big)), np.nanmax(crop(big)), "declive p98", np.nanpercentile(crop(slope), 98))


# ---------------- validação ----------------
def worldcover():
    for ano in (2020, 2021):
        out = c.VAL / f"worldcover_{ano}.tif"
        if ja(out):
            continue
        its = catalogo().search(collections=["esa-worldcover"], bbox=list(c.BBOX_LL), datetime=f"{ano}-01-01/{ano}-12-31").item_collection()
        its = [i for i in its if str(ano) in i.id]
        assert its, f"sem WorldCover {ano}"
        a = np.zeros(c.SHAPE, "float32")
        for it in its:
            with rasterio.open(it.assets["map"].href) as s:
                t = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", src_nodata=0, dst_nodata=0)
            a = np.where(a == 0, np.nan_to_num(t, nan=0), a)
        c.grava(out, categorico(a), descricoes=["worldcover_class"], nodata=0,
                tags=dict(fonte=",".join(i.id for i in its), reamostragem="nearest 10 m -> 30 m"))
        classes = its[0].assets["map"].extra_fields.get("classification:classes", [])
        legenda_set(f"worldcover_{ano}", {"fonte": "PC esa-worldcover " + ",".join(i.id for i in its), "nodata": 0,
                                         "classes": {str(x["value"]): x["description"] for x in classes}})


def io_lulc():
    items = catalogo().search(collections=["io-lulc-annual-v02"], bbox=list(c.BBOX_LL)).item_collection()
    por_ano = {}
    for i in items:
        por_ano.setdefault(yr(i), []).append(i)
    for ano in range(2017, 2024):
        out = c.VAL / f"io_lulc_{ano}.tif"
        if ja(out):
            continue
        a = np.zeros(c.SHAPE, "uint8")
        for it in por_ano[ano]:
            with rasterio.open(it.assets["data"].href) as s:
                t = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", src_nodata=0, dst_nodata=0)
            a = np.where(a == 0, categorico(t), a)
        c.grava(out, a, descricoes=["io_lulc_class"], nodata=0, tags=dict(fonte="PC io-lulc-annual-v02 " + ",".join(i.id for i in por_ano[ano]), reamostragem="nearest 10 m -> 30 m"))
        if not legenda_tem("io_lulc"):
            vals = items[0].assets["data"].extra_fields if False else None
            col = catalogo().get_collection("io-lulc-annual-v02")
            fv = col.extra_fields["item_assets"]["data"]["file:values"]
            legenda_set("io_lulc", {"fonte": "PC io-lulc-annual-v02 (Impact Observatory/Esri)", "nodata": 0,
                                    "classes": {str(x["values"][0]): x["summary"] for x in fv}})


def glad():
    # tiles de 10 graus nomeados pelo canto superior esquerdo: Beira (lat -19,95..-19,60; lon 34,72..35,10) -> 10S_030E
    base = "/vsicurl/https://storage.googleapis.com/earthenginepartners-hansen/GLCLU2000-2020/v2/{ano}/10S_030E.tif"
    for ano in (2000, 2005, 2010, 2015, 2020):
        out = c.VAL / f"glad_{ano}.tif"
        if ja(out):
            continue
        c.log("  GLAD", ano)
        with rasterio.open(base.format(ano=ano)) as s:
            a = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", src_nodata=None, dst_nodata=255)
            cm = s.colormap(1) if ano == 2020 else None
        c.grava(out, categorico(a, 255), descricoes=["glad_glcluc_class"], nodata=255,
                tags=dict(fonte=f"GLAD GLCLUC v2 {ano} tile 10S_030E (leitura em janela via /vsicurl/)", reamostragem="nearest 30 m -> 30 m (grade UTM)"))
        if cm is not None:
            vals = np.unique(np.nan_to_num(a, nan=255)).astype(int).tolist()
            legenda_set("glad_glcluc", {
                "fonte": "Potapov et al. 2022, https://glad.umd.edu/dataset/GLCLUC2020",
                "status": "NAO_VERIFICADO: nomes de classe nao obtidos de fonte aberta nesta rodada; consultar o PDF/pagina do GLAD",
                "nodata_usado_aqui": 255, "valores_presentes_no_bbox_2020": vals,
                "grupos_pela_tabela_de_cores_do_proprio_tif": "0-24, 25-48, 49-72, 73-96, 97-99, 100-124, 125-148, 149-172, 173-196, 197-199, 200-207, 208-209, 240-253 (agrupamentos de cor; semantica a confirmar)"})


def ghsl():
    # tile calculado pela projeção do bbox em ESRI:54009 (tiles de 1000 km; origem -18041000, 9000000)
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "ESRI:54009", always_xy=True)
    pts = [t.transform(lo, la) for lo in (c.LON_MIN, c.LON_MAX) for la in (c.LAT_MIN, c.LAT_MAX)]
    rows = {int((9000000 - y) // 1e6) + 1 for x, y in pts}
    cols = {int((x + 18041000) // 1e6) + 1 for x, y in pts}
    c.log(f"  GHSL tiles do bbox: linhas {rows}, colunas {cols}")
    assert len(rows) == 1 and len(cols) == 1, "bbox cruza mais de um tile GHSL"
    R, C = rows.pop(), cols.pop()
    TILE = f"R{R}_C{C}"
    d = c.RAW / "ghsl"
    d.mkdir(parents=True, exist_ok=True)
    for ano in (1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025):
        out = c.VAL / f"ghsl_built_{ano}.tif"
        if ja(out):
            continue
        nome = f"GHS_BUILT_S_E{ano}_GLOBE_R2023A_54009_100_V1_0_{TILE}"
        z = d / f"{nome}.zip"
        url = f"https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E{ano}_GLOBE_R2023A_54009_100/V1-0/tiles/{nome}.zip"
        ok = False
        if z.exists():
            try:
                ok = zipfile.ZipFile(z).testzip() is None
            except Exception:
                ok = False
        if not ok:
            c.log("  baixando", nome)
            with requests.get(url, headers=c.HEADERS, stream=True, timeout=(30, 120)) as r:
                r.raise_for_status()
                with open(z, "wb") as f:
                    for ch in r.iter_content(1 << 20):
                        f.write(ch)
        ex = d / nome
        ex.mkdir(exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(ex)
        tif = [p for p in ex.rglob("*.tif")][0]
        with rasterio.open(tif) as s:
            a = c.para_grade(s, resampling=Resampling.average, src_nodata=s.nodata, dst_nodata=np.nan)
            nd = s.nodata
        c.grava(out, a.astype("float32"), descricoes=["ghsl_built_s_m2_por_celula_100m"],
                tags=dict(fonte=nome, reamostragem="average, 100 m (Mollweide 54009) -> 30 m UTM; valores = m2 construidos por celula de 100 m (0-10000)"))
    legenda_set("ghsl_built_s", {"fonte": f"GHS-BUILT-S R2023A, tile {TILE}, JRC",
                                 "tipo": "continuo", "unidade": "m2 de area construida por celula de 100 m (0-10000)",
                                 "nodata": "NaN", "reamostragem": "average 100 m -> 30 m; valores nao reescalados"})


def cci():
    items = catalogo().search(collections=["esa-cci-lc"], bbox=list(c.BBOX_LL), max_items=100).item_collection()
    por_ano = {yr(i): i for i in items}
    for ano in (1995, 2000, 2005, 2010, 2015, 2020):
        out = c.VAL / f"cci_{ano}.tif"
        if ja(out):
            continue
        it = por_ano[ano]
        with rasterio.open(it.assets["lccs_class"].href) as s:
            a = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", src_nodata=0, dst_nodata=0)
        c.grava(out, categorico(a), descricoes=["cci_lccs_class"], nodata=0, tags=dict(fonte=it.id, reamostragem="nearest 300 m -> 30 m"))
        if not legenda_tem("esa_cci_lc"):
            cl = it.assets["lccs_class"].extra_fields["classification:classes"]
            legenda_set("esa_cci_lc", {"fonte": "PC esa-cci-lc (C3S/ESA CCI LC, LCCS)", "nodata": 0,
                                       "classes": {str(x["value"]): x["description"] for x in cl}})


def wsf():
    out = c.VAL / "wsf_evolution.tif"
    if ja(out):
        return
    r = requests.post("https://explorer.digitalearth.africa/stac/search",
                      json={"collections": ["wsf_evolution"], "bbox": list(c.BBOX_LL), "limit": 10}, headers=c.HEADERS, timeout=60)
    r.raise_for_status()
    feats = r.json()["features"]
    a = np.zeros(c.SHAPE, "float32")
    usados = []
    for f in feats:
        href = f["assets"]["wsfevolution"]["href"]
        href = href.replace("s3://deafrica-input-datasets/", "https://deafrica-input-datasets.s3.af-south-1.amazonaws.com/")
        with rasterio.open(href) as s:
            t = c.para_grade(s, resampling=Resampling.nearest, dtype="float32", src_nodata=s.nodata, dst_nodata=0)
            c.log("  WSF", href.split("/")[-1], s.dtypes, s.nodata, s.res)
        a = np.where(a == 0, np.nan_to_num(t, nan=0), a)
        usados.append(href.split("/")[-1])
    c.grava(out, a.astype("uint16"), descricoes=["wsf_evolution_ano"], nodata=0, dtype=None) if False else \
        c.grava(out, a.astype("uint16"), descricoes=["wsf_evolution_ano"], nodata=0,
                tags=dict(fonte="DE Africa wsf_evolution (WSF Evolution, DLR) " + ",".join(usados), reamostragem="nearest"))
    legenda_set("wsf_evolution", {"fonte": "DE Africa wsf_evolution; DLR WSF Evolution",
                                  "status": "PARCIAL: semantica (valor = ano de deteccao do assentamento; 0 = sem assentamento) nao conferida em metadado aberto nesta rodada; ver valores_presentes",
                                  "valores_presentes": np.unique(a).astype(int).tolist()[:60]})


def s2():
    """Sentinel-2 GeoMAD anual 2020 (DE Africa gm_s2_annual), 10 m, alinhado à grade de 30 m (3x3). Mosaico dos tiles do bbox."""
    from rasterio.transform import from_origin
    from rasterio.windows import from_bounds, Window
    out_p = c.PROC / "s2_2020_10m.tif"
    nx, ny = c.WIDTH * 3, c.HEIGHT * 3
    try:
        with rasterio.open(out_p) as t:
            if t.width == nx and t.height == ny and t.crs.to_string() == c.CRS:
                c.log("  já existe:", out_p.name)
                return
    except Exception:
        pass
    bandas = ["B02", "B03", "B04", "B08", "B11"]
    r = requests.post("https://explorer.digitalearth.africa/stac/search",
                      json={"collections": ["gm_s2_annual"], "bbox": list(c.BBOX_LL),
                            "datetime": "2020-01-01/2020-12-31", "limit": 20}, headers=c.HEADERS, timeout=60)
    r.raise_for_status()
    feats = r.json()["features"]
    assert feats, "sem gm_s2_annual 2020"
    c.log("  S2 tiles:", [f["properties"].get("odc:region_code") for f in feats])
    tr10 = from_origin(c.X0, c.Y1, 10.0, 10.0)
    out = np.zeros((len(bandas), ny, nx), "uint16")
    for i, b in enumerate(bandas):
        acc = np.zeros((ny, nx), "float32")
        for f in feats:
            url = f["assets"][b]["href"].replace("s3://deafrica-services/", "https://deafrica-services.s3.af-south-1.amazonaws.com/")
            with rasterio.open(url) as sx:
                bb = c.bbox_em(sx.crs, 1000.0)
                w = from_bounds(*bb, transform=sx.transform).round_offsets(op="floor").round_lengths(op="ceil")
                w = w.intersection(Window(0, 0, sx.width, sx.height))
                if w.width <= 0 or w.height <= 0:
                    continue
                arr = sx.read(1, window=w)
                dst = np.zeros((ny, nx), "float32")
                reproject(arr.astype("float32"), dst, src_transform=sx.window_transform(w), src_crs=sx.crs,
                          dst_transform=tr10, dst_crs=c.CRS, resampling=Resampling.bilinear, src_nodata=0, dst_nodata=0)
            acc = np.where(acc > 0, acc, dst)
        out[i] = np.clip(np.rint(acc), 0, 65535).astype("uint16")
        c.log("  S2", b, "ok; válido %:", round(float((out[i] > 0).mean() * 100), 2))
    p = dict(driver="GTiff", height=ny, width=nx, count=len(bandas), dtype="uint16", crs=c.CRS, transform=tr10,
             nodata=0, compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    tmp = out_p.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **p) as d:
        d.write(out)
        for i, b in enumerate(bandas, 1):
            d.set_band_description(i, b)
        d.update_tags(fonte="DE Africa gm_s2_annual 2020 " + ",".join(f["properties"].get("odc:region_code", "") for f in feats),
                      item=",".join(f["id"] for f in feats), escala="DN/10000=reflectancia",
                      composicao="verdadeira B04,B03,B02; falsa B08,B04,B03")
    tmp.replace(out_p)


def main():
    c.VAL.mkdir(parents=True, exist_ok=True)
    with rasterio.Env(**ENV):
        for nome, fn in [("dem/declive/tpi", dem), ("worldcover", worldcover), ("io_lulc", io_lulc), ("cci", cci),
                         ("wsf", wsf), ("glad", glad), ("ghsl", ghsl), ("s2 geomad 2020", s2)]:
            c.log("==", nome)
            tenta(nome, fn)
    c.log("FALHAS:", FALHAS if FALHAS else "nenhuma")


if __name__ == "__main__":
    main()
