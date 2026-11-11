"""10 - Amostra de validacao cega de 2020 (chips de imagem sem informacao de classe).

1. Usa o GeoMAD Sentinel-2 anual 2020 (DE Africa gm_s2_annual, tiles x215y051+x216y051; B02,B03,B04,B08,B11) ja gerado por
   03_auxiliares.py em dados/proc/s2_2020_10m.tif (UTM 36S, 10 m, alinhado a grade de 30 m; uint16 = reflectancia x 1e4).
2. Amostra aleatoria estratificada de class_final/2020.tif DENTRO DO MUNICIPIO da Beira (legenda agregada: 1:60, 2:60,
   45:60, 3:40, 6:30, 7:30 = 280 pontos), distancia minima 300 m entre pontos, semente fixa. Estratos raros sao sorteados primeiro.
3. Chips de 3 paineis (S2 cor verdadeira 600 m; S2 falsa-cor NIR-vermelho-verde 600 m; Landsat 30 m falsa-cor
   SWIR1-NIR-vermelho 1,5 km), pixel de 30 m marcado, barra de 100 m, texto so com id, altitude e EMAD.
4. Folhas de 6 chips em dados/proc/validacao/folhas/folha_NN.png; pontos sem classe em pontos_2020_cego.csv;
   chave (id, classe mapeada, estrato) em dados/proc/validacao/.chave/chave_2020.csv (NAO ler ao rotular).
Ordem dos pontos embaralhada entre folhas; ids atribuidos apos o embaralhamento.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import geopandas as gpd
from rasterio import features
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds, Window
from pyproj import Transformer

from comum import *  # noqa

SEED = 20260611
ESTRATOS = {1: 60, 2: 60, 45: 60, 3: 40, 6: 30, 7: 30}
ORDEM_SORTEIO = [7, 6, 3, 2, 45, 1]
DMIN = 300.0
LUT = np.array([0, 1, 2, 3, 45, 45, 6, 7])
BANDAS_S2 = ["B02", "B03", "B04", "B08", "B11"]
S2TIF = PROC / "s2_2020_10m.tif"
VALD = PROC / "validacao"
POR_FOLHA = 6


# ------------------------------------------------------------------ 1. imagem S2
def baixa_s2():
    if integro10(S2TIF):
        log("S2 10 m ja existe (gerado por 03_auxiliares.py):", S2TIF)
        return
    raise SystemExit("dados/proc/s2_2020_10m.tif ausente ou fora da grade: rode scripts/03_auxiliares.py")


def integro10(path):
    try:
        with rasterio.open(path) as s:
            return s.width == WIDTH * 3 and s.height == HEIGHT * 3 and s.crs.to_string() == CRS
    except Exception:
        return False


# ------------------------------------------------------------------ 2. amostra
def amostra():
    with rasterio.open(PROC / "class_final" / "2020.tif") as s:
        cl = s.read(1)
    muni = gpd.read_file(PROC / "limites.gpkg", layer="municipio")
    dentro = features.rasterize(((g, 1) for g in muni.geometry), out_shape=SHAPE, transform=TRANSFORM, fill=0, dtype="uint8").astype(bool)
    agr = np.where(dentro, LUT[cl], 0)
    rng = np.random.default_rng(SEED)
    pts = []
    xs_ok = np.empty(0); ys_ok = np.empty(0)
    for k in ORDEM_SORTEIO:
        n = ESTRATOS[k]
        idx = np.flatnonzero((agr == k).ravel())
        rng.shuffle(idx)
        r, c = np.unravel_index(idx, SHAPE)
        x = X0 + (c + 0.5) * RES; y = Y1 - (r + 0.5) * RES
        got = 0
        for j in range(len(idx)):
            if len(xs_ok) and np.min(np.hypot(xs_ok - x[j], ys_ok - y[j])) < DMIN:
                continue
            xs_ok = np.append(xs_ok, x[j]); ys_ok = np.append(ys_ok, y[j])
            pts.append(dict(x=x[j], y=y[j], row=int(r[j]), col=int(c[j]), classe_mapeada=k))
            got += 1
            if got == n:
                break
        assert got == n, f"estrato {k}: so {got} pontos com distancia minima"
        log(f"estrato {k}: {got} pontos de {len(idx)} pixels elegiveis")
    df = pd.DataFrame(pts)
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    df["id"] = [f"P{i + 1:03d}" for i in range(len(df))]
    df["folha"] = [i // POR_FOLHA + 1 for i in range(len(df))]
    t = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    lon, lat = t.transform(df.x.values, df.y.values)
    df["lon"] = np.round(lon, 6); df["lat"] = np.round(lat, 6)
    # confere distancia minima
    d = np.hypot(df.x.values[:, None] - df.x.values[None], df.y.values[:, None] - df.y.values[None])
    np.fill_diagonal(d, 1e9)
    log("distancia minima entre pontos (m):", round(float(d.min()), 1))
    return df


# ------------------------------------------------------------------ 3. chips e folhas
def estica(a, lo, hi, gamma=1.0):
    return np.clip((a - lo) / (hi - lo), 0, 1) ** gamma


def prepara_imagens():
    with rasterio.open(S2TIF) as s:
        s2 = s.read().astype("float32") / 1e4
    s2[s2 <= 0] = np.nan
    with rasterio.open(COMP / "2020.tif") as s:
        ls = s.read().astype("float32")
        desc = list(s.descriptions)
    ix = {b: i for i, b in enumerate(desc)}
    B = {b: s2[i] for i, b in enumerate(BANDAS_S2)}
    tc = np.stack([B["B04"], B["B03"], B["B02"]], -1)
    fc = np.stack([B["B08"], B["B04"], B["B03"]], -1)
    lf = np.stack([ls[ix["swir1"]], ls[ix["nir"]], ls[ix["red"]]], -1)

    def lims(img):
        return [tuple(np.nanpercentile(img[..., c], (2, 98))) for c in range(3)]
    L = {"tc": lims(tc), "fc": lims(fc), "lf": lims(lf)}
    def norm(img, lm, g=1.0):
        out = np.stack([estica(img[..., c], *lm[c], g) for c in range(3)], -1)
        out[np.isnan(img).any(-1)] = 0.5
        return out
    return dict(tc=norm(tc, L["tc"], 0.85), fc=norm(fc, L["fc"]), lf=norm(lf, L["lf"])), ls[ix["emad"]], L


def recorte(img, r, c, meia, fator):
    """Janela (2*meia) px (em px da imagem de resolucao=fator*grade) centrada no centro do pixel 30 m (r,c); padding cinza."""
    cr = int(round((r + 0.5) * fator)); cc = int(round((c + 0.5) * fator))
    h, w = img.shape[:2]
    out = np.full((2 * meia, 2 * meia, 3), 0.5, "float32")
    r0, c0 = cr - meia, cc - meia
    rs, re = max(r0, 0), min(r0 + 2 * meia, h)
    cs, ce = max(c0, 0), min(c0 + 2 * meia, w)
    out[rs - r0:re - r0, cs - c0:ce - c0] = img[rs:re, cs:ce]
    return out


def folhas(df, imgs, emad, dem):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.patches import Rectangle
    import ardosia_palette as ap
    ap.apply_ardosia()
    (VALD / "folhas").mkdir(parents=True, exist_ok=True)
    halo = [pe.withStroke(linewidth=2.2, foreground="black")]
    nf = int(df.folha.max())
    for f in range(1, nf + 1):
        sub = df[df.folha == f].reset_index(drop=True)
        fig = plt.figure(figsize=(19.2, 3.55 * 3 + 0.3), dpi=100, facecolor="white")
        # 3 linhas x 2 colunas de chips; cada chip = 3 paineis
        outer = fig.add_gridspec(3, 2, left=0.005, right=0.995, top=0.975, bottom=0.005, hspace=0.12, wspace=0.03)
        for i, p in sub.iterrows():
            gs = outer[i // 2, i % 2].subgridspec(1, 3, wspace=0.03)
            r, c = int(p.row), int(p.col)
            alt = dem[r, c]; em = emad[r, c]
            specs = [("tc", 3, 30, 10.0, 600.0), ("fc", 3, 30, 10.0, 600.0), ("lf", 1, 25, 30.0, 1500.0)]
            for j, (nome, fator, meia, res, larg) in enumerate(specs):
                ax = fig.add_subplot(gs[0, j])
                im = recorte(imgs[nome], r, c, meia, fator)
                ax.imshow(im, interpolation="bicubic" if fator == 3 else "nearest", extent=(-larg / 2, larg / 2, -larg / 2, larg / 2))
                ax.add_patch(Rectangle((-15, -15), 30, 30, fill=False, ec="red", lw=1.3))
                ax.plot([-larg / 2 + larg * 0.05, -larg / 2 + larg * 0.05 + 100], [-larg / 2 + larg * 0.06] * 2, color="white", lw=2.2,
                        path_effects=halo, solid_capstyle="butt")
                ax.text(-larg / 2 + larg * 0.05 + 50, -larg / 2 + larg * 0.085, "100 m", color="white", ha="center", va="bottom",
                        fontsize=7, path_effects=halo)
                ax.set_xlim(-larg / 2, larg / 2); ax.set_ylim(-larg / 2, larg / 2)
                ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
                for sp in ax.spines.values():
                    sp.set_visible(True); sp.set_color("#888888"); sp.set_linewidth(0.6)
                if j == 0:
                    ax.set_title(f"{p.id}   alt {alt:.1f} m   EMAD {em:.0f}", loc="left", fontsize=10, pad=3, color="black")
        fig.savefig(VALD / "folhas" / f"folha_{f:02d}.png", dpi=100, facecolor="white")
        plt.close(fig)
    log("folhas:", nf)


def main():
    VALD.mkdir(parents=True, exist_ok=True)
    (VALD / ".chave").mkdir(exist_ok=True)
    baixa_s2()
    if "--forcar" not in sys.argv and (VALD / "pontos_2020_cego.csv").exists() and (VALD / ".chave" / "chave_2020.csv").exists():
        n = len(pd.read_csv(VALD / "pontos_2020_cego.csv"))
        nf = len(list((VALD / "folhas").glob("folha_*.png")))
        if n == sum(ESTRATOS.values()) and nf == -(-n // POR_FOLHA):
            log(f"amostra ja existe ({n} pontos, {nf} folhas); use --forcar para refazer. Nao sobrescreva se ja houver rotulos_2020.csv.")
            return
    df = amostra()
    imgs, emad, L = prepara_imagens()
    with rasterio.open(PROC / "dem.tif") as s:
        dem = s.read(1)
    folhas(df, imgs, emad, dem)
    df[["id", "x", "y", "lon", "lat", "folha"]].to_csv(VALD / "pontos_2020_cego.csv", index=False)
    chave = df[["id", "classe_mapeada", "folha"]].copy()
    chave["estrato"] = chave.classe_mapeada
    chave[["id", "classe_mapeada", "estrato"]].to_csv(VALD / ".chave" / "chave_2020.csv", index=False)
    json.dump(dict(semente=SEED, estratos=ESTRATOS, dmin_m=DMIN, n=int(len(df)), folhas=int(df.folha.max()),
                   estiramento_p2_p98={k: [list(map(float, x)) for x in v] for k, v in L.items()}),
              open(VALD / ".chave" / "amostra_params.json", "w"), indent=1)
    log("ok")


if __name__ == "__main__":
    main()
