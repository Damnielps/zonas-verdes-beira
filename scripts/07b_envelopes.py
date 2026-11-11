"""07b - Ocupacao por construcao de tres perimetros fixos, independentes da classe agricola (Beira).

A classe agricola (2) e a menos confiavel da classificacao; a metrica central mede a classe construida dentro
de perimetros definidos sem ela, todos dentro do MUNICIPIO da Beira (camada `municipio`), excluida a agua permanente
(pixels de agua em todas as epocas de class_final):
 (a) baixadas: terra com DEM Copernicus <= 8 m e TPI < 0 (sensibilidade: <= 6 m e <= 10 m);
 (b) mangal de referencia: mangal WorldCover 2020 (95) uniao Global Mangrove Watch v3 1996 (rotulos/mangal_ref.tif);
 (c) feicoes agricolas OSM (landuse farmland, paddy, allotments, greenhouse_horticulture; farmyard e orchard fora).
Saida: dados/proc/areas/envelopes.csv (perimetro, ambito, epoca, area_ha, construido_ha, pct_construido, classe2_ha,
classe45_ha) para class_final. A comparacao das tres estimativas (GHSL, bruta, pos-processada) esta em 07c.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "dados" / "proc"
EPOCAS = [1985, 1990, 1995, 1997, 2000, 2005, 2007, 2010, 2015, 2017, 2019, 2020, 2025, 2026]
PIX_HA = 30 * 30 / 10_000
ELEV_PRINCIPAL = 8.0
ELEV_SENS = [6.0, 8.0, 10.0]
OSM_USOS = ["farmland", "paddy", "allotments", "greenhouse_horticulture"]


def ler(p):
    with rasterio.open(p) as r:
        return r.read(1), r.transform, r.shape, r.crs


def mascara(gdf, transform, shape):
    if gdf is None or len(gdf) == 0:
        return np.zeros(shape, bool)
    return rasterize(((g, 1) for g in gdf.geometry if g is not None and not g.is_empty),
                     out_shape=shape, transform=transform, fill=0, dtype="uint8").astype(bool)


def perimetros():
    """Devolve (dict nome -> mascara, mascara do municipio, mascara de agua permanente, transform, shape, crs)."""
    dem, tr, shp, crs = ler(PROC / "dem.tif")
    tpi, *_ = ler(PROC / "tpi.tif")
    agua = None
    for e in EPOCAS:
        c, *_ = ler(PROC / "class_final" / f"{e}.tif")
        agua = (c == 6) if agua is None else agua & (c == 6)
    muni = mascara(gpd.read_file(PROC / "limites.gpkg", layer="municipio").to_crs(crs), tr, shp)
    per = {}
    for lim in ELEV_SENS:
        nome = f"baixada_dem<={lim:g}m_tpi<0"
        per[nome] = (np.nan_to_num(dem, nan=99) <= lim) & (np.nan_to_num(tpi, nan=0) < 0)
    per["mangal_ref_wc2020_gmw1996"] = ler(PROC / "rotulos" / "mangal_ref.tif")[0].astype(bool)
    osm = gpd.read_file(PROC / "osm.gpkg", layer="osm_agricola").to_crs(crs)
    per["osm_agricola"] = mascara(osm[osm.landuse.isin(OSM_USOS)], tr, shp)
    return per, muni, agua, tr, shp, crs


def main():
    per, muni, agua, *_ = perimetros()
    linhas = []
    for e in EPOCAS:
        c, *_ = ler(PROC / "class_final" / f"{e}.tif")
        for pnome, pm in per.items():
            m = pm & muni & ~agua & (c > 0)
            area = m.sum() * PIX_HA
            linhas.append(dict(perimetro=pnome, ambito="municipio", epoca=e, area_ha=round(area, 1),
                               construido_ha=round((m & (c == 1)).sum() * PIX_HA, 1),
                               pct_construido=round(100 * (m & (c == 1)).sum() * PIX_HA / area, 2) if area else None,
                               classe2_ha=round((m & (c == 2)).sum() * PIX_HA, 1),
                               classe45_ha=round((m & np.isin(c, (4, 5))).sum() * PIX_HA, 1)))
    out = PROC / "areas" / "envelopes.csv"
    pd.DataFrame(linhas).to_csv(out, index=False)
    print(out)


if __name__ == "__main__":
    main()
