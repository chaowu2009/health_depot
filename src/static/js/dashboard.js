// Dashboard charts (Chart.js). Data comes from <script id="dashboard-data" type="application/json">.
(function () {
  "use strict";
  var el = document.getElementById("dashboard-data");
  if (!el || !window.Chart) return;
  var data = JSON.parse(el.textContent);
  var ready = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
  ready.then(function () { draw(data); });
  function draw(data) {
  // Validated categorical palette (fixed order) + text tokens.
  var SERIES = ["#2a78d6", "#eda100", "#1baf7a", "#eb6834"];
  var PRIMARY = "#005ea2";  // single-series bars use the site's primary blue
  var INK = "#1b1b1b", MUTED = "#565c65", GRID = "#e6e6e6";

  // Same self-hosted font as the page (falls back to system fonts).
  Chart.defaults.font.family = "'Public Sans', system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = MUTED;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.color = INK;
  Chart.defaults.plugins.tooltip.backgroundColor = "#162e51";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation = false;

  // Shorten long category names on the axis; the tooltip and table show the full name.
  function shortLabel(label) {
    var text = String(label).replace(" (fictional)", "");
    return text.length > 21 ? text.slice(0, 20) + "…" : text;
  }

  function bar(id, pairs, opts) {
    var canvas = document.getElementById(id);
    if (!canvas || !pairs || !pairs.length) return;
    opts = opts || {};
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: pairs.map(function (p) { return p[0]; }),
        datasets: [{
          label: opts.label || "Referrals",
          data: pairs.map(function (p) { return p[1]; }),
          backgroundColor: opts.color || PRIMARY,
          borderRadius: 4, borderSkipped: "start", maxBarThickness: 22,
          borderColor: "#ffffff", borderWidth: { left: 0, right: 0, top: 2, bottom: 2 },
        }],
      },
      options: {
        layout: { padding: { left: 6 } },
        indexAxis: opts.horizontal === false ? "x" : "y",
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: function (items) {
            return items.length ? String(items[0].label).replace(" (fictional)", "") : "";
          }, label: function (ctx) {
            return " " + ctx.formattedValue + (opts.suffix || "");
          } } },
        },
        scales: {
          x: { grid: { color: opts.horizontal === false ? "transparent" : GRID },
               border: { display: false }, ticks: { precision: 0 },
               max: opts.max },
          y: { grid: { color: opts.horizontal === false ? GRID : "transparent" },
               border: { display: false },
               afterFit: opts.horizontal === false ? undefined : function (scale) {
                 scale.width = Math.max(scale.width, 162);  // room for category names
               },
               ticks: opts.horizontal === false ? { color: INK, precision: 0 } : {
                 color: INK, autoSkip: false,
                 callback: function (value) { return shortLabel(this.getLabelForValue(value)); },
               } },
        },
      },
    });
  }

  // Referrals over time: stacked by status group.
  var ot = data.over_time;
  var timeCanvas = document.getElementById("chart-over-time");
  if (timeCanvas && ot) {
    new Chart(timeCanvas, {
      type: "bar",
      data: {
        labels: ot.labels,
        datasets: ot.series.map(function (s, i) {
          return { label: s.name, data: s.data, backgroundColor: SERIES[i],
                   borderColor: "#ffffff", borderWidth: { top: 2 }, borderRadius: 2,
                   maxBarThickness: 28 };
        }),
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top", align: "start" } },
        scales: {
          x: { stacked: true, grid: { display: false }, border: { display: false } },
          y: { stacked: true, grid: { color: GRID }, border: { display: false },
               ticks: { precision: 0 } },
        },
      },
    });
  }
  bar("chart-program", data.by_program);
  bar("chart-needs", data.needs);
  bar("chart-partner-completion", data.partner_completion, { suffix: "%", max: 100,
                                                             label: "Completion rate" });
  bar("chart-ages", data.ages, { horizontal: false });
  bar("chart-races", data.races);
  bar("chart-ethnicities", data.ethnicities);
  bar("chart-languages", data.languages);
  bar("chart-zips", data.zips);
  }
})();
