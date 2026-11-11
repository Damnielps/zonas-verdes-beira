"""12 - Resultados consolidados (fonte única de números do site e do artigo) e exportação do site (Beira).

Entradas: dados/proc/areas/*, dados/proc/class/oob.json, dados/proc/validacao/exatidao_2020.json (opcional),
dados/proc/limites.gpkg, dem.tif, tpi.tif, fontes/*.csv, CREDITOS.md, comp/ e class_final/,
../zonas.verdes.maputo/dados/proc/resultados.json (referência publicada de Maputo; opcional).
Saídas:
  dados/proc/resultados.json     (o campo "citacao" e "doi", se já preenchidos à mão, são preservados)
  site/dados/dados.js            (window.DADOS = {...}; funciona em file://)
  site/dados/limites.geojson, baixada8.geojson, conflitos.geojson
  site/dados/*.csv               (tabelas para download) e resultados.json
  site/img/painel/*.webp         (imagem, classificação, conversão; EPSG:3857) e painel.json (cantos lon/lat)
Uso: .venv/bin/python -I scripts/12_resultados.py [--sem-rasters]
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import shapely
from PIL import Image
from pyproj import Transformer
from rasterio import features
from rasterio.warp import calculate_default_transform, reproject, Resampling

from comum import *  # noqa
import ardosia_palette as P

AREAS = PROC / "areas"
FONTES = RAIZ / "fontes"
SITE = RAIZ / "site"
SDADOS = SITE / "dados"
SPAINEL = SITE / "img" / "painel"
CLS = PROC / "class_final"
HA = RES * RES / 1e4
AGR_COD = [1, 2, 3, 45, 6, 7]
AGR_NOME = {1: "Construído", 2: "Agricultura de baixada e hortícola (indicativa)", 3: "Cultivo e mosaico de terra firme (indicativo)",
            45: "Vegetação natural e zonas húmidas (inclui mangal)", 6: "Água", 7: "Solo exposto e areia"}
# cores do mapa classificado: apenas paleta Ardósia (ardosia_palette.py)
COR_CLASSE = {1: P.TERRACOTA, 2: P.PETROLEO, 3: P.OCRE, 45: P.VIZ_MUTED, 6: P.ARDOSIA, 7: P.BORDO}
EP_ANALISE = [e for e in EPOCAS if e != 1979]
MARCO_TIPO = {"plano": "Plano", "politica": "Política", "obra": "Obra", "ciclone": "Ciclone", "outro": "Outro"}
AMBITO = "municipio"
ENV_ROT = {
    "baixada_dem<=8m_tpi<0": "Baixadas (altitude ≤ 8 m, TPI < 0)",
    "baixada_dem<=6m_tpi<0": "Baixadas (≤ 6 m, sensibilidade)",
    "baixada_dem<=10m_tpi<0": "Baixadas (≤ 10 m, sensibilidade)",
    "mangal_ref_wc2020_gmw1996": "Mangal de referência (WorldCover 2020 ∪ GMW 1996)",
    "osm_agricola": "Feições agrícolas do OpenStreetMap",
    "municipio_total": "Município (sem água permanente)",
}
MESES = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]
MESES_EXT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def nn(v):
    """NaN -> None; numpy -> python."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is pd.NA:
        return None
    return v


def registros(df):
    return [{k: nn(v) for k, v in r.items()} for r in df.to_dict("records")]


def r0(x):
    return int(round(float(x)))


def r1(x):
    return round(float(x), 1)


