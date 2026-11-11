"""01 - Limites da Beira (HDX COD-AB Moçambique) e vetores OSM (Overpass). Idempotente."""
import os, sys, time, json, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum as c
import geopandas as gpd
import requests
from shapely.geometry import box, shape, LineString, Polygon

URL_HDX = ("https://data.humdata.org/dataset/5e8d83a5-1210-49be-b7d9-cf286dbc15df/resource/"
           "f1d97232-4cb5-4083-b3cc-d192aa9bdcfe/download/moz_admin_boundaries.geojson.zip")
HDX_DIR = c.RAW / "hdx"
ZIP = HDX_DIR / "moz_admin_boundaries.geojson.zip"
OUT_LIM = c.PROC / "limites.gpkg"
OUT_OSM = c.PROC / "osm.gpkg"
OVERPASS = "https://overpass-api.de/api/interpreter"


def zip_ok():
    try:
        with zipfile.ZipFile(ZIP) as z:
            return z.testzip() is None
    except Exception:
        return False


def baixa_hdx():
    HDX_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP.exists() and zip_ok():
        c.log("HDX zip já presente e íntegro:", ZIP.stat().st_size)
        return
    c.log("baixando HDX ...")
    with requests.get(URL_HDX, headers=c.HEADERS, stream=True, timeout=(30, 120)) as r:
        r.raise_for_status()
        with open(ZIP, "wb") as f:
            for ch in r.iter_content(1 << 20):
                f.write(ch)
    assert zip_ok(), "zip corrompido"


def limites():
    camadas = ["municipio", "distritos", "bairros", "vizinhos_adm2", "vizinhos_adm4", "bbox"]
    if OUT_LIM.exists() and all(l in gpd.list_layers(OUT_LIM)["name"].tolist() for l in camadas):
        c.log("limites.gpkg já existe, pulando")
        return
    baixa_hdx()
    dest = HDX_DIR / "extraido"
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP) as z:
        c.log("conteúdo do zip:", z.namelist())
        z.extractall(dest)

    def le(nivel):
        cand = [p for p in dest.rglob("*.geojson") if p.name.lower().endswith(f"admin{nivel}.geojson")]
        assert cand, f"adm{nivel} não encontrado"
        return gpd.read_file(cand[0])
    adm2, adm3, adm4 = le(2), le(3), le(4)
    bb = gpd.GeoDataFrame({"nome": ["bbox"]}, geometry=[box(*c.BBOX_LL)], crs="EPSG:4326")
    bbg = bb.geometry.iloc[0]

    def beira(df):
        return df["adm2_name"].astype(str).str.contains("Cidade da Beira", case=False, regex=False)
    # Município/Cidade da Beira (adm2), postos administrativos urbanos (adm3), bairros (adm4)
    mun = adm2[beira(adm2)].copy()
    dist = adm3[beira(adm3)].copy()
    bair = adm4[beira(adm4)].copy()
    viz2 = adm2[adm2.intersects(bbg) & ~beira(adm2)].copy()
    viz4 = adm4[adm4.intersects(bbg) & ~beira(adm4)].copy()
    c.log("município:", len(mun), "postos (adm3):", len(dist), "bairros (adm4):", len(bair),
          "| vizinhos adm2:", viz2["adm2_name"].tolist(), "adm4 vizinhos no bbox:", len(viz4))
    to = lambda g: g.to_crs(c.CRS)
    c.PROC.mkdir(parents=True, exist_ok=True)
    tmp = OUT_LIM.with_suffix(".tmp.gpkg")
    if tmp.exists():
        tmp.unlink()
    for nome, g in (("municipio", mun), ("distritos", dist), ("bairros", bair),
                    ("vizinhos_adm2", viz2), ("vizinhos_adm4", viz4), ("bbox", bb)):
        to(g).to_file(tmp, layer=nome, driver="GPKG")
    tmp.replace(OUT_LIM)
    c.log("limites.gpkg gravado (distritos = postos administrativos urbanos da Beira, adm3)")


