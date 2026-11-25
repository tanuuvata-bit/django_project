// static/js/phase-renderer.js
// Requires ApexCharts and Plotly to be loaded in the HTML

const WIDE_NAMES = new Set([
  "top_status_paths", "monthly_impact", "monthly_counts",
  "geo_points", "fastest_growing_cities", "growth_monthly_chart_a",
  "growth_monthly_chart_b", "scatter_chart", "summary_table",
  "outliers_table", "mixed_pure_table", "route_timeline",
  "gantt_chart", "daily_route_agenda", "orders_per_vehicle",
  "vehicle_route_map", "cascading_route_map" // Make sure this is here
]);

function renderPhases(data, container) {
  const phases = Array.isArray(data.phases) ? data.phases : [];
  container.innerHTML = "";

  if (!phases.length) {
    container.innerHTML = `<div class="col-12"><div class="alert alert-warning">No phases computed for this dataset.</div></div>`;
    return;
  }

  phases.forEach((phase, idx) => {
    const elId = `chart-${idx}-${phase.name}`;

    const isWide = WIDE_NAMES.has(phase.name) ||
                   phase.chart === "map" ||
                   phase.chart === "route_map" ||
                   phase.chart === "cascading_map" || // Ensure this is here
                   phase.chart === "grouped_bar" ||
                   phase.chart === "table" ||
                   phase.chart === "scatter";

    const colClass = isWide ? "col-12" : "col-md-6";

    const card = document.createElement("div");
    card.className = colClass;

    card.innerHTML = `
      <div class="card shadow-sm h-100">
        <div class="card-body">
          <h6 class="card-title mb-3">${phase.title || phase.name}</h6>
          <div id="${elId}"></div>
        </div>
      </div>`;
    container.appendChild(card);

    setTimeout(() => renderSinglePhase(phase, elId), 0);
  });

  window.dispatchEvent(new Event("resize"));
}