def data_ext(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{d} de {MESES_EXT[m - 1]} de {y}"


# ----------------------------------------------------------------------------- tabelas
def tabelas():
    R = {}
    ac = pd.read_csv(AREAS / "areas_agregado_classe_epoca.csv")
    mun = ac[ac.ambito == AMBITO]
    R["areas_municipio"] = {}
    R["areas_municipio_pct"] = {}
    R["sem_dado_municipio_ha"] = {}
    for ep in EP_ANALISE:
        d = mun[mun.epoca == ep].set_index("classe_agr")
        R["areas_municipio"][str(ep)] = {str(k): r0(d.loc[k, "ha"]) for k in AGR_COD}
        R["areas_municipio_pct"][str(ep)] = {str(k): r1(d.loc[k, "pct_com_dado"]) for k in AGR_COD}
        R["sem_dado_municipio_ha"][str(ep)] = r0(d.loc[0, "ha"])
    d79 = mun[mun.epoca == 1979].set_index("classe_agr")
    R["areas_1979_indicativa"] = {
        "nota": "1979 (MSS, 60 m) tem legenda reduzida: classe 3 = toda a vegetação fora da baixada, classe 45 ausente. Fica fora das séries quantitativas.",
        "ha": {str(k): r0(d79.loc[k, "ha"]) for k in AGR_COD}}
    R["area_municipio_ha"] = r0(sum(R["areas_municipio"]["2020"].values()))

    dd = pd.read_csv(AREAS / "areas_agregado_distrito.csv")
    R["areas_posto"] = {}
    for un, g in dd[dd.epoca != 1979].groupby("unidade"):
        R["areas_posto"][un] = {str(ep): {str(k): r0(x.ha.iloc[0]) for k, x in gg.groupby("classe_agr") if k in AGR_COD}
                                for ep, gg in g.groupby("epoca")}

    cv = pd.read_csv(AREAS / "conversao.csv")
    cvc = cv[cv.ambito == AMBITO].copy()

    def lin(r):
        return dict(t0=int(r.t0), t1=int(r.t1), anos=int(r.anos),
                    agri_para_construido_ha=r0(r.ha_agri_para_construido), agri_ha_ano=r1(r.ha_agri_ano),
                    agri_pct_inicial=r1(r.pct_agri_inicial), zv_para_construido_ha=r0(r.ha_zv_para_construido),
                    zv_ha_ano=r1(r.ha_zv_ano), zv_pct_inicial=r1(r.pct_zv_inicial),
                    area_agri_inicial_ha=r0(r.area_agri_inicial_ha), area_zv_inicial_ha=r0(r.area_zv_inicial_ha))
    R["conversao"] = {
        "nota": "Área agrícola (classes 2+3) e agricultura de baixada mapeada (classe 2, indicativa) que passam a construído entre épocas; a classe 3 é indicativa. O intervalo 1979–1985 não é comparável (legenda reduzida de 1979).",
        "intervalos": [dict(lin(r), comparavel=bool(r.t0 != 1979)) for r in cvc[cvc.consecutivo].itertuples()],
        "acumulada": [lin(r) for r in cvc[~cvc.consecutivo].itertuples()],
    }

    pb = pd.read_csv(AREAS / "perda_bairro.csv")
    pb = pb[pb.grupo == "bairro"].sort_values("convertida_construido_ha", ascending=False)

    def rowb(r):
        return dict(bairro=r.unidade, pcode=r.pcode, zv_1990_ha=r0(r.zv_1990_ha), zv_2025_ha=r0(r.zv_2025_ha),
                    variacao_liquida_ha=r0(r.variacao_liquida_ha), perda_bruta_ha=r0(r.perda_bruta_ha),
                    convertida_construido_ha=r0(r.convertida_construido_ha), ganho_bruto_ha=r0(r.ganho_bruto_ha),
                    area_bairro_ha=r0(r.area_unidade_ha))
    R["perda_bairro_top10"] = {
        "nota": ("Medida principal: área de classe 2 em 1990 que passou a construído até 2025 (transição 2→1; a época 1985 usa cena de 1984 e fica fora da base). "
                 "A variação líquida inclui também a passagem 2→vegetação, que não é interpretável (a classe 2 não se separa com segurança da vegetação natural), e é só indicativa."),
        "bairros": [rowb(r) for r in pb.head(10).itertuples()], "n_bairros": int(len(pb))}
    return R


# ----------------------------------------------------------------------------- exatidão
def exatidao():
    oob = json.load(open(PROC / "class" / "oob.json"))
    out = {"oob": {}, "cv_blocos": {}, "validacao_independente_2020": None,
           "nota": ("OOB e validação cruzada usam rótulos derivados de produtos de terceiros (não é verdade de campo). "
                    "A validação cega de 2020 (amostra estratificada, interpretação visual) está em avaliação enquanto o campo é nulo.")}
    for ep, v in oob["oob"].items():
        out["oob"][ep] = dict(acc=round(v["acc"], 3), n=v["n"], f1_zonas_verdes=v["f1"].get("2"), f1_construido=v["f1"].get("1"),
                              f1_sequeiro=v["f1"].get("3"))
    for ep, v in oob["cv_bloques"].items():
        out["cv_blocos"][ep] = dict(acc=round(v["acc"], 3), n_blocos=v["n_blocos"], f1_zonas_verdes=v["f1"].get("2"),
                                    f1_construido=v["f1"].get("1"), f1_sequeiro=v["f1"].get("3"))

    def resumo(a, com_mapeada):
        d = dict(n_pontos=int(sum(a["n_por_estrato"].values())), exatidao_global=round(a["exatidao_global"]["valor"], 3),
                 exatidao_global_ic95=round(a["exatidao_global"]["ic95"], 3), classes={})
        for k in a["exatidao_usuario"]:
            c = dict(ua=round(a["exatidao_usuario"][k]["valor"], 2), ua_ic95=round(a["exatidao_usuario"][k]["ic95"], 2),
                     pa=round(a["exatidao_produtor"][k]["valor"], 2), pa_ic95=round(a["exatidao_produtor"][k]["ic95"], 2),
                     area_ajustada_ha=r0(a["area_ajustada_ha"][k]["valor"]), area_ajustada_ic95_ha=r0(a["area_ajustada_ha"][k]["ic95"]))
            if com_mapeada:
                c["area_mapeada_ha"] = r0(a["area_mapeada_ha"][k])
            d["classes"][k] = c
        return d
    p = PROC / "validacao" / "exatidao_2020.json"
    if p.exists():
        v = json.load(open(p))
        out["validacao_independente_2020"] = v
        out["validacao_resumo"] = {amb: resumo(a, True) for amb, a in v["ambitos"].items()}
        out["nota"] = ("Validação cega de 2020 (amostra estratificada, interpretação visual de imagens): leia a exatidão de cada classe com o intervalo de confiança; "
                       "classes com exatidão baixa são indicativas.")
    ps = PROC / "validacao" / "exatidao_2020_sem_baixa.json"
    if ps.exists():
        vs = json.load(open(ps))
        out["sem_baixa"] = {"distribuicao_confianca": vs.get("distribuicao_confianca"),
                            "ambitos": {amb: resumo(a, False) for amb, a in vs["ambitos"].items()}}
        out["distribuicao_confianca"] = vs.get("distribuicao_confianca")
    try:
        gh = pd.read_csv(AREAS / "qa_ghsl_concordancia.csv")
        gh = gh[(gh.classificacao == "final") & (gh.ambito == AMBITO)]
        out["ghsl_construido"] = [dict(epoca=int(r.epoca), ghsl_ano=int(r.ghsl_ano), construido_ha=r0(r.construido_km2 * 100),
                                       ghsl_ha=r0(r.ghsl_ge2000_km2 * 100), f1=round(r.f1 / 100, 3))
                                  for r in gh.itertuples() if int(r.epoca) in EP_ANALISE]
    except Exception:
        out["ghsl_construido"] = None
    return out


# ----------------------------------------------------------------------------- envelopes (baixadas, mangal, OSM)
def _mm(vals):
    v = [x for x in vals if x is not None and np.isfinite(x)]
    return (min(v), max(v)) if v else (None, None)


def envelopes_comparacao():
    """Três estimativas da fração construída por perímetro (bruta, pós-processada, GHSL) e faixa min–max."""
    e = pd.read_csv(AREAS / "envelopes_comparacao.csv")
    mar = pd.read_csv(FONTES / "marcos.csv")
    idai = mar[mar.titulo.str.contains("Idai", na=False) & (mar.tipo == "ciclone")]
    out = {"nota": ("Três estimativas da parcela construída: classificação bruta (Random Forest por época), classificação pós-processada "
                    "(janela de três épocas, monotonia do construído, suavização 2↔5) e GHSL GHS-BUILT-S R2023A (fração de superfície edificada, "
                    "produto de terceiros). As três não são independentes: a bruta e a pós-processada vêm do mesmo modelo, e o GHSL orientou os rótulos de treino "
                    "(construído só onde GHSL ≥ 20%; outras classes só onde < 5%). O GHSL R2023A interpola entre épocas observadas (1975, 1990, 2000, 2014 e 2018; "
                    "European Commission, GHSL Data Package 2023, p. 6); 2020 e 2025 são extrapolados. "
                    "O GHSL mede superfície de edifícios, não a mancha urbana, e por isso tende a ser o mais baixo. "
                    "A faixa é o mínimo e o máximo das três; as três são estimativas, nenhuma é a verdade. "
                    "GHSL só existe em anos múltiplos de 5 (épocas intermediárias usam o ano GHSL mais próximo, ver ghsl_epoca)."),
           "marcos": [dict(ano=int(r.ano), rotulo="Ciclone Idai") for r in idai.itertuples()][:1],
           "perimetros": {}}
    for per, g in e.groupby("perimetro"):
        d = {"rotulo": ENV_ROT.get(per, per), "serie": {}}
        for r in g.itertuples():
            lo, hi = _mm((r.pct_bruto, r.pct_final, r.pct_ghsl))
            hlo, hhi = _mm((r.ha_bruto, r.ha_final, r.ha_ghsl))
            d["serie"][str(int(r.epoca))] = dict(
                area_ha=r0(r.area_ha), pct_bruto=nn(r.pct_bruto), pct_final=nn(r.pct_final), pct_ghsl=nn(r.pct_ghsl),
                ha_bruto=nn(r.ha_bruto), ha_final=nn(r.ha_final), ha_ghsl=nn(r.ha_ghsl),
                ghsl_epoca=(int(r.ghsl_epoca) if pd.notna(r.ghsl_epoca) else None),
                pct_min=lo, pct_max=hi, ha_min=hlo, ha_max=hhi)
        out["perimetros"][per] = d
    return out


def kpis_envelopes(ec):
    """Indicadores de abertura (1985 → 2025): faixas entre as três estimativas, lidas do CSV e conferidas com envelopes_resumo.json."""
    Pm = ec["perimetros"]
    e = pd.read_csv(AREAS / "envelopes_comparacao.csv")
    assert set(Pm) == set(ENV_ROT), set(Pm) ^ set(ENV_ROT)
    ai, af = 1985, 2025
    mun = Pm["municipio_total"]["serie"]
    cres, pctm = {}, {}
    for k in ("ghsl", "bruto", "final"):
        f0 = mun[str(ai)]["ha_" + k] / mun[str(ai)]["area_ha"]
        f1 = mun[str(af)]["ha_" + k] / mun[str(af)]["area_ha"]
        cres[k] = round(100 * (f1 / f0 - 1), 1)
    out = dict(
        ano_inicial=ai, ano_final=af,
        construido_ha_1985={k: r0(mun[str(ai)]["ha_" + k]) for k in ("ghsl", "bruto", "final")},
        construido_ha_2025={k: r0(mun[str(af)]["ha_" + k]) for k in ("ghsl", "bruto", "final")},
        construido_crescimento_pct=cres, construido_crescimento_min_pct=min(cres.values()), construido_crescimento_max_pct=max(cres.values()),
        faixas={})
    for chave, per, anos in (("municipio", "municipio_total", (ai, af)), ("baixada_8m", "baixada_dem<=8m_tpi<0", (ai, af)),
                             ("baixada_6m", "baixada_dem<=6m_tpi<0", (ai, af)), ("baixada_10m", "baixada_dem<=10m_tpi<0", (ai, af)),
                             ("mangal_ref", "mangal_ref_wc2020_gmw1996", (ai, af)), ("osm_agricola", "osm_agricola", (ai, af))):
        out["faixas"][chave] = {str(a): [Pm[per]["serie"][str(a)]["pct_min"], Pm[per]["serie"][str(a)]["pct_max"]] for a in anos}
        for a in anos:  # fonte única: faixa = min/max recalculado direto do CSV
            r = e[(e.perimetro == per) & (e.epoca == a)].iloc[0]
            v = [r.pct_bruto, r.pct_final, r.pct_ghsl]
            assert out["faixas"][chave][str(a)] == [min(v), max(v)], (chave, a)
    # confere com envelopes_resumo.json (gerado em 07c)
    rs = json.load(open(AREAS / "envelopes_resumo.json"))
    for per, d in rs["perimetros"].items():
        lo, hi = d["intervalo_pct_final_ano"]
        assert [lo, hi] == [Pm[per]["serie"][str(rs["ano_final"])]["pct_min"], Pm[per]["serie"][str(rs["ano_final"])]["pct_max"]], per
    # e com artigo/valores.json, apenas se já existir (chaves opcionais)
    vp = RAIZ / "artigo" / "valores.json"
    verif = []
    if vp.exists():
        vj = json.load(open(vp))
        pref = {"municipio": "mun", "baixada_8m": "baix8", "mangal_ref": "mangal"}
        for chave, f in out["faixas"].items():
            for a, (lo, hi) in f.items():
                for suf, val in (("min", lo), ("max", hi)):
                    k = f"kpi_{pref.get(chave, chave)}_{a}_{suf}"
                    if k in vj:
                        assert abs(float(str(vj[k]).replace(",", ".")) - val) < 0.051, (k, vj[k], val)
                        verif.append(k)
        for k, v in cres.items():
            kk = f"kpi_cresc_{k}"
            if kk in vj:
                assert abs(float(str(vj[kk]).replace(",", ".")) - v) < 0.6, (kk, vj[kk], v)
                verif.append(kk)
    out["verificado_contra_valores_json"] = verif if vp.exists() else None
    return out


# ----------------------------------------------------------------------------- fontes
def fontes_csv():
    out = {}
    pl = pd.read_csv(FONTES / "planos.csv").rename(columns={"aprovado[s/n/?]": "aprovado"})
    out["planos"] = registros(pl)
    co = pd.read_csv(FONTES / "conflitos.csv")
    co["georreferenciado"] = co.lat.notna() & co.lon.notna()
    out["conflitos"] = registros(co)
    out["casos_costeiros"] = registros(pd.read_csv(FONTES / "casos_costeiros.csv"))
    out["casos_comparados_maputo"] = registros(pd.read_csv(FONTES / "casos_comparados_maputo.csv"))
    return out


def marcos(imagens):
    mar = pd.read_csv(FONTES / "marcos.csv")
    mar["tipo_pt"] = mar.tipo.map(MARCO_TIPO).fillna(mar.tipo)
    mar["ordem"] = mar.data.fillna(mar.ano.astype(str))
    mar = mar.sort_values(["ano", "ordem"]).drop(columns="ordem")
    rec = registros(mar)
    for m in rec:  # imagens de planos do mesmo ano de um marco do tipo plano
        m["imagens"] = [i["arquivo"] for i in imagens if m["tipo"] == "plano" and str(i["data"]) == str(m["ano"])]
    return rec


def siueia():
    q = pd.read_csv(AREAS / "qa_siueia_io_lulc.csv")
    return dict(
        nota=("Siueia et al. (2025) usam o mapa IO LULC de 10 m sobre o município da Beira (658 km2, shapefile DIVA-GIS). A coluna 'IO na nossa máscara' reaplica o IO LULC "
              "ao município deste estudo (607 km2 na grade de 30 m). A classe 'culturas' do IO exclui o arrozal inundado (classe 'vegetação inundada'). "
              "As nossas classes 2 e 3 têm definição própria e não são equivalentes à classe 'culturas' do IO."),
        linhas=registros(q))


def series_producao():
    s = pd.read_csv(FONTES / "series_producao.csv")
    s = s[s.status.isin(["VERIFICADO", "PARCIAL"])].copy()
    s["ano"] = s.ano_referencia.astype(str)
    linhas = [dict(variavel=r.variavel, valor=nn(r.valor), unidade=r.unidade, ano=r.ano, recorte=r.recorte_espacial,
                   definicao=r.definicao, fonte=r.fonte_chave, pagina=nn(r.pagina_tabela), status=r.status, nota=nn(r.nota))
              for r in s.itertuples()]
    fontes = sorted(s.fonte_chave.unique())
    return dict(
        nota=("Cada linha tem a sua própria definição espacial e conceitual; não se somam nem se comparam sem nota. Valores PARCIAL foram lidos em fontes secundárias ou resumos. "
              "Só entram linhas verificadas ou parcialmente verificadas."),
        fontes=fontes, linhas=linhas,
        lacuna=("Entre as linhas verificadas ou parcialmente verificadas não há série de produtores, de área cultivada ou de produção de fonte oficial (INE, direção provincial, município) "
                "para a Beira: os dados disponíveis são mapas globais de cobertura (IO LULC), o Atlas da Expansão Urbana e estimativas de danos das cheias. "
                "A classificação de satélite deste estudo é, por isso, a principal série espacial."))


def maputo_ref():
    for p in (RAIZ.parent / "zonas.verdes.maputo" / "dados" / "proc" / "resultados.json",
              RAIZ.parent / "zonas.verdes.maputo" / "site" / "dados" / "resultados.json"):
        if p.exists():
            m = json.load(open(p))
            k = m["kpi"]
            return dict(
                origem=str(p.relative_to(RAIZ.parent)), doi=m["doi"]["conceito"],
                ano_final=k["ano_final"], crescimento_pct=k["construido_crescimento_pct"],
                crescimento_min=k["construido_crescimento_min_pct"], crescimento_max=k["construido_crescimento_max_pct"],
                baixadas=k["faixas"]["baixadas"], rotulo_baixada=m["envelopes_comparacao"]["perimetros"]["baixada_<15m_tpi<0"]["rotulo"],
                area_cidade_ha=m["area_cidade_ha"], construido_ha_1985=k["construido_ha_1985"], construido_ha_2025=k["construido_ha_2025"])
    return None


# ----------------------------------------------------------------------------- créditos
def split_row(l):
    return [c.strip() for c in l.strip().strip("|").split("|")]


def le_creditos():
    txt = (RAIZ / "CREDITOS.md").read_text(encoding="utf-8")
    secoes = re.split(r"^## ", txt, flags=re.M)
    res = {"intro": None, "planos": [], "dados": []}
    for s in secoes[1:]:
        titulo, _, corpo = s.partition("\n")
        linhas = [l for l in corpo.splitlines() if l.startswith("|")]
        if titulo.startswith("Licença"):
            res["intro"] = corpo.strip()
        if not linhas:
            continue
        cab = split_row(linhas[0])
        rows = [dict(zip(cab, split_row(l))) for l in linhas[2:]]
        if titulo.startswith("Planos"):
            res["planos"] = rows
        elif titulo.startswith("Dados"):
            res["dados"] = rows
    return res


def imagens(cred):
    """Galeria: uma entrada por linha de CREDITOS.md (planos) com arquivo existente em site/img/planos; liga a figuras_planos.csv/planos.csv."""
    fig = pd.read_csv(FONTES / "figuras_planos.csv")
    fig["stem"] = fig.arquivo.map(lambda a: Path(a).stem)
    pl = pd.read_csv(FONTES / "planos.csv").set_index("id")
    webdir = SITE / "img" / "planos"
    out = []
    for r in cred["planos"]:
        f = r["Arquivo do site"]
        if not (webdir / f).exists():
            continue
        m = fig[fig.stem == Path(f).stem]
        pid = nn(m.plano_id.iloc[0]) if len(m) else None
        desc = r["Descrição"]
        curto = re.split(r"\s*\(|,", desc)[0].strip()
        out.append(dict(arquivo=f, plano_id=pid, titulo=curto, legenda=desc, data=r["Data"], autor=r["Autor"], detentor=r["Detentor"],
                        licenca=r["Situação de direitos"], fonte=r["Fonte de onde foi obtida (URL)"],
                        plano=(pl.loc[pid, "titulo"] if pid in pl.index else None),
                        mini=(webdir / f.replace(".webp", "_mini.webp")).exists()))
    return out


# ----------------------------------------------------------------------------- rasters
def _tr_ll():
    return Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


def _ver(p):
    """Marcador de versão pelo conteúdo, para o navegador não reaproveitar imagem antiga do cache."""
    return hashlib.md5(Path(p).read_bytes()).hexdigest()[:8]


def para_3857(arr, src_transform, src_crs, resampling, dtype, fill=0, src_nodata=None):
    """arr (H,W) ou (B,H,W) -> (B,H',W') em EPSG:3857 + cantos lon/lat [[NW],[NE],[SE],[SW]].

    Mapas categóricos devem passar src_nodata com um valor AUSENTE do mapa (ex.: 255): com src_nodata=None
    o GDAL tratava 0 como sem-dado e preenchia esses píxeis com a classe vizinha (lição de Maputo: buracos
    de nuvem apareciam como construído no painel)."""
    if arr.ndim == 2:
        arr = arr[None]
    b, h, w = arr.shape
    left = src_transform.c
    top = src_transform.f
    right = left + w * src_transform.a
    bottom = top + h * src_transform.e
    dtr, dw, dh = calculate_default_transform(src_crs, "EPSG:3857", w, h, left, bottom, right, top)
    out = np.full((b, dh, dw), fill, dtype=dtype)
    for i in range(b):
        reproject(arr[i], out[i], src_transform=src_transform, src_crs=src_crs, dst_transform=dtr, dst_crs="EPSG:3857",
                  resampling=resampling, src_nodata=src_nodata, dst_nodata=(fill if src_nodata is None else src_nodata))
        if src_nodata is not None:
            out[i][out[i] == src_nodata] = fill
    x0, y1 = dtr.c, dtr.f
    x1, y0 = x0 + dw * dtr.a, y1 + dh * dtr.e
    t = _tr_ll()
    nw, ne, se, sw = t.transform(x0, y1), t.transform(x1, y1), t.transform(x1, y0), t.transform(x0, y0)
    cantos = [[round(nw[0], 6), round(nw[1], 6)], [round(ne[0], 6), round(ne[1], 6)],
              [round(se[0], 6), round(se[1], 6)], [round(sw[0], 6), round(sw[1], 6)]]
    return out, cantos


def salva_webp(rgba, path, lossless=False, q=80):
    im = Image.fromarray(np.moveaxis(rgba, 0, -1) if rgba.shape[0] == 4 else rgba, "RGBA")
    im.save(path, "WEBP", lossless=lossless, quality=q, method=6)
    return path.stat().st_size


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def estica(a):
    ok = np.isfinite(a)
    lo, hi = np.nanpercentile(a[ok], [2, 98])
    return np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1), ok


