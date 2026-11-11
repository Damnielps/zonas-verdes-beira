"""Constroi o artigo de ponta a ponta: artigo.md -> artigo_final.md, artigo.docx, artigo.pdf.

Uso: .venv/bin/python -I scripts/21_artigo.py [--tolerar] [--sem-pdf]

Etapas: (1) figuras 1-6 (fig1 e fig4 geradas; 2, 3 e 5 copiadas de dados/fig/class; 6 = anteprojeto de 1943); (2) quadros gerados;
(3) placeholders {{chave}}; (4) citacoes [@chave] -> autor-data ABNT e lista NBR 6023;
(5) artigo_final.md; (6) blocos JSON -> artigo.docx (artigo/build/build_docx.js) e HTML -> PDF (Chrome);
(7) exportacao web: site/artigo.html + site/artigo/{img,artigo.pdf} (só o PDF é oferecido para download no site).
Falhas duras (chave sem ficha, placeholder nao resolvido, figura ausente) abortam,
exceto com --tolerar, que registra o problema e segue com um fallback explicito.
Nao edita a prosa de artigo/artigo.md.
"""
import csv
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from ardosia_palette import (apply_ardosia, ARDOSIA, ARDOSIA_CL, ARDOSIA_NEV, TERRACOTA, PETROLEO,  # noqa: E402
                             PEDRA, GRAFITE, FILETE, TINTA, PAPEL_FIG)

# Citação exibida no site (rodapé e "Como citar"). DOI conceitual (Zenodo).
CITACAO_SITE = ("PESSINI SOBREIRA, Daniel. Zonas verdes da Beira (1985–2026): agricultura urbana, baixadas e "
                "expansão construída. Zenodo, 2026. DOI: 10.5281/zenodo.24147238.")

TOLERAR = "--tolerar" in sys.argv
SEM_PDF = "--sem-pdf" in sys.argv
ART = RAIZ / "artigo"
BUILD = ART / "build"
IMG = BUILD / "img"
FIGART = RAIZ / "dados" / "fig" / "artigo"
FICHAS = RAIZ / "fontes" / "fichas"
ACESSO = "11 nov. 2026"
ERROS = []   # falhas duras
AVISOS = []


def erro(msg):
    ERROS.append(msg)
    print("ERRO:", msg)


def lr(path):
    return list(csv.DictReader(open(path, encoding="utf8")))


def nbsp(s):
    return s.replace("\u202f", "\u00a0")


# ------------------------------------------------------------------ 1. figuras
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    apply_ardosia()
    return plt


def fig1():
    """Figura 1: área de estudo (município, postos, bairros, baixada <= 8 m, mangal de referência)."""
    import geopandas as gpd
    import rasterio
    from matplotlib.colors import ListedColormap
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from rasterio.features import rasterize
    from comum import BOUNDS
    plt = _plt()
    P = RAIZ / "dados" / "proc"
    with rasterio.open(P / "dem.tif") as r:
        dem, tr, shp, crs = r.read(1), r.transform, r.shape, r.crs
    with rasterio.open(P / "tpi.tif") as r:
        tpi = r.read(1)
    with rasterio.open(P / "rotulos" / "mangal_ref.tif") as r:
        mg = r.read(1) > 0
    with rasterio.open(P / "class_final" / "2025.tif") as r:
        c25 = r.read(1)
    mun = gpd.read_file(P / "limites.gpkg", layer="municipio").to_crs(crs)
    pos = gpd.read_file(P / "limites.gpkg", layer="distritos").to_crs(crs)
    bai = gpd.read_file(P / "limites.gpkg", layer="bairros").to_crs(crs)
    dentro = rasterize(((g, 1) for g in mun.geometry), out_shape=shp, transform=tr, fill=0).astype(bool)
    baixada = (dem <= 8) & (tpi < 0) & dentro
    img = np.zeros(shp, np.uint8)
    img[c25 == 6] = 1                      # água (classe final 2025)
    img[baixada] = 2
    img[mg & dentro] = 3
    cmap = ListedColormap([(0, 0, 0, 0), ARDOSIA_NEV, ARDOSIA_CL, PETROLEO])
    x0, y0, x1, y1 = BOUNDS
    fig, ax = plt.subplots(figsize=(6.3, 6.1))
    ax.imshow(img, cmap=cmap, vmin=0, vmax=3, extent=(x0, x1, y0, y1), interpolation="nearest", zorder=1)
    bai.boundary.plot(ax=ax, color=GRAFITE, lw=0.3, zorder=3)
    pos.boundary.plot(ax=ax, color=GRAFITE, lw=0.9, linestyle="--", zorder=4)
    mun.boundary.plot(ax=ax, color=TERRACOTA, lw=1.3, zorder=5)
    for nome, g in zip(pos.adm3_name, pos.geometry):
        p = g.representative_point()
        ax.annotate(nome, (p.x, p.y), fontsize=6.5, ha="center", color=TINTA, family="sans-serif", zorder=6)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.legend(handles=[
        Patch(fc=ARDOSIA_CL, label="Baixada (altitude ≤ 8 m e TPI < 0)"),
        Patch(fc=PETROLEO, label="Mangal de referência"),
        Patch(fc=ARDOSIA_NEV, label="Água (mapa de 2025)"),
        Line2D([0], [0], color=TERRACOTA, lw=1.3, label="Município da Beira"),
        Line2D([0], [0], color=GRAFITE, lw=0.9, ls=(0, (4, 2)), label="Postos administrativos"),
        Line2D([0], [0], color=GRAFITE, lw=0.4, label="Bairros")],
        loc="lower right", fontsize=6.5, frameon=True, facecolor=PAPEL_FIG, edgecolor=FILETE).set_zorder(10)
    out = FIGART / "fig1_area_estudo.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("fig1 ->", out)


def fig4():
    """Figura 4: três estimativas da fração construída por perímetro, 1985–2025, pequenos múltiplos."""
    plt = _plt()
    d = pd.read_csv(RAIZ / "dados/proc/areas/envelopes_comparacao.csv")
    d = d[d.epoca <= 2025]
    paineis = [
        ("baixada_dem<=8m_tpi<0", "Baixada (altitude ≤ 8 m, TPI < 0)"),
        ("mangal_ref_wc2020_gmw1996", "Mangal de referência"),
        ("osm_agricola", "Feições agrícolas do OpenStreetMap"),
        ("municipio_total", "Município inteiro"),
    ]
    est = [("pct_ghsl", "GHSL (superfície construída)", (0, (1, 1.6)), "o"),
           ("pct_bruto", "Classificação bruta", (0, (4, 2)), "s"),
           ("pct_final", "Classificação pós-processada", "-", "^")]
    fig, axs = plt.subplots(2, 2, figsize=(6.3, 5.0), sharex=True)
    for ax, (per, tit) in zip(axs.flat, paineis):
        s_ = d[d.perimetro == per].sort_values("epoca")
        cols = ["pct_ghsl", "pct_bruto", "pct_final"]
        lo, hi = s_[cols].min(axis=1), s_[cols].max(axis=1)
        ax.fill_between(s_.epoca, lo, hi, color=FILETE, alpha=0.6, lw=0, zorder=1)
        for col, lab, ls, mk in est:
            ax.plot(s_.epoca, s_[col], color=ARDOSIA if col != "pct_final" else TERRACOTA,
                    ls=ls, marker=mk, ms=2.8, lw=1.3, zorder=3, label=lab)
        ax.axvline(2019, color=PEDRA, lw=0.7, ls=(0, (3, 3)), zorder=0)
        ax.set_title(tit, fontsize=8, loc="left", family="sans-serif")
        ax.set_ylim(0, max(hi.max() * 1.15, 1))
        ax.yaxis.grid(True)
        ax.tick_params(labelsize=7)
    for ax in axs[:, 0]:
        ax.set_ylabel("Fração construída (%)", fontsize=7.5, family="sans-serif")
    axs[0, 0].text(2018.6, axs[0, 0].get_ylim()[1] * 0.04, "Idai", fontsize=6, color=GRAFITE, family="sans-serif", ha="right")
    for ax in axs[1]:
        ax.set_xticks([1985, 1995, 2005, 2015, 2025])
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out = FIGART / "fig4_envelopes.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("fig4 ->", out)