# ---------------- Overpass ----------------
S, W, N, E = c.LAT_MIN, c.LON_MIN, c.LAT_MAX, c.LON_MAX
BB = f"({S},{W},{N},{E})"
AGR = "farmland|allotments|orchard|greenhouse_horticulture|paddy|vineyard|plant_nursery"
CONSULTAS = {
    "osm_agricola": f'[out:json][timeout:180];(way["landuse"~"^({AGR})$"]{BB};relation["landuse"~"^({AGR})$"]{BB};'
                    f'way["crop"="rice"]{BB};way["landuse"="farmyard"]{BB};);out geom;',
    "osm_wetland": f'[out:json][timeout:180];(way["natural"="wetland"]{BB};relation["natural"="wetland"]{BB};'
                   f'way["wetland"~"mangrove|swamp|marsh|tidalflat"]{BB};way["natural"="mud"]{BB};'
                   f'way["landuse"="salt_pond"]{BB};);out geom;',
    "osm_mangal": f'[out:json][timeout:180];(way["wetland"="mangrove"]{BB};relation["wetland"="mangrove"]{BB};'
                  f'way["natural"="wood"]["leaf_type"~"mangrove"]{BB};way["natural"="tree_row"]["species"~"Avicennia|Rhizophora"]{BB};);out geom;',
    "osm_estradas": f'[out:json][timeout:180];(way["highway"~"^(motorway|trunk|primary|secondary)$"]{BB};);out geom;',
    "osm_porto": f'[out:json][timeout:180];(way["landuse"="port"]{BB};relation["landuse"="port"]{BB};way["harbour"]{BB};'
                 f'way["man_made"~"^(pier|quay)$"]{BB};way["industrial"="port"]{BB};);out geom;',
    "osm_chiveve": f'[out:json][timeout:180];(way["waterway"]["name"~"Chiveve",i]{BB};way["natural"="water"]["name"~"Chiveve",i]{BB};'
                   f'relation["name"~"Chiveve",i]{BB};way["waterway"~"^(river|stream|canal|drain)$"]{BB};);out geom;',
}


def consulta(nome, q, tentativas=7):
    esp = 30
    for i in range(tentativas):
        try:
            r = requests.post(OVERPASS, data={"data": q}, headers={"User-Agent": "zonas-verdes-research/1.0", "Accept": "application/json"}, timeout=300)  # UA tipo navegador recebe 406 no Overpass
            if r.status_code == 200:
                return r.json()
            c.log(f"  {nome}: HTTP {r.status_code}, tentativa {i+1}")
        except Exception as e:
            c.log(f"  {nome}: erro {e!r}, tentativa {i+1}")
        time.sleep(esp)
        esp = min(esp * 2, 240)
    return None


def elementos_para_gdf(js):
    feats = []
    for el in js.get("elements", []):
        tags = el.get("tags", {})
        geoms = []
        if el["type"] == "way" and "geometry" in el:
            pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
            geoms.append(pts)
        elif el["type"] == "relation":
            for m in el.get("members", []):
                if m.get("type") == "way" and "geometry" in m and m.get("role") in ("outer", ""):
                    geoms.append([(p["lon"], p["lat"]) for p in m["geometry"]])
        for pts in geoms:
            if len(pts) < 2:
                continue
            if len(pts) >= 4 and pts[0] == pts[-1]:
                g = Polygon(pts)
            else:
                g = LineString(pts)
            if g.is_empty:
                continue
            d = {k: tags.get(k) for k in ("name", "ref", "highway", "landuse", "natural", "wetland", "waterway", "harbour", "man_made", "bridge", "crop", "surface")}
            d.update(osm_id=el["id"], osm_tipo=el["type"], geometry=g)
            feats.append(d)
    return gpd.GeoDataFrame(feats, geometry="geometry", crs="EPSG:4326") if feats else None


def osm():
    existentes = gpd.list_layers(OUT_OSM)["name"].tolist() if OUT_OSM.exists() else []
    falt = [n for n in CONSULTAS if n not in existentes]
    if not falt:
        c.log("osm.gpkg completo, pulando")
        return
    brutos = c.RAW / "overpass"
    brutos.mkdir(parents=True, exist_ok=True)
    for nome in falt:
        f = brutos / f"{nome}.json"
        if f.exists():
            js = json.loads(f.read_text())
        else:
            c.log("Overpass:", nome)
            js = consulta(nome, CONSULTAS[nome])
            if js is None:
                c.log(f"  FALHA em {nome} (continuando)")
                continue
            f.write_text(json.dumps(js))
            time.sleep(10)
        gdf = elementos_para_gdf(js)
        if gdf is None:
            c.log(f"  {nome}: 0 feições; camada vazia não gravada")
            gdf = gpd.GeoDataFrame({"osm_id": []}, geometry=[], crs="EPSG:4326")
        gdf.to_crs(c.CRS).to_file(OUT_OSM, layer=nome, driver="GPKG")
        c.log(f"  {nome}: {len(gdf)} feições")


if __name__ == "__main__":
    limites()
    osm()