def rasters_painel():
    SPAINEL.mkdir(parents=True, exist_ok=True)
    B = {b: i for i, b in enumerate(BANDAS)}
    info = {"imagem": {}, "classes": {}, "conversao": {}, "tamanhos_bytes": {}}
    tot = 0
    for ep in EPOCAS:
        with rasterio.open(COMP / f"{ep}.tif") as s:
            st = s.read()
        bandas = ["nir", "red", "green"] if ep == 1979 else ["red", "green", "blue"]
        ch, ok = [], None
        for b in bandas:
            r, o = estica(st[B[b]])
            ch.append(r)
            ok = o if ok is None else ok & o
        rgb = (np.stack(ch) * 255).astype("uint8")
        med = np.array([np.median(rgb[i][ok]) for i in range(3)], dtype="uint8")
        for i in range(3):
            rgb[i][~ok] = med[i]
        a = (ok * 255).astype("uint8")
        rgb3, cantos = para_3857(rgb, TRANSFORM, CRS, Resampling.bilinear, "uint8")
        al, _ = para_3857(a, TRANSFORM, CRS, Resampling.nearest, "uint8", src_nodata=1)
        rgba = np.concatenate([rgb3, al], 0)
        p = SPAINEL / f"img_{ep}.webp"
        tot += salva_webp(rgba, p, lossless=False, q=80)
        info["imagem"][str(ep)] = dict(arquivo=f"img/painel/{p.name}?v={_ver(p)}", coordenadas=cantos,
                                       composicao="falsa-cor NIR-vermelho-verde" if ep == 1979 else "cor verdadeira (vermelho, verde, azul)",
                                       estiramento="percentis 2-98% por canal")
        cl = rasterio.open(CLS / f"{ep}.tif").read(1)
        agr = np.array([0, 1, 2, 3, 4, 4, 5, 6], dtype="uint8")[cl]  # índice 1..6 em AGR_COD
        idx, cantos = para_3857(agr, TRANSFORM, CRS, Resampling.nearest, "uint8", src_nodata=255)
        rgba = np.zeros((4,) + idx.shape[1:], "uint8")
        for i, k in enumerate(AGR_COD, 1):
            m = idx[0] == i
            for j, v in enumerate(hex_rgb(COR_CLASSE[k])):
                rgba[j][m] = v
            rgba[3][m] = 255
        p = SPAINEL / f"cls_{ep}.webp"
        tot += salva_webp(rgba, p, lossless=True)
        info["classes"][str(ep)] = dict(arquivo=f"img/painel/{p.name}?v={_ver(p)}", coordenadas=cantos)
    # conversão (1985 fica fora: o intervalo 1979-1985 não é comparável)
    cv = rasterio.open(CLS / "conversao_agri_construido.tif").read(1)
    idx, cantos = para_3857(cv, TRANSFORM, CRS, Resampling.nearest, "uint16", src_nodata=65535)
    anos = [e for e in EP_ANALISE if e > 1985]
    from matplotlib.colors import LinearSegmentedColormap
    cm = LinearSegmentedColormap.from_list("seq", P.VIZ_SEQUENTIAL[1:])
    cores = {a: tuple(int(round(255 * c)) for c in cm(i / (len(anos) - 1))[:3]) for i, a in enumerate(anos)}
    rgba = np.zeros((4,) + idx.shape[1:], "uint8")
    for a, c in cores.items():
        m = idx[0] == a
        for j in range(3):
            rgba[j][m] = c[j]
        rgba[3][m] = 255
    p = SPAINEL / "conversao.webp"
    tot += salva_webp(rgba, p, lossless=True)
    info["conversao"] = dict(arquivo=f"img/painel/{p.name}?v={_ver(p)}", coordenadas=cantos, anos=anos,
                             cores_hex={str(a): "#%02X%02X%02X" % c for a, c in cores.items()})
    info["tamanho_total_bytes"] = int(tot)
    json.dump(info, open(SPAINEL / "painel.json", "w"), indent=1, ensure_ascii=False)
    return info


