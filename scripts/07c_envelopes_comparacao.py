"""07c - Tres estimativas da fracao construida nos perimetros de 07b (Beira): GHSL, bruta, pos-processada.

(a) GHSL GHS-BUILT-S R2023A (fracao de superficie construida por celula de 100 m; independente deste estudo; ano
    GHSL mais proximo da epoca, limitado a 2025); (b) classificacao bruta (dados/proc/class); (c) pos-processada
    (dados/proc/class_final). Todas sobre a mesma mascara (perimetro, municipio, sem agua permanente, com dado em
    class_final). Ano final da comparacao: 2025.
Saidas: dados/proc/areas/envelopes_comparacao.csv e envelopes_resumo.json (1985 -> 2025: valores e intervalo).
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("env", Path(__file__).with_name("07b_envelopes.py"))
env = importlib.util.module_from_spec(spec); spec.loader.exec_module(env)
PROC = env.PROC
ANO_FINAL = 2025


def main():
    per, muni, agua, tr, shp, crs = env.perimetros()
    per["municipio_total"] = np.ones(shp, bool)
    rows = []
    for e in env.EPOCAS:
        bruto, *_ = env.ler(PROC / "class" / f"{e}.tif")
        final, *_ = env.ler(PROC / "class_final" / f"{e}.tif")
        ga = min(2025, int(round(e / 5) * 5))
        gp = PROC / "val" / f"ghsl_built_{ga}.tif"
        ghsl = np.clip(np.nan_to_num(env.ler(gp)[0].astype(float) / 10000.0, nan=0.0), 0, 1)
        for nome, pm in per.items():
            m = pm & muni & ~agua & (final > 0)
            n = m.sum()
            rows.append(dict(perimetro=nome, epoca=e, area_ha=round(n * env.PIX_HA, 1),
                             pct_bruto=round(100 * (m & (bruto == 1)).sum() / n, 2),
                             pct_final=round(100 * (m & (final == 1)).sum() / n, 2),
                             ghsl_epoca=ga, pct_ghsl=round(100 * ghsl[m].mean(), 2),
                             ha_bruto=round((m & (bruto == 1)).sum() * env.PIX_HA, 1),
                             ha_final=round((m & (final == 1)).sum() * env.PIX_HA, 1),
                             ha_ghsl=round(ghsl[m].sum() * env.PIX_HA, 1)))
    df = pd.DataFrame(rows)
    df.to_csv(PROC / "areas" / "envelopes_comparacao.csv", index=False)
    resumo = {"ano_inicial": 1985, "ano_final": ANO_FINAL, "perimetros": {}}
    for nome, g in df.groupby("perimetro"):
        g = g.set_index("epoca")
        d = {}
        for est in ("pct_ghsl", "pct_bruto", "pct_final"):
            d[est] = {"1985": float(g.loc[1985, est]), str(ANO_FINAL): float(g.loc[ANO_FINAL, est]),
                      "variacao_pp": round(float(g.loc[ANO_FINAL, est] - g.loc[1985, est]), 2)}
        v = [d[k]["variacao_pp"] for k in d]
        d["intervalo_variacao_pp"] = [min(v), max(v)]
        d["intervalo_pct_final_ano"] = [min(d[k][str(ANO_FINAL)] for k in ("pct_ghsl", "pct_bruto", "pct_final")),
                                        max(d[k][str(ANO_FINAL)] for k in ("pct_ghsl", "pct_bruto", "pct_final"))]
        d["area_ha_2025"] = float(g.loc[ANO_FINAL, "area_ha"])
        resumo["perimetros"][nome] = d
    json.dump(resumo, open(PROC / "areas" / "envelopes_resumo.json", "w"), indent=1, ensure_ascii=False)
    print(df[df.epoca.isin([1985, 2000, 2025])].to_string())


if __name__ == "__main__":
    main()
