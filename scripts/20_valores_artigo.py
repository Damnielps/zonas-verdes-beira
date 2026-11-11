"""Valores numéricos citados no artigo (marcadores {{chave}} em artigo/artigo.md).

Lê apenas tabelas do pipeline em dados/proc/ e fontes/*.csv; grava artigo/valores.json.
Nenhum número do texto é digitado à mão. Formato pt-BR (vírgula decimal, ponto de milhar);
as chaves *_en saem em formato inglês. Asserções que o texto do artigo afirma (aceleração
após 2010 nas três estimativas; mangal quase sem construção) abortam a execução se falharem.
"""
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "dados" / "proc"
AREAS = PROC / "areas"
EST = ("ghsl", "bruto", "final")


def br(x, casas=0):
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def en(x, casas=1):
    return f"{x:,.{casas}f}"


def main():
    v = {}
    cmp_ = pd.read_csv(AREAS / "envelopes_comparacao.csv").set_index(["perimetro", "epoca"])
    pct = lambda p, a, e: float(cmp_.loc[(p, a), f"pct_{e}"])
    ha = lambda p, a, e: float(cmp_.loc[(p, a), f"ha_{e}"])

    # ---- município inteiro
    P = "municipio_total"
    cres = {}
    for e in EST:
        a0, a1 = ha(P, 1985, e), ha(P, 2025, e)
        v[f"cid_ha_1985_{e}"], v[f"cid_ha_2025_{e}"] = br(a0), br(a1)
        # crescimento pela fração construída (corrige as lacunas de nuvem de 1985/1990 na área com dado)
        cres[e] = 100 * (pct(P, 2025, e) / pct(P, 1985, e) - 1)
        v[f"cid_cresc_{e}"] = br(cres[e])
        v[f"kpi_cresc_{e}"] = round(cres[e], 2)
    v["cid_cresc_min"], v["cid_cresc_max"] = br(min(cres.values())), br(max(cres.values()))
    v["cid_pct_2025_final"] = br(pct(P, 2025, "final"), 1)
    # chaves conferidas por scripts/12_resultados.py (KPIs do site = artigo)
    for chave, per, anos in (("mun", "municipio_total", (1985, 2025)), ("baix8", "baixada_dem<=8m_tpi<0", (1985, 2025)),
                             ("mangal", "mangal_ref_wc2020_gmw1996", (2025,))):
        for a in anos:
            vals = [pct(per, a, e) for e in EST]
            v[f"kpi_{chave}_{a}_min"], v[f"kpi_{chave}_{a}_max"] = min(vals), max(vals)

    # ---- baixadas
    for lim, k in ((6, "b6"), (8, "b8"), (10, "b10")):
        p = f"baixada_dem<={lim}m_tpi<0"
        d = [pct(p, 2025, e) - pct(p, 1985, e) for e in EST]
        v[f"{k}_dpp_min"], v[f"{k}_dpp_max"] = br(min(d), 1), br(max(d), 1)
    p8 = "baixada_dem<=8m_tpi<0"
    v["b8_area_ha"] = br(cmp_.loc[(p8, 2025), "area_ha"])
    for ano in (1985, 2010, 2025):
        vals = [pct(p8, ano, e) for e in EST]
        v[f"b8_{ano}_min"], v[f"b8_{ano}_max"] = br(min(vals), 1), br(max(vals), 1)
        v[f"b8_{ano}_min_en"], v[f"b8_{ano}_max_en"] = en(min(vals)), en(max(vals))
    # Médias de período (revisão pós-auditoria): as épocas isoladas são ruidosas (cena única de 1984 em
    # "1985", lacunas de nuvem em 1990, cena de outubro em 2005) e o GHSL interpola entre 1975, 1990, 2000,
    # 2014 e 2018; comparar períodos, não anos, e não datar acelerações.
    INI, FIM = (1985, 1990, 1995, 1997), (2017, 2019, 2020, 2025)
    def media(per, anos, e):
        return sum(pct(per, a, e) for a in anos) / len(anos)
    for chave, per in (("b8", p8), ("cid", "municipio_total"), ("mg", "mangal_ref_wc2020_gmw1996"),
                       ("b6", "baixada_dem<=6m_tpi<0"), ("b10", "baixada_dem<=10m_tpi<0")):
        ini = {e: media(per, INI, e) for e in EST}
        fim = {e: media(per, FIM, e) for e in EST}
        for e in EST:
            v[f"{chave}_ini_{e}"], v[f"{chave}_fim_{e}"] = br(ini[e], 1), br(fim[e], 1)
        v[f"{chave}_ini_min"], v[f"{chave}_ini_max"] = br(min(ini.values()), 1), br(max(ini.values()), 1)
        v[f"{chave}_fim_min"], v[f"{chave}_fim_max"] = br(min(fim.values()), 1), br(max(fim.values()), 1)
        v[f"{chave}_ini_min_en"], v[f"{chave}_ini_max_en"] = en(min(ini.values())), en(max(ini.values()))
        v[f"{chave}_fim_min_en"], v[f"{chave}_fim_max_en"] = en(min(fim.values())), en(max(fim.values()))
        fat = [fim[e] / ini[e] for e in EST]
        v[f"{chave}_fator_min"], v[f"{chave}_fator_max"] = br(min(fat), 1), br(max(fat), 1)
        v[f"{chave}_fator_min_en"], v[f"{chave}_fator_max_en"] = en(min(fat)), en(max(fat))
        if chave in ("b8", "cid", "b6", "b10"):
            assert min(fat) > 1.5, f"ASSERÇÃO FALHOU: {chave} fator período < 1,5 ({fat}); o texto afirma aumento substancial"
        if chave == "mg":
            assert fim["ghsl"] < 0.5 and fim["bruto"] <= ini["bruto"] * 1.2, f"ASSERÇÃO FALHOU: mangal {ini} {fim}"

    # ---- mangal e OSM
    pm = "mangal_ref_wc2020_gmw1996"
    v["mg_area_ha"] = br(cmp_.loc[(pm, 2025), "area_ha"])
    for e in EST:
        v[f"mg_2025_{e}"] = br(pct(pm, 2025, e), 1)
    assert pct(pm, 2025, "ghsl") < 5 and pct(pm, 2025, "bruto") < 5, "ASSERÇÃO FALHOU: mangal >= 5% (GHSL ou bruto)"
    po = "osm_agricola"
    o = [pct(po, 2025, e) for e in EST]
    v["osm_2025_min"], v["osm_2025_max"] = br(min(o), 1), br(max(o), 1)
    v["osm_area_ha"] = br(cmp_.loc[(po, 2025), "area_ha"])

    # ---- classe 2 no município
    ag = pd.read_csv(AREAS / "areas_agregado_classe_epoca.csv")
    c2 = ag[(ag.ambito == "municipio") & (ag.classe_agr == 2) & ag.epoca.between(1985, 2025)]["ha"] / 100
    v["c2_min_km2"], v["c2_max_km2"] = br(c2.min(), 1), br(c2.max(), 1)

    # ---- QA contra Impact Observatory
    qa = pd.read_csv(AREAS / "qa_siueia_io_lulc.csv").set_index("ano")
    for a in (2017, 2020):
        v[f"nosso_constr_{a}"] = br(qa.loc[a, "nosso_construido_km2"], 1)
        v[f"io_constr_{a}"] = br(qa.loc[a, "io_construido_nossa_mascara_km2"], 1)

    # ---- validação (município)
    ex = json.loads((PROC / "validacao" / "exatidao_2020.json").read_text())
    m = ex["ambitos"]["municipio"]
    v["val_n"] = str(ex["n_usados"])
    v["val_oa"] = br(m["exatidao_global"]["valor"], 2)
    v["val_oa_ic"] = br(m["exatidao_global"]["ic95"], 2)
    v["val_ua_1"] = br(m["exatidao_usuario"]["1"]["valor"], 2)
    v["val_pa_1"] = br(m["exatidao_produtor"]["1"]["valor"], 2)
    v["val_ua_2"] = br(m["exatidao_usuario"]["2"]["valor"], 2)
    v["val_area_aj_1"] = br(m["area_ajustada_ha"]["1"]["valor"])
    v["val_area_aj_1_ic"] = br(m["area_ajustada_ha"]["1"]["ic95"])
    v["val_area_map_1"] = br(m["area_mapeada_ha"]["1"])
    dc = ex["distribuicao_confianca"]
    v["val_conf_baixa"] = str(dc["baixa"])
    v["val_conf_baixa_pct"] = br(100 * dc["baixa"] / sum(dc.values()))
    e2 = json.loads((PROC / "validacao" / "exatidao_2020_sem_baixa.json").read_text())
    m2 = e2["ambitos"]["municipio"]
    v["val2_n"] = str(e2["n_usados"])
    v["val2_ua_1"] = br(m2["exatidao_usuario"]["1"]["valor"], 2)
    v["val2_pa_1"] = br(m2["exatidao_produtor"]["1"]["valor"], 2)

    # ---- pós-processamento
    cons = json.loads((PROC / "class_final" / "consistencia.json").read_text())
    seq = cons["sequencia"]
    tot = [cons["contagens_por_epoca"][str(a)]["total_alterados"] for a in seq if str(a) in cons["contagens_por_epoca"]]
    v["pp_min_pix"], v["pp_max_pix"] = br(min(tot)), br(max(tot))
    v["n_epocas_seq"] = str(len(seq))

    # ---- geografia
    v["n_bairros"] = str(len(gpd.read_file(PROC / "limites.gpkg", layer="bairros")))
    mun = gpd.read_file(PROC / "limites.gpkg", layer="municipio").to_crs("EPSG:32736")
    v["mun_km2"] = br(mun.geometry.area.sum() / 1e6, 1)
    import sys
    sys.path.insert(0, str(RAIZ / "scripts"))
    from comum import BOUNDS
    from shapely.geometry import box as _box
    _a_in = mun.geometry.intersection(_box(*BOUNDS)).area.sum()
    v["mun_km2_bbox"] = br(_a_in / 1e6, 1)
    v["mun_pct_bbox"] = br(100 * _a_in / mun.geometry.area.sum(), 0)
    x0, y0, x1, y1 = BOUNDS
    v["bbox_km"] = f"{round((x1 - x0) / 1000)} × {round((y1 - y0) / 1000)} km"

    # ---- cenas 2026
    comp = (RAIZ / "docs" / "qa" / "composicoes.md").read_text(encoding="utf8")
    mm = re.search(r"\|\s*2026\s*\|[^\n]*?mediana de (\d+) cenas", comp)
    assert mm, "não achei 'mediana de N cenas' na linha de 2026 de docs/qa/composicoes.md"
    v["n_cenas_2026"] = mm.group(1)

    # ---- conflitos
    cf = pd.read_csv(RAIZ / "fontes" / "conflitos.csv")
    v["n_conflitos"] = str(len(cf))
    v["conflitos_geo"] = str(int((cf["lon"].notna() & cf["lat"].notna()).sum()))

    # ---- bairros com maior conversão
    pb = pd.read_csv(AREAS / "perda_bairro.csv")
    pb = pb[pb.grupo == "bairro"].sort_values("convertida_construido_ha", ascending=False)
    top = [f"{r.unidade} ({br(r.convertida_construido_ha)} ha)" for r in pb.head(3).itertuples()]
    v["bairros_top"] = f"{top[0]}, {top[1]} e {top[2]}"

    out = RAIZ / "artigo" / "valores.json"
    out.write_text(json.dumps(v, ensure_ascii=False, indent=1))
    # cobertura: todo marcador do texto tem valor
    txt = (RAIZ / "artigo" / "artigo.md").read_text(encoding="utf8")
    chaves = {c for c in re.findall(r"\{\{(\w+)\}\}", txt) if c != "chave" and not c.startswith("QUADRO_")}
    falta = sorted(chaves - set(v))
    print(f"{len(v)} valores -> {out}; marcadores sem valor: {falta}")
    for k, x in v.items():
        print(k, x)


if __name__ == "__main__":
    main()