def baixada8_poligonos():
    """Perímetro de baixada principal (DEM <= 8 m e TPI < 0, no município, sem água permanente), como em 07b."""
    with rasterio.open(PROC / "dem.tif") as s:
        dem = s.read(1)
        assert s.transform == TRANSFORM and dem.shape == SHAPE
    tpi = rasterio.open(PROC / "tpi.tif").read(1)
    agua = None
    for e in EP_ANALISE:
        c6 = rasterio.open(CLS / f"{e}.tif").read(1) == 6
        agua = c6 if agua is None else agua & c6
    mun = gpd.read_file(PROC / "limites.gpkg", layer="municipio").to_crs(CRS)
    muni = features.rasterize(((g, 1) for g in mun.geometry), out_shape=SHAPE, transform=TRANSFORM, fill=0, dtype="uint8").astype(bool)
    m = (np.nan_to_num(dem, nan=99) <= 8.0) & (np.nan_to_num(tpi, nan=0) < 0) & muni & ~agua
    polys = [shapely.geometry.shape(g) for g, v in features.shapes(m.astype("uint8"), mask=m, transform=TRANSFORM) if v == 1]
    g = gpd.GeoDataFrame(geometry=polys, crs=CRS)
    g = g[g.area >= 20000].copy()  # descarta fragmentos < 2 ha (só para exibição)
    g["geometry"] = g.geometry.simplify(30, preserve_topology=True)
    g["nome"] = "Baixada ≤ 8 m, TPI < 0"
    return g, float(m.sum() * HA)


