"""04 - QA das composições: tabela em docs/qa/composicoes.md, quick-looks PNG e painel de contato."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import rasterio
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import comum as c
from ardosia_palette import apply_ardosia

B = {b: i for i, b in enumerate(c.BANDAS)}


def estica(a, lo=None, hi=None):
    ok = np.isfinite(a)
    if lo is None:
        lo, hi = np.nanpercentile(a[ok], [2, 98])
    r = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
    return r, ok


def rgb_img(stack, bands):
    ch, ok = [], None
    rng = []
    for b in bands:
        a = stack[B[b]]
        r, o = estica(a)
        ch.append(r); ok = o if ok is None else ok & o
    im = (np.stack(ch, -1) * 255).astype("uint8")
    im[~ok] = 255
    return im


def mascara_agua():
    """Água de referência = WorldCover 2020 classe 80 (mar, estuário, rios) na grade comum; None se ausente."""
    p = c.VAL / "worldcover_2020.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as s:
        return s.read(1) == 80


def main():
    agua = mascara_agua()
    c.QA.mkdir(parents=True, exist_ok=True)
    (c.FIG / "qa").mkdir(parents=True, exist_ok=True)
    linhas = []
    imgs = {}
    perc = []
    agua_col = []
    for ano in c.EPOCAS:
        with rasterio.open(c.COMP / f"{ano}.tif") as s:
            st = s.read()
            t = s.tags()
        mss = ano == 1979
        if mss:
            rgb = rgb_img(st, ["red", "green", "green"])
            fc = rgb_img(st, ["nir", "red", "green"])
        else:
            rgb = rgb_img(st, ["red", "green", "blue"])
            fc = rgb_img(st, ["swir1", "nir", "red"])
        Image.fromarray(rgb).save(c.FIG / "qa" / f"{ano}_rgb.png")
        Image.fromarray(fc).save(c.FIG / "qa" / f"{ano}_falsacor.png")
        imgs[ano] = rgb
        nan_pct = float(np.mean(~np.isfinite(st[B["red"]])) * 100)
        cnt = st[B["count"]]
        cm = np.nanmedian(cnt) if np.isfinite(cnt).any() else float("nan")
        ps = []
        for b in ["blue", "green", "red", "nir", "swir1", "swir2"]:
            a = st[B[b]]
            if np.isfinite(a).any():
                p2, p98 = np.nanpercentile(a, [2, 98])
                ps.append(f"{b} {p2:.3f}-{p98:.3f}")
        perc.append((ano, "; ".join(ps)))
        if agua is not None:
            red = st[B["red"]][agua]
            nan_ag = float(np.mean(~np.isfinite(red)) * 100)
            # "nuvem provável" sobre a água: refletância no vermelho > 0,12 (água limpa/estuário turvo fica abaixo)
            bri_ag = float(np.mean(np.isfinite(red) & (red > 0.12)) * 100)
            ag = f"{nan_ag:.1f} / {bri_ag:.1f}"
        else:
            ag = "n/d"
        agua_col.append(ag)
        linhas.append((ano, t.get("fonte", ""), t.get("sensor", ""), t.get("datas", ""), nan_pct, cm,
                       t.get("substituicao", ""), t.get("item", ""), t.get("notas", "")))
    md = ["# QA das composições (30 m, EPSG:32736)", "",
          "Gerado por `scripts/04_qa_composicoes.py`. NaN % = fração da grade do bbox sem dado válido na banda vermelha; "
          "COUNT = número de observações por píxel (GeoMAD: banda COUNT; cena única: 1; 2026: observações válidas). "
          "Coluna Água: sobre a máscara de água do WorldCover 2020 (classe 80: mar, estuário, rios), % de píxeis sem dado e % com refletância vermelha > 0,12 "
          "(indício de nuvem/espuma/sedimento, lição de Maputo: nuvem sobre o mar virou 'construído'); é diagnóstico, não máscara.", "",
          "| Época | Fonte | Sensor | Datas | NaN % | COUNT mediana | Água: NaN % / vermelho>0,12 % | Substituição / notas |",
          "|---|---|---|---|---|---|---|---|"]
    for (a, f, se, d, n, cm, sub, it, no), ag in zip(linhas, agua_col):
        nota = ("" if sub in ("", "nenhuma") else sub + ". ") + no
        md.append(f"| {a} | {f} ({it}) | {se} | {d} | {n:.2f} | {cm:.0f} | {ag} | {nota or '-'} |")
    md += ["", "## Percentis 2-98% por banda (reflectância)", "", "| Época | Bandas |", "|---|---|"]
    md += [f"| {a} | {p} |" for a, p in perc]
    md += ["", "## Notas", "",
           "- 1979 (MSS, Landsat 2; proxy do censo de 1980): sem banda azul; quick-look 'rgb' é pseudo-cor (R=vermelho, G=verde, B=verde); falsa-cor = NIR-vermelho-verde.",
           "- Quick-looks com estiramento 2-98% por banda e por imagem; NaN em branco.",
           "- Painel de contato: `dados/fig/qa/painel_rgb.png`.",
           "- Grade: bbox 34,72-35,10 E, -19,95 a -19,60 S, EPSG:32736, 30 m. Tiles GeoMAD DE Africa que cobrem o bbox: x215y051 e x216y051 (mosaico por NaN-fill). "
           "Cena Landsat que cobre 100% do bbox: path/row 167/074 (167/073 cobre ~3%). GeoMAD 1985 não existe (coleção vazia); a coleção L2 do Planetary Computer começa em 1984.",
           "- GeoMAD 2005 e 2007 (e o 2010 em menor grau) mostram faixas SLC-off do Landsat 7 sobre o mar; 2005 e 2007 foram substituídos por cena TM única; 2010 manteve o GeoMAD (alternativas pioraram a terra).",
           "- Água (WorldCover 2020, classe 80): a coluna 'vermelho>0,12' inclui sedimento do estuário do Púngue e espuma de arrebentação, não só nuvem; é limite superior de contaminação por nuvem sobre a água.",
           "- Cor da água varia muito entre épocas (turbidez, maré, fitoplâncton/areias submersas): efeito esperado em composições de poucas observações; a classe água deve ser definida por MNDWI/NIR, não por cor.",
           "- Auxiliares (03): Copernicus DEM 30 m, WorldCover 2020/2021, IO LULC 2017-2023, ESA CCI LC 1995-2020, WSF Evolution, GLAD GLCLUC 2000-2020 (tile 10S_030E), GHSL built-up 1975-2025 (tile R12_C22), Sentinel-2 GeoMAD 2020 10 m (`dados/proc/s2_2020_10m.tif`)."]
    (c.QA / "composicoes.md").write_text("\n".join(md) + "\n")
    apply_ardosia()
    fig, axs = plt.subplots(3, 5, figsize=(17, 13))
    for ax, ano in zip(axs.ravel(), c.EPOCAS):
        ax.imshow(imgs[ano]); ax.set_title(str(ano) + (" (MSS)" if ano == 1979 else "")); ax.axis("off")
    fig.tight_layout()
    fig.savefig(c.FIG / "qa" / "painel_rgb.png", dpi=110)
    c.log("QA escrito")


if __name__ == "__main__":
    main()