function renderSinglePhase(phase, elId) {
  const el = document.getElementById(elId);
  if (!el) return;

  const color = phase.color || "#6366f1";
  const suffix = phase.suffix || "";

  switch (phase.chart) {
    case "donut":
      new ApexCharts(el, {
        chart: { type: "donut", height: 340 },
        series: phase.values,
        labels: phase.labels,
        legend: { position: "bottom" },
        colors: phase.colors || ["#6366f1", "#10b981", "#ef4444", "#f59e0b", "#8b5cf6", "#ec4899"],
        dataLabels: { enabled: true, formatter: (val) => val.toFixed(1) + "%" },
        plotOptions: { pie: { donut: { size: "60%" } } }
      }).render();
      break;

    case "multi_line":
      new ApexCharts(el, {
        chart: { type: "line", height: 400, zoom: { enabled: false }, toolbar: { show: false } },
        series: phase.series.map(s => ({ name: s.name, data: s.values })),
        xaxis: { categories: phase.labels, title: { text: "Date" } },
        yaxis: { title: { text: "" } },
        stroke: { curve: "smooth", width: 3 },
        markers: { size: 4 },
        colors: ["#6366f1", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"],
        legend: { position: "bottom", horizontalAlign: "left" },
        dataLabels: { enabled: false }
      }).render();
      break;

    case "h_bar":
      new ApexCharts(el, {
        chart: {type: "bar", height: Math.max(380, phase.labels.length * 28), toolbar: {show: false}},
        series: [{name: "Count", data: phase.values}],
        xaxis: {categories: phase.labels},
        plotOptions: {
          bar: {
            horizontal: true,
            borderRadius: 4,
            barHeight: "85%"
          }
        },
        colors: [color],
        dataLabels: {
          enabled: true,
          style: {
            colors: ['#ffffff'],
            fontSize: '13px',
            fontWeight: 'bold'
          },
          formatter: (val) => Number(val).toLocaleString() + suffix
        }
      }).render();
      break;

    case "column":
    case "grouped_bar":
      const isGrouped = phase.chart === "grouped_bar";
      new ApexCharts(el, {
        chart: { type: "bar", height: 380, toolbar: { show: false } },
        series: isGrouped ? phase.series.map(s => ({ name: s.name, data: s.values })) : [{ name: "Count", data: phase.values }],
        xaxis: { categories: phase.labels },
        plotOptions: { bar: { columnWidth: isGrouped ? "50%" : "60%", borderRadius: 4 } },
        colors: isGrouped ? undefined : [color],
        dataLabels: { enabled: true, formatter: (val) => isGrouped ? val.toFixed(1) + "%" : Number(val).toLocaleString() },
        legend: { position: "bottom" }
      }).render();
      break;

    case "line":
    case "line_cancel":
    case "area":
      const isArea = phase.chart === "area";
      new ApexCharts(el, {
        chart: { type: isArea ? "area" : "line", height: 340, zoom: { enabled: false } },
        series: [{ name: "Count", data: phase.values }],
        xaxis: { categories: phase.labels },
        stroke: { curve: "smooth", width: isArea ? 2 : 3 },
        markers: { size: isArea ? 0 : 5 },
        fill: isArea ? { type: "gradient" } : undefined,
        colors: [color],
        dataLabels: { enabled: false }
      }).render();
      break;

    case "scatter":
      const scatterSeries = [{
        name: "Orders", type: "scatter", color: "#6366f1",
        data: phase.points, markers: { size: 4, opacity: 0.5 }
      }];
      if (phase.trend && phase.trend.length > 0) {
        scatterSeries.push({
          name: "Trendline", type: "line", color: "#ef4444",
          stroke: { width: 3, curve: "straight" }, markers: { size: 0 },
          data: phase.trend
        });
      }
      new ApexCharts(el, {
        chart: { type: "scatter", height: 400, toolbar: { show: false } },
        series: scatterSeries,
        xaxis: { title: { text: "Number of Items" }, tickAmount: 10, labels: { formatter: (val) => Math.round(val) } },
        yaxis: { title: { text: "Processing Time (Mins)" }, labels: { formatter: (val) => Math.round(val) } }
      }).render();
      break;

    case "map":
      if (!phase.lat || !phase.lon || !phase.lat.length) {
        el.innerHTML = `<p class="text-muted">No valid coordinates in dataset.</p>`;
        return;
      }
      Plotly.newPlot(el, [{
        type: "scattermapbox", mode: "markers",
        lat: phase.lat, lon: phase.lon,
        marker: { size: 6, color: "#6366f1", opacity: 0.6 },
        hoverinfo: "skip"
      }], {
        mapbox: { style: "open-street-map", zoom: 4, center: { lat: phase.lat[0], lon: phase.lon[0] } },
        margin: { t: 0, b: 0, l: 0, r: 0 },
        height: 500
      }, { displayModeBar: false, responsive: true });
      break;

    case "route_map":
      if (!phase.lat || !phase.lon || !phase.lat.length) {
        el.innerHTML = `<p class="text-muted">No route coordinates found.</p>`;
        return;
      }

      const numPoints = phase.lat.length;
      const markerColors = phase.lat.map((_, i) => {
        if (i === 0) return "#10b981";
        if (i === numPoints - 1) return "#ef4444";
        return "#6366f1";
      });

      Plotly.newPlot(el, [{
        type: "scattermapbox",
        mode: "lines+markers",
        lat: phase.lat,
        lon: phase.lon,
        text: phase.labels,
        line: { width: 3, color: "#94a3b8" },
        marker: { size: 8, color: markerColors },
        hoverinfo: "text"
      }], {
        mapbox: {
          style: "open-street-map",
          zoom: 11,
          center: { lat: phase.lat[0], lon: phase.lon[0] }
        },
        margin: { t: 0, b: 0, l: 0, r: 0 },
        height: 500
      }, { displayModeBar: false, responsive: true });
      break;

    case "cascading_map":
      let controlsHTML = `
        <div class="row mb-4 g-3 bg-light p-3 rounded border mx-0">
          <div class="col-md-4">
            <label class="form-label small fw-bold mb-1">Select Date</label>
            <select id="map-date-${elId}" class="form-select form-select-sm map-filter"></select>
          </div>
          <div class="col-md-4">
            <label class="form-label small fw-bold mb-1">Select Warehouse</label>
            <select id="map-wh-${elId}" class="form-select form-select-sm map-filter"></select>
          </div>
          <div class="col-md-4">
            <label class="form-label small fw-bold mb-1">Select Vehicle</label>
            <select id="map-veh-${elId}" class="form-select form-select-sm map-filter"></select>
          </div>
        </div>
        <div id="map-plot-${elId}" style="height: 500px; border-radius: 8px; overflow: hidden;"></div>
      `;

      el.innerHTML = controlsHTML;
      el.dataset.records = JSON.stringify(phase.records);

      setTimeout(() => {
        const records = JSON.parse(el.dataset.records);
        const dateSelect = document.getElementById(`map-date-${elId}`);
        const whSelect = document.getElementById(`map-wh-${elId}`);
        const vehSelect = document.getElementById(`map-veh-${elId}`);

        const dates = [...new Set(records.map(r => r.date))].sort();
        dateSelect.innerHTML = dates.map(d => `<option value="${d}">${d}</option>`).join('');

        function updateDropdowns() {
          const selectedDate = dateSelect.value;
          const dayRecords = records.filter(r => r.date === selectedDate);
          const whs = [...new Set(dayRecords.map(r => r.warehouse))].sort();
          whSelect.innerHTML = whs.map(w => `<option value="${w}">${w}</option>`).join('');
          updateVehicles();
        }

        function updateVehicles() {
          const selectedDate = dateSelect.value;
          const selectedWh = whSelect.value;
          const whRecords = records.filter(r => r.date === selectedDate && r.warehouse === selectedWh);
          const vehs = [...new Set(whRecords.map(r => r.vehicle))].sort();
          vehSelect.innerHTML = vehs.map(v => `<option value="${v}">${v}</option>`).join('');
          drawMap();
        }

        function drawMap() {
          const selectedDate = dateSelect.value;
          const selectedWh = whSelect.value;
          const selectedVeh = vehSelect.value;

          const routeData = records.filter(r =>
            r.date === selectedDate &&
            r.warehouse === selectedWh &&
            r.vehicle === selectedVeh
          );

          const mapDiv = document.getElementById(`map-plot-${elId}`);
          if (routeData.length === 0) {
            mapDiv.innerHTML = "<p class='text-center text-muted mt-5'>No route data for this selection.</p>";
            return;
          }

          const lat = routeData.map(r => r.lat);
          const lon = routeData.map(r => r.lon);
          const text = routeData.map(r => `<b>Order:</b> ${r.order_id}<br><b>Time:</b> ${r.time}`);

          Plotly.newPlot(mapDiv, [{
            type: "scattermapbox",
            mode: "lines+markers",
            lat: lat, lon: lon, text: text,
            line: { width: 3, color: "#94a3b8" },
            marker: { size: 8, color: "#6366f1" }
          }], {
            mapbox: { style: "open-street-map", zoom: 11, center: { lat: lat[0], lon: lon[0] } },
            margin: { t: 0, b: 0, l: 0, r: 0 }
          }, { displayModeBar: false, responsive: true });
        }

        dateSelect.addEventListener('change', updateDropdowns);
        whSelect.addEventListener('change', updateVehicles);
        vehSelect.addEventListener('change', drawMap);
        updateDropdowns();
      }, 100);
      break;

    case "timeline":
      let timelineHTML = `<div class="timeline-container" style="position: relative; padding-left: 30px; border-left: 2px solid #e2e8f0; margin-left: 10px;">`;
      phase.rows.forEach(row => {
        const distNum = parseFloat(row.distance) || 0;
        const dotColor = distNum > 40 ? "#ef4444" : "#10b981";
        timelineHTML += `
          <div class="timeline-item" style="position: relative; margin-bottom: 20px;">
            <div style="position: absolute; left: -37px; top: 4px; width: 12px; height: 12px; border-radius: 50%; background-color: ${dotColor}; border: 2px solid white; box-shadow: 0 0 0 2px ${dotColor};"></div>
            <div class="d-flex gap-3 align-items-start">
              <div style="min-width: 100px; font-weight: 600; color: #475569;">${row.time}</div>
              <div>
                <span class="badge bg-label-primary mb-1">${row.vehicle}</span>
                <div style="font-weight: 600; color: #1e293b;">${row.order_id}</div>
                <div class="text-muted small">${row.items}</div>
                <div class="fw-bold small mt-1" style="color: ${dotColor};">${row.distance}</div>
              </div>
            </div>
          </div>`;
      });
      timelineHTML += `</div>`;
      el.innerHTML = timelineHTML;
      break;

    case "gantt":
      new ApexCharts(el, {
        chart: { type: "rangeBar", height: 600, toolbar: { show: false }, animations: { enabled: false } },
        series: phase.series,
        plotOptions: { bar: { horizontal: true, barHeight: "50%", rangeBar: { isDashed: false }, borderRadius: 3 } },
        xaxis: { type: "datetime", labels: { datetimeUTC: false, format: "HH:mm" } },
        tooltip: {
          custom: function(opts) {
            const data = opts.w.config.series[opts.seriesIndex].data[opts.dataPointIndex];
            const start = new Date(data.y[0]).toLocaleTimeString('en-US', {hour: '2-digit', minute:'2-digit'});
            const end = new Date(data.y[1]).toLocaleTimeString('en-US', {hour: '2-digit', minute:'2-digit'});
            return `<div style="padding: 10px; background: white; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 13px;">
              <b style="color: #1e293b;">Order:</b> ${data.x}<br><b style="color: #1e293b;">Time:</b> ${start} - ${end}<br><b style="color: #1e293b;">Duration:</b> ${data.duration} mins<br><b style="color: #1e293b;">Product:</b> ${data.product}
            </div>`;
          }
        },
        colors: ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#06b6d4", "#84cc16"],
        legend: { position: "top", horizontalAlign: "left" }
      }).render();
      break;

    case "timeline_3csv":
      let tl3HTML = `<div class="timeline-container" style="position: relative; padding-left: 30px; border-left: 3px solid #cbd5e1; margin-left: 20px; margin-top: 20px;">`;
      phase.rows.forEach(row => {
        const isEnd = row.vehicle === "END";
        const dotShape = isEnd ? "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" : "50%";
        const dotSize = isEnd ? "18px" : "16px";
        tl3HTML += `
          <div class="timeline-item" style="position: relative; margin-bottom: 30px;">
            <div style="position: absolute; left: -40px; top: 4px; width: ${dotSize}; height: ${dotSize}; background-color: ${row.color}; border: 2px solid white; clip-path: ${dotShape}; border-radius: ${isEnd ? '0' : '50%'}; box-shadow: 0 0 0 3px ${row.color};"></div>
            <div class="d-flex gap-3 align-items-start">
              <div style="min-width: 110px; font-weight: 700; color: #1e293b; font-size: 14px; padding-top: 2px;">${isEnd ? row.time_start : `${row.time_start} – ${row.time_end}`}</div>
              <div>
                <div style="font-weight: 700; color: #1e293b; font-size: 15px; margin-bottom: 4px;">
                  ${row.order_id}
                  ${!isEnd ? `<span style="color: ${row.color}; margin-left: 10px;">(${row.duration}m)</span>` : ''}
                </div>
                <div class="text-muted" style="max-width: 600px; font-size: 13.5px; line-height: 1.4; max-height: 60px; overflow-y: auto; padding-right: 10px;">${row.product_title}</div>
              </div>
            </div>
          </div>
        `;
      });
      tl3HTML += `</div>`;
      el.innerHTML = tl3HTML;
      break;

    case "table":
      let tableHTML = `<div class="table-responsive"><table class="table table-hover table-sm align-middle"><thead class="table-light"><tr>`;
      phase.headers.forEach(h => tableHTML += `<th>${h}</th>`);
      tableHTML += `</tr></thead><tbody>`;
      phase.rows.forEach(row => {
        tableHTML += `<tr>`;
        row.forEach(cell => {
           const tdClass = cell.toString().includes('σ') ? 'text-danger fw-bold' : '';
           tableHTML += `<td class="${tdClass}">${cell}</td>`;
        });
        tableHTML += `</tr>`;
      });
      tableHTML += `</tbody></table></div>`;
      el.innerHTML = tableHTML;
      break;

    default:
      el.innerHTML = `<p class="text-muted small">Unsupported chart type: ${phase.chart}</p>`;
  }
}