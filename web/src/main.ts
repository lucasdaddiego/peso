import "./styles.css";
import * as charts from "./charts";
import { fmtARS, fmtMonth, fmtNum, fmtPct, fmtPctBig, fmtUSD, fmtX, parseMoney } from "./format";
import { buildModel, monthsBetween, type Model } from "./inflation";
import { fetchBlue, type BlueRate } from "./usd";
import type { Artifact } from "./types";

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

const state = {
  amountARS: 1000,
  startMonth: "2003-01",
  inflFreq: "annual" as "annual" | "monthly",
  blue: null as BlueRate | null,
};

let data: Artifact;
let model: Model;

async function init() {
  data = await fetch("/series.v1.json").then((r) => r.json());
  model = buildModel(data);
  state.blue = await fetchBlue();
  // Stateless: no params, no storage. Strip any stray query string on load.
  if (location.search) history.replaceState(null, "", location.pathname);

  $("source-badge").innerHTML =
    `Datos hasta <strong>${data.vintage_label}</strong> · IPC INDEC + IPC San Luis (2007–2015) · ` +
    `dólar BCRA y Bluelytics · series reales vía datos.gob.ar`;
  if (state.blue) {
    $("live-blue").innerHTML = `dólar blue hoy: <strong>$${fmtNum(state.blue.venta)}</strong>`;
  }

  populateWhen();
  wireControls();
  setupSticky();
  renderMethodology();
  renderBlindspots();
  renderFooter();
  renderAll();

  let t: number;
  window.addEventListener("resize", () => {
    clearTimeout(t);
    t = window.setTimeout(renderVisuals, 150);
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => renderAll());
}

// ---------- controls ----------
function populateWhen() {
  const [vy] = data.vintage.split("-").map(Number);
  const [fy] = data.start_month.split("-").map(Number);
  const yearSel = $<HTMLSelectElement>("start-year");
  yearSel.innerHTML = Array.from({ length: vy - fy + 1 }, (_, i) => fy + i)
    .map((y) => `<option value="${y}">${y}</option>`)
    .join("");
  $<HTMLSelectElement>("start-month").innerHTML = MESES.map((name, i) => `<option value="${i + 1}">${name}</option>`).join("");
  // Seed the selects from the default start month, then read it back so the two can't drift.
  const [sy, sm] = state.startMonth.split("-").map(Number);
  yearSel.value = String(sy);
  $<HTMLSelectElement>("start-month").value = String(sm);
  syncWhen();
}

/** Read the selects, clamp into [start, vintage], and write the clamped value back. */
function syncWhen() {
  const y = parseInt($<HTMLSelectElement>("start-year").value, 10);
  const m = parseInt($<HTMLSelectElement>("start-month").value, 10);
  const clamped = model.clampMonth(`${y}-${String(m).padStart(2, "0")}`);
  state.startMonth = clamped;
  const [cy, cm] = clamped.split("-").map(Number);
  $<HTMLSelectElement>("start-year").value = String(cy);
  $<HTMLSelectElement>("start-month").value = String(cm);
}

function wireControls() {
  const num = $<HTMLInputElement>("amount-number");
  num.addEventListener("input", () => {
    reformatWithCaret(num);
    state.amountARS = parseMoney(num.value);
    renderAll();
  });
  for (const id of ["start-year", "start-month"]) {
    $<HTMLSelectElement>(id).addEventListener("change", () => {
      syncWhen();
      renderAll();
    });
  }
  $("infl-toggle").querySelectorAll<HTMLButtonElement>(".seg-btn").forEach((btn) => {
    btn.onclick = () => {
      state.inflFreq = btn.dataset.freq as "annual" | "monthly";
      $("infl-toggle").querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      renderInfl();
    };
  });
}

// Re-format the amount field with thousands separators while typing, keeping the caret in place.
// Exported for direct unit testing (the null-selectionStart fallback isn't reachable via jsdom events).
export function reformatWithCaret(input: HTMLInputElement) {
  const sel = input.selectionStart ?? input.value.length;
  const digitsBeforeCaret = input.value.slice(0, sel).replace(/\D/g, "").length;
  const digits = input.value.replace(/\D/g, "");
  const formatted = digits ? fmtNum(parseInt(digits, 10)) : "";
  input.value = formatted;
  let pos = 0;
  let seen = 0;
  while (pos < formatted.length && seen < digitsBeforeCaret) {
    if (/\d/.test(formatted[pos])) seen++;
    pos++;
  }
  input.setSelectionRange(pos, pos);
}

// ---------- sticky bar ----------
function setupSticky() {
  const bar = $("sticky-bar");
  const headline = $("headline");
  const update = () => {
    bar.hidden = headline.getBoundingClientRect().bottom > 8;
  };
  window.addEventListener("scroll", update, { passive: true });
  update();
  bar.onclick = () => $("controls").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- render ----------
function renderAll() {
  charts.refreshPalette();
  renderHeadline();
  renderUsd();
  renderDecayText();
  renderDollarText();
  renderInflText();
  renderIndexText();
  renderSticky();
  renderVisuals();
}

const equivToday = () => model.equivalent(state.amountARS, state.startMonth);
const elapsedMonths = () => monthsBetween(state.startMonth, data.vintage);

function renderHeadline() {
  const amount = state.amountARS;
  const from = state.startMonth;
  const equiv = equivToday();
  const mult = model.cpi(data.vintage) / model.cpi(from);
  const cumPct = (mult - 1) * 100;
  const annPct = model.annualisedPct(from);
  const n = elapsedMonths();
  const years = (n / 12).toLocaleString("es-AR", { maximumFractionDigits: 1 });

  $("result").innerHTML = `
    <div class="big-num">${fmtARS(equiv)}<span>de hoy</span></div>
    <div class="big-text">
      <p class="lead"><strong>${fmtARS(amount)}</strong> de ${fmtMonth(from)} equivalen a <strong>${fmtARS(equiv)}</strong> de hoy.</p>
      <p>Los precios se multiplicaron por <strong>${fmtX(mult)}</strong> desde entonces.</p>
    </div>`;

  if (n === 0) {
    $("headline-explain").innerHTML =
      `Elegiste el mes más reciente que tenemos (${fmtMonth(from)}), así que todavía no hay inflación acumulada. ` +
      `Elegí un mes anterior para ver cuánto perdió el peso.`;
    return;
  }
  $("headline-explain").innerHTML =
    `Dicho de otro modo: hoy necesitás <strong>${fmtARS(equiv)}</strong> para comprar lo mismo que <strong>${fmtARS(amount)}</strong> ` +
    `compraban en ${fmtMonth(from)}. La <strong>inflación acumulada</strong> en esos ${years} años fue de <strong>${fmtPctBig(cumPct)}</strong>, ` +
    `equivalente a <strong>${fmtPct(annPct)}</strong> anual promedio (interés compuesto). ` +
    `<span class="muted">El índice de ${fmtMonth(from)} proviene de la serie <strong>${segName(from)}</strong>.</span>`;
}

function segName(month: string): string {
  const r = model.row(month);
  return { gba: "IPC-GBA del INDEC", sanluis: "IPC de San Luis", nacional: "IPC Nacional del INDEC" }[r.src];
}

function renderUsd() {
  const amount = state.amountARS;
  const from = state.startMonth;
  const equiv = equivToday();
  const today = data.vintage;

  const thenOff = model.usd(amount, from, "off");
  const thenBlue = model.usd(amount, from, "blue");
  const nowOff = model.usd(equiv, today, "off");
  const nowBlue = model.usd(equiv, today, "blue");
  const estThen = model.row(from).blue_est;

  const card = (title: string, off: number, blue: number, est: boolean) =>
    `<div class="usd-card">
       <span class="usd-when">${title}</span>
       <div class="usd-row"><span>al oficial</span><strong>${fmtUSD(off)}</strong></div>
       <div class="usd-row"><span>al blue</span><strong class="${est ? "muted" : "warn"}">${est ? "—" : fmtUSD(blue)}</strong></div>
     </div>`;

  $("usd-cards").innerHTML =
    card(`${fmtARS(amount)} en ${fmtMonth(from)}`, thenOff, thenBlue, estThen) +
    card(`${fmtARS(equiv)} hoy`, nowOff, nowBlue, false);

  const brechaNow = model.brechaPct(today);
  const thenClause = estThen
    ? `En ${fmtMonth(from)} no había dólar blue (sin cepo, el paralelo no era relevante), así que <strong>${fmtARS(amount)}</strong> eran <strong>${fmtUSD(thenOff)}</strong>.`
    : `En ${fmtMonth(from)}, <strong>${fmtARS(amount)}</strong> eran <strong>${fmtUSD(thenOff)}</strong> al oficial y <strong>${fmtUSD(thenBlue)}</strong> al blue.`;
  $("usd-intro").innerHTML =
    `Ajustar por inflación en pesos no es lo mismo que mantener el valor en dólares, y el dólar tiene dos precios. ` +
    `${thenClause} Su equivalente de hoy (<strong>${fmtARS(equiv)}</strong>) son <strong>${fmtUSD(nowOff)}</strong> al oficial ` +
    `pero apenas <strong>${fmtUSD(nowBlue)}</strong> al blue —una <strong>brecha</strong> del ${fmtPct(brechaNow)} entre los dos dólares de hoy.`;

  const estNote = estThen
    ? ` El blue arranca en 2011: antes del cepo se usa el oficial.`
    : ` Entonces la brecha era del ${fmtPct(model.brechaPct(from))}.`;
  $("usd-foot").innerHTML =
    `Oficial: tipo de cambio de referencia del BCRA. Blue: cotización informal (Bluelytics).${estNote}`;

  charts.renderUsdBars($("chart-usd"), [
    { label: `entonces · oficial`, usd: thenOff, kind: "off", when: "then" },
    { label: `entonces · blue`, usd: estThen ? thenOff : thenBlue, kind: "blue", when: "then" },
    { label: `hoy · oficial`, usd: nowOff, kind: "off", when: "now" },
    { label: `hoy · blue`, usd: nowBlue, kind: "blue", when: "now" },
  ]);
}

function renderDecayText() {
  const from = state.startMonth;
  const amount = state.amountARS;
  $("decay-caption").textContent = `Poder de compra de ${fmtARS(amount)} guardados desde ${fmtMonth(from)}`;
  $("decay-intro").innerHTML =
    `Si hubieras guardado <strong>${fmtARS(amount)}</strong> en efectivo desde ${fmtMonth(from)} sin moverlos, ` +
    `su poder de compra se habría ido derritiendo mes a mes. La curva arranca en lo que valían (${fmtARS(equivToday())} de hoy) ` +
    `y termina en los <strong>${fmtARS(amount)}</strong> nominales que seguirían siendo: todo lo que falta se lo comió la inflación.`;
  $("decay-foot").textContent =
    `Valor expresado en pesos de hoy. Fuente: IPC empalmado (INDEC / San Luis), datos hasta ${data.vintage_label}.`;
}

function renderDollarText() {
  $("dollar-intro").innerHTML =
    `El peso no sólo pierde contra los precios: también contra el dólar. Acá están las dos cotizaciones —la ` +
    `<strong>oficial</strong> (BCRA) y la <strong>blue</strong> (informal)— en escala logarítmica para que se vean ` +
    `juntas pese a la diferencia de magnitud, y la <strong>brecha</strong> entre ambas, que se dispara en los años de cepo.`;
  $("dollar-foot").textContent =
    `El blue arranca en 2011 (antes del cepo no había un paralelo relevante: se usa el oficial). ` +
    `Oficial: BCRA. Blue: Bluelytics.`;
}

function renderInflText() {
  $("infl-intro").innerHTML =
    `Cada barra es la inflación de un año. El color marca de qué fuente sale: ` +
    `<span style="color:var(--chart-muted);font-weight:600">IPC-GBA</span> antes de 2007, ` +
    `<span style="color:var(--warn);font-weight:600">San Luis</span> en la década intervenida, e ` +
    `<span style="color:var(--accent);font-weight:600">IPC Nacional</span> desde 2017.`;
  $("infl-foot").textContent =
    `En los años intervenidos (2007–2015) el INDEC declaraba una inflación mucho menor a la real; por eso este tramo usa San Luis.`;
}

function renderIndexText() {
  $("index-intro").innerHTML =
    `Esta es la columna vertebral de todo el cálculo: el índice de precios que arranca en 1993 y termina en 100 (hoy). ` +
    `Se ve el empalme de las tres series y, sombreada, la ventana en que el INDEC estuvo intervenido.`;
  $("index-foot").textContent =
    `Índice empalmado por variación mensual, rebasado a hoy = 100. Tramos: IPC-GBA · IPC San Luis · IPC Nacional.`;
  $("seg-legend").innerHTML = data.source.ipc_segments
    .map((s) => `<span class="seg-item" data-k="${s.key}"><span class="seg-sw seg-${s.key}"></span>${s.label} <span class="muted">(${s.start} – ${s.end})</span></span>`)
    .join("");
}

function renderInfl() {
  const fromYear = parseInt(state.startMonth.slice(0, 4), 10);
  if (state.inflFreq === "annual") {
    $("infl-caption").textContent = "Inflación interanual (diciembre a diciembre)";
    charts.renderAnnual($("chart-infl"), data.annual_inflation, fromYear);
  } else {
    $("infl-caption").textContent = "Inflación mensual, desde el mes elegido";
    charts.renderMonthly($("chart-infl"), data.series, state.startMonth);
  }
}

function renderSticky() {
  $("sticky-bar").innerHTML =
    `<div class="sticky-inner"><span><strong>${fmtARS(state.amountARS)}</strong> de ${fmtMonth(state.startMonth)} ` +
    `= <strong>${fmtARS(equivToday())}</strong> hoy</span><span class="sticky-edit">Editar ↑</span></div>`;
}

function renderVisuals() {
  charts.refreshPalette();
  charts.renderDecay($("chart-decay"), model, state.startMonth, state.amountARS);
  charts.renderDollar($("chart-dollar"), model, state.startMonth);
  charts.renderBrecha($("chart-brecha"), data.series);
  charts.renderIndex($("chart-index"), model, state.startMonth);
  renderInfl();
}

function renderBlindspots() {
  const items = [
    `Es <strong>inflación nacional</strong>: tu costo de vida real depende de qué consumís y dónde vivís (alquiler, alimentos y tarifas no se mueven todos igual).`,
    `Para 2007–2015 usamos el <strong>IPC de San Luis</strong> como referencia creíble. Otras alternativas (IPC Congreso, CABA, provincias) dan números parecidos pero no idénticos; el oficial de esos años está desacreditado.`,
    `El <strong>empalme</strong> encadena variaciones mensuales de series con bases y canastas distintas: el nivel exacto de un peso de los 90 tiene más incertidumbre que uno reciente.`,
    `El <strong>dólar blue</strong> arranca en 2011; antes del cepo se usa el oficial. La cotización informal es ruidosa y varía intradía.`,
    `Convierte <strong>poder de compra</strong>, no rendimientos: no contempla intereses, plazos fijos ni inversiones que podrían haber ganado (o perdido) contra la inflación.`,
  ];
  $("blindspots-list").innerHTML = items.map((x) => `<li>${x}</li>`).join("");
}

function renderMethodology() {
  const segs = data.source.ipc_segments;
  const rows = charts
    .validationRows(data.annual_inflation, data.anchors.indec_nacional_annual)
    .map((r) => `<tr><td>${r.year}</td><td>${fmtPct(r.official)}</td><td>${fmtPct(r.ours)}</td><td>${r.ok ? "✓" : "✗"}</td></tr>`)
    .join("");
  const segRows = segs
    .map((s) => `<tr><td>${s.start} – ${s.end}</td><td><strong>${s.label}</strong><br><span class="muted">${s.source}. ${s.note}</span></td></tr>`)
    .join("");
  const cum = data.anchors.cum;

  $("methodology-body").innerHTML = `
    <p>Casi todos los “convertidores de inflación” usan una sola serie y se rompen en los años en que el INDEC
    estuvo intervenido. Acá se descargan las <strong>series oficiales reales</strong> (INDEC y BCRA, vía
    datos.gob.ar) y se <strong>empalman</strong> tramo a tramo, encadenando la variación mensual.</p>

    <h3>El empalme del IPC</h3>
    <table class="val-table seg-table">
      <thead><tr><th>Período</th><th>Fuente</th></tr></thead>
      <tbody>${segRows}</tbody>
    </table>
    <p>Entre 2007 y 2015 el INDEC <strong>subdeclaró la inflación</strong> (informaba ~10% anual cuando la real
    rondaba 25–40%). Por eso ese tramo usa el <strong>IPC de San Luis</strong>, una dirección provincial de
    estadística fuera de la intervención. El empalme une los tramos por su variación mes a mes, con un mes de
    solapamiento en cada quiebre, y rebasa todo para que <strong>hoy = 100</strong>.</p>

    <h3>El dólar</h3>
    <p><strong>Oficial:</strong> tipo de cambio de referencia del BCRA (billete), diario desde 1992. <strong>Blue:</strong>
    cotización informal histórica de Bluelytics, desde 2011; antes del cepo no había un paralelo relevante, así que
    se usa el oficial. Todo se promedia a fin de mes.</p>

    <h3>Lo verificamos contra las cifras oficiales</h3>
    <p>El empalme reproduce la inflación interanual publicada por el INDEC para el IPC Nacional:</p>
    <table class="val-table">
      <thead><tr><th>Año</th><th>INDEC</th><th>Nuestro cálculo</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="muted">Y un cross-check independiente: <strong>${fmtARS(cum.pesos)}</strong> de ${fmtMonth(cum.from_month)}
    equivalen a <strong>${fmtARS(cum.computed_today)}</strong> de hoy.</p>

    <h3>Qué tener en cuenta</h3>
    <ul>
      <li>El índice está <strong>vintage-pinneado</strong> a ${data.vintage_label}: se ignoran meses nuevos hasta actualizarlo, para que el cálculo sea reproducible.</li>
      <li>Es inflación <strong>nacional</strong>; tu canasta personal puede moverse distinto.</li>
      <li>El nivel de los pesos más viejos tiene más incertidumbre (empalme de canastas distintas).</li>
    </ul>`;
}

function renderFooter() {
  const d = new Date(data.generated_at);
  const segIds = data.source.ipc_segments.map((s) => s.series_id).join(", ");
  $("site-footer").innerHTML = `
    <p>${data.citation}</p>
    <p class="muted">
      Series datos.gob.ar: ${segIds}, ${data.source.fx_official.series_id} ·
      blue: <a href="${data.source.fx_blue.url}" rel="noopener">Bluelytics</a> ·
      vintage ${data.vintage} · artefacto generado ${d.toLocaleDateString("es-AR")}
    </p>`;
}

init();