def vetores(perda):
    SDADOS.mkdir(parents=True, exist_ok=True)

    def prep(g, tol):
        g = g.copy()
        g["geometry"] = g.geometry.simplify(tol, preserve_topology=True)
        g = g.to_crs("EPSG:4326")
        g["geometry"] = shapely.set_precision(g.geometry.values, 1e-5)
        return g

    mun = gpd.read_file(PROC / "limites.gpkg", layer="municipio")[["adm2_name", "adm2_pcode", "geometry"]]
    mun = mun.rename(columns={"adm2_name": "nome", "adm2_pcode": "pcode"})
    mun["camada"] = "municipio"
    ps = gpd.read_file(PROC / "limites.gpkg", layer="distritos")[["adm3_name", "adm3_pcode", "geometry"]]
    ps = ps.rename(columns={"adm3_name": "nome", "adm3_pcode": "pcode"})
    ps["camada"] = "posto"
    pb = perda[perda.grupo == "bairro"].set_index("pcode")
    b = gpd.read_file(PROC / "limites.gpkg", layer="bairros")[["adm4_name", "adm4_pcode", "adm3_name", "geometry"]]
    b = b.rename(columns={"adm4_name": "nome", "adm4_pcode": "pcode", "adm3_name": "posto"})
    b["camada"] = "bairro"
    b["zv1990"] = b.pcode.map(lambda p: r0(pb.zv_1990_ha[p]) if p in pb.index else None)
    b["zv2025"] = b.pcode.map(lambda p: r0(pb.zv_2025_ha[p]) if p in pb.index else None)
    b["dif"] = b.pcode.map(lambda p: r0(pb.variacao_liquida_ha[p]) if p in pb.index else None)
    lim = gpd.GeoDataFrame(pd.concat([mun, ps, b], ignore_index=True), crs=mun.crs)
    prep(lim, 25).to_file(SDADOS / "limites.geojson", driver="GeoJSON")
    g, ha = baixada8_poligonos()
    prep(g, 10).to_file(SDADOS / "baixada8.geojson", driver="GeoJSON")
    co = pd.read_csv(FONTES / "conflitos.csv")
    c = co.dropna(subset=["lat", "lon"])
    feats = [dict(type="Feature", geometry=dict(type="Point", coordinates=[float(r.lon), float(r.lat)]),
                  properties=dict(id=r.id, local=r.local, ano=nn(r.ano), tipo=r.tipo, desc=r.descricao, fonte=r.fonte_chave,
                                  pagina=nn(r.pagina), precisao=nn(r.precisao_coord))) for r in c.itertuples()]
    json.dump(dict(type="FeatureCollection", features=feats,
                   nota="Posições aproximadas (local descrito na fonte), não coordenadas medidas."),
              open(SDADOS / "conflitos.geojson", "w"), ensure_ascii=False)
    return ha