def reaproveita():
    """Figuras 2, 3 e 5: geradas em 08_qa_classificacao.py/07 já no estilo Ardósia; copiadas para dados/fig/artigo/."""
    mapa = {"fig2_painel_classes.png": "dados/fig/class/mapas_classes.png",
            "fig3_area_classes.png": "dados/fig/class/area_empilhada_municipio.png",
            "fig5_ano_conversao.png": "dados/fig/class/mapa_ano_conversao.png"}
    for dst, src in mapa.items():
        if not (RAIZ / src).exists():
            erro(f"figura ausente: {src}")
        else:
            shutil.copy2(RAIZ / src, FIGART / dst)


def legenda_fig6():
    r = next(x for x in lr(RAIZ / "fontes/figuras_planos.csv") if "fig7_anteprojecto_1943" in x["arquivo"])
    return r


FIGURAS = [  # (trecho do parágrafo após o qual entra a figura, nº, arquivo em dados/fig/artigo/, legenda, fonte)
    ("A análise cobre um retângulo", 2, "fig1_area_estudo.png",
     "Área de estudo: Município da Beira, postos administrativos, bairros, baixada e mangal de referência.",
     "elaboração própria; limites administrativos de [@ocha_codab_2025]; altitude do Copernicus DEM GLO-30 [@copernicus_dem]; "
     "TPI calculado pelos autores; mangal de referência = WorldCover 2020 ∪ Global Mangrove Watch v3 (1996); água do mapa de 2025."),
    ("A Figura 3 mostra o painel classificado", 3, "fig2_painel_classes.png",
     "Cobertura e uso do solo no Município da Beira e arredores, 1979–2026 (classificação final).",
     "elaboração própria, a partir de imagens Landsat [@usgs_landsat_c2; @deafrica_geomad]; a época de 1979 usa cena MSS [@usgs_landsat_mss] e é excluída das séries."),
    ("A Figura 3 mostra o painel classificado", 4, "fig3_area_classes.png",
     "Área por classe no município, 1985–2026 (inclui água interior).",
     "elaboração própria, a partir das classificações finais; a série de 1985 a 2026 tem épocas irregularmente espaçadas."),
    ("As baixadas do município, na definição adotada", 5, "fig4_envelopes.png",
     "Fração construída (%) segundo três estimativas, 1985–2025: baixada, mangal de referência, feições agrícolas do OpenStreetMap e município. A faixa cinza cobre o intervalo entre estimativas; a linha tracejada marca o ciclone Idai (2019).",
     "elaboração própria; GHSL GHS-BUILT-S R2023A [@pesaresi_2023]."),
    ("A conversão concentrou-se nos bairros", 6, "fig5_ano_conversao.png",
     "Ano de conversão de áreas agrícolas (classes 2 e 3) em construído, 1985–2026; a escala indica a época do mapa em que a conversão ficou estável.",
     "elaboração própria, a partir das classificações finais."),
]


def figuras_md():
    """Blocos Markdown de figura (alt = 'Figura N – legenda. Fonte: ...'), por trecho-âncora."""
    out = {}
    for anc, n, arq, cap, fonte in FIGURAS:
        p = f"../dados/fig/artigo/{arq}"
        out.setdefault(anc, []).append(f"![Figura {n} – {cap} Fonte: {fonte}]({p})")
    r = legenda_fig6()
    cap6 = ("Ante-Projecto de Urbanização da Cidade da Beira, de Joaquim de Oliveira Ribeiro Alegre e José Porto, 1943, "
            "com perspetiva.")
    fonte6 = (f"Figura 7 de [@fernandes_2016, p. 159], obtida via Redalyc ({r['url']}); autores: {r['autor']}; "
              f"data: {r['data']}; detentor: {r['detentor']}. Situação de direitos: reprodução com citação; direitos do original não verificados.")
    import shutil
    src6 = RAIZ / "dados/raw/planos/mealha/fig7_anteprojecto_1943_alegre_porto.jpg"
    dst6 = FIGART / "fig1_plano_1943.jpg"   # cópia versionada (material de terceiros; ver CREDITOS.md)
    if src6.exists():
        FIGART.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src6, dst6)
    out.setdefault("O primeiro plano geral de expansão foi", []).append(
        f"![Figura 1 – {cap6} Fonte: {fonte6}](../dados/fig/artigo/fig1_plano_1943.jpg)")
    return out


def inserir_figuras(md):
    paras = md.split("\n\n")
    ins = figuras_md()
    for anc, blocos in ins.items():
        for i, p in enumerate(paras):
            if anc in p and not p.startswith(("#", "!", "|")):
                paras[i] = p + "\n\n" + "\n\n".join(blocos)
                break
        else:
            erro(f"âncora de figura não encontrada: {anc}")
    return "\n\n".join(paras)


