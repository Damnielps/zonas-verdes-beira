/* Zonas verdes da Beira - site estático. Todos os números vêm de window.DADOS (scripts/12_resultados.py). */
(function () {
  "use strict";
  const D = window.DADOS;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmt = (x, d) => (x == null || isNaN(x) ? "—" : d === 2 ? nf2.format(x) : d === 1 ? nf1.format(x) : nf0.format(x));
  const pct = (x) => fmt(x, 1) + "%";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  // MapLibre não aceita color-mix(): resolve a cor da variável CSS para rgb() via canvas
  const corMapa = (n) => {
    try {
      const c = document.createElement("canvas"); c.width = c.height = 1;
      const x = c.getContext("2d"); x.fillStyle = css(n); x.fillRect(0, 0, 1, 1);
      const [r, g, b] = x.getImageData(0, 0, 1, 1).data; return `rgb(${r},${g},${b})`;
    } catch (e) { return css(n); }
  };
  const CLS_VAR = { 1: "--viz-2", 2: "--viz-3", 3: "--viz-5", 45: "--viz-muted", 6: "--viz-1", 7: "--viz-6" };
  const corCls = (k) => css(CLS_VAR[k]);
  const NOME = {}; D.classes.forEach((c) => (NOME[c.cod] = c.nome));
  const NOME_CURTO = { 1: "Construído", 2: "Agricultura de baixada (indicativa)", 3: "Terra firme e mosaico (indicativa)", 45: "Vegetação natural e zonas húmidas", 6: "Água", 7: "Solo exposto e areia" };
  const nomeCls = (k) => NOME_CURTO[k] || String(k);
  const EP = D.epocas.map((e) => e.ano);
  const EP_Q = EP.filter((a) => a !== 1979);
  const EPINFO = {}; D.epocas.forEach((e) => (EPINFO[e.ano] = e));
  const SUBST = new Set(D.epocas.filter((e) => e.marca_cena_substituta).map((e) => e.ano));
  const reg = [];
  function chart(fn) { reg.push(fn); fn(); }
  function redraw() { reg.forEach((f) => f()); }
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(redraw, 150); });
  const largura = (host) => Math.max(260, Math.floor(host.getBoundingClientRect().width - 28));
  const rg = (v) => `${fmt(v[0], 1)}–${fmt(v[1], 1)}%`;

  /* ---------------------------------------------------------------- tema */
  const root = document.documentElement;
  function setTema(t) { root.setAttribute("data-theme", t); try { localStorage.setItem("zv-tema", t); } catch (e) {} }
  const onTema = []; /* ganchos extras (mapas, legendas) chamados a cada troca de tema */
  let temaTimer;
  function temaMudou() { clearTimeout(temaTimer); temaTimer = setTimeout(() => { redraw(); onTema.forEach((f) => { try { f(); } catch (e) {} }); }, 30); }
  (function () {
    let t = null; try { t = localStorage.getItem("zv-tema"); } catch (e) {}
    const mq = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
    if (!t) t = mq && mq.matches ? "dark" : "light";
    root.setAttribute("data-theme", t);
    $("#btnTema").addEventListener("click", () => setTema(root.getAttribute("data-theme") === "dark" ? "light" : "dark"));
    /* qualquer mudança de data-theme (botão, outro script) redesenha gráficos e legendas */
    new MutationObserver(temaMudou).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    /* o esquema do sistema só vale enquanto a pessoa não escolheu um tema */
    const seguirSistema = () => { let guardado = null; try { guardado = localStorage.getItem("zv-tema"); } catch (e) {} if (!guardado) root.setAttribute("data-theme", mq.matches ? "dark" : "light"); else temaMudou(); };
    if (mq) { if (mq.addEventListener) mq.addEventListener("change", seguirSistema); else if (mq.addListener) mq.addListener(seguirSistema); }
  })();

  /* ---------------------------------------------------------------- abertura */
  (function () {
    const k = D.kpi; const F = k.faixas;
    const seta = ' <span class="seta">→</span> ';
    const V = D.valores; const mg = (a) => `${V[a + "_min"]}–${V[a + "_max"]}%`;
    const tiles = [
      ["Fração construída do município, média 1985–1997 → 2017–2025", `${mg("cid_ini")}${seta}${mg("cid_fim")}`, `Fator de ${V.cid_fator_min} a ${V.cid_fator_max}, conforme a estimativa (GHSL, bruta, pós-processada). Médias de período, não valores de um ano.`],
      ["Baixadas (altitude ≤ 8 m, TPI < 0), média 1985–1997 → 2017–2025", `${mg("b8_ini")}${seta}${mg("b8_fim")}`, `Fator de ${V.b8_fator_min} a ${V.b8_fator_max}. Faixa entre as três estimativas, que não são independentes.`],
      ["Mangal de referência, média 1985–1997 → 2017–2025", `${V.mg_ini_ghsl}%${seta}${V.mg_fim_ghsl}% (GHSL)`, `Bruta: ${V.mg_ini_bruto}%${seta}${V.mg_fim_bruto}%. Sem aumento detectável; a pós-processada cresce pela regra de monotonia e não deve ser lida como ocupação.`],
      ["Conflitos documentados", `${fmt(k.conflitos_documentados)}`, `${fmt(k.conflitos_documentados)} episódios documentados (${fmt(k.conflitos_georreferenciados)} com localização).`],
    ];
    $("#kpis").innerHTML = tiles.map((t) => `<div class="ard-card kpi"><p class="ard-kpi-label">${t[0]}</p><p class="ard-kpi-value num">${t[1]}</p><p class="kpi-sub">${t[2]}</p></div>`).join("");
    $("#kpiNota").textContent = "Os indicadores são faixas entre três estimativas (GHSL, classificação bruta e classificação pós-processada), não intervalos de confiança; os valores são médias de períodos (1985–1997 e 2017–2025), sem anos isolados. As três estimativas não são independentes: a classificação bruta e a pós-processada vêm do mesmo modelo, e o GHSL orientou os rótulos de treino (construído só onde GHSL ≥ 20%; outras classes só onde < 5%). O GHSL R2023A interpola entre épocas observadas (1975, 1990, 2000, 2014 e 2018; European Commission, GHSL Data Package 2023, p. 6); 2020 e 2025 são extrapolados. A agricultura de baixada mapeada (classe 2) não é destaque: ver a validação na seção de metodologia.";
  })();

  /* ---------------------------------------------------------------- lightbox */
  const IMG = {}; D.imagens.forEach((i) => (IMG[i.arquivo] = i));
  function credito(i) {
    const p = [];
    if (i.autor) p.push(i.autor);
    if (i.data) p.push(i.data);
    let s = p.join(", ");
    if (i.detentor) s += `. Detentor original: ${i.detentor}`;
    s += `. Situação de direitos: ${String(i.licenca).replace(/^reproducao_com_citacao/, "reprodução com citação").replace(/^dominio_publico/, "domínio público")}`;
    if (i.fonte) s += `. Fonte: ${i.fonte}`;
    return s + ".";
  }
  const lb = $("#lightbox");
  function abre(arq) {
    const i = IMG[arq]; if (!i) return;
    $("#lbImg").src = "img/planos/" + i.arquivo; $("#lbImg").alt = (i.legenda || i.titulo) + (i.data ? " (" + i.data + ")" : "");
    $("#lbCred").innerHTML = `<b>${esc(i.legenda || i.titulo)}</b>. ${esc(credito(i))}`;
    if (lb.showModal) lb.showModal(); else lb.setAttribute("open", "");
  }
  $("#lbFechar").addEventListener("click", () => lb.close());
  lb.addEventListener("click", (e) => { if (e.target === lb) lb.close(); });
  function thumb(arq) {
    const i = IMG[arq]; if (!i) return "";
    const mini = i.mini ? arq.replace(".webp", "_mini.webp") : arq;
    return `<button type="button" class="thumb" data-lb="${esc(arq)}" aria-label="Ampliar: ${esc(i.titulo)}"><img src="img/planos/${esc(mini)}" alt="${esc(i.titulo)}${i.data ? ", " + esc(i.data) : ""}" loading="lazy"><span>${esc(i.titulo)}${i.data ? " (" + esc(i.data) + ")" : ""}</span></button>`;
  }
  document.addEventListener("click", (e) => { const b = e.target.closest("[data-lb]"); if (b) abre(b.dataset.lb); });

  /* ---------------------------------------------------------------- linha do tempo */
  (function () {
    const anos = D.marcos.map((m) => m.ano);
    $("#tlKicker").textContent = `${Math.min(...anos)}–${Math.max(...anos)}`;
    const tipos = [["todos", "Todos"]].concat([...new Set(D.marcos.map((m) => m.tipo))].map((t) => [t, D.marcos.find((m) => m.tipo === t).tipo_pt]));
    let filtro = "todos";
    const f = $("#tlFiltros");
    f.innerHTML = tipos.map((t) => `<button type="button" class="chip" data-t="${t[0]}" aria-pressed="${t[0] === "todos"}">${esc(t[1])}</button>`).join("");
    function render() {
      const itens = D.marcos.filter((m) => filtro === "todos" || m.tipo === filtro);
      $("#tlLista").innerHTML = itens.map((m) => {
        const th = (m.imagens || []).map(thumb).join("");
        return `<li><div><div class="ano num">${esc(m.ano)}</div><div class="data">${esc(m.data || "")}</div></div><div><p class="ev"><span class="tipo-pill" data-tipo="${esc(m.tipo)}">${esc(m.tipo_pt)}</span>${esc(m.titulo)}</p>${m.descricao ? `<p class="corpo">${esc(m.descricao)}</p>` : ""}<p class="meta">Fonte: ${esc(m.fonte_chave)}${m.pagina ? " · " + esc(m.pagina) : ""}</p>${th ? `<div class="thumbs">${th}</div>` : ""}</div></li>`;
      }).join("") || "<li>Nenhum marco neste filtro.</li>";
    }
    f.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; filtro = b.dataset.t; $$("button", f).forEach((x) => x.setAttribute("aria-pressed", x === b)); render(); });
    render();
  })();

  /* ---------------------------------------------------------------- utilitários de gráfico */
  const SYM = [d3.symbolCircle, d3.symbolSquare, d3.symbolTriangle, d3.symbolDiamond, d3.symbolCross, d3.symbolStar];
  const symPath = (i, size) => d3.symbol().type(SYM[i % SYM.length]).size(size || 60)();
  function eixos(g, x, y, w, h, opts) {
    opts = opts || {};
    g.append("g").attr("class", "grade").call(d3.axisLeft(y).ticks(opts.ny || 5).tickSize(-w).tickFormat("")).select(".domain").remove();
    const gx = g.append("g").attr("class", "eixo").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(opts.nx || 8).tickFormat(d3.format("d")).tickSizeOuter(0));
    const gy = g.append("g").attr("class", "eixo").call(d3.axisLeft(y).ticks(opts.ny || 5).tickFormat((v) => nf0.format(v) + (opts.sufy || "")).tickSize(0).tickPadding(6));
    gy.select(".domain").remove();
    return { gx, gy };
  }
  function tabela(cab, linhas, cap) {
    return `<div class="tab-rolavel"><table>${cap ? `<caption>${esc(cap)}</caption>` : ""}<thead><tr>${cab.map((c, i) => `<th scope="col"${i ? ' class="num"' : ""}>${esc(c)}</th>`).join("")}</tr></thead><tbody>${linhas.map((l) => `<tr>${l.map((c, i) => `<${i ? "td class=\"num\"" : "th scope=\"row\""}>${c == null ? "—" : c}</${i ? "td" : "th"}>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  const altDet = (html, t) => `<details class="alt"><summary>${t || "Ver dados em tabela"}</summary>${html}</details>`;

  /* ---------------------------------------------------------------- três estimativas por perímetro */
  const EPH = EP_Q.filter((e) => e <= D.kpi.ano_final);
  const SER = [["ghsl", "GHSL (fração edificada)", "2 3"], ["bruto", "Classificação bruta", "6 3"], ["final", "Classificação pós-processada", ""]];
  function painelEnv(host, chaves, titulo, sub, notas) {
    const per = D.envelopes_comparacao.perimetros;
    const cores = ["--viz-1", "--viz-2", "--viz-3", "--viz-5"].map(css);
    const w0 = largura(host); const cw = Math.max(250, Math.floor((w0 - 12) / (chaves.length > 1 && w0 > 760 ? Math.min(chaves.length, 3) : 1)));
    host.innerHTML = `<h4>${esc(titulo)}</h4><p class="fig-sub">${sub}</p><div class="multiplos" id="mult-${host.id}"></div><ul class="legenda" id="leg-${host.id}"></ul>${notas}`;
    const mult = $("#mult-" + host.id, host);
    chaves.forEach((k, i) => {
      const S = per[k].serie;
      const dados = (n) => EPH.map((e) => ({ e, v: S[e]["pct_" + n] }));
      const band = EPH.map((e) => ({ e, lo: S[e].pct_min, hi: S[e].pct_max }));
      const m = { t: 8, r: 10, b: 22, l: 42 }, w = cw, h = w0 < 400 ? 125 : 190, iw = w - m.l - m.r, ih = h - m.t - m.b;
      const x = d3.scaleLinear([1985, 2025], [0, iw]); const y = d3.scaleLinear([0, d3.max(band, (d) => d.hi) * 1.1], [ih, 0]).nice(4);
      const dec = y.domain()[1] <= 5;
      const div = document.createElement("div");
      const f25 = S["2025"];
      div.innerHTML = `<h5>${esc(per[k].rotulo)}</h5><svg role="img" aria-label="${esc(per[k].rotulo)}: parcela construída em 2025 entre ${fmt(f25.pct_min, 1)}% e ${fmt(f25.pct_max, 1)}% segundo três estimativas" viewBox="0 0 ${w} ${h}"></svg>`;
      mult.appendChild(div);
      const g = d3.select(div).select("svg").append("g").attr("transform", `translate(${m.l},${m.t})`);
      g.append("g").attr("class", "grade").call(d3.axisLeft(y).ticks(4).tickSize(-iw).tickFormat("")).select(".domain").remove();
      g.append("g").attr("class", "eixo").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).tickValues([1985, 1995, 2005, 2015, 2025]).tickFormat(d3.format("d")).tickSizeOuter(0));
      g.append("g").attr("class", "eixo").call(d3.axisLeft(y).ticks(4).tickFormat((v) => (dec ? nf1.format(v) : nf0.format(v)) + "%").tickSize(0).tickPadding(4)).select(".domain").remove();
      D.envelopes_comparacao.marcos.forEach((mk) => g.append("line").attr("x1", x(mk.ano)).attr("x2", x(mk.ano)).attr("y1", 0).attr("y2", ih).attr("stroke", css("--ard-text-3")).attr("stroke-dasharray", "3 3").attr("stroke-width", 1));
      g.append("path").datum(band).attr("fill", cores[i % 4]).attr("fill-opacity", 0.18).attr("d", d3.area().x((d) => x(d.e)).y0((d) => y(d.lo)).y1((d) => y(d.hi)));
      SER.forEach((sr) => g.append("path").datum(dados(sr[0])).attr("fill", "none").attr("stroke", cores[i % 4]).attr("stroke-width", 2).attr("stroke-dasharray", sr[2]).attr("d", d3.line().defined((d) => d.v != null).x((d) => x(d.e)).y((d) => y(d.v))));
    });
    $("#leg-" + host.id, host).innerHTML = SER.map((sr) => `<li><svg width="34" height="12" aria-hidden="true"><line x1="0" x2="34" y1="6" y2="6" stroke="${css("--ard-text-2")}" stroke-width="2" stroke-dasharray="${sr[2]}"/></svg>${sr[1]}</li>`).join("") + `<li><i class="sw" style="background:${css("--ard-text-3")};opacity:.35"></i>Faixa mín.–máx.</li>` + (D.envelopes_comparacao.marcos.length ? `<li><svg width="34" height="12" aria-hidden="true"><line x1="17" x2="17" y1="0" y2="12" stroke="${css("--ard-text-3")}" stroke-dasharray="3 3"/></svg>${esc(D.envelopes_comparacao.marcos[0].rotulo)} (${D.envelopes_comparacao.marcos[0].ano})</li>` : "");
    const cab = ["Época"]; chaves.forEach((k) => ["GHSL", "bruta", "pós-proc."].forEach((n) => cab.push(per[k].rotulo + ", " + n + " (%)")));
    host.insertAdjacentHTML("beforeend", altDet(tabela(cab, EPH.map((e) => [e].concat(...chaves.map((k) => ["ghsl", "bruto", "final"].map((n) => fmt(per[k].serie[e]["pct_" + n], 2))))), "Parcela construída por perímetro e estimativa")));
  }

  chart(function figMun() {
    painelEnv($("#figMun"), ["municipio_total"], "Parcela construída do município: três estimativas",
      "Parcela (%) do município (sem água permanente) construída, 1985–2025. Faixa sombreada: mínimo e máximo das três estimativas. Pontilhada: GHSL; tracejada: classificação bruta; contínua: classificação pós-processada.",
      `<p class="nota">${esc(D.envelopes_comparacao.nota)} A série pós-processada do construído é não decrescente por construção, e por isso não mede reversões reais; a faixa expressa a incerteza entre estimativas, não um intervalo de confiança.</p><p class="nota">As três estimativas não são independentes: a classificação bruta e a pós-processada vêm do mesmo modelo, e o GHSL orientou os rótulos de treino (construído só onde GHSL ≥ 20%; outras classes só onde < 5%). O GHSL R2023A interpola entre épocas observadas (1975, 1990, 2000, 2014 e 2018; European Commission, GHSL Data Package 2023, p. 6); 2020 e 2025 são extrapolados.</p>`);
  });

  chart(function figEnv() {
    const F = D.kpi.faixas; const per = D.envelopes_comparacao.perimetros;
    const m = per["mangal_ref_wc2020_gmw1996"].serie;
    const sens = `Sensibilidade ao limiar de altitude (2025): ≤ 6 m, ${rg(F.baixada_6m["2025"])}; ≤ 8 m (principal), ${rg(F.baixada_8m["2025"])}; ≤ 10 m, ${rg(F.baixada_10m["2025"])}. Em 1985: ${rg(F.baixada_6m["1985"])}, ${rg(F.baixada_8m["1985"])} e ${rg(F.baixada_10m["1985"])}.`;
    painelEnv($("#figEnv"), ["baixada_dem<=8m_tpi<0", "mangal_ref_wc2020_gmw1996", "osm_agricola"], "Parcela construída nas baixadas, no mangal e nas feições agrícolas: três estimativas",
      `Parcela (%) de cada perímetro construída, município, 1985–2025. Faixa sombreada: mínimo e máximo das três estimativas. Pontilhada: GHSL; tracejada: classificação bruta; contínua: pós-processada. Linha vertical: ciclone Idai (2019). Cada painel tem a sua escala vertical.`,
      `<p class="nota">${esc(sens)}</p><p class="nota nota--aviso">Mangal de referência (WorldCover 2020 ∪ Global Mangrove Watch 1996): a estimativa pós-processada é inflada pela monotonia do construído (${fmt(m["1985"].pct_final, 1)}% em 1985 para ${fmt(m["2025"].pct_final, 1)}% em 2025, contra ${fmt(m["1985"].pct_bruto, 1)}% e ${fmt(m["2025"].pct_bruto, 1)}% na bruta); leia a faixa e não uma só linha. As feições agrícolas do OpenStreetMap são poucas e de cobertura incompleta.</p><p class="nota">As três estimativas não são independentes: a classificação bruta e a pós-processada vêm do mesmo modelo, e o GHSL orientou os rótulos de treino (construído só onde GHSL ≥ 20%; outras classes só onde < 5%). O GHSL R2023A interpola entre épocas observadas (1975, 1990, 2000, 2014 e 2018; European Commission, GHSL Data Package 2023, p. 6); 2020 e 2025 são extrapolados.</p>` +
      altDet(tabela(["Perímetro (sensibilidade)", "Área 2025 (ha)", "1985, mín.–máx. (%)", "2025, mín.–máx. (%)"], ["baixada_dem<=6m_tpi<0", "baixada_dem<=8m_tpi<0", "baixada_dem<=10m_tpi<0"].map((k) => [esc(per[k].rotulo), fmt(per[k].serie["2025"].area_ha), rg([per[k].serie["1985"].pct_min, per[k].serie["1985"].pct_max]), rg([per[k].serie["2025"].pct_min, per[k].serie["2025"].pct_max])]), "Baixadas: limiares de altitude"), "Ver a sensibilidade ao limiar de altitude"));
  });

  /* ---------------------------------------------------------------- áreas por classe */
  const ordemEmp = ["1", "2", "3", "7", "6", "45"];
  const sel = $("#selDistrito");
  sel.innerHTML = `<option value="municipio">Município</option>` + Object.keys(D.areas_posto).sort().map((n) => `<option>${esc(n)}</option>`).join("");
  let areasVista = "emp";
  $("#areasVista").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; areasVista = b.dataset.v; $$("#areasVista button").forEach((x) => x.setAttribute("aria-pressed", x === b)); figAreas(); });
  sel.addEventListener("change", figAreas);
  const dadosArea = () => (sel.value === "municipio" ? D.areas_municipio : D.areas_posto[sel.value]);
  function figAreas() {
    const host = $("#figAreas"); const A = dadosArea();
    const eps = EP_Q.filter((e) => A[e]);
    const lab = sel.value === "municipio" ? "município" : sel.value;
    const subs = EP_Q.filter((e) => SUBST.has(e)).map((e) => EPINFO[e].rotulo).join("; ");
    $("#notaAreas").innerHTML = `Épocas de cena única ou de mediana de cenas (círculos vazados): ${esc(subs)}. ${esc(D.areas_1979_indicativa.nota)} Classes 2 e 3: indicativas (ver validação). Os postos administrativos são os cinco Urbano 1 a 5.`;
    if (areasVista === "tab") {
      const cab = ["Época"].concat(D.classes.map((c) => nomeCls(c.cod) + " (ha)"));
      host.innerHTML = `<h4>Área por classe, ${esc(lab)} (ha)</h4>` + tabela(cab, eps.map((e) => [e + (SUBST.has(+e) ? "*" : "")].concat(D.classes.map((c) => fmt(A[e][c.cod])))), "Hectares por classe agregada; * cena única ou mediana de cenas");
      return;
    }
    if (areasVista === "emp") {
      const w = largura(host), h = Math.min(380, Math.max(260, w * 0.5)), m = { t: 10, r: 14, b: 40, l: 52 };
      const iw = w - m.l - m.r, ih = h - m.t - m.b;
      host.innerHTML = `<h4>Uso do solo por classe agregada, ${esc(lab)}</h4><p class="fig-sub">Hectares empilhados; de baixo para cima na mesma ordem da legenda.</p><svg role="img" aria-label="Área empilhada por classe de uso do solo de 1985 a 2026" viewBox="0 0 ${w} ${h}" tabindex="0"></svg><ul class="legenda" id="legEmp"></ul><p class="leitura" aria-live="polite"></p>`;
      const dt = eps.map((e) => Object.assign({ e: +e }, A[e]));
      const st = d3.stack().keys(ordemEmp)(dt);
      const x = d3.scaleLinear([1985, 2026], [0, iw]); const y = d3.scaleLinear([0, d3.max(st[st.length - 1], (d) => d[1])], [ih, 0]).nice();
      const svg = d3.select(host).select("svg"); const g = svg.append("g").attr("transform", `translate(${m.l},${m.t})`);
      eixos(g, x, y, iw, ih, { nx: 6 });
      const area = d3.area().x((d) => x(d.data.e)).y0((d) => y(d[0])).y1((d) => y(d[1]));
      st.forEach((s) => g.append("path").datum(s).attr("d", area).attr("fill", corCls(s.key)).attr("fill-opacity", 0.9).attr("stroke", css("--ard-surface")).attr("stroke-width", 0.8));
      eps.forEach((e) => g.append("circle").attr("cx", x(+e)).attr("cy", ih + 32).attr("r", 3).attr("fill", SUBST.has(+e) ? css("--ard-surface") : css("--ard-text-3")).attr("stroke", css("--ard-text-3")));
      $("#legEmp", host).innerHTML = ordemEmp.slice().reverse().map((k) => `<li><i class="sw" style="background:${corCls(k)}"></i>${nomeCls(k)}</li>`).join("");
      const lei = $(".leitura", host);
      const mostra = (e) => { lei.innerHTML = `<b>${e}</b>${SUBST.has(e) ? " (cena única ou mediana)" : ""}: ` + D.classes.map((c) => `${nomeCls(c.cod)} ${fmt(A[e][c.cod])} ha`).join(" · "); };
      mostra(+eps[eps.length - 1]);
      const idx = (px) => { const a = x.invert(px - m.l); return eps.map(Number).reduce((p, c) => (Math.abs(c - a) < Math.abs(p - a) ? c : p)); };
      svg.on("pointermove", (ev) => mostra(idx(d3.pointer(ev, svg.node())[0])));
      svg.on("keydown", (ev) => { const l = eps.map(Number); const cur = +(lei.dataset.e || l[l.length - 1]); let i = l.indexOf(cur); if (ev.key === "ArrowLeft") i = Math.max(0, i - 1); else if (ev.key === "ArrowRight") i = Math.min(l.length - 1, i + 1); else return; lei.dataset.e = l[i]; mostra(l[i]); ev.preventDefault(); });
      host.insertAdjacentHTML("beforeend", altDet(tabela(["Época"].concat(D.classes.map((c) => nomeCls(c.cod) + " (ha)")), eps.map((e) => [e].concat(D.classes.map((c) => fmt(A[e][c.cod])))), "Hectares por classe")));
      return;
    }
    host.innerHTML = `<h4>Parcela de cada classe, ${esc(lab)} (% da área com dado)</h4><p class="fig-sub">Círculos: classificação de 30 m (vazados = cena única ou mediana de cenas). Cada painel tem a sua escala vertical.</p><div class="multiplos" id="mult"></div>`;
    const mult = $("#mult", host); const cw = Math.max(240, Math.min(360, (largura(host) - 28) / (largura(host) > 760 ? 3 : largura(host) > 520 ? 2 : 1)));
    D.classes.forEach((c) => {
      const tot = (e) => D.classes.reduce((s, k) => s + A[e][k.cod], 0);
      const dt = eps.map((e) => ({ e: +e, v: 100 * A[e][c.cod] / tot(e) }));
      const m = { t: 8, r: 8, b: 22, l: 34 }, w = cw, h = 150, iw = w - m.l - m.r, ih = h - m.t - m.b;
      const x = d3.scaleLinear([1985, 2026], [0, iw]); const y = d3.scaleLinear([0, d3.max(dt, (d) => d.v) * 1.15], [ih, 0]).nice(4);
      const div = document.createElement("div");
      div.innerHTML = `<h5>${nomeCls(c.cod)}</h5><svg role="img" aria-label="${esc(nomeCls(c.cod))}: parcela da área de ${fmt(dt[0].v, 1)}% em 1985 para ${fmt(dt[dt.length - 1].v, 1)}% em 2026" viewBox="0 0 ${w} ${h}"></svg>`;
      mult.appendChild(div);
      const g = d3.select(div).select("svg").append("g").attr("transform", `translate(${m.l},${m.t})`);
      g.append("g").attr("class", "grade").call(d3.axisLeft(y).ticks(4).tickSize(-iw).tickFormat("")).select(".domain").remove();
      g.append("g").attr("class", "eixo").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).tickValues([1985, 2000, 2015, 2026]).tickFormat(d3.format("d")).tickSizeOuter(0));
      g.append("g").attr("class", "eixo").call(d3.axisLeft(y).ticks(4).tickFormat((v) => v + "%").tickSize(0).tickPadding(4)).select(".domain").remove();
      g.append("path").datum(dt).attr("fill", "none").attr("stroke", corCls(c.cod)).attr("stroke-width", 2).attr("d", d3.line().x((d) => x(d.e)).y((d) => y(d.v)));
      g.selectAll(null).data(dt).enter().append("circle").attr("cx", (d) => x(d.e)).attr("cy", (d) => y(d.v)).attr("r", 3.2).attr("fill", (d) => (SUBST.has(d.e) ? css("--ard-surface") : corCls(c.cod))).attr("stroke", corCls(c.cod)).attr("stroke-width", 1.5);
    });
    host.insertAdjacentHTML("beforeend", altDet(tabela(["Época"].concat(D.classes.map((c) => nomeCls(c.cod) + " (%)")), eps.map((e) => { const t = D.classes.reduce((s, k) => s + A[e][k.cod], 0); return [e].concat(D.classes.map((c) => fmt(100 * A[e][c.cod] / t, 1))); }), "Percentual da área com dado")));
  }
  chart(figAreas);

  /* ---------------------------------------------------------------- conversão */
  chart(function figConv() {
    const host = $("#figConv");
    const iv = D.conversao.intervalos.filter((d) => d.comparavel);
    const w = largura(host), h = Math.min(360, Math.max(260, w * 0.48)), m = { t: 12, r: 10, b: 40, l: 44 };
    const iw = w - m.l - m.r, ih = h - m.t - m.b;
    const x0 = d3.scaleBand(iv.map((d) => d.t0 + "-" + d.t1), [0, iw]).padding(0.18); const x1 = d3.scaleBand(["agri", "zv"], [0, x0.bandwidth()]).padding(0.08);
    const y = d3.scaleLinear([0, d3.max(iv, (d) => d.agri_ha_ano)], [ih, 0]).nice();
    const cA = css("--viz-2"), cZ = css("--viz-3");
    host.innerHTML = `<h4>Conversão de terra agrícola em construído, por ano</h4><p class="fig-sub">Hectares por ano entre épocas consecutivas, município. Barras cheias: agricultura (classes 2 e 3, a 3 indicativa); barras hachuradas: classe 2. O intervalo 1985–1990 parte da cena de 1984; os intervalos curtos amplificam o ruído entre composições.</p><svg role="img" aria-label="Barras agrupadas de hectares por ano convertidos de agricultura e de agricultura de baixada (classe 2) em construído, 1985 a 2026" viewBox="0 0 ${w} ${h}"><defs><pattern id="hach" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="${css("--ard-surface")}"/><rect width="2" height="5" fill="${cZ}"/></pattern></defs></svg><ul class="legenda"><li><i class="sw" style="background:${cA}"></i>Agricultura (2+3) para construído</li><li><svg width="14" height="14" aria-hidden="true"><rect width="14" height="14" fill="url(#hach)" stroke="${cZ}"/></svg>Agricultura de baixada (2) para construído, indicativo</li></ul>`;
    const g = d3.select(host).select("svg").append("g").attr("transform", `translate(${m.l},${m.t})`);
    g.append("g").attr("class", "grade").call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat("")).select(".domain").remove();
    g.append("g").attr("class", "eixo").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x0).tickFormat((k) => { const [a, b] = k.split("-"); return a + "–" + b.slice(2); }).tickSizeOuter(0)).selectAll("text").attr("transform", "rotate(-35)").style("text-anchor", "end");
    g.append("g").attr("class", "eixo").call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(6)).select(".domain").remove();
    iv.forEach((d) => {
      const k = d.t0 + "-" + d.t1;
      g.append("rect").attr("x", x0(k) + x1("agri")).attr("width", x1.bandwidth()).attr("y", y(d.agri_ha_ano)).attr("height", ih - y(d.agri_ha_ano)).attr("fill", cA);
      g.append("rect").attr("x", x0(k) + x1("zv")).attr("width", x1.bandwidth()).attr("y", y(d.zv_ha_ano)).attr("height", ih - y(d.zv_ha_ano)).attr("fill", "url(#hach)").attr("stroke", cZ).attr("stroke-width", 1);
    });
    const ac = D.conversao.acumulada.find((a) => a.t0 === 1985 && a.t1 === 2026);
    host.insertAdjacentHTML("beforeend", `<p class="leitura">1985–2026: ${fmt(ac.agri_para_construido_ha)} ha de terra agrícola (${pct(ac.agri_pct_inicial)} da área agrícola de 1985) passaram a construído; destes, ${fmt(ac.zv_para_construido_ha)} ha eram classe 2 (${pct(ac.zv_pct_inicial)} da classe 2 de 1985; indicativo).</p>` +
      altDet(tabela(["Intervalo", "Anos", "Agricultura → construído (ha)", "ha/ano", "Classe 2 → construído (ha)", "ha/ano"], iv.map((d) => [`${d.t0}–${d.t1}`, d.anos, fmt(d.agri_para_construido_ha), fmt(d.agri_ha_ano, 1), fmt(d.zv_para_construido_ha), fmt(d.zv_ha_ano, 1)]), "Conversão entre épocas consecutivas")));
  });

  chart(function figBairros() {
    const host = $("#figBairros");
    const dt = D.perda_bairro_top10.bairros;
    const w = largura(host), rowh = 40, m = { t: 6, r: 70, b: 24, l: Math.min(150, w * 0.36) }, h = m.t + m.b + rowh * dt.length;
    const iw = w - m.l - m.r;
    const x = d3.scaleLinear([0, d3.max(dt, (d) => Math.max(d.convertida_construido_ha, -d.variacao_liquida_ha))], [0, iw]).nice();
    const y = d3.scaleBand(dt.map((d) => d.bairro), [0, rowh * dt.length]).padding(0.18);
    host.innerHTML = `<h4>Dez bairros com maior conversão de área agrícola mapeada em construído (indicativa), 1990–2025</h4><p class="fig-sub">Barra principal: área de classe 2 em 1990 que passou a construído até 2025 (transição 2→1), em hectares. Barra cinzenta: variação líquida da classe 2, apenas indicativa (inclui a passagem para vegetação, que não é interpretável). Base em 1990 porque 1985 usa cena de 1984. Dez de ${D.perda_bairro_top10.n_bairros} bairros.</p><svg role="img" aria-label="Barras horizontais com a área de agricultura de baixada mapeada (classe 2) convertida em construído em dez bairros, com a variação líquida indicativa em cinza" viewBox="0 0 ${w} ${h}"></svg><ul class="legenda"><li><i class="sw" style="background:${css("--viz-3")}"></i>Convertida em construído (2→1), ha</li><li><i class="sw" style="background:${css("--ard-text-3")};opacity:.45"></i>Variação líquida, indicativa (inclui 2→vegetação, não interpretável)</li></ul>`;
    const g = d3.select(host).select("svg").append("g").attr("transform", `translate(${m.l},${m.t})`);
    g.append("g").attr("class", "grade").call(d3.axisBottom(x).ticks(4).tickSize(rowh * dt.length).tickFormat("")).select(".domain").remove();
    g.append("g").attr("class", "eixo").attr("transform", `translate(0,${rowh * dt.length})`).call(d3.axisBottom(x).ticks(4).tickSizeOuter(0).tickFormat((v) => nf0.format(v)));
    dt.forEach((d) => {
      const y0 = y(d.bairro), bh = y.bandwidth() * 0.58, nl = d.variacao_liquida_ha;
      g.append("rect").attr("x", 0).attr("y", y0).attr("height", bh).attr("width", x(d.convertida_construido_ha)).attr("fill", css("--viz-3"));
      g.append("rect").attr("x", 0).attr("y", y0 + bh + 2).attr("height", y.bandwidth() * 0.3).attr("width", x(Math.max(0, -nl))).attr("fill", css("--ard-text-3")).attr("fill-opacity", 0.45);
      g.append("text").attr("x", -6).attr("y", y0 + y.bandwidth() / 2 + 4).attr("text-anchor", "end").text(d.bairro).style("fill", "var(--ard-text)");
      g.append("text").attr("x", x(d.convertida_construido_ha) + 4).attr("y", y0 + bh - 3).text(nf0.format(d.convertida_construido_ha) + " ha");
      g.append("text").attr("x", x(Math.max(0, -nl)) + 4).attr("y", y0 + bh + 2 + y.bandwidth() * 0.3 - 1).style("fill", "var(--ard-text-2)").style("font-size", "10px").text((nl < 0 ? "−" : "+") + nf0.format(Math.abs(nl)) + " ha (indicativa)");
    });
    host.insertAdjacentHTML("beforeend", altDet(tabela(["Bairro", "Classe 2 em 1990 (ha)", "2025 (ha)", "Convertida em construído (ha)", "Variação líquida, indicativa (ha)"], dt.map((d) => [esc(d.bairro), fmt(d.zv_1990_ha), fmt(d.zv_2025_ha), fmt(d.convertida_construido_ha), fmt(d.variacao_liquida_ha)]), D.perda_bairro_top10.nota)));
  });

  /* conflitos */
  (function () {
    $("#notaConf").textContent = `${D.kpi.conflitos_documentados} casos; ${D.kpi.conflitos_georreferenciados} têm posição aproximada no mapa (local descrito na fonte, não coordenada medida); todos constam da lista.`;
    $("#listaConf").innerHTML = D.conflitos.map((c) => `<li id="conf-${esc(c.id)}"><div class="cab">${esc(c.local)} · ${esc(c.ano || "ano não indicado")}</div><p class="corpo">${esc(c.descricao)}</p><div class="meta">Tipo: ${esc(c.tipo)}${c.bairro ? " · Bairro: " + esc(c.bairro) : ""} · Fonte: ${esc(c.fonte_chave)}${c.pagina ? ", " + esc(c.pagina) : ""}</div>${c.georreferenciado ? `<div class="meta">Posição: ${esc(c.precisao_coord)}.</div><button type="button" class="link-mapa" data-conf="${esc(c.id)}">Ver no mapa</button>` : `<div class="meta">Sem posição precisa na fonte.</div>`}</li>`).join("");
  })();

  /* ---------------------------------------------------------------- produção */
  chart(function producao() {
    const host = $("#producaoCorpo"); const PR = D.producao; const SQ = D.siueia;
    const num = (v) => (typeof v === "number" ? v : parseFloat(String(v).replace(",", ".")));
    const sIO = (nome) => PR.linhas.filter((l) => l.fonte === "siueia_2025" && l.variavel.startsWith(nome)).map((l) => ({ ano: +l.ano, v: num(l.valor) })).sort((a, b) => a.ano - b.ano);
    const cult = sIO("área de culturas (classe crops)"), inund = sIO("vegetação inundada");
    const outros = PR.linhas.filter((l) => l.fonte !== "siueia_2025");
    let h = `<p class="nota nota--aviso">${esc(PR.lacuna)}</p>`;
    h += `<div class="fig"><h4>Classes do mapa IO LULC de 10 m no município, 2017–2023</h4><p class="fig-sub">Siueia et al. (2025), Tabela 2. Culturas (sem arrozal inundado) e vegetação inundada (inclui arrozal e mangal inundado), em km². Definições do IO LULC; sem validação local.</p><div id="cSiu"></div><ul class="legenda" id="lSiu"></ul></div>`;
    h += `<div class="fig"><h4>Comparação com a classificação deste estudo</h4>${tabela(["Ano", "Culturas, Siueia (km²)", "Culturas, IO na nossa máscara (km²)", "Vegetação inundada, IO (km²)", "Construído, Siueia (km²)", "Construído, IO na nossa máscara (km²)", "Construído, este estudo (km²)", "Classe 2, este estudo (km²)", "Classe 3, este estudo (km²)"], SQ.linhas.map((r) => [`<span class="nw">${r.ano}</span>`, fmt(r.siueia_culturas_km2, 2), fmt(r.io_culturas_nossa_mascara_km2, 2), fmt(r.io_inundada_km2, 2), fmt(r.siueia_construido_km2, 2), fmt(r.io_construido_nossa_mascara_km2, 2), fmt(r.nosso_construido_km2, 2), fmt(r.nosso_classe2_km2, 2), fmt(r.nosso_classe3_km2, 2)]))}<p class="nota">${esc(SQ.nota)} Células com traço: época sem classificação neste estudo.</p></div>`;
    h += `<div class="fig"><h4>Outros indicadores verificados</h4>${tabela(["Variável", "Ano", "Valor", "Recorte e fonte"], outros.map((l) => [esc(l.variavel), `<span class="nw">${esc(l.ano)}</span>`, fmt(l.valor) + " " + esc(l.unidade), `${esc(l.recorte)}. ${esc(l.fonte)}${l.pagina ? ", " + esc(l.pagina) : ""}${l.status !== "VERIFICADO" ? " (" + esc(l.status) + ")" : ""}`]))}</div>`;
    h += altDet(tabela(["Variável", "Ano", "Valor", "Definição", "Fonte", "Status"], PR.linhas.map((l) => [esc(l.variavel), `<span class="nw">${esc(l.ano)}</span>`, fmt(l.valor, l.valor % 1 ? 2 : 0) + " " + esc(l.unidade), esc(l.definicao), esc(l.fonte) + (l.pagina ? ", " + esc(l.pagina) : ""), esc(l.status)]), "Todas as linhas de series_producao.csv verificadas ou parciais"), "Ver todas as linhas e definições") + `<p class="nota">${esc(PR.nota)}</p>`;
    host.innerHTML = h;
    const hostc = $("#cSiu"); const w = Math.max(260, hostc.getBoundingClientRect().width || 600), hh = 210, m = { t: 10, r: 14, b: 24, l: 44 }, iw = w - m.l - m.r, ih = hh - m.t - m.b;
    hostc.innerHTML = `<svg role="img" aria-label="Área de culturas e de vegetação inundada no município da Beira segundo o IO LULC, 2017 a 2023" viewBox="0 0 ${w} ${hh}"></svg>`;
    const x = d3.scaleLinear([2017, 2023], [0, iw]); const y = d3.scaleLinear([0, d3.max(cult.concat(inund), (d) => d.v)], [ih, 0]).nice(4);
    const g = d3.select(hostc).select("svg").append("g").attr("transform", `translate(${m.l},${m.t})`);
    g.append("g").attr("class", "grade").call(d3.axisLeft(y).ticks(4).tickSize(-iw).tickFormat("")).select(".domain").remove();
    g.append("g").attr("class", "eixo").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(7).tickFormat(d3.format("d")).tickSizeOuter(0));
    g.append("g").attr("class", "eixo").call(d3.axisLeft(y).ticks(4).tickFormat((t) => nf0.format(t)).tickSize(0).tickPadding(4)).select(".domain").remove();
    [[cult, "--viz-5", 0, "Culturas (sem arrozal inundado)"], [inund, "--viz-1", 1, "Vegetação inundada (arrozal e mangal inundado)"]].forEach(([s, c, i]) => {
      g.append("path").datum(s).attr("fill", "none").attr("stroke", css(c)).attr("stroke-width", 2).attr("d", d3.line().x((d) => x(d.ano)).y((d) => y(d.v)));
      g.selectAll(null).data(s).enter().append("path").attr("d", symPath(i, 60)).attr("transform", (d) => `translate(${x(d.ano)},${y(d.v)})`).attr("fill", css(c));
    });
    $("#lSiu").innerHTML = [["--viz-5", 0, "Culturas (sem arrozal inundado), km²"], ["--viz-1", 1, "Vegetação inundada (arrozal e mangal inundado), km²"]].map(([c, i, t]) => `<li><svg width="14" height="14" aria-hidden="true"><path d="${symPath(i, 60)}" transform="translate(7,7)" fill="${css(c)}"/></svg><span>${t}</span></li>`).join("");
  });

  /* ---------------------------------------------------------------- planos */
  (function () {
    const v = (x) => (x == null || x === "" ? "—" : esc(x));
    $("#galeriaPlanos").innerHTML = D.imagens.map((i) => thumb(i.arquivo)).join("") || "<p class='nota'>Nenhuma imagem de plano disponível.</p>";
    $("#planosLista").innerHTML = D.planos.slice().sort((a, b) => a.ano - b.ano).map((p) => {
      const th = D.imagens.filter((i) => i.plano_id === p.id).map((i) => thumb(i.arquivo)).join("");
      return `<article class="plano"><h4><span class="num">${esc(p.ano)}</span> · ${esc(p.titulo)}</h4><p class="ap">${v(p.autor)} · ${v(p.entidade)}${p.escala ? " · escala: " + esc(p.escala) : ""} · aprovado: ${v(p.aprovado)}</p><p><b class="sans" style="font-size:13px">Agricultura:</b> ${v(p.trata_agricultura)}</p><p><b class="sans" style="font-size:13px">Verde e mangal:</b> ${v(p.trata_verde_mangal)}</p>${p.citacao_curta ? `<p class="ap">“${esc(p.citacao_curta)}”</p>` : ""}<p class="ap">Fonte: ${v(p.fonte_chave)}${p.pagina ? " (" + esc(p.pagina) + ")" : ""} · georreferenciável: ${v(p.georreferenciavel)}</p>${th ? `<div class="thumbs">${th}</div>` : ""}</article>`;
    }).join("");
  })();

  /* ---------------------------------------------------------------- comparação entre cidades */
  (function () {
    const v = (x) => (x == null || x === "" ? "—" : esc(x));
    const M = D.maputo_ref; const K = D.kpi;
    if (M) {
      const cr = (a, b) => `+${fmt(a)}% a +${fmt(b)}%`;
      $("#compMaputo").innerHTML = `<h3>Beira e Maputo, mesmo método</h3>` + tabela(["Indicador", "Beira (município)", "Maputo (cidade)"], [
        ["Área analisada (ha)", fmt(D.area_municipio_ha), fmt(M.area_cidade_ha)],
        [`Crescimento relativo do construído, ${K.ano_inicial}→${M.ano_final}`, cr(K.construido_crescimento_min_pct, K.construido_crescimento_max_pct), cr(M.crescimento_min, M.crescimento_max)],
        [`Construído nas baixadas, ${K.ano_inicial}`, `${rg(K.faixas.baixada_8m[K.ano_inicial])} (≤ 8 m, TPI < 0)`, `${rg(M.baixadas["1985"])} (${esc(M.rotulo_baixada)})`],
        [`Construído nas baixadas, ${K.ano_final}`, `${rg(K.faixas.baixada_8m[K.ano_final])} (≤ 8 m, TPI < 0)`, `${rg(M.baixadas["2025"])} (${esc(M.rotulo_baixada)})`],
      ], "Faixas entre três estimativas (GHSL, bruta, pós-processada)") +
        `<p class="nota">Os perímetros de baixada diferem (limiar de altitude e relevo de cada cidade): compare a direção e a ordem de grandeza, não o nível. Maputo: resultado publicado, DOI <a href="https://doi.org/${esc(M.doi)}">${esc(M.doi)}</a>, valores lidos de ${esc(M.origem)}.</p>`;
    }
    const tabCasos = (sel, arr, licaoRot) => {
      $(sel).innerHTML = `<thead><tr><th>Cidade</th><th>Modelo institucional</th><th>Proteção do solo</th><th>Números</th><th>Pressões e resultados</th><th>${licaoRot}</th><th>Fontes</th></tr></thead><tbody>` + arr.map((c) =>
        `<tr><td data-rot="Cidade"><b>${v(c.cidade)}</b><br>${v(c.pais)} · ${v(c.continente)}</td><td data-rot="Modelo institucional">${v(c.modelo_institucional)}</td><td data-rot="Proteção do solo">${v(c.instrumento_de_protecao_do_solo)}</td><td data-rot="Números">Ano: ${v(c.ano_referencia)}<br>Produtores: ${v(c.produtores)}<br>Área (ha): ${v(c.area_ha)}<br>Abastecimento de hortaliças: ${v(c.participacao_abastecimento_hortalicas)}<br>Agregados praticantes: ${v(c.agregados_praticantes_pct)}</td><td data-rot="Pressões e resultados">${v(c.principais_pressoes)}<br><br>${v(c.resultados)}</td><td data-rot="${esc(licaoRot)}">${v(c.licao_para_maputo)}</td><td data-rot="Fontes">${v(c.fontes_chaves)}</td></tr>`).join("") + "</tbody>";
      $(sel).style.minWidth = "1000px";
    };
    tabCasos("#tabCostas", D.casos_costeiros, "Lição para a Beira"); tabCasos("#tabCasos", D.casos_comparados_maputo, "Lição (formulada para Maputo)");
  })();

  /* ---------------------------------------------------------------- metodologia */
  let vAmbito = "municipio";
  const AMB_ROT = { municipio: "Município", bbox: "Retângulo de estudo" };
  chart(function metodologia() {
    const host = $("#metCorpo"); const ex = D.exatidao; const vr = ex.validacao_resumo; const dc0 = ex.distribuicao_confianca || {};
    let h = `<p class="lead">${EP.length} épocas (${EP.join(", ")}) numa grade de 30 m (EPSG:32736), sobre o Município da Beira (incluindo Nhangau e o estuário do Púngue). A fonte principal são as composições geomedianas anuais do Digital Earth Africa; onde faltam ou são rejeitadas, entram cenas Landsat Collection 2 do Planetary Computer. Um modelo Random Forest por época usa bandas, índices espectrais e relevo (Copernicus DEM). As amostras de treino derivam de mapas globais concordantes (WorldCover, IO LULC, GHSL) e de polígonos do OpenStreetMap, propagadas entre épocas por estabilidade espectral.</p>`;
    h += `<h3>Épocas</h3>${tabela(["Época", "Fonte e observação"], D.epocas.map((e) => [esc(e.rotulo), esc(e.caveat)]))}`;
    h += `<h3>Ressalvas de leitura</h3><ul class="sans" style="font:400 14px/1.6 var(--ard-sans);color:var(--ard-text-2)">${D.ressalvas.map((r) => `<li>${esc(r)}</li>`).join("")}<li>Pós-processamento temporal: o construído de cada época segue a maioria numa janela de três épocas; depois disso é forçado a ser não decrescente, e a oscilação entre as classes 2 e 5 é suavizada. Por construção, a série pós-processada do construído não decresce e não mede reversões reais; a classificação bruta e o GHSL são mostrados ao lado para expor essa diferença.</li><li>As faixas dos indicadores vão do mínimo ao máximo de três estimativas (GHSL, bruta, pós-processada) e não são intervalos de confiança.</li><li>Os perímetros (baixadas, mangal de referência, feições agrícolas do OpenStreetMap) são definidos sem usar a classificação agrícola.</li><li>As três estimativas não são independentes: a bruta e a pós-processada vêm do mesmo modelo, e o GHSL orientou os rótulos de treino (construído só onde GHSL ≥ 20%; outras classes só onde < 5%). O GHSL R2023A interpola entre épocas observadas (1975, 1990, 2000, 2014 e 2018; European Commission, GHSL Data Package 2023, p. 6); 2020 e 2025 são extrapolados.</li></ul>`;
    h += `<h3>Exatidão</h3>`;
    if (vr) {
      const ambs = Object.keys(vr); if (!vr[vAmbito]) vAmbito = ambs[0];
      h += `<p class="nota nota--aviso">${esc(ex.nota)}</p>`;
      if (ambs.length > 1) h += `<div class="grupo" id="vAmb" role="group" aria-label="Âmbito da validação">${ambs.map((a) => `<button type="button" class="chip" data-a="${a}" aria-pressed="${vAmbito === a}">${esc(AMB_ROT[a] || a)}</button>`).join("")}</div>`;
      const a = vr[vAmbito];
      h += tabela(["Classe", "Exatidão do usuário", "Exatidão do produtor", "Área mapeada (ha)", "Área ajustada (ha, IC 95%)"], Object.keys(a.classes).map((k) => { const c = a.classes[k]; return [esc(nomeCls(k)), `${fmt(100 * c.ua)}% ± ${fmt(100 * c.ua_ic95)}`, `${fmt(100 * c.pa)}% ± ${fmt(100 * c.pa_ic95)}`, fmt(c.area_mapeada_ha), `${fmt(c.area_ajustada_ha)} ± ${fmt(c.area_ajustada_ic95_ha)}`]; }), `Validação cega de 2020, ${a.n_pontos} pontos; exatidão global ${fmt(100 * a.exatidao_global)}% ± ${fmt(100 * a.exatidao_global_ic95)} (IC 95%). Áreas ajustadas segundo Olofsson et al. (2014).`);
    } else h += `<p class="nota nota--aviso">A validação cega de 2020 está em avaliação: a tabela de exatidão do usuário e do produtor, com áreas ajustadas, aparece aqui quando a rotulagem for concluída.</p>`;
    if (ex.sem_baixa && vr) {
      const A = vr[vAmbito], B = ex.sem_baixa.ambitos[vAmbito], dc = ex.distribuicao_confianca || {};
      if (B) {
        const pm = (c, k) => (c.classes[k] ? `${fmt(100 * c.classes[k].ua)} ± ${fmt(100 * c.classes[k].ua_ic95)} / ${fmt(100 * c.classes[k].pa)} ± ${fmt(100 * c.classes[k].pa_ic95)}` : "—");
        const a2 = (c) => (c.classes["2"] ? `${fmt(c.classes["2"].area_ajustada_ha)} ± ${fmt(c.classes["2"].area_ajustada_ic95_ha)}` : "—");
        h += `<h3>Sensibilidade a rótulos de baixa confiança</h3><p class="nota">Confiança dos rótulos: alta ${fmt(dc.alta)}, média ${fmt(dc.media)}, baixa ${fmt(dc.baixa)}. Excluir os de confiança baixa reduz a amostra e alarga os intervalos.</p>` + tabela(["Medida (âmbito selecionado)", "Todos os rótulos", "Sem confiança baixa"], [
          ["Pontos usados", fmt(A.n_pontos), fmt(B.n_pontos)],
          ["Exatidão global (%)", `${fmt(100 * A.exatidao_global, 1)} ± ${fmt(100 * A.exatidao_global_ic95, 1)}`, `${fmt(100 * B.exatidao_global, 1)} ± ${fmt(100 * B.exatidao_global_ic95, 1)}`],
          ["Construído: usuário / produtor (%)", pm(A, "1"), pm(B, "1")],
          ["Agricultura de baixada (classe 2): usuário / produtor (%)", pm(A, "2"), pm(B, "2")],
          ["Área ajustada da classe 2 (ha)", a2(A), a2(B)]], "Validação cega de 2020; IC 95%");
      }
    }
    h += `<p class="nota nota--aviso">A amostra de validação foi rotulada por um agente automático de análise de imagens, não por pessoas: ${dc0.baixa != null ? fmt(dc0.baixa) + " dos rótulos (" + fmt(100 * dc0.baixa / (dc0.alta + dc0.media + dc0.baixa)) + "%) têm baixa confiança, " : ""}as notas são genéricas e os recortes mostram altitude e o EMAD. A revisão humana está pendente. O construído tem exatidão do usuário alta e exatidão do produtor baixa: está subestimado. A classe 2 (agricultura de baixada) tem exatidão do usuário de 0,02 e é só indicativa.</p>`;
    const oo = Object.keys(ex.oob);
    h += `<details class="alt"><summary>Exatidão fora-do-saco e validação cruzada espacial por época</summary>${tabela(["Época", "Exatidão OOB", "F1 classe 2", "F1 construído", "Validação cruzada em blocos (exat.)"], oo.map((e) => [e, fmt(100 * ex.oob[e].acc, 1) + "%", fmt(ex.oob[e].f1_zonas_verdes != null ? 100 * ex.oob[e].f1_zonas_verdes : null, 1), fmt(ex.oob[e].f1_construido != null ? 100 * ex.oob[e].f1_construido : null, 1), ex.cv_blocos[e] ? fmt(100 * ex.cv_blocos[e].acc, 1) + "%" : "—"]), "Rótulos derivados de produtos de terceiros, não verdade de campo")}</details>`;
    if (ex.ghsl_construido) h += `<details class="alt"><summary>Concordância do construído com o GHSL</summary>${tabela(["Época", "Ano GHSL", "Construído (ha)", "GHSL (ha)", "F1"], ex.ghsl_construido.map((g) => [g.epoca, g.ghsl_ano, fmt(g.construido_ha), fmt(g.ghsl_ha), fmt(g.f1, 2)]), "Município; GHSL com superfície edificada ≥ 2000 m² por célula")}</details>`;
    const dl = [["resultados.json", "Todos os números do site e do artigo"], ["areas_agregado_classe_epoca.csv", "Área por classe e época"], ["areas_agregado_distrito.csv", "Área por posto administrativo"], ["areas_agregado_bairro.csv", "Área por bairro"], ["areas_agregado_transicoes.csv", "Matrizes de transição"], ["conversao.csv", "Conversão agricultura para construído"], ["perda_bairro.csv", "Perda por bairro"], ["envelopes_comparacao.csv", "Três estimativas por perímetro"], ["qa_siueia_io_lulc.csv", "Comparação com Siueia et al. (2025)"], ["series_producao.csv", "Séries com fonte e definição (verificadas e parciais)"], ["conflitos.csv", "Conflitos documentados"], ["marcos.csv", "Marcos da linha do tempo"], ["planos.csv", "Planos urbanísticos"], ["casos_costeiros.csv", "Cidades costeiras"], ["casos_comparados_maputo.csv", "Outros casos"], ["limites.geojson", "Município, postos e bairros"], ["baixada8.geojson", "Baixadas ≤ 8 m (exibição, fragmentos < 2 ha omitidos)"], ["conflitos.geojson", "Conflitos (posição aproximada)"]];
    h += `<h3>Dados para baixar</h3><ul class="downloads">${dl.map((d) => `<li><a href="dados/${d[0]}" download>${d[0]}</a> <span class="nota">${d[1]}</span></li>`).join("")}</ul>`;
    h += `<h3>Como citar</h3><p class="cit">${esc(D.citacao)}</p><h3>Licenças e créditos</h3><p class="nota">O código está sob licença MIT. O material de terceiros (planos históricos, mapas e dados) não é coberto por essa licença e mantém os direitos dos titulares; é reproduzido para fins de citação científica, com indicação da fonte.</p>`;
    h += `<details class="alt"><summary>Créditos das imagens (${D.imagens.length})</summary>${tabela(["Arquivo", "Legenda e crédito"], D.imagens.map((i) => [esc(i.arquivo), esc((i.legenda || i.titulo) + ". " + credito(i))]))}</details>`;
    h += `<details class="alt"><summary>Fontes de dados e licenças</summary>${tabela(["Fonte", "Licença"], D.creditos.dados.map((d) => [esc(d["Fonte"]), esc(d["Licença"])]))}</details>`;
    host.innerHTML = h;
    $$("#vAmb button", host).forEach((b) => b.addEventListener("click", () => { vAmbito = b.dataset.a; metodologia(); }));
  });
  $("#rodape").textContent = `${D.citacao} Dados gerados em ${D.meta.gerado_em}.`;

  /* ---------------------------------------------------------------- mapa */
  const estado = { modo: "cls", ano: EP[EP.length - 1], anoB: EP[EP.length - 1], anoA: 1985, comp: false, play: null };
  const M = {};
  const GEO = {};
  const get = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(u); return r.json(); });
  let geoPromise = null;
  function carregaGeo() {
    if (!geoPromise) geoPromise = Promise.all(["limites", "baixada8", "conflitos"].map((n) => get("dados/" + n + ".geojson").then((j) => (GEO[n] = j))));
    return geoPromise;
  }
  const camadas = { mun: true, posto: false, bairro: false, baix: false, conf: false };
  const isCam = (c) => ["==", ["get", "camada"], c];

  function iniciaMapa(id, chave) {
    const bb = D.meta.bbox_lonlat;
    const map = new maplibregl.Map({ container: id, style: "https://tiles.openfreemap.org/styles/positron", bounds: [[bb[0], bb[1]], [bb[2], bb[3]]], fitBoundsOptions: { padding: 8 }, attributionControl: { compact: true }, cooperativeGestures: false });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    const o = { map, pronto: false, ativa: null, fila: [] };
    M[chave] = o;
    map.on("load", () => {
      carregaGeo().then(() => {
        const L = (n, d) => map.addSource(n, { type: "geojson", data: d });
        L("limites", GEO.limites); L("baix", GEO.baixada8); L("conf", GEO.conflitos);
        map.addLayer({ id: "baix-fill", type: "fill", source: "baix", layout: { visibility: "none" }, paint: { "fill-color": corMapa("--viz-4"), "fill-opacity": 0.14 } });
        map.addLayer({ id: "baix-line", type: "line", source: "baix", layout: { visibility: "none" }, paint: { "line-color": corMapa("--viz-4"), "line-width": 1 } });
        map.addLayer({ id: "bairro-fill", type: "fill", source: "limites", filter: isCam("bairro"), layout: { visibility: "none" }, paint: { "fill-color": corMapa("--viz-1"), "fill-opacity": 0.03 } });
        map.addLayer({ id: "bairro-line", type: "line", source: "limites", filter: isCam("bairro"), layout: { visibility: "none" }, paint: { "line-color": corMapa("--viz-1"), "line-width": 0.8, "line-dasharray": [2, 2] } });
        map.addLayer({ id: "posto-line", type: "line", source: "limites", filter: isCam("posto"), layout: { visibility: "none" }, paint: { "line-color": corMapa("--viz-1"), "line-width": 1.6 } });
        map.addLayer({ id: "mun-line", type: "line", source: "limites", filter: isCam("municipio"), layout: { visibility: "none" }, paint: { "line-color": corMapa("--viz-1"), "line-width": 2.4 } });
        map.addLayer({ id: "conf-pt", type: "circle", source: "conf", layout: { visibility: "none" }, paint: { "circle-radius": 7, "circle-color": corMapa("--viz-2"), "circle-stroke-color": corMapa("--ard-papel-fig"), "circle-stroke-width": 2 } });
        map.on("click", "conf-pt", (e) => { const f = e.features[0]; popupConf(map, f.properties, e.lngLat); });
        map.on("click", "bairro-fill", (e) => {
          if (map.queryRenderedFeatures(e.point, { layers: ["conf-pt"] }).length) return;
          const f = e.features[0].properties;
          const t = f.zv1990 != null && f.zv1990 !== "null" ? `<br>Classe 2 (indicativa): ${fmt(+f.zv1990)} ha em 1990, ${fmt(+f.zv2025)} ha em 2025 (${fmt(+f.dif)} ha)` : "";
          new maplibregl.Popup({ maxWidth: "280px" }).setLngLat(e.lngLat).setHTML(`<b>${esc(f.nome)}</b>${f.posto ? " (" + esc(f.posto) + ")" : ""}${t}`).addTo(map);
        });
        map.on("mouseenter", "conf-pt", () => (map.getCanvas().style.cursor = "pointer")); map.on("mouseleave", "conf-pt", () => (map.getCanvas().style.cursor = ""));
        o.pronto = true;
        aplicaCamadas(); aplicaRaster(o);
      }).catch(() => { $("#" + id).insertAdjacentHTML("beforeend", `<div class="mapa-erro">Não foi possível carregar as camadas vetoriais. Abra o site por um servidor HTTP, e não diretamente do disco.</div>`); o.pronto = true; o.semGeo = true; aplicaRaster(o); });
    });
    return o;
  }
  function popupConf(map, p, ll) { new maplibregl.Popup({ maxWidth: "300px" }).setLngLat(ll).setHTML(`<b>${esc(p.local)}</b> (${esc(p.ano)})<br>${esc(p.tipo)}<br>${esc(p.desc)}<br><i>${esc(p.fonte)}${p.pagina && p.pagina !== "null" ? ", " + esc(p.pagina) : ""}. Posição aproximada.</i>`).addTo(map); }

  const vis = (map, ids, on) => ids.forEach((i) => map.getLayer(i) && map.setLayoutProperty(i, "visibility", on ? "visible" : "none"));
  function aplicaCamadas() {
    Object.values(M).forEach((o) => {
      if (!o.pronto || o.semGeo) return; const m = o.map;
      vis(m, ["mun-line"], camadas.mun); vis(m, ["posto-line"], camadas.posto); vis(m, ["bairro-line", "bairro-fill"], camadas.bairro);
      vis(m, ["baix-fill", "baix-line"], camadas.baix); vis(m, ["conf-pt"], camadas.conf);
    });
    legenda();
  }
  function chaveRaster(ano) {
    if (estado.modo === "img") return "img_" + ano;
    if (estado.modo === "conv") return "conv";
    return "cls_" + ano;
  }
  function infoRaster(ch) {
    if (ch === "conv") return D.painel.conversao;
    const [t, a] = ch.split("_"); return t === "img" ? D.painel.imagem[a] : D.painel.classes[a];
  }
  function aplicaRaster(o) {
    if (!o.pronto) return;
    const m = o.map; const ano = o === M.B ? estado.anoB : (estado.comp ? estado.anoA : estado.ano);
    const ch = chaveRaster(ano);
    if (o.ativa && o.ativa !== ch && m.getLayer("r-" + o.ativa)) m.setPaintProperty("r-" + o.ativa, "raster-opacity", 0);
    if (ch) {
      if (!m.getSource("s-" + ch)) {
        const r = infoRaster(ch);
        m.addSource("s-" + ch, { type: "image", url: r.arquivo, coordinates: r.coordenadas });
        m.addLayer({ id: "r-" + ch, type: "raster", source: "s-" + ch, paint: { "raster-opacity": 0, "raster-fade-duration": 0, "raster-opacity-transition": { duration: 0 }, "raster-resampling": ch.startsWith("img") ? "linear" : "nearest" } }, m.getLayer("baix-fill") ? "baix-fill" : undefined);
      }
      m.setPaintProperty("r-" + ch, "raster-opacity", ch.startsWith("img") ? 1 : 0.88);
    }
    o.ativa = ch;
  }
  function legenda() {
    let h = "";
    if (estado.modo === "cls") h += D.classes.map((c) => `<li><i class="sw" style="background:${corCls(c.cod)}"></i>${esc(nomeCls(c.cod))}</li>`).join("");
    else if (estado.modo === "conv") h += Object.keys(D.painel.conversao.cores_hex).map((a) => `<li><i class="sw" style="background:${D.painel.conversao.cores_hex[a]}"></i>${a}</li>`).join("") + `<li>Ano da primeira conversão estável de agricultura para construído</li>`;
    else h += `<li>Cor verdadeira (1979: falsa-cor NIR, vermelho, verde); vegetação verde, áreas construídas em tons claros e rosados.</li>`;
    if (camadas.baix) h += `<li><i class="sw" style="background:${css("--viz-4")};opacity:.6"></i>Baixadas ≤ 8 m, TPI &lt; 0 (fragmentos &lt; 2 ha omitidos)</li>`;
    if (camadas.conf) h += `<li><i class="sw" style="background:${css("--viz-2")};border-radius:50%"></i>Conflito (posição aproximada)</li>`;
    $("#legenda").innerHTML = h;
  }
  /* tema: repinta as camadas vetoriais e a legenda do mapa */
  onTema.push(function () {
    Object.values(M).forEach((o) => {
      if (!o.pronto || o.semGeo) return; const m = o.map;
      [["baix-fill", "fill-color", corMapa("--viz-4")], ["baix-line", "line-color", corMapa("--viz-4")], ["bairro-fill", "fill-color", corMapa("--viz-1")], ["bairro-line", "line-color", corMapa("--viz-1")], ["posto-line", "line-color", corMapa("--viz-1")], ["mun-line", "line-color", corMapa("--viz-1")], ["conf-pt", "circle-color", corMapa("--viz-2")], ["conf-pt", "circle-stroke-color", corMapa("--ard-papel-fig")]]
        .forEach(([id, prop, val]) => { if (m.getLayer(id)) m.setPaintProperty(id, prop, val); });
    });
    if ($("#legenda")) legenda();
  });
  function textos() {
    const mA = estado.comp ? estado.anoA : estado.ano; const eA = EPINFO[mA], eB = EPINFO[estado.anoB];
    let t = (estado.comp ? `Esquerda, ${eA.rotulo}: ` : "") + eA.caveat;
    if (estado.comp) t += ` Direita, ${eB.rotulo}: ` + eB.caveat;
    if (estado.modo === "conv") t = "Ano da primeira conversão estável de agricultura (classes 2 ou 3) para construído, 1990 a 2026. A classe 3 é indicativa.";
    if (estado.modo === "cls") t += " Classes 2 e 3 indicativas: ver validação.";
    $("#caveat").textContent = t;
    $("#rotA").textContent = estado.comp ? EPINFO[estado.anoA].rotulo : ""; $("#rotB").textContent = estado.comp ? EPINFO[estado.anoB].rotulo : "";
    $("#notaMapa").textContent = estado.modo === "cls" ? "Classificação a 30 m; classe 2 = agricultura de baixada (indicativa; exatidão do usuário 0,02). Hortas pequenas são subpíxel." : "";
    $("#anoGrande").textContent = estado.modo === "conv" ? "1990–2026" : estado.comp ? `${estado.anoA} | ${estado.anoB}` : String(estado.ano);
    $("#sliderAno").setAttribute("aria-valuetext", EPINFO[estado.ano].rotulo);
  }
  function atualiza() {
    $("#sliderAno").value = EP.indexOf(estado.ano); $("#sliderAno").disabled = estado.comp || estado.modo === "conv";
    $("#chkComp").disabled = estado.modo === "conv"; $("#selComp").hidden = !estado.comp;
    $("#mapaWrap").dataset.comp = estado.comp ? "1" : "0";
    $("#selA").value = estado.anoA; $("#selB").value = estado.anoB;
    $$("#modoGrupo button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.modo === estado.modo));
    Object.values(M).forEach(aplicaRaster); textos(); legenda();
    if (estado.comp && M.B) { M.B.map.resize(); sincroniza(M.A.map, M.B.map); }
  }
  let sync = false;
  function sincroniza(a, b) { sync = true; b.jumpTo({ center: a.getCenter(), zoom: a.getZoom(), bearing: a.getBearing(), pitch: a.getPitch() }); sync = false; }
  function setClip() { const v = +$("#compRange").value; $("#mapaB").style.clipPath = `inset(0 0 0 ${v}%)`; $("#compLinha").style.left = v + "%"; }

  function montaControles() {
    const opts = D.epocas.map((e) => `<option value="${e.ano}">${esc(e.rotulo)}</option>`).join("");
    $("#selA").innerHTML = opts; $("#selB").innerHTML = opts;
    $("#sliderAno").max = EP.length - 1; $("#sliderAno").value = EP.length - 1;
    $("#ticksAno").innerHTML = EP.map((a) => `<span>${[1979, 1990, 2000, 2010, 2020, 2026].includes(a) ? a : ""}</span>`).join("");
    $("#sliderAno").addEventListener("input", (e) => { estado.ano = EP[+e.target.value]; atualiza(); });
    $("#modoGrupo").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; estado.modo = b.dataset.modo; if (estado.modo === "conv") { estado.comp = false; $("#chkComp").checked = false; } atualiza(); });
    $("#chkComp").addEventListener("change", (e) => { estado.comp = e.target.checked; if (estado.comp) { estado.anoA = Math.min(estado.anoA, estado.ano) === estado.ano ? 1985 : estado.anoA; estado.anoB = estado.ano; } else { estado.ano = estado.anoB; } if (estado.comp && !M.B) { M.B = iniciaMapa("mapaB", "B"); M.B.map.on("move", () => { if (!sync) { sync = true; M.A.map.jumpTo({ center: M.B.map.getCenter(), zoom: M.B.map.getZoom(), bearing: M.B.map.getBearing(), pitch: M.B.map.getPitch() }); sync = false; } }); M.A.map.on("move", () => { if (!sync && M.B) sincroniza(M.A.map, M.B.map); }); M.B.map.once("load", () => sincroniza(M.A.map, M.B.map)); } atualiza(); });
    $("#selA").addEventListener("change", (e) => { estado.anoA = +e.target.value; atualiza(); });
    $("#selB").addEventListener("change", (e) => { estado.anoB = +e.target.value; atualiza(); });
    $("#compRange").addEventListener("input", setClip);
    [["chkMun", "mun"], ["chkPosto", "posto"], ["chkBairro", "bairro"], ["chkBaix", "baix"], ["chkConf", "conf"]].forEach(([id, k]) => $("#" + id).addEventListener("change", (e) => { camadas[k] = e.target.checked; aplicaCamadas(); }));
    $("#btnPlay").addEventListener("click", () => {
      const b = $("#btnPlay");
      if (estado.play) { clearInterval(estado.play); estado.play = null; b.textContent = "Reproduzir"; b.setAttribute("aria-pressed", "false"); return; }
      if (estado.comp || estado.modo === "conv") return;
      b.textContent = "Pausar"; b.setAttribute("aria-pressed", "true");
      if (estado.ano === EP[EP.length - 1]) estado.ano = EP[0];
      atualiza();
      estado.play = setInterval(() => { const i = EP.indexOf(estado.ano); if (i >= EP.length - 1) { clearInterval(estado.play); estado.play = null; b.textContent = "Reproduzir"; b.setAttribute("aria-pressed", "false"); return; } estado.ano = EP[i + 1]; atualiza(); }, 1400);
    });
    document.addEventListener("click", (e) => {
      const b = e.target.closest("[data-conf]"); if (!b) return;
      const f = (GEO.conflitos ? GEO.conflitos.features : []).find((x) => x.properties.id === b.dataset.conf); if (!f) return;
      camadas.conf = true; $("#chkConf").checked = true; aplicaCamadas();
      $("#painel").scrollIntoView({ behavior: "smooth" });
      M.A.map.flyTo({ center: f.geometry.coordinates, zoom: 13 });
      setTimeout(() => popupConf(M.A.map, f.properties, f.geometry.coordinates), 900);
    });
  }
  if (window.maplibregl && D.painel) {
    montaControles(); setClip();
    M.A = iniciaMapa("mapaA", "A");
    atualiza();
  } else {
    $("#mapaA").innerHTML = `<div class="mapa-erro">O mapa não carregou neste aparelho (biblioteca MapLibre ou dados do painel indisponíveis).</div>`;
    $("#caveat").textContent = "Sem o mapa, use as seções de gráficos e tabelas abaixo.";
  }

  /* navegação ativa */
  if ("IntersectionObserver" in window) {
    const links = $$(".topo nav a");
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) links.forEach((l) => l.setAttribute("aria-current", l.getAttribute("href") === "#" + e.target.id)); }), { rootMargin: "-40% 0px -55% 0px" });
    $$("main section[id]").forEach((s) => io.observe(s));
  }
})();