# ----------------------------------------------------------------------------- épocas
def epocas():
    eps = []
    for ep in EPOCAS:
        t = rasterio.open(COMP / f"{ep}.tif").tags()
        datas = t.get("datas") or ""
        subst = t.get("substituicao")
        subst = None if subst in (None, "nenhuma") else subst
        item = t.get("item") or ""
        sensor = {"LM02": "Landsat 2 MSS", "LT05": "Landsat 5 TM"}.get(item[:4], "Landsat")
        d = dict(ano=ep, fonte=t.get("fonte"), datas=datas, count_mediana=t.get("count_mediana"), substituicao=subst, quantitativa=ep != 1979)
        mm = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", datas)
        if ep == 1979:
            d["rotulo"] = "1979 (imagem MSS; indicativa, fora das séries)"
            d["caveat"] = (f"Imagem {sensor} de {data_ext(datas)} (60 m, falsa-cor NIR, vermelho, verde): indicativa, fora das séries quantitativas. "
                           "Legenda reduzida (classe 3 = toda a vegetação fora da baixada, classe 45 ausente).")
        elif item and mm:
            d["rotulo"] = f"{ep} (cena de {MESES[int(mm.group(2)) - 1]} {mm.group(1)})"
            motivo = (subst or "").split("; substituído")[0]
            d["caveat"] = f"Cena {sensor} de {data_ext(datas)}, no lugar da composição anual. Motivo: {motivo}." if subst else f"Cena {sensor} de {data_ext(datas)}."
        elif "mediana de" in (t.get("fonte") or ""):
            n = re.search(r"mediana de (\d+) cenas", t["fonte"]).group(1)
            a, z = datas.split("/")
            d["rotulo"] = f"{ep} (cenas {MESES[int(a[5:7]) - 1]}–{MESES[int(z[5:7]) - 1]})"
            d["caveat"] = f"Mediana de {n} cenas Landsat de {a[8:10].lstrip('0')} de {MESES_EXT[int(a[5:7]) - 1]} a {z[8:10].lstrip('0')} de {MESES_EXT[int(z[5:7]) - 1]} de {ep} (ainda sem composição anual)."
        else:
            d["rotulo"] = str(ep)
            d["caveat"] = "Composição anual geomediana do Digital Earth Africa (GeoMAD)."
        d["marca_cena_substituta"] = bool(subst) or "mediana de" in (t.get("fonte") or "")
        eps.append(d)
    return eps


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-rasters", action="store_true")
    args = ap.parse_args()
    SDADOS.mkdir(parents=True, exist_ok=True)
    antigo = {}
    if (PROC / "resultados.json").exists():
        antigo = json.load(open(PROC / "resultados.json"))

    R = tabelas()
    R["epocas"] = epocas()
    R["classes"] = [dict(cod=k, nome=AGR_NOME[k], cor_hex=COR_CLASSE[k]) for k in AGR_COD]
    sub = [e for e in R["epocas"] if e["marca_cena_substituta"] and e["ano"] != 1979]
    R["ressalvas"] = [
        "1979 (Landsat MSS, 60 m) é indicativa e fica fora das séries quantitativas: legenda reduzida.",
        "Épocas de cena única ou de mediana de cenas (" + ", ".join(str(e["ano"]) for e in sub) + ") não são composições anuais; ver a legenda de cada época.",
        "As classes 2 (agricultura de baixada; exatidão do usuário 0,02 na validação) e 3 (cultivo e mosaico de terra firme) são indicativas: a 3 é a de maior confusão com herbácea e construído disperso.",
        "Hortas pequenas são subpíxel a 30 m; as áreas são estimativas do mapa, não áreas ajustadas por amostra probabilística.",
    ]
    acum = [x for x in R["conversao"]["acumulada"] if x["t0"] == 1985 and x["t1"] == 2026][0]
    fo = fontes_csv()
    R["envelopes_comparacao"] = envelopes_comparacao()
    R["kpi"] = kpis_envelopes(R["envelopes_comparacao"])
    R["kpi"].update(
        pct_agricola_convertido_1985_2026=acum["agri_pct_inicial"], pct_zonas_verdes_convertido_1985_2026=acum["zv_pct_inicial"],
        agricola_convertido_ha=acum["agri_para_construido_ha"], zonas_verdes_convertidas_ha=acum["zv_para_construido_ha"],
        conflitos_documentados=len(fo["conflitos"]), conflitos_georreferenciados=sum(1 for c in fo["conflitos"] if c["georreferenciado"]))
    R["kpi"]["nota"] = ("Indicadores de topo: médias de período (1985–1997 e 2017–2025), lidas de artigo/valores.json; sem valores de 2026. Cada indicador é uma faixa entre três "
                        "estimativas (GHSL, bruta, pós-processada) que não são independentes: bruta e pós-processada vêm do mesmo modelo e o GHSL orientou os rótulos de treino.")
    vj = json.load(open(RAIZ / "artigo" / "valores.json"))
    chaves_kpi = [f"{p}_{t}_{s}" for p in ("cid", "b8") for t in ("ini", "fim") for s in ("min", "max")] + \
                 [f"{p}_fator_{s}" for p in ("cid", "b8") for s in ("min", "max")] + \
                 [f"mg_{t}_{e}" for t in ("ini", "fim") for e in ("ghsl", "bruto")]
    R["valores"] = {k: vj[k] for k in chaves_kpi}  # strings idênticas às de valores.json
    assert all(R["valores"][k] == vj[k] and isinstance(vj[k], str) for k in chaves_kpi)
    R.update({k: v for k, v in fo.items()})
    R["exatidao"] = exatidao()
    R["siueia"] = siueia()
    R["producao"] = series_producao()
    cred = le_creditos()
    R["creditos"] = cred
    R["imagens"] = imagens(cred)
    R["marcos"] = marcos(R["imagens"])
    R["maputo_ref"] = maputo_ref()
    R["citacao"] = ("PESSINI SOBREIRA, Daniel. Zonas verdes da Beira (1985–2026): agricultura urbana, baixadas e expansão construída. "
                                              "Zenodo, 2026. DOI: 10.5281/zenodo.24147238.")
    R["doi"] = {"conceito": "10.5281/zenodo.24147238", "v1.0.0": "10.5281/zenodo.24147239", "maputo": "10.5281/zenodo.24141821"}
    R["meta"] = dict(
        gerado_em=datetime.date.today().isoformat(), script="scripts/12_resultados.py", crs_trabalho=CRS, resolucao_m=RES,
        bbox_lonlat=[LON_MIN, LAT_MIN, LON_MAX, LAT_MAX], area_municipio_ha=R["area_municipio_ha"],
        entradas=["dados/proc/areas/*.csv", "dados/proc/areas/envelopes_resumo.json", "dados/proc/class_final/*.tif", "dados/proc/class/oob.json",
                  "dados/proc/validacao/exatidao_2020.json (opcional)", "dados/proc/validacao/exatidao_2020_sem_baixa.json (opcional)",
                  "dados/proc/limites.gpkg", "dados/proc/dem.tif", "dados/proc/tpi.tif", "fontes/series_producao.csv", "fontes/marcos.csv",
                  "fontes/planos.csv", "fontes/conflitos.csv", "fontes/casos_costeiros.csv", "fontes/casos_comparados_maputo.csv",
                  "fontes/figuras_planos.csv", "CREDITOS.md", "../zonas.verdes.maputo/dados/proc/resultados.json (opcional)"],
        validacao_independente_disponivel=R["exatidao"]["validacao_independente_2020"] is not None,
        ressalvas=R["ressalvas"])
    json.dump(R, open(PROC / "resultados.json", "w"), indent=1, ensure_ascii=False)
    log("resultados.json ok")

    # site
    perda = pd.read_csv(AREAS / "perda_bairro.csv")
    ha_baixada = vetores(perda)
    log("baixada <= 8 m (município, sem água permanente):", round(ha_baixada), "ha")
    if not args.sem_rasters:
        info = rasters_painel()
        log("rasters ok:", round(info["tamanho_total_bytes"] / 1e6, 1), "MB")
    pj = SPAINEL / "painel.json"
    painel = json.load(open(pj)) if pj.exists() else None
    D = dict(R)
    D["painel"] = painel
    with open(SDADOS / "dados.js", "w", encoding="utf-8") as f:
        f.write("/* Gerado por scripts/12_resultados.py; não editar. */\nwindow.DADOS = ")
        json.dump(D, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    shutil.copy(PROC / "resultados.json", SDADOS / "resultados.json")
    for nome, src in [("areas_agregado_classe_epoca.csv", AREAS), ("areas_agregado_distrito.csv", AREAS), ("areas_agregado_bairro.csv", AREAS),
                      ("areas_agregado_transicoes.csv", AREAS), ("conversao.csv", AREAS), ("perda_bairro.csv", AREAS),
                      ("envelopes_comparacao.csv", AREAS), ("qa_siueia_io_lulc.csv", AREAS),
                      ("conflitos.csv", FONTES), ("marcos.csv", FONTES), ("planos.csv", FONTES),
                      ("casos_costeiros.csv", FONTES), ("casos_comparados_maputo.csv", FONTES)]:
        shutil.copy(src / nome, SDADOS / nome)
    sp = pd.read_csv(FONTES / "series_producao.csv")
    sp[sp.status.isin(["VERIFICADO", "PARCIAL"])].to_csv(SDADOS / "series_producao.csv", index=False)
    log("site/dados ok")


if __name__ == "__main__":
    main()