# ------------------------------------------------------------------ 2. quadros
def tabela_md(cab, linhas, alinh=None):
    alinh = alinh or ["---"] * len(cab)
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(esc(c) for c in cab) + " |", "|" + "|".join(alinh) + "|"]
    out += ["| " + " | ".join(esc(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def br(x, casas=0):
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def quadro1():
    """Planos: ano, plano, autor, aprovado, tratamento de agricultura/verde, fonte (citação autor-data)."""
    rows = sorted(lr(RAIZ / "fontes/planos.csv"), key=lambda r: (int(r["ano"]), r["id"]))
    linhas = []
    for r in rows:
        ap = r["aprovado[s/n/?]"].strip()
        cod, _, resto = ap.partition(" ")
        nome = {"s": "Sim", "n": "Não", "?": "Não confirmado"}.get(cod, cod)
        aprov = nome + (f" {resto}" if resto else "")
        trat = r["trata_agricultura"].strip()
        verde = r["trata_verde_mangal"].strip()
        tv = trat if verde.lower().startswith("sem tratamento") or not verde else f"{trat}; {verde}"
        chaves = [k.strip() for k in r["fonte_chave"].split(";") if k.strip() and k.strip() != "delagoabay_2018"]
        fonte = "[" + "; ".join(f"@{k}" for k in chaves) + "]"
        linhas.append((r["ano"], r["titulo"].strip(), r["autor"].strip(), aprov, tv, fonte))
    return ("Quadro 1 – Planos urbanísticos e projetos relativos à Beira e às suas terras húmidas, 1893–2022\n\n"
            + tabela_md(["Ano", "Plano ou projeto", "Autor/órgão", "Aprovado", "Agricultura; verde e mangal", "Fonte"], linhas)
            + "\n\nFonte: elaboração própria a partir de fontes/planos.csv e das fichas de leitura citadas. "
              "Nota: “n.i.” = não identificado nas fontes lidas; a entrada de 1975 refere-se ao programa nacional de zonas verdes.")


OBS_EPOCA = {
    "1979": "MSS de 60 m reamostrada a 30 m; sem bandas azul e SWIR; proxy do censo de 1980; fora das séries quantitativas",
    "1985": "Sem GeoMAD de 1985 (coleção vazia no bbox): cena TM de estação seca de 1984",
    "2005": "GeoMAD com faixas SLC-off do Landsat 7: substituído por cena TM",
    "2007": "GeoMAD com faixas SLC-off do Landsat 7: substituído por cena TM",
    "2010": "GeoMAD com faixas SLC-off mantido (alternativas pioraram a terra)",
    "2026": "Sem composição anual: mediana de cenas de maio a setembro",
}


def quadro2():
    oob = json.load(open(RAIZ / "dados/proc/class/oob.json"))["oob"]
    txt = (RAIZ / "docs/qa/composicoes.md").read_text(encoding="utf8").split("## Percentis")[0]
    linhas = []
    for l in txt.splitlines():
        m = re.match(r"\|\s*(\d{4})\s*\|(.*)\|\s*$", l)
        if not m:
            continue
        ep = m.group(1)
        c = [x.strip() for x in m.group(2).split("|")]
        fonte, sensor, datas = c[0], c[1], c[2]
        g = re.search(r"(gm_[a-z0-9_]+)", fonte)
        cena = re.search(r"\b(L[MTC]\d\d_L\d[A-Z]{2}_\d{6}_\d{8}_\d{2}_T\d)", fonte)
        if ep == "2026":
            n = re.search(r"mediana de (\d+) cenas", fonte).group(1)
            f = f"Mediana de {n} cenas Landsat 8/9 (Planetary Computer)"
        elif g:
            f = f"GeoMAD anual, Digital Earth Africa ({g.group(1)})"
        elif cena:
            f = f"Cena {cena.group(1)} (Planetary Computer)"
        else:
            f = fonte[:80]
        s = {"landsat-5": "Landsat 5 TM", "landsat-8 + landsat-9": "Landsat 8/9 OLI"}.get(sensor, sensor)
        if "/" in datas and len(datas) > 11:
            a, b = datas.split("/")
            iso = lambda t: "/".join(reversed(t.split("-")))
            d = f"ano de {a[:4]}" if (a.endswith("-01-01") and b.endswith("-12-31")) else f"{iso(a)} a {iso(b)}"
        else:
            d = "/".join(reversed(datas.split("-")))
        acc = oob.get(ep, {}).get("acc")
        linhas.append((ep, f, s, d, OBS_EPOCA.get(ep, "—"), br(acc, 2) if acc is not None else "—"))
    if len(linhas) != 15:
        erro(f"Quadro 2: esperadas 15 épocas (14 + 1979), achei {len(linhas)}")
    return ("Quadro 2 – Imagens, sensores e substituições por época do painel Landsat\n\n"
            + tabela_md(["Época", "Fonte/imagem", "Sensor", "Datas", "Observação", "OOB"], linhas)
            + "\n\nFonte: elaboração própria, a partir de docs/qa/composicoes.md e dados/proc/class/oob.json. "
              "OOB = exatidão out-of-bag dos modelos (reprodução dos rótulos de treino, não validação independente).")


def quadro3():
    pb = pd.read_csv(RAIZ / "dados/proc/areas/perda_bairro.csv")
    pb = pb[pb.grupo == "bairro"].sort_values("convertida_construido_ha", ascending=False).head(10)
    linhas = [(r.unidade, br(r.area_unidade_ha), br(r.zv_1990_ha), br(r.zv_2025_ha), br(r.convertida_construido_ha))
              for r in pb.itertuples()]
    return ("Quadro 3 – Os dez bairros com maior conversão de agricultura de baixada em construído, 1990–2025 (ha)\n\n"
            + tabela_md(["Bairro", "Área do bairro", "Agrícola em 1990", "Agrícola em 2025", "Convertida em construído"],
                        linhas, ["---", "---:", "---:", "---:", "---:"])
            + "\n\nFonte: elaboração própria, classificação pós-processada (dados/proc/areas/perda_bairro.csv). "
              "Nota: “agrícola” é a classe 2 (agricultura de baixada/hortícola), cuja exatidão do usuário é baixa (Seção 5.4); "
              "a conversão é a área classe 2 em 1990 e construída em 2025.")


def quadro4():
    rows = sorted(lr(RAIZ / "fontes/conflitos.csv"), key=lambda r: (int(r["ano"]), r["id"]))
    linhas = []
    for r in rows:
        pg = r["pagina"].strip()
        loc = f", p. {pg}" if pg and pg[0].isdigit() else ""
        linhas.append((r["ano"], r["local"], r["tipo"], f"[@{r['fonte_chave']}{loc}]"))
    return ("Quadro 4 – Conflitos de uso do solo documentados que envolvem baixadas e terras agrícolas na Beira\n\n"
            + tabela_md(["Ano", "Local", "Tipo", "Fonte"], linhas)
            + "\n\nFonte: elaboração própria a partir de fontes/conflitos.csv. Nota: o ano é o do evento ou do registro na fonte; "
              "descrições e coordenadas aproximadas estão no arquivo.")


# ------------------------------------------------------------------ 4. citacoes
SURN = re.compile(r"^\s*((?:[A-ZÀ-ÝÇ][A-ZÀ-ÝÇ'’\- ]+)|(?:Mc[A-Z]+)),\s")
OVERRIDE_LABEL = {"uccla_2020": "UCCLA", "cmb_2019": "CONSELHO MUNICIPAL DA BEIRA"}
# Autores institucionais: (regex do inicio da entrada na ficha, novo inicio "SIGLA – NOME", sigla usada na citacao)
SIGLAS = [
    (r"^JAPAN INTERNATIONAL COOPERATION AGENCY \(JICA\)", "JICA – JAPAN INTERNATIONAL COOPERATION AGENCY", "JICA"),
    (r"^CONSELHO MUNICIPAL DE MAPUTO(?: \(CMM\))?", "CMM – CONSELHO MUNICIPAL DE MAPUTO", "CMM"),
    (r"^REPÚBLICA DE MOÇAMBIQUE; INTERNATIONAL DEVELOPMENT ASSOCIATION", "IDA – INTERNATIONAL DEVELOPMENT ASSOCIATION; REPÚBLICA DE MOÇAMBIQUE", "IDA"),
    (r"^OCHA FIELD INFORMATION SERVICES SECTION(?: \(FISS\))?", "OCHA – FIELD INFORMATION SERVICES SECTION (FISS)", "OCHA"),
    (r"^FAO(?=\.)", "FAO – FOOD AND AGRICULTURE ORGANIZATION OF THE UNITED NATIONS", "FAO"),
    (r"^INSTITUTO NACIONAL DE PLANEAMENTO FÍSICO(?: \(INPF\))?", "INPF – INSTITUTO NACIONAL DE PLANEAMENTO FÍSICO", "INPF"),
]


def aplicar_sigla(ref):
    for rx, novo, sig in SIGLAS:
        if re.match(rx, ref):
            return re.sub(rx, novo, ref, count=1)
    return ref
BOLD_OVERRIDE = {"mougeot_2000": "Growing cities, growing food"}
REF_OVERRIDE = {
    # reformatações de cabeçalhos de ficha (nenhum dado novo): título em destaque, ano visível para o sufixo a/b/c
    "cmb_2019": ("CONSELHO MUNICIPAL DA BEIRA. **Beira Municipal Recovery and Resilience Plan: a roadmap to building Beira "
                 "back better**. Volume 1, Main Report. Beira, maio 2019. Assistência técnica do Governo dos Países Baixos, "
                 "UN-Habitat, Programa SHELTER (Arcadis). Disponível em: https://www.dutchwatersector.com/sites/default/files/"
                 "2019-06/Summary%20Beira%20Municipal%20Recovery%20and%20Resilience%20Plan.pdf."),
    "noticias_2016": ("CONFLITO de terras na Beira: mulheres amotinam-se no município. **Notícias**, Maputo, 23 nov. 2016. "
                      "Reprodução em: WLSA Moçambique. Disponível em: https://www.wlsa.org.mz/wp-content/uploads/2016/11/"
                      "CONFLITO-DE-TERRAS-NA-BEIRA.pdf."),
    "deltares_2013": ("DELTARES; WITTEVEEN+BOS. **Masterplan Beira, Mozambique: Summary (Masterplan Beira 2035)**. Delft/Deventer, "
                      "19 nov. 2013. Consórcio com Wissing, NIRAS Moçambique e VandenBroek, para o Conselho Municipal da Beira, "
                      "financiado pela Agência NL. Disponível em: https://www.dutchwatersector.com/sites/default/files/2019-06/"
                      "Summary%20Beira%20Masterplan%20English%20version.pdf."),
    "witteveenbos_2018": ("WITTEVEEN+BOS. **GreenInfra4Beira: integral process of sustainable design (notícia do projeto)**. 2018. "
                          "Parceiros: Deltares, Alterra (Wageningen UR), Wissing. Disponível em: "
                          "https://www.witteveenbos.com/news/greeninfra4beira-integral-process-of-sustainable-design."),
    "wb_icr_2021": ("WORLD BANK. **Implementation Completion Report Review: MZ - Cities and Climate Change (P123201)**. "
                    "Report ICRR0022585. Independent Evaluation Group. Washington: World Bank, 2021. Disponível em: "
                    "https://documents1.worldbank.org/curated/en/401241630075790853/text/Mozambique-MZ-Cities-Climate-Change.txt."),
    "iclei_2026_altomanga": ("ICLEI AFRICA. **Alto da Manga: settlement profile (dashboard e análise de risco)**. [S.l.]: ICLEI Africa, "
                             "2026. Material de aprendizagem. Disponível em: https://learnwithicleiafrica.org/wp-content/uploads/2026/08/Alto-da-Manga.pdf."),
    "iclei_2026_mungassa": ("ICLEI AFRICA. **Mungassa: settlement profile**. [S.l.]: ICLEI Africa, 2026. Material de aprendizagem. "
                            "Disponível em: https://learnwithicleiafrica.org/wp-content/uploads/2026/08/Mungassa.pdf."),
    "iclei_2026_ndunda": ("ICLEI AFRICA. **Ndunda: settlement profile**. [S.l.]: ICLEI Africa, 2026. Material de aprendizagem. "
                          "Disponível em: https://learnwithicleiafrica.org/wp-content/uploads/2026/08/Ndunda.pdf."),
    "leitgeb_2015": ("LEITGEB, Friedrich; SCHNEIDER, Sarah; VOGL, Christian R. Increasing food sovereignty with urban "
                     "agriculture in Cuba. **Agriculture and Human Values**, 2015. DOI: 10.1007/s10460-015-9616-9."),
    "rosario_2002": ("MUNICIPALIDAD DE ROSARIO. Concejo Municipal. **Ordenanza n. 7341: crea el Programa Municipal de "
                     "Desarrollo de la Agricultura Orgánica**. Sala de Sesiones, 17 jun. 2002."),
    "mougeot_2000": ("MOUGEOT, L. J. A. Urban agriculture: definition, presence, potentials and risks. In: "
                     "*Growing cities, growing food*: urban agriculture on the policy agenda. Feldafing: DSE/ZEL, 2000. "
                     "(Thematic Paper 1). Disponível em: https://ruaf.org/assets/2019/11/Growing-Cities-Growing-Food.pdf."),
}


def cabeca(linha):
    """Retorna (head, resto) separando autoria do resto da referencia."""
    for m in re.finditer(r"\.\s+", linha):
        pre = linha[:m.start()]
        prev = re.search(r"(\S+)$", pre).group(1)
        nxt = linha[m.end():].split(" ", 1)[0]
        if len(prev) == 1 and prev.isupper():
            if re.match(r"^[A-Z]\.[;,]?$", nxt) or nxt.startswith("(ed") or nxt[:1].islower():
                continue
        return linha[:m.start()], linha[m.end():]
    return linha, ""


def ficha_info(chave):
    p = FICHAS / f"{chave}.md"
    if not p.exists():
        return None
    ls = p.read_text(encoding="utf8").splitlines()
    ref = aplicar_sigla(ls[0].lstrip("# ").strip())
    st = next((l for l in ls if l.startswith("- status")), "- status: ?")
    url = next((l for l in ls if l.startswith("- url")), "")
    return {"ref": ref, "status": st.split(":", 1)[1].strip(), "url": url}


def autores_label(chave, head):
    if chave in OVERRIDE_LABEL:
        return OVERRIDE_LABEL[chave]
    for _, novo, sig in SIGLAS:
        if head.startswith(sig + " – "):
            return sig
    segs = [s.strip() for s in head.split(";")]
    if not SURN.match(segs[0] + ", x"):  # institucional (sem 'SOBRENOME,')
        pass
    if SURN.match(head + " ") or SURN.match(segs[0] + " "):
        sob = []
        for s in segs:
            m = SURN.match(s + " ") or re.match(r"^((?:[A-ZÀ-ÝÇ][A-ZÀ-ÝÇ'’\- ]+)|(?:Mc[A-Z]+)),", s)
            if m:
                sob.append(m.group(1).strip().upper())
        etal = "et al" in head
        if etal or len(sob) >= 4:
            return sob[0] + " et al."
        return "; ".join(sob)
    return re.sub(r"\s+", " ", head).upper() if head.isupper() or not head[:1].islower() else head.upper()


def ano_ref(ref):
    t = re.sub(r"\(catálogo:\s*\d{4}\)", "", ref)
    t = re.sub(r"Acesso em:\s*\d{1,2}\s\w+\.\s\d{4}\.?", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"DOI:?\s*\S+", "", t)
    t = re.sub(r"\(?\b\d{4}\s*[-–]\s*\d{4}\)?", "", t)
    t = re.sub(r"\d+\.\s*º|n\.º\s*\d+/\d{4}", "", t)
    anos = re.findall(r"(?<![\d/-])(1[89]\d\d|20[0-3]\d)(?![\d])", t)
    return anos[-1] if anos else "s.d."


def formatar_ref(chave, info):
    """Referencia NBR 6023 em markdown (** = destaque tipografico do titulo)."""
    if chave in REF_OVERRIDE:
        s = REF_OVERRIDE[chave]
    else:
        s = info["ref"]
    s = re.sub(r"\s*\(catálogo:\s*\d{4}\)", "", s)
    s = re.sub(r"\s*Acesso aberto,\s*CC BY[-A-Z]*\s*\d\.\d\.?", "", s)
    s = re.sub(r"\s*\(acesso aberto\)", "", s)
    s = re.sub(r"\s*\(CC BY 4\.0\)", "", s)
    s = re.sub(r"\s*Licença:\s*CC BY-IGO\.", "", s)
    s = re.sub(r"\bDOI\s+(?=10\.)", "DOI: ", s)
    s = re.sub(r"\bDOI:\s*10", "DOI: 10", s)
    s = s.strip()
    # titulo em destaque
    if "*" in s:
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"**\1**", s)
    elif chave in BOLD_OVERRIDE:
        pass
    else:
        head, resto = cabeca(s)
        if head and not head.isupper() and "," not in head and not head.startswith("Mc"):
            head = head.upper()   # autor institucional em caixa mista
        m = re.search(r"([.?!])\s+([^.?!]*?),\s+(?=v\.\s|n\.\s\d|\d{1,2}\s\w+\.\s\d{4})", resto)
        if " In: " in " " + resto:
            # capitulo de livro: titulo do capitulo simples, titulo do livro em negrito
            s = head + ". " + re.sub(
                r"(In:\s.*?\((?:ed|eds|org|orgs|coord)\.?\)\.?\s+)([^.?!*]+?)([.?!](?:\s|$))",
                lambda mm: f"{mm.group(1)}**{mm.group(2).strip()}**{mm.group(3)}", resto, count=1)
        elif m and ":" not in m.group(2) and not resto.lstrip().startswith("In:"):
            # artigo de periodico: destaca o periodico
            jr = m.group(2).strip()
            if jr and len(jr) < 120:
                s = head + ". " + resto[:m.start(2)] + f"**{jr}**" + resto[m.end(2):]
        elif resto and not resto.lstrip().startswith(("In:", "[", "\"")) and not head.startswith("MOÇAMBIQUE"):
            mt = re.search(r"(?<=[.?!])\s", resto)
            tit, post = (resto[:mt.start()], resto[mt.end():]) if mt else (resto, "")
            if tit and len(tit) > 8:
                tit = tit.rstrip(".")
                pt = "" if tit[-1] in "?!" else "."
                s = f"{head}. **{tit}**{pt}" + (f" {post}" if post else "")
    s = re.sub(r"(?:DOI:?\s*)?<?https?://(?:dx\.)?doi\.org/(10\.[^\s<>]+?)>?\.?(?=\s|$)", r"DOI: \1.", s)
    s = re.sub(r"(?<![\[\w])s\.\s?d\.(?!\])", "[s.d.]", s)
    # online / DOI
    tem_doi = re.search(r"DOI:?\s*10\.", s) is not None
    if "Disponível em:" not in s and "Acesso em" in s:
        s = re.sub(r"\s*Acesso em:\s*\d{1,2}\s\w+\.\s\d{4}\.?", "", s)
    if "Disponível em:" in s:
        s = re.sub(r"Disponível em:\s*(https?://\S+?)(?=\.?(?:\s|$))", r"Disponível em: <\1>", s)
        if "Acesso em" not in s:
            s = s.rstrip() + f" Acesso em: {ACESSO}."
    elif not tem_doi:
        u = re.search(r"https://doi\.org/(10\.\S+?)(?=[\s;.]*(?:\s|;|$))", info["url"])
        if u:
            s = s.rstrip() + f" DOI: {u.group(1).rstrip('.')}."
        else:
            u = re.search(r"https?://[^\s;()]+", info["url"])
            if u:
                s = s.rstrip() + f" Disponível em: <{u.group(0).rstrip('.')}>. Acesso em: {ACESSO}."
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\.\s*\.", ".", s)
    s = s.rstrip()
    if s and s[-1] not in ".?!":
        s += "."
    return s


def processar_citacoes(md):
    chaves = []
    for m in re.finditer(r"\[(@[^\]]+)\]", md):
        for part in m.group(1).split(";"):
            k = re.match(r"\s*@([A-Za-z0-9_]+)", part)
            if k and k.group(1) not in chaves:
                chaves.append(k.group(1))
    infos, base = {}, {}
    nao_verif, sem_ficha = [], []
    for k in chaves:
        info = ficha_info(k)
        if info is None:
            sem_ficha.append(k)
            erro(f"chave citada sem ficha em fontes/fichas/: {k}")
            if k == "clubofmozambique_2026":   # fallback explicito a partir de fontes/ref_L4.csv
                r = next(x for x in lr(RAIZ / "fontes/ref_L4.csv") if x["chave"] == k)
                info = {"ref": f"CLUB OF MOZAMBIQUE (LUSA). {r['titulo']}. {r['veiculo']}. Disponível em: {r['url']}. "
                               f"Acesso em: {ACESSO}.", "status": f"SEM FICHA (ref_L4.csv: {r['status']})", "url": ""}
            else:
                info = {"ref": f"[{k}: ficha ausente]", "status": "SEM FICHA", "url": ""}
        infos[k] = info
        if not info["status"].startswith("VERIFICADO") or info["status"].startswith("SEM FICHA"):
            nao_verif.append((k, info["status"]))
        head, _ = cabeca(info["ref"])
        base[k] = (autores_label(k, head), ano_ref(info["ref"]))
    # colisao autor+ano -> sufixos a, b, ...
    grupos = {}
    for k, v in base.items():
        grupos.setdefault(v, []).append(k)
    anos = {}
    for v, ks in grupos.items():
        if len(ks) > 1:
            for i, k in enumerate(sorted(ks)):
                anos[k] = v[1] + "abcdefghij"[i]
        else:
            anos[ks[0]] = v[1]

    def cit(m):
        partes = []
        for part in m.group(1).split(";"):
            mm = re.match(r"\s*@([A-Za-z0-9_]+)\s*(?:,\s*(.*))?$", part.strip())
            if not mm:
                erro(f"citacao mal formada: {m.group(0)}")
                return m.group(0)
            k, loc = mm.group(1), mm.group(2)
            t = f"{base[k][0]}, {'[s.d.]' if anos[k] == 's.d.' else anos[k]}" + (f", {loc.strip()}" if loc else "")
            partes.append(t)
        return "(" + "; ".join(partes) + ")"

    md2 = re.sub(r"\[(@[^\]]+)\]", cit, md)
    # lista de referencias (alfabetica)
    itens = []
    for k in chaves:
        s = formatar_ref(k, infos[k])
        ano = anos[k]
        if ano != base[k][1] or ano == "s.d.":
            # reescreve ano com sufixo (a/b) no texto da referencia
            if ano != "s.d.":
                corpo_s, sep, cauda = s.partition(" Disponível em:")
                corpo_s = re.sub(rf"(?<![\d]){base[k][1]}(?![\d])(?!.*{base[k][1]})", ano, corpo_s, count=1)
                s = corpo_s + sep + cauda
        itens.append((base[k][0], s, k))
    itens.sort(key=lambda t: (re.sub(r"[^A-ZÀ-Ý0-9 ]", "", t[0].upper().replace("Ç", "C")), anos[t[2]], t[1]))
    lista = "\n\n".join(t[1] for t in itens)
    nao_citadas = sorted(p.stem for p in FICHAS.glob("*.md") if p.stem not in chaves)
    return md2, lista, nao_verif, chaves, sem_ficha, nao_citadas, base, anos


def _num_en(m):
    t = m.group(0)
    if "," in t and re.search(r"[.\u00a0\u202f]", t.split(",")[0]) is None:
        return t.replace(",", ".")                       # decimal: 39,2 -> 39.2
    inteiro, _, dec = t.partition(",")
    inteiro = re.sub(r"[.\u00a0\u202f]", ",", inteiro)   # milhares: 6.239 -> 6,239
    return inteiro + ("." + dec if dec else "")


def abstract_decimais(md):
    """Apenas na secao Abstract: formato numerico ingles (39,2% -> 39.2%; 6.239 -> 6,239)."""
    m = re.search(r"(^#\s+Abstract\s*\n)(.*?)(?=^#\s|\Z)", md, re.S | re.M)
    if not m:
        AVISOS.append("secao Abstract nao encontrada: decimais nao convertidos")
        return md
    rx = r"(?<![\d.,])(?:[1-9]\d{0,2}(?:[.\u00a0\u202f]\d{3})+(?:,\d+)?|\d+,\d+)(?![\d])"
    corpo = re.sub(rx, _num_en, m.group(2))
    return md[:m.start(2)] + corpo + md[m.end(2):]


# ------------------------------------------------------------------ 5. markdown -> blocos
def runs(texto):
    out = []
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", texto):
        if not tok:
            continue
        if tok.startswith("**"):
            out.append({"t": tok[2:-2], "b": True})
        elif tok.startswith("*") and len(tok) > 2:
            out.append({"t": tok[1:-1], "i": True})
        else:
            out.append({"t": tok})
    return out


def para_blocos(md, meta):
    from PIL import Image
    linhas = md.split("\n")
    blocos = [{"type": "title", "titulo": meta["titulo"], "autor": meta["autor"], "orcid": meta["orcid"]}]
    i, modo = 0, "corpo"
    while i < len(linhas):
        l = linhas[i]
        if not l.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,2})\s+(.*)$", l)
        if m:
            nivel, t = len(m.group(1)), m.group(2).strip()
            modo = "resumo" if t in ("Resumo", "Abstract") else ("ref" if t == "Referências" else "corpo")
            blocos.append({"type": f"h{nivel}", "runs": runs(t), "unnum": not re.match(r"^\d", t)})
            i += 1
            continue
        m = re.match(r"^!\[(.*)\]\(([^)]*)\)\s*$", l)
        if m:
            alt, path = m.group(1), m.group(2)
            cap, _, fonte = alt.partition(" Fonte:")
            p = (ART / path).resolve()
            if not p.exists():
                erro(f"figura ausente: {path}")
                w = h = 1
            else:
                w, h = Image.open(p).size
            blocos.append({"type": "fig", "path": str(p), "w": w, "h": h, "caption": runs(cap.strip()),
                           "source": runs("Fonte:" + fonte) if fonte else []})
            i += 1
            continue
        if re.match(r"^(Quadro|Tabela) \d+ – ", l):
            cap = l.strip()
            i += 1
            while not linhas[i].strip():
                i += 1
            tab = []
            while i < len(linhas) and linhas[i].startswith("|"):
                tab.append(linhas[i])
                i += 1
            while i < len(linhas) and not linhas[i].strip():
                i += 1
            fonte = ""
            if i < len(linhas) and (linhas[i].startswith("Fonte:")):
                fonte = linhas[i].strip()
                i += 1
            cel = lambda ln: [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
            cab = cel(tab[0])
            alin = ["r" if c.strip().endswith(":") else "l" for c in cel(tab[1])]
            corpo = [cel(x) for x in tab[2:]]
            blocos.append({"type": "table", "caption": runs(cap), "header": cab, "rows": corpo, "align": alin,
                           "source": runs(fonte) if fonte else []})
            continue
        # paragrafo (linhas contiguas)
        buf = [l]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not re.match(r"^(#|!\[|\|)", linhas[i]):
            buf.append(linhas[i])
            i += 1
        t = " ".join(x.strip() for x in buf)
        if modo == "ref":
            blocos.append({"type": "ref", "runs": runs(t)})
        elif modo == "resumo":
            blocos.append({"type": "resumo", "runs": runs(t)})
        else:
            blocos.append({"type": "p", "runs": runs(t)})
    return blocos


def contar_palavras(blocos):
    n_corpo = n_total = 0
    em_corpo = False
    for b in blocos:
        if b["type"] in ("h1", "h2"):
            t = "".join(r["t"] for r in b["runs"])
            if b["type"] == "h1":
                em_corpo = bool(re.match(r"^\d", t))
                if t == "Referências":
                    em_corpo = False
        if b["type"] in ("p",) and em_corpo:
            n_corpo += len(re.findall(r"\S+", "".join(r["t"] for r in b["runs"])))
        if b["type"] in ("p", "resumo"):
            n_total += len(re.findall(r"\S+", "".join(r["t"] for r in b["runs"])))
    return n_corpo, n_total


# ------------------------------------------------------------------ HTML / PDF
def html_runs(rs):
    out = ""
    for r in rs:
        t = html.escape(r["t"])
        if r.get("b"):
            t = f"<strong>{t}</strong>"
        if r.get("i"):
            t = f"<em>{t}</em>"
        out += t
    return out


CSS_IMPRESSAO = """
@page { size: A4; margin: 3cm 2cm 2cm 3cm;
  @bottom-right { content: counter(page); font-family: var(--ard-sans); font-size: 8pt; color: var(--ard-text-3); }
  @bottom-left { content: "Pessini Sobreira · Zonas verdes da Beira (1985–2026)"; font-family: var(--ard-sans); font-size: 8pt; color: var(--ard-text-3); } }
html { background: #fff; }
body { font-family: Georgia, var(--ard-serif); font-size: 11pt; line-height: 1.5; color: var(--ard-grafite-cl); margin: 0; background: transparent; }
h1.titulo { font-weight: 400; font-size: 20pt; line-height: 1.2; color: var(--ard-tinta); margin: 0 0 10pt; }
.autor { font-family: var(--ard-sans); font-size: 10pt; color: var(--ard-grafite); margin: 0; }
.orcid { font-family: var(--ard-sans); font-size: 8.5pt; color: var(--ard-text-3); margin: 0 0 18pt; padding-bottom: 10pt; border-bottom: 1px solid var(--ard-filete); }
h1 { font-weight: 400; font-size: 15pt; color: var(--ard-tinta); margin: 22pt 0 8pt; padding-bottom: 3pt; border-bottom: 1px solid var(--ard-filete); break-after: avoid; }
h2 { font-weight: 700; font-size: 11.5pt; color: var(--ard-tinta); margin: 16pt 0 5pt; break-after: avoid; }
p { text-align: justify; hyphens: auto; margin: 0 0 7pt; text-indent: 1.25cm; orphans: 3; widows: 3; }
p.resumo { text-indent: 0; line-height: 1.3; font-size: 10pt; }
p.ref { text-indent: 0; text-align: left; line-height: 1.25; font-size: 9.5pt; margin: 0 0 7pt; hyphens: manual; overflow-wrap: anywhere; }
figure { margin: 12pt 0 12pt; padding: 0; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 17.5cm; }
figcaption { font-family: var(--ard-sans); font-size: 8.5pt; color: var(--ard-grafite); text-align: left; line-height: 1.3; margin-top: 4pt; }
figcaption .fonte { color: var(--ard-text-3); display: block; }
.quadro { margin: 12pt 0; }
.quadro .cap { font-family: var(--ard-sans); font-size: 8.5pt; color: var(--ard-grafite); font-weight: 600; margin-bottom: 4pt; break-after: avoid; }
.quadro .fonte { font-family: var(--ard-sans); font-size: 8pt; color: var(--ard-text-3); margin-top: 3pt; line-height: 1.3; }
table { width: 100%; border-collapse: collapse; font-family: var(--ard-sans); font-size: 8pt; line-height: 1.3; }
th { text-align: left; color: var(--ard-primaria); font-weight: 600; border-bottom: 1.5px solid var(--ard-primaria); border-top: 0; padding: 3pt 4pt; vertical-align: bottom; }
td { padding: 3pt 4pt; border-bottom: 0.5pt solid var(--ard-filete-cl); vertical-align: top; }
th.r, td.r { text-align: right; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
"""


def montar_html(blocos, meta, saida):
    css_ard = (RAIZ / "site/assets/ardosia.css").read_text(encoding="utf8")
    css_ard = re.sub(r"@import[^;]+;", "", css_ard)
    # remove regras de body/h1.. do ardosia.css que conflitem: usamos apenas os tokens (:root)
    tokens = css_ard.split("[data-theme")[0]
    partes = []
    for b in blocos:
        t = b["type"]
        if t == "title":
            partes.append(f'<h1 class="titulo">{html.escape(b["titulo"])}</h1><p class="autor">{html.escape(b["autor"])}</p>'
                          f'<p class="orcid">ORCID: https://orcid.org/{b["orcid"]}</p>')
        elif t in ("h1", "h2"):
            partes.append(f"<{t}>{html_runs(b['runs'])}</{t}>")
        elif t == "p":
            partes.append(f"<p>{html_runs(b['runs'])}</p>")
        elif t == "resumo":
            partes.append(f'<p class="resumo">{html_runs(b["runs"])}</p>')
        elif t == "ref":
            partes.append(f'<p class="ref">{html_runs(b["runs"])}</p>')
        elif t == "fig":
            rel = Path(b["path"]).as_uri()
            src = f'<span class="fonte">{html_runs(b["source"])}</span>' if b["source"] else ""
            partes.append(f'<figure><img src="{rel}" alt=""><figcaption>{html_runs(b["caption"])}{src}</figcaption></figure>')
        elif t == "table":
            w = b.get("widths") or [1] * len(b["header"])
            tot = sum(w)
            cg = "".join(f'<col style="width:{100 * x / tot:.1f}%">' for x in w)
            th = "".join(f'<th class="{"r" if a == "r" else ""}">{html.escape(c)}</th>' for c, a in zip(b["header"], b["align"]))
            tb = "".join("<tr>" + "".join(f'<td class="{"r" if a == "r" else ""}">{html.escape(c)}</td>'
                                          for c, a in zip(r, b["align"])) + "</tr>" for r in b["rows"])
            src = f'<div class="fonte">{html_runs(b["source"])}</div>' if b["source"] else ""
            partes.append(f'<div class="quadro"><div class="cap">{html_runs(b["caption"])}</div>'
                          f'<table><colgroup>{cg}</colgroup><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>{src}</div>')
    doc = (f'<!doctype html><html lang="pt"><head><meta charset="utf-8"><title>{html.escape(meta["titulo"])}</title>'
           f'<style>{tokens}\n{CSS_IMPRESSAO}</style></head><body>{"".join(partes)}</body></html>')
    Path(saida).write_text(doc, encoding="utf8")


# ------------------------------------------------------------------ 7. exportacao web (site/artigo.html)
SITE = RAIZ / "site"
NAV_SITE = [("linha-do-tempo", "Linha do tempo"), ("painel", "Painel"), ("areas", "Áreas"), ("conversao", "Conversão"),
            ("planejado", "Planejado × ocorrido"), ("producao", "Produção"), ("planos", "Planos"),
            ("comparacao", "Cidades"), ("metodologia", "Metodologia")]


def _slug(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


def _linkar(h):
    """Transforma URLs soltas (ja escapadas) em links; tira pontuacao final do href."""
    def sub(m):
        u = m.group(0)
        fim = ""
        while u and u[-1] in ".,;)":
            fim = u[-1] + fim
            u = u[:-1]
        return f'<a href="{u}" rel="noopener">{u}</a>{fim}'
    return re.sub(r"https?://[^\s<]+", sub, h)


def exportar_web(blocos, meta):
    from PIL import Image
    dest = SITE / "artigo"
    (dest / "img").mkdir(parents=True, exist_ok=True)
    if (ART / "artigo.pdf").exists():
        shutil.copy2(ART / "artigo.pdf", dest / "artigo.pdf")
    (dest / "artigo.docx").unlink(missing_ok=True)  # o site oferece só o PDF
    tam = lambda ext: f"{(dest / f'artigo.{ext}').stat().st_size / 1e6:.1f}".replace(".", ",") + " MB" if (dest / f"artigo.{ext}").exists() else ""

    partes, sumario = [], []
    aberta = False
    n_fig = 0
    lang_en = False

    def fecha():
        nonlocal aberta
        if aberta:
            partes.append("</section>")
            aberta = False

    for b in blocos:
        t = b["type"]
        if t == "title":
            continue
        if t in ("h1", "h2"):
            txt = "".join(r["t"] for r in b["runs"])
            sid = "s-" + _slug(txt)
            if t == "h1":
                fecha()
                lang_en = txt == "Abstract"
                partes.append(f'<section class="sec-art" id="{sid}"' + (' lang="en"' if lang_en else "") + ">")
                aberta = True
                partes.append(f'<h2>{html_runs(b["runs"])}</h2>')
                sumario.append((1, sid, txt))
            else:
                partes.append(f'<h3 id="{sid}">{html_runs(b["runs"])}</h3>')
                sumario.append((2, sid, txt))
        elif t == "p":
            partes.append(f'<p>{html_runs(b["runs"])}</p>')
        elif t == "resumo":
            partes.append(f'<p class="resumo">{html_runs(b["runs"])}</p>')
        elif t == "ref":
            partes.append(f'<p class="ref">{_linkar(html_runs(b["runs"]))}</p>')
        elif t == "fig":
            n_fig += 1
            mnum = re.match(r"Figura (\d+)", "".join(r["t"] for r in b["caption"]))
            num = int(mnum.group(1)) if mnum else n_fig
            nome = f"fig{num}.webp"
            if Path(b["path"]).exists():
                im = Image.open(b["path"]).convert("RGB")
                if im.width > 1800:
                    im = im.resize((1800, round(im.height * 1800 / im.width)), Image.LANCZOS)
                im.save(dest / "img" / nome, "WEBP", quality=84, method=6)
                w, h = im.size
            else:
                w = h = 1
            legenda = "".join(r["t"] for r in b["caption"])
            alt = legenda.split(". ")[0][:200]
            src = f'<span class="fonte">{html_runs(b["source"])}</span>' if b["source"] else ""
            partes.append(f'<figure class="fig-art" id="fig-{num}"><a href="artigo/img/{nome}" aria-label="Abrir a figura {num} em tamanho inteiro">'
                          f'<img src="artigo/img/{nome}" width="{w}" height="{h}" loading="lazy" alt="{html.escape(alt)}"></a>'
                          f'<figcaption>{html_runs(b["caption"])}{src}</figcaption></figure>')
        elif t == "table":
            cap = "".join(r["t"] for r in b["caption"])
            tid = "q-" + _slug(cap.split(" – ")[0])
            th = "".join(f'<th scope="col"{" class=num" if a == "r" else ""}>{html.escape(c)}</th>' for c, a in zip(b["header"], b["align"]))
            tb = "".join("<tr>" + "".join((f'<th scope="row">{html.escape(c)}</th>' if k == 0 and a != "r" else
                                          f'<td{" class=num" if a == "r" else ""}>{html.escape(c)}</td>')
                                         for k, (c, a) in enumerate(zip(r, b["align"]))) + "</tr>" for r in b["rows"])
            src = f'<p class="fonte">{html_runs(b["source"])}</p>' if b["source"] else ""
            partes.append(f'<div class="quadro-art" id="{tid}"><p class="cap" id="{tid}-cap">{html_runs(b["caption"])}</p>'
                          f'<div class="tab-rolavel" tabindex="0" role="region" aria-labelledby="{tid}-cap">'
                          f'<table class="tab-art"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>{src}</div>')
    fecha()

    toc, sub_aberta, item_aberto = [], False, False
    for nivel, sid, txt in sumario:
        li = f'<a href="#{sid}">{html.escape(txt)}</a>'
        if nivel == 1:
            if sub_aberta:
                toc.append("</ol>")
                sub_aberta = False
            if item_aberto:
                toc.append("</li>")
            toc.append(f"<li>{li}")
            item_aberto = True
        else:
            if not sub_aberta:
                toc.append('<ol class="sub">')
                sub_aberta = True
            toc.append(f"<li>{li}</li>")
    if sub_aberta:
        toc.append("</ol>")
    if item_aberto:
        toc.append("</li>")
    toc_html = "<ol>" + "".join(toc) + "</ol>"

    nav = "".join(f'<a href="index.html#{i}">{html.escape(n)}</a>' for i, n in NAV_SITE) + '<a href="artigo.html" aria-current="page">Artigo</a>'
    baixar = (f'<div class="baixar" role="group" aria-label="Baixar o artigo">'
              f'<a class="btn-baixar" href="artigo/artigo.pdf" download>Baixar PDF <span>{tam("pdf")}</span></a>'
              '</div>')
    # metadados de indexacao (SEO, Google Scholar, JSON-LD), lidos do proprio texto
    import json as _json
    _res = [("".join(r["t"] for r in x["runs"])).strip() for x in blocos if x["type"] == "resumo"]
    _resumo_pt = next((x for x in _res if not x.lower().startswith(("palavras-chave", "keywords"))), "")
    _kw = next((x.split(":", 1)[1].strip().rstrip(".") for x in _res if x.lower().startswith("palavras-chave")), "")
    _kws = [k.strip() for k in _kw.split(";") if k.strip()]
    _desc = _resumo_pt if len(_resumo_pt) <= 155 else _resumo_pt[:155].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    _base = "https://damnielps.github.io/zonas-verdes-beira/"
    _url = _base + "artigo.html"
    _pdf = _base + "artigo/artigo.pdf"
    _doi = "10.5281/zenodo.24147238"
    _autor_ci = "Pessini Sobreira, Daniel"
    _img = _base + "artigo/img/fig4.webp"
    _ld = {"@context": "https://schema.org", "@type": "ScholarlyArticle", "headline": meta["titulo"],
           "author": {"@type": "Person", "name": "Daniel Pessini Sobreira", "sameAs": "https://orcid.org/" + meta["orcid"]},
           "datePublished": "2026-11-11", "inLanguage": "pt", "identifier": "https://doi.org/" + _doi,
           "url": _url, "isPartOf": {"@type": "WebSite", "name": "Zonas verdes da Beira, 1985–2026", "url": _base},
           "license": "https://opensource.org/licenses/MIT", "abstract": _resumo_pt, "keywords": _kws}
    _ld_json = _json.dumps(_ld, ensure_ascii=False, indent=2).replace("</", "<\\/")
    _e = lambda v: html.escape(v, quote=True)
    seo = f"""<meta name="description" content="{_e(_desc)}">
<link rel="canonical" href="{_url}">
<meta name="robots" content="index, follow">
<meta name="author" content="Daniel Pessini Sobreira">
<meta property="og:type" content="article">
<meta property="og:title" content="{_e(meta["titulo"])}">
<meta property="og:description" content="{_e(_desc)}">
<meta property="og:url" content="{_url}">
<meta property="og:locale" content="pt_BR">
<meta property="og:site_name" content="Zonas verdes da Beira, 1985–2026">
<meta property="og:image" content="{_img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="citation_title" content="{_e(meta["titulo"])}">
<meta name="citation_author" content="{_autor_ci}">
<meta name="citation_publication_date" content="2026/11/11">
<meta name="citation_language" content="pt">
<meta name="citation_doi" content="{_doi}">
<meta name="citation_pdf_url" content="{_pdf}">
<meta name="citation_abstract_html_url" content="{_url}">
<meta name="citation_keywords" content="{_e('; '.join(_kws))}">
<meta name="citation_publisher" content="Zenodo">
<script type="application/ld+json">
{_ld_json}
</script>
"""
    doc = f"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(meta["titulo"])} (artigo)</title>
{seo}<link rel="stylesheet" href="assets/ardosia.css">
<link rel="stylesheet" href="assets/site.css">
<link rel="stylesheet" href="assets/correcoes.css">
<link rel="stylesheet" href="assets/artigo.css">
</head>
<body class="pagina-artigo">
<a class="skip" href="#texto">Ir para o texto</a>
<header class="topo">
  <div class="wrap">
    <a class="topo__marca" href="index.html">Zonas verdes da Beira</a>
    <nav aria-label="Seções">{nav}</nav>
    <button type="button" class="btn-tema" id="btnTema" aria-label="Alternar tema claro e escuro">Tema</button>
  </div>
</header>
<main class="wrap artigo-layout">
  <aside class="artigo-lado" aria-label="Sumário e downloads">
    <div class="caixa-baixar">
      <p class="rot">Baixar</p>
      {baixar}
    </div>
    <details class="sumario" open>
      <summary>Sumário</summary>
      <nav aria-label="Sumário do artigo">{toc_html}</nav>
    </details>
  </aside>
  <article class="artigo" id="texto" lang="pt-BR">
    <header class="artigo-cab">
      <p class="ard-kicker">Artigo científico</p>
      <h1>{html.escape(meta["titulo"])}</h1>
      <p class="autor">{html.escape(meta["autor"])}</p>
      <p class="orcid">ORCID: <a href="https://orcid.org/{html.escape(meta["orcid"])}" rel="noopener">https://orcid.org/{html.escape(meta["orcid"])}</a></p>
      {baixar}
    </header>
    {"".join(partes)}
    <section class="sec-art citar" id="como-citar">
      <h2>Como citar</h2>
      <p class="cit">{html.escape(CITACAO_SITE)}</p>
      <p class="nota">Este texto é a versão web do artigo, gerada a partir do mesmo arquivo-fonte do PDF; os números vêm de <code>dados/proc/resultados.json</code>. A <a href="index.html#metodologia">seção de metodologia do site</a> descreve como os números foram produzidos.</p>
      {baixar}
    </section>
  </article>
</main>
<footer class="rodape"><div class="wrap"><p>{html.escape(CITACAO_SITE)}</p></div></footer>
<script src="assets/artigo.js"></script>
</body>
</html>
"""
    (SITE / "artigo.html").write_text(doc, encoding="utf8")
    print(f"web: site/artigo.html ({len(doc) // 1024} KB), {n_fig} figuras em site/artigo/img/")


LARGURAS = {  # pesos relativos de colunas, por (1.o cabeçalho, nº de colunas)
    ("Ano", 6): [5, 20, 16, 12, 30, 17],
    ("Ano", 4): [7, 30, 36, 27],
    ("Época", 6): [7, 27, 12, 14, 32, 8],
    ("Bairro", 5): [24, 18, 19, 19, 20],
}


def main():
    FIGART.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    fig1()
    fig4()
    reaproveita()
    mapa_img = {}

    bruto = (ART / "artigo.md").read_text(encoding="utf8")
    m = re.match(r"^---\n(.*?)\n---\n", bruto, re.S)
    if not m:
        erro("cabecalho YAML nao encontrado")
        return
    cab = m.group(1)
    meta = {k: re.search(rf'^{k}:\s*"(.*)"\s*$', cab, re.M).group(1) for k in ("titulo", "autor", "orcid")}
    md = bruto[m.end():]

    vals = json.load(open(ART / "valores.json", encoding="utf8"))
    blocos_gerados = {
        "QUADRO_1_PLANOS": quadro1(), "QUADRO_2_EPOCAS": quadro2(), "QUADRO_3_BAIRROS": quadro3(),
        "QUADRO_4_CONFLITOS": quadro4(),
    }
    # quadros gerados entram antes: as chaves citadas nas linhas "Fonte:" contam como citadas
    for k, v in blocos_gerados.items():
        md = md.replace("{{" + k + "}}", v)
    md = inserir_figuras(md)
    md, lista, nao_verif, chaves, sem_ficha, nao_citadas, base, anos = processar_citacoes(md)
    if "{{REFERENCIAS}}" in md:
        md = md.replace("{{REFERENCIAS}}", lista)
    else:
        md = md.rstrip() + "\n\n" + lista + "\n"
    md = re.sub(r"\{\{(\w+)\}\}", lambda mm: vals[mm.group(1)] if mm.group(1) in vals else mm.group(0), md)
    pend = sorted(set(re.findall(r"\{\{[^}]*\}\}", md)))
    if pend:
        erro(f"placeholders nao resolvidos: {pend}")
    for a, b in mapa_img.items():
        md = md.replace(a, b)
    md = abstract_decimais(md)
    md = nbsp(md)
    (ART / "artigo_final.md").write_text(md, encoding="utf8")

    nv = sorted((k, st) for k, st in nao_verif if st.startswith(("NAO_VERIFICADO", "SEM FICHA")))
    parc = sorted((k, st) for k, st in nao_verif if (k, st) not in nv)
    (BUILD / "citacoes_nao_verificadas.txt").write_text(
        "Chaves citadas em artigo.md com status NAO_VERIFICADO ou sem ficha (deve ficar vazio):\n"
        + "".join(f"{k}\t{st}\n" for k, st in nv)
        + "\nInformativo: chaves citadas com ficha PARCIAL (lidas em parte; conferir o trecho citado):\n"
        + "".join(f"{k}\t{st[:120]}\n" for k, st in parc), encoding="utf8")
    print(f"NAO_VERIFICADO/sem ficha: {[k for k, _ in nv]}; PARCIAL: {len(parc)}")

    blocos = para_blocos(md, meta)
    for b in blocos:
        if b["type"] == "table":
            b["widths"] = LARGURAS.get((b["header"][0], len(b["header"])), [1] * len(b["header"]))
    n_corpo, n_total = contar_palavras(blocos)
    n_fig = sum(b["type"] == "fig" for b in blocos)
    n_tab = sum(b["type"] == "table" for b in blocos)
    json.dump({"blocos": blocos, "meta": meta}, open(BUILD / "blocos.json", "w", encoding="utf8"), ensure_ascii=False)

    # docx
    r = subprocess.run(["node", str(BUILD / "build_docx.js"), str(BUILD / "blocos.json"), str(ART / "artigo.docx")],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[:2000])
    if r.returncode != 0:
        erro("falha ao gerar docx")

    # html + pdf
    montar_html(blocos, meta, BUILD / "artigo.html")
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if SEM_PDF:
        pass
    elif Path(chrome).exists():
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ART / 'artigo.pdf'}", (BUILD / "artigo.html").as_uri()],
                       timeout=240, capture_output=True)
        print("pdf", (ART / "artigo.pdf").stat().st_size // 1024, "KB" if (ART / "artigo.pdf").exists() else "")
    else:
        AVISOS.append("Chrome nao encontrado: PDF nao gerado")

    try:
        exportar_web(blocos, meta)
    except Exception as e:  # noqa: BLE001
        erro(f"exportacao web falhou: {e!r}")

    print("\n=== RELATORIO ===")
    print(f"palavras do corpo (secoes 1-8, sem referencias, quadros, legendas): {n_corpo}")
    print(f"palavras incl. resumo e abstract: {n_total}")
    print(f"figuras: {n_fig} | tabelas/quadros: {n_tab} | chaves citadas: {len(chaves)}")
    print(f"chaves sem ficha: {sem_ficha}")
    print(f"citadas nao VERIFICADO ({len(nao_verif)}): {[k for k, _ in nao_verif]}")
    print(f"fichas nao citadas (informativo, nao entram na lista): {len(nao_citadas)}")
    print("avisos:", AVISOS)
    if ERROS:
        print("ERROS:", *ERROS, sep="\n  ")
        if not TOLERAR:
            sys.exit(1)


if __name__ == "__main__":
    main()
