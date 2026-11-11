#!/usr/bin/env bash
# Roda o pipeline do zero, na ordem da Beira (sem 09: não há georreferenciação de planos).
# 11 só age se existir dados/proc/validacao/rotulos_2020.csv; a 2.a execução (--sem-baixa) gera a sensibilidade.
# 20 vem antes do 12: o 12 confere os KPIs contra artigo/valores.json.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/00_ambiente.sh
rodar() {
  echo "=== scripts/$*"
  .venv/bin/python -I "scripts/$@"
}
rodar 01_limites.py
rodar 02_composicoes.py
rodar 03_auxiliares.py
rodar 04_qa_composicoes.py
rodar 05_rotulos.py
rodar 06_classificar.py
rodar 06b_consistencia.py          # pós-processamento temporal
rodar 07_areas_transicoes.py
rodar 07b_envelopes.py             # envelopes (baixada, mangal, OSM)
rodar 07c_envelopes_comparacao.py  # três estimativas; depende de 07b
rodar 08_qa_classificacao.py
rodar 10_amostra_validacao.py
rodar 11_avaliacao_exatidao.py
rodar 11_avaliacao_exatidao.py --sem-baixa
rodar 20_valores_artigo.py
rodar 12_resultados.py
rodar 21_artigo.py
