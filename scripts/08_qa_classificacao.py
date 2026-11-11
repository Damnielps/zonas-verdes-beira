"""08 - QA da classificacao da Beira: figuras e docs/qa/classificacao.md.

Entradas: dados/proc/class (bruta), class_final (06b), areas/ (07, 07b, 07c), rotulos/rotulos_resumo.json,
class/oob.json, val/ghsl_built_*.tif, val/io_lulc_*.tif. Legenda agregada (1, 2, 3, 45, 6, 7), paleta Ardosia.
Saidas: dados/fig/class/{mapas_classes,area_empilhada_municipio,linhas_classe1_classe2,mapa_ano_conversao,
envelopes_construido}.png; dados/proc/areas/qa_*.csv; docs/qa/classificacao.md (reescrito inteiro; a secao 8 de
validacao e anexada por 11_avaliacao_exatidao.py depois de rodar este script).
Numeros de comparacao externa (Siueia et al. 2025) vem de fontes/fichas/siueia_2025.md (tab. 2, p. 90).
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features

from comum import *  # noqa

CLS = PROC / "class"
CLF = PROC / "class_final"
AREAS = PROC / "areas"
ROT = PROC / "rotulos"
FIGC = FIG / "class"
HA = RES * RES / 1e4
SERIE = [e for e in EPOCAS if e != 1979]
AGR_LAB = {1: "1 Construído", 2: "2 Agricultura de baixada/hortícola", 3: "3 Cultivo e mosaico de terra firme",
           45: "4+5 Vegetação natural e zonas húmidas", 6: "6 Água", 7: "7 Solo exposto e areia"}
LUT = np.array([0, 1, 2, 3, 4, 4, 5, 6])  # classe 0..7 -> indice agregado
# Siueia et al. 2025, tab. 2, p. 90 (fontes/fichas/siueia_2025.md): km2, municipio de 658,12 km2
SIUEIA = {"ano": [2017, 2018, 2019, 2020, 2021, 2022, 2023],
          "culturas_km2": [8.25, 5.72, 2.70, 5.23, 6.8, 9.54, 7.06],
          "construido_km2": [103.81, 109.03, 106.45, 118.46, 122.72, 130.08, 124.96]}


def le(p, b=1):
    with rasterio.open(p) as s:
        return s.read(b)


def fmt(v, c=""):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if c in ("epoca", "época", "ghsl_ano", "t0", "t1", "n", "ano", "anos") and not isinstance(v, str):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return f"{v:,.1f}" if abs(v) >= 10 else f"{v:.2f}"
    return str(v)


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(fmt(r[c], c) for c in cols) + " |")
    return "\n".join(out) + "\n"


def masc_municipio():
    m = gpd.read_file(PROC / "limites.gpkg", layer="municipio")
    return features.rasterize(((g, 1) for g in m.geometry), out_shape=SHAPE, transform=TRANSFORM, fill=0, dtype="uint8").astype(bool)


def concordancia_ghsl(cl_f, cl_b, mun):
    m5 = importlib.import_module("05_rotulos")
    rows = []
    for ep in EPOCAS:
        g = np.nan_to_num(m5.ghsl(m5.GHSL_ANO[ep])) >= 2000
        gfrac = np.clip(np.nan_to_num(m5.ghsl(m5.GHSL_ANO[ep]), nan=0) / 10000.0, 0, 1)
        for tipo, cl in (("final", cl_f[ep]), ("bruta", cl_b[ep])):
            for amb, msk in (("bbox", np.ones(SHAPE, bool)), ("municipio", mun)):
                b = (cl == 1) & msk; gg = g & msk
                rows.append(dict(epoca=ep, ghsl_ano=m5.GHSL_ANO[ep], classificacao=tipo, ambito=amb,
                                 construido_km2=b.sum() * HA / 100, ghsl_ge2000_km2=gg.sum() * HA / 100,
                                 ghsl_soma_fracao_km2=gfrac[msk].sum() * HA / 100,
                                 pct_nosso_em_ghsl=100 * (b & gg).sum() / max(b.sum(), 1),
                                 pct_ghsl_no_nosso=100 * (b & gg).sum() / max(gg.sum(), 1),
                                 f1=200 * (b & gg).sum() / max(b.sum() + gg.sum(), 1)))
    return pd.DataFrame(rows)


def comparacao_io(cl_f, mun):
    rows = []
    for k, ano in enumerate(SIUEIA["ano"]):
        io = le(VAL / f"io_lulc_{ano}.tif")
        io_c = ((io == 5) & mun).sum() * HA / 100; io_b = ((io == 7) & mun).sum() * HA / 100
        io_f = ((io == 4) & mun).sum() * HA / 100
        r = dict(ano=ano, siueia_culturas_km2=SIUEIA["culturas_km2"][k], io_culturas_nossa_mascara_km2=io_c,
                 io_inundada_km2=io_f, siueia_construido_km2=SIUEIA["construido_km2"][k], io_construido_nossa_mascara_km2=io_b)
        ep = ano if ano in cl_f else None
        if ep:
            c = cl_f[ep]
            r.update(nosso_construido_km2=((c == 1) & mun).sum() * HA / 100, nosso_classe2_km2=((c == 2) & mun).sum() * HA / 100,
                     nosso_classe3_km2=((c == 3) & mun).sum() * HA / 100)
        rows.append(r)
    return pd.DataFrame(rows)


def figuras(cl, ag, ghsl_df, io_df, env, mun):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    import ardosia_palette as ap
    ap.apply_ardosia()
    FIGC.mkdir(parents=True, exist_ok=True)
    cor = {1: ap.GRAFITE, 2: ap.TERRACOTA, 3: ap.OCRE, 45: ap.PETROLEO, 6: ap.ARDOSIA_MED, 7: ap.FILETE}
    ordem = [1, 2, 3, 45, 6, 7]
    cm = ListedColormap([ap.PAPEL_FIG] + [cor[k] for k in ordem])
    norm = BoundaryNorm(np.arange(-0.5, 7.5, 1), cm.N)
    cid = ag[ag.ambito == "municipio"].pivot(index="epoca", columns="classe_agr", values="ha") / 100.0  # km2
    mun_g = gpd.read_file(PROC / "limites.gpkg", layer="municipio")
    contorno = []
    for g in mun_g.geometry:
        for poly in (g.geoms if hasattr(g, "geoms") else [g]):
            xs, ys = poly.exterior.xy
            contorno.append(((np.array(xs) - X0) / RES, (Y1 - np.array(ys)) / RES))

    fig, axs = plt.subplots(4, 4, figsize=(16, 15.5))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.01, wspace=0.03, hspace=0.12)
    for ax in axs.ravel():
        ax.set_axis_off(); ax.grid(False)
    notas = {1979: " (MSS, excluída das séries)", 1985: " (cena jun/1984)", 2005: " (cena out/2005)", 2007: " (cena ago/2007)"}
    for ax, ep in zip(axs.ravel(), EPOCAS):
        ax.imshow(LUT[cl[ep]], cmap=cm, norm=norm, interpolation="nearest")
        for xs, ys in contorno:
            ax.plot(xs, ys, color=ap.PAPEL_FIG, lw=0.7)
        ax.set_title(f"{ep}{notas.get(ep, '')}", fontsize=11, loc="left", pad=4)
    axs.ravel()[15].legend(handles=[Patch(color=cor[k], label=AGR_LAB[k]) for k in ordem], loc="upper left", frameon=False,
                           fontsize=10, title="Classes (legenda agregada)", title_fontsize=11)
    axs.ravel()[15].text(0, 0.0, "Grade 30 m, EPSG:32736\nRandom Forest por época + consistência (06b)\nLinha clara: Município da Beira",
                         fontsize=9, color=ap.PEDRA, transform=axs.ravel()[15].transAxes)
    fig.suptitle("Cobertura e uso do solo, Beira, 1979–2026 (classificação final)", x=0.05, ha="left", fontsize=16)
    fig.savefig(FIGC / "mapas_classes.png", dpi=100); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.stackplot(SERIE, [cid.loc[SERIE, k] for k in ordem], colors=[cor[k] for k in ordem], labels=[AGR_LAB[k] for k in ordem])
    ax.set_ylabel("área (km²)"); ax.set_xlabel("época")
    ax.set_title("Classes no Município da Beira (inclui água interior), 1985–2026", fontsize=13)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    ax.set_xticks(SERIE); ax.set_xticklabels(SERIE, rotation=60)
    fig.savefig(FIGC / "area_empilhada_municipio.png", dpi=150, bbox_inches="tight"); plt.close(fig)

    fig, axs = plt.subplots(2, 1, figsize=(9.5, 7.5), sharex=True)
    g = ghsl_df[(ghsl_df.ambito == "municipio") & (ghsl_df.classificacao == "final") & (ghsl_df.epoca != 1979)].set_index("epoca")
    axs[0].plot(SERIE, cid.loc[SERIE, 1], marker="o", color=ap.GRAFITE, label="Classificação final (município)")
    bru = ghsl_df[(ghsl_df.ambito == "municipio") & (ghsl_df.classificacao == "bruta") & (ghsl_df.epoca != 1979)].set_index("epoca")
    axs[0].plot(SERIE, bru.loc[SERIE, "construido_km2"], marker=".", ls=":", color=ap.PEDRA, label="Classificação bruta")
    axs[0].plot(SERIE, g.loc[SERIE, "ghsl_ge2000_km2"], marker="s", ms=4, lw=0, color=ap.ARDOSIA_MED, label="GHSL ≥ 20% da célula (km²)")
    axs[0].plot(io_df.ano, io_df.siueia_construido_km2, marker="D", ms=6, lw=0, mfc=ap.PAPEL_FIG, mec=ap.TERRACOTA, mew=1.5,
                label="Siueia et al. (2025), IO LULC, 658 km²")
    axs[1].plot(SERIE, cid.loc[SERIE, 2], marker="o", color=ap.TERRACOTA, label="2 Agricultura de baixada")
    axs[1].plot(SERIE, cid.loc[SERIE, 3], marker="o", color=ap.OCRE, label="3 Terra firme (indicativo)")
    axs[1].plot(io_df.ano, io_df.siueia_culturas_km2, marker="D", ms=6, lw=0, mfc=ap.PAPEL_FIG, mec=ap.ARDOSIA_MED, mew=1.5,
                label="Siueia et al. (2025), 'culturas' (exclui arrozal inundado)")
    for a, t in zip(axs, (AGR_LAB[1], "Classes agrícolas")):
        a.set_ylabel("km²"); a.set_title(t, fontsize=11, loc="left"); a.set_ylim(bottom=0); a.legend(frameon=False, fontsize=8, loc="upper left" if a is axs[0] else "upper center", ncol=1)
    axs[1].set_xticks(SERIE); axs[1].set_xticklabels(SERIE, rotation=60, fontsize=8)
    fig.suptitle("Construído e classes agrícolas, Município da Beira", x=0.1, ha="left", fontsize=13)
    fig.savefig(FIGC / "linhas_classe1_classe2.png", dpi=150); plt.close(fig)

    # frentes de conversao
    cv = le(CLF / "conversao_agri_construido.tif")
    anos = [e for e in EPOCAS if e > 1979]
    cmap = mpl.colormaps["ardosia_seq"].resampled(len(anos))
    fig, ax = plt.subplots(figsize=(9, 9.5))
    fundo = np.where(cl[2026] == 1, 1, np.where(cl[2026] == 6, 2, 0))
    ax.imshow(fundo, cmap=ListedColormap([ap.PAPEL_FIG, ap.FILETE_CL, ap.ARDOSIA_NEV]), vmin=0, vmax=2, interpolation="nearest")
    ys, xs = np.where(cv > 0)
    sc = ax.scatter(xs, ys, c=[anos.index(int(a)) for a in cv[ys, xs]], s=3, cmap=cmap, vmin=-0.5, vmax=len(anos) - 0.5, marker="s")
    cb = fig.colorbar(sc, ax=ax, ticks=range(len(anos)), shrink=0.6); cb.ax.set_yticklabels(anos)
    cb.set_label("ano da conversão estável (agricultura 2/3 para construído)")
    ax.set_axis_off(); ax.grid(False)
    ax.set_title("Frentes de conversão de áreas agrícolas em construído", fontsize=13)
    fig.savefig(FIGC / "mapa_ano_conversao.png", dpi=150); plt.close(fig)

    # tres estimativas nos perimetros
    nomes = ["baixada_dem<=8m_tpi<0", "mangal_ref_wc2020_gmw1996", "osm_agricola"]
    tit = {"baixada_dem<=8m_tpi<0": "Baixadas (DEM ≤ 8 m, TPI < 0)", "mangal_ref_wc2020_gmw1996": "Mangal de referência (WC 2020 e GMW 1996)",
           "osm_agricola": "Feições agrícolas OSM"}
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.3))
    for a, n in zip(axs, nomes):
        d = env[env.perimetro == n].set_index("epoca")
        a.plot(d.index, d.pct_final, marker="o", color=ap.GRAFITE, label="pós-processada")
        a.plot(d.index, d.pct_bruto, marker=".", ls=":", color=ap.TERRACOTA, label="bruta")
        a.plot(d.index, d.pct_ghsl, marker="s", ms=4, color=ap.ARDOSIA_MED, label="GHSL (fração)")
        a.set_title(f"{tit[n]}\n" + f"{d.area_ha.iloc[-1]:,.0f}".replace(",", " ") + " ha", fontsize=10, loc="left")
        a.set_ylabel("% construído"); a.set_ylim(bottom=0)
        a.set_xticks(SERIE[::2]); a.set_xticklabels(SERIE[::2], rotation=60, fontsize=8)
    axs[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Fração construída em perímetros fixos do município: três estimativas", x=0.05, ha="left", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIGC / "envelopes_construido.png", dpi=150); plt.close(fig)
    log("figuras ok:", FIGC)


def secao_rotulos(rot, oob):
    L = []
    w = L.append
    p = rot["params"]
    w("## 1. Rótulos de treino\n")
    w("### 1.1 Âncora 2020 e regras\n")
    mr = rot.get("mangal_referencia", {})
    w("- Construído: WorldCover 2021 = 50 E IO LULC 2020 = Built E GHSL-BUILT-S 2020 ≥ 2000 m² por célula de 100 m.")
    w("- Árvore/arbusto e mangal (45): (WC 10 E IO Trees E GHSL < 500) OU WC 95 (mangal; subclasse 41 na coluna `sub`); nunca agricultura.")
    w("- Agricultura: polígonos OSM `farmland`, `allotments`, `greenhouse_horticulture` OU (WC 2021 = 40 ou WC 2020 = 40) E IO = Crops ou Flooded vegetation "
      "(arrozal inundado é rotulado `flooded vegetation` pelo IO LULC; Siueia et al. 2025, tab. 1), com GHSL ≤ 500 e fora de WC 95.")
    w(f"- Divisão 2 × 3: classe 2 se altitude ≤ {p['ELEV_BAIXADA']:g} m E TPI < 0, ou a ≤ 100 m de zona húmida OSM de água doce (`tidalflat` e `mangrove` excluídos); caso contrário classe 3.")
    w("- Herbácea/húmida natural (5): (WC 2021 = 90 E WC 2020 = 90 E IO Flooded vegetation ou Rangeland) OU (WC 30 em 2020 e 2021 E IO Rangeland), com GHSL < 500, fora de agricultura e de mangal. "
      "A exigência de concordância entre as duas versões do WorldCover evita rotular como zona húmida natural o arrozal, que alterna 30/40/90 entre versões.")
    w("- Água: WC 80 em 2020 e 2021 E IO Water. Solo exposto: WC 60 E IO Bare.")
    w(f"- Píxeis que cumprem mais de uma regra foram descartados ({rot['ancora_conflito_px']} px); máscaras erodidas em 1 píxel (3×3); classes sem erosão: {rot['ancora_sem_erosao'] or 'nenhuma'}.")
    w(f"- Reserva de até {p['N_POOL']} pontos por classe (`pool_2020.parquet`); âncora `treino_2020` com até {p['N_ANCORA']} por classe. Pontos na reserva: {rot['pool_2020']}; na âncora: {rot['treino_2020']}.")
    w("- Píxeis brutos por classe antes da erosão: " + ", ".join(f"{k}: {v:,}" for k, v in sorted(rot["ancora_px_bruto"].items())) + ".\n")
    w("**Mangal de referência** (usado em 06 para 1979 e em 07b/07c): WorldCover 2020 (classe 95) e Global Mangrove Watch v3, extensão de 1996 "
      "(Zenodo, doi 10.5281/zenodo.6894273, CC BY 4.0; baixado de `zenodo.org/api/records/6894273`, tiles GMW_S19/S20 × E034/E035). "
      f"Píxeis de 30 m: WorldCover {mr.get('worldcover_2020_px', 'n/d'):,}; GMW 1996 {mr.get('gmw1996_px', 'n/d'):,}; interseção {mr.get('intersecao_px', 'n/d'):,}; união {mr.get('uniao_px', 'n/d'):,}. "
      "O GMW 1996 não rotula 2020 (pode ter sido convertido depois); serve como máscara de referência.\n")
    w("### 1.2 Propagação temporal\n")
    w(f"Ângulo espectral entre o vetor 2020 e o da época t em (verde, vermelho, NIR, SWIR1, SWIR2; 1979: verde, vermelho, NIR), calculado sobre pseudo-invariantes: "
      f"{rot['invariantes']['agua_profunda']} pontos de água profunda (WC 80 E IO água, erodida 3 px) e {rot['invariantes']['nucleo_construido_Urbano1e2']} pontos do núcleo construído antigo "
      "(GHSL 1975 ≥ 5000 e GHSL 2020 ≥ 5000 nos postos Urbano 1 e 2, erodido). Consistência com GHSL(t) (ano GHSL mais próximo): construído exige ≥ 2000; agricultura, árvore e herbácea exigem < 500.\n")
    w("**Desvios documentados.** (i) O limiar das classes construído, 2 e 3 sai dos invariantes de núcleo construído no percentil 20 e sobe para 50 e 80 só enquanto alguma classe retiver menos de min(150; 50% do pool) pontos. "
      f"(ii) Vegetação natural (4, 5) e solo exposto (7) usam o percentil {rot['angulos'][next(iter(rot['angulos']))].get('perc_natural', 95)} dos mesmos invariantes: com o limiar estrito, as cenas de estação seca (2005 e 2007) perderam grande parte da vegetação seca ou queimada da amostra de treino e o RF a classificava como construído (2005 bruto: 232 mil píxeis construídos contra 115 mil depois da correção). "
      "(iii) A água não usa ângulo: um ponto da reserva de água só entra se, na época t, MNDWI (verde−SWIR1; NDWI verde−NIR em 1979) > 0 e NIR < 0,15, isto é, por índice e não por cor (turbidez do Púngue).\n")
    w("| época | bandas | percentil (terra) | limiar terra (rad) | limiar natural p95 (rad) |")
    w("|---|---|---|---|---|")
    for ep, v in rot["angulos"].items():
        w(f"| {ep} | {','.join(v['bandas'])} | {v['percentil_usado']} | {v['limiar_terra_rad']:.4f} | {v.get('limiar_natural_rad', float('nan')):.4f} |")
    w("")
    w("Pontos de treino por época e classe (após propagação; limite 1 500 por classe e época):\n")
    linhas = []
    for ep in sorted(oob["n_treino"], key=int):
        r = {"época": int(ep)}
        r.update({f"cl {k}": v for k, v in oob["n_treino"][ep].items()})
        linhas.append(r)
    tb = pd.DataFrame(linhas).fillna(0).astype(int)
    w(md(tb[["época"] + sorted(c for c in tb.columns if c != "época")].astype(str)))
    return L


def secao_oob(oob):
    L = []
    w = L.append
    w("## 2. Reprodução dos rótulos (OOB e validação cruzada em blocos de 3 km)\n")
    w("| época | n | acurácia OOB | F1 por classe (OOB) | acurácia CV blocos | principais variáveis |")
    w("|---|---|---|---|---|---|")
    for ep in oob["oob"]:
        o = oob["oob"][ep]
        cv = oob["cv_bloques"].get(ep)
        w(f"| {ep} | {o['n']} | {o['acc']:.3f} | " + ", ".join(f"{k}: {v:.2f}" for k, v in o["f1"].items()) +
          f" | {cv['acc']:.3f} (F1: " + ", ".join(f"{k}: {v:.2f}" for k, v in cv["f1"].items()) + ") | " if cv else
          f"| {ep} | {o['n']} | {o['acc']:.3f} | " + ", ".join(f"{k}: {v:.2f}" for k, v in o["f1"].items()) + " |  | ", )
        L[-1] = L[-1] + ", ".join(f"{a} ({b})" for a, b in o["top_importancias"][:3]) + " |"
    w("\n**Leitura.** OOB e CV medem a reprodução dos rótulos (derivados de WorldCover, IO LULC, GHSL e OSM), não a exatidão contra verdade de campo; a exatidão está na seção 8 (validação cega de 2020). "
      f"F1 da classe 2: OOB entre {min(v['f1'].get('2', 1) for v in oob['oob'].values() if '2' in v['f1']):.2f} e {max(v['f1'].get('2', 0) for v in oob['oob'].values() if '2' in v['f1']):.2f}; CV em blocos " + ", ".join(f"{e}: {v['f1']['2']:.2f}" for e, v in oob['cv_bloques'].items()) + ". "
      "A queda na CV espacial indica que a classe 2 não se generaliza entre blocos de 3 km (poucos rótulos propagados, uma só âncora de ~1 100 píxeis e sobreposição espectral provável com herbácea de baixada): é a classe de menor confiabilidade.\n")
    w("Nota 1979: legenda reduzida (1 construído, 3 vegetação/agricultura de todo o tipo, 6 água, 7 solo exposto; 4, 5 e 45 ausentes); a classe 2 é derivada por regra de baixada fora do mangal de referência. "
      "1979 fica fora das séries quantitativas e das regras de 06b.\n")
    return L


def main():
    FIGC.mkdir(parents=True, exist_ok=True); QA.mkdir(parents=True, exist_ok=True)
    cl = {ep: le(CLF / f"{ep}.tif") for ep in EPOCAS}
    cb = {ep: le(CLS / f"{ep}.tif") for ep in EPOCAS}
    mun = masc_municipio()
    ag = pd.read_csv(AREAS / "areas_agregado_classe_epoca.csv")
    env = pd.read_csv(AREAS / "envelopes_comparacao.csv")
    envr = json.load(open(AREAS / "envelopes_resumo.json"))
    conv = pd.read_csv(AREAS / "conversao.csv")
    rot = json.load(open(ROT / "rotulos_resumo.json"))
    oob = json.load(open(CLS / "oob.json"))
    cons = json.load(open(CLF / "consistencia.json"))

    ghsl_df = concordancia_ghsl(cl, cb, mun)
    io_df = comparacao_io(cl, mun)
    ghsl_df.to_csv(AREAS / "qa_ghsl_concordancia.csv", index=False)
    io_df.to_csv(AREAS / "qa_siueia_io_lulc.csv", index=False)
    figuras(cl, ag, ghsl_df, io_df, env, mun)

    L = []
    w = L.append
    w("# QA da classificação (30 m, EPSG:32736) — Beira\n")
    w("Gerado por `scripts/08_qa_classificacao.py` a partir de `05_rotulos.py`, `06_classificar.py`, `06b_consistencia.py`, `07_areas_transicoes.py`, `07b/07c`. "
      "Números lidos de `dados/proc/class/oob.json`, `dados/proc/rotulos/rotulos_resumo.json`, `dados/proc/class_final/consistencia.json` e `dados/proc/areas/`. "
      "A seção 8 (validação cega de 2020) é anexada por `11_avaliacao_exatidao.py` quando existir `dados/proc/validacao/rotulos_2020.csv`.\n")
    L += secao_rotulos(rot, oob)
    L += secao_oob(oob)

    w("## 3. Pós-processamento de consistência (06b)\n")
    w("Sequência: 1985, 1990, 1995, 1997, 2000, 2005, 2007, 2010, 2015, 2017, 2019, 2020, 2025, 2026 (1979 fora). Regra 0: píxel que é água em pelo menos metade das épocas é mar/estuário/leito e passa a água nas demais "
      "(elimina nuvem e névoa sobre o mar). Regra 1: construído em t só permanece se estiver construído em pelo menos 2 das 3 épocas da janela {t−1, t, t+1}; depois, monotonia (construído nunca reverte). Regra 2: tremulação 2↔5 em épocas interiores. "
      "Píxeis alterados por época e regra:\n")
    c = pd.DataFrame.from_dict(cons["contagens_por_epoca"], orient="index").rename_axis("epoca").reset_index()
    c["epoca"] = c["epoca"].astype(int)
    c = c.rename(columns={"regra0_mar": "r0_mar", "regra1_removidos_construido": "r1_removidos", "regra1_acrescentados_construido": "r1_acrescentados",
                          "regra2_flicker_2_5": "r2_2↔5", "total_alterados": "total"})[["epoca", "r0_mar", "r1_removidos", "r1_acrescentados", "r2_2↔5", "total"]]
    w(md(c))
    w(f"Construído monotônico: {cons['monotonico']} (violações: {cons['violacoes_monotonia']}). "
      "Hipótese não testada: o estuário do Púngue tem bancos de areia e lamaçais que podem alternar entre água e solo exposto com a maré e a data da cena; "
      "pelo critério de metade das épocas, esses píxeis ficam água em todas as épocas e a variação real de água/solo exposto no estuário fica mascarada.\n")

    w("## 4. Áreas (km²) no Município da Beira (07)\n")
    mm = ag[ag.ambito == "municipio"].pivot(index="epoca", columns="classe_agr", values="ha") / 100.0
    mm = mm.rename(columns={0: "sem dado", 1: "1 construído", 2: "2 agric. baixada", 3: "3 terra firme", 45: "4+5 natural", 6: "6 água", 7: "7 solo exposto"})
    mm.insert(0, "época", mm.index.astype(int))
    w(md(mm.reset_index(drop=True)))
    w(f"Município = polígono HDX COD-AB (camada `municipio`), {mun.sum() * HA / 100:,.0f} km² na grade de 30 m (inclui água interior do estuário). "
      "1979 aparece só por completude: legenda reduzida (3 = toda a vegetação, 45 ausente), não comparável. "
      f"1985 tem {100 * ag[(ag.ambito == 'municipio') & (ag.epoca == 1985) & (ag.classe_agr == 0)].ha.iloc[0] / (mun.sum() * HA):.1f}% do município sem dado (nuvens da cena de 1984). "
      f"As classes 2 e 3 são menos confiáveis (ver seções 2 e 8); a classe 2 varia entre {mm['2 agric. baixada'].loc[SERIE].min():.0f} e {mm['2 agric. baixada'].loc[SERIE].max():.0f} km² ao longo das épocas, sem tendência monótona nem explicação documentada; ler como indicativo, não como série de agricultura real.\n")
    fig_note = "Figuras: `dados/fig/class/mapas_classes.png`, `area_empilhada_municipio.png`, `linhas_classe1_classe2.png`, `mapa_ano_conversao.png`, `envelopes_construido.png`."
    w(fig_note + "\n")

    w("## 5. Concordância externa do construído com o GHSL-BUILT-S\n")
    w("Construído nosso (classe 1) contra células GHSL ≥ 2000 m² (≥ 20% de superfície construída por célula de 100 m), ano GHSL mais próximo; `ghsl_soma_fracao` é a soma da fração construída do GHSL (mesma unidade de superfície, mas conceito diferente: superfície edificada, não ocupação por píxel de 30 m).\n")
    gm = ghsl_df[(ghsl_df.ambito == "municipio") & (ghsl_df.classificacao == "final")].drop(columns=["ambito", "classificacao"])
    w("Classificação final, município:\n")
    w(md(gm))
    gb = ghsl_df[(ghsl_df.ambito == "municipio") & (ghsl_df.classificacao == "bruta")][["epoca", "construido_km2", "pct_nosso_em_ghsl", "pct_ghsl_no_nosso", "f1"]]
    w("Classificação bruta, município:\n")
    w(md(gb))
    w("GHSL e nosso construído não medem o mesmo: o GHSL com limiar de 20% por célula de 100 m exclui o casario de baixa densidade e os bairros periféricos de caniço que a classificação de 30 m capta, "
      "de modo que o nosso construído é maior que GHSL ≥ 2000 em todas as épocas e a concordância (F1) cresce com a densificação.\n")

    io20 = le(VAL / "io_lulc_2020.tif"); wc21 = le(VAL / "worldcover_2021.tif")
    m5 = importlib.import_module("05_rotulos")
    g20 = np.nan_to_num(m5.ghsl(2020), nan=0)
    x = (wc21 == 30) & (io20 == 7) & mun
    ncl1 = ((cl[2020] == 1) & x).sum()
    w("## 6. Comparação com Siueia et al. (2025), IO LULC 2017–2023\n")
    w("Siueia et al. (2025, tab. 2, p. 90; `fontes/fichas/siueia_2025.md`) usam o IO LULC 10 m recortado ao município de 658,12 km²; as colunas `io_*_nossa_mascara` recalculam as mesmas classes IO na nossa máscara municipal (HDX COD-AB, menor), como checagem de máscara. "
      "Arrozal e agricultura inundada entram em `flooded vegetation` no IO, não em `crops`; por isso `culturas` do IO é ≈ 1% do município.\n")
    w(md(io_df))
    w(f"O nosso construído (2017–2020: {io_df.nosso_construido_km2.dropna().min():.0f}–{io_df.nosso_construido_km2.dropna().max():.0f} km²) é inferior ao do IO LULC ({io_df.io_construido_nossa_mascara_km2.min():.0f}–{io_df.io_construido_nossa_mascara_km2.max():.0f} km² em 2017–2023). "
      f"Parte da diferença está em píxeis que o IO 2020 marca como Built e o WorldCover 2021 como herbácea (Grassland): {x.sum() * HA / 100:.0f} km² no município, dos quais "
      f"{100 * (g20[x] >= 2000).mean():.0f}% têm GHSL ≥ 20% e {100 * ncl1 / max(x.sum(), 1):.0f}% são construído na nossa classificação de 2020. "
      "Nossa classe agrícola (2+3) é maior que `crops` do IO, que exclui o arrozal inundado (`flooded vegetation`). "
      "Sem verdade de campo não se decide qual lado erra: a validação cega de 2020 (seção 8) é o árbitro.\n")

    per_mg = le(ROT / "mangal_ref.tif").astype(bool)
    w("## 7. Perímetros fixos (07b/07c): fração construída em três estimativas\n")
    w("Perímetros dentro do município, sem água permanente: (a) baixadas = DEM Copernicus ≤ 8 m e TPI < 0 (sensibilidade 6 e 10 m); (b) mangal de referência = WorldCover 2020 e GMW 1996; (c) feições agrícolas OSM (farmland, paddy, allotments, greenhouse_horticulture; farmyard e orchard fora). "
      "Estimativas: GHSL (fração construída média), classificação bruta e pós-processada; ano final 2025.\n")
    linhas = []
    for nome, d in envr["perimetros"].items():
        linhas.append(dict(perimetro=nome, area_ha_2025=d["area_ha_2025"], ghsl_1985=d["pct_ghsl"]["1985"], ghsl_2025=d["pct_ghsl"]["2025"],
                           bruta_1985=d["pct_bruto"]["1985"], bruta_2025=d["pct_bruto"]["2025"],
                           final_1985=d["pct_final"]["1985"], final_2025=d["pct_final"]["2025"],
                           var_pp_min=d["intervalo_variacao_pp"][0], var_pp_max=d["intervalo_variacao_pp"][1]))
    w(md(pd.DataFrame(linhas)))
    w("Percentuais de área construída no perímetro; `var_pp` = variação 1985→2025 em pontos percentuais (mínimo e máximo entre as três estimativas). "
      "Série completa em `dados/proc/areas/envelopes_comparacao.csv`.\n")
    mgm = per_mg & mun & (cl[2025] > 0)
    n_mg = int((mgm & (cl[2025] == 1)).sum())
    ever_mg = int((mgm & (cl[2025] == 1) & np.any([cb[e] == 1 for e in SERIE], 0)).sum())
    n_mg85 = int((mgm & (cl[2025] == 1) & (cl[1985] == 1)).sum())
    w("Duas ressalvas. O GHSL dá níveis cerca de três vezes menores que a classificação (conceito de superfície edificada por célula de 100 m), mas a mesma direção. "
      f"No mangal de referência a estimativa pós-processada cresce mais que a bruta: dos {n_mg:,} píxeis do mangal construídos em 2025 na classificação final, {100 * ever_mg / max(n_mg, 1):.0f}% foram construído bruto em alguma época e {n_mg85:,} já eram construído em 1985; a monotonia acumula, ao longo de 14 épocas, qualquer comissão que se repita em 2 de 3 épocas. "
      "O GHSL é ≈ 0 no mangal, então a variação aí é provavelmente erro de classificação e não perda de mangal; não usar o perímetro do mangal como medida de pressão construída sem validação.\n")

    w("## 7.1 Frentes de conversão (agricultura → construído, 2+3 → 1)\n")
    cv = conv[(conv.ambito == "municipio") & conv.consecutivo][["t0", "t1", "anos", "ha_agri_para_construido", "ha_agri_ano", "ha_zv_para_construido"]]
    w(md(cv))
    w("Intervalos curtos amplificam as diferenças entre composições; usar os intervalos 1985→2025 e 1990→2025 (`conversao.csv`).\n")

    w("## 9. Problemas conhecidos\n")
    w("- **Cenas de estação seca (2005, 2007).** As cenas únicas de out/2005 e ago/2007 inflam o construído bruto (vegetação seca/queimada); a regra 1 da 06b remove parte e a monotonia propaga o resto. O construído final salta de "
      f"{mm['1 construído'].loc[2000]:.0f} km² (2000) para {mm['1 construído'].loc[2005]:.0f} km² (2005), mais que os {mm['1 construído'].loc[2010] - mm['1 construído'].loc[2005]:.0f} km² de 2005 a 2010: resíduo provável de comissão em 2005.")
    w("- **1985** vem de uma cena de 1984 (GeoMAD inexistente), com ~1% de nuvens no NE (sem dado, não classificado).")
    w("- **2010** e **1990**: GeoMAD de poucas observações (faixas SLC-off do Landsat 7 / COUNT 3); o mar é corrigido pela regra 0.")
    w("- **Classe 3** mostra manchas anelares no NE do bbox (fora do perímetro urbano), de natureza não verificada (cicatrizes de queimada ou cultivo extensivo são hipóteses); a classe é indicativa.")
    w("- **Nuvem sobre o mar**: o erro conhecido de Maputo (nuvem → construído) não aparece nos mapas finais de 1985, 2000, 2019 e 2025 após a regra 0.")
    txt = "\n".join(L)
    old = (QA / "classificacao.md").read_text(encoding="utf-8") if (QA / "classificacao.md").exists() else ""
    ini = ("<!-- exatidao_2020:inicio -->", "<!-- exatidao_2020:fim -->")
    ini_s = ("<!-- sensibilidade_2020:inicio -->", "<!-- sensibilidade_2020:fim -->")
    for a_, b_ in (ini, ini_s):  # preserva as secoes anexadas por 11_avaliacao_exatidao.py
        if a_ in old and b_ in old:
            txt = txt.rstrip("\n") + "\n\n" + old[old.index(a_): old.index(b_) + len(b_)] + "\n"
    (QA / "classificacao.md").write_text(txt, encoding="utf-8")
    log("qa ok:", QA / "classificacao.md")


if __name__ == "__main__":
    main()
