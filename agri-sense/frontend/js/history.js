// AgriSense 历史分析页：多指标趋势图 + 分页数据表 + CSV 导出
// 依赖：echarts、jQuery、dashboard.js（API_BASE、fmtTime）

const METRICS = {
  soil_moisture: { label: "土壤墒情(%)", color: "#8d6e63", unit: "%" },
  temperature:  { label: "温度(°C)",     color: "#ef6c00", unit: "°C" },
  humidity:     { label: "湿度(%)",      color: "#1976d2", unit: "%" },
  light:        { label: "光照(lux)",    color: "#f9a825", unit: "lux" },
};

const PAGE_SIZE = 15;
let currentHours = 24;
let activeMetrics = ["soil_moisture", "temperature", "humidity"];
let rawHistory = [];
let currentPage = 1;
let historyChart = null;

// ---------- 图表初始化 ----------
function initChart() {
  historyChart = echarts.init(document.getElementById("history-chart"));
  historyChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: [],
      axisLabel: { fontSize: 10, color: "#888" },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, color: "#888" },
      splitLine: { lineStyle: { color: "#f0f0f0" } },
    },
    series: [],
  });
}

function renderChart() {
  const series = activeMetrics.map((m) => ({
    name: METRICS[m].label,
    type: "line",
    smooth: true,
    symbol: "none",
    data: rawHistory.map((d) => d[m]),
    lineStyle: { color: METRICS[m].color, width: 2 },
    itemStyle: { color: METRICS[m].color },
    areaStyle: m === "soil_moisture" ? { color: "rgba(141,110,99,0.08)" } : undefined,
  }));

  historyChart.setOption({
    legend: { data: activeMetrics.map((m) => METRICS[m].label) },
    xAxis: { data: rawHistory.map((d) => d.time) },
    series: series,
  });

  // 摘要
  if (rawHistory.length > 0) {
    const summary = activeMetrics.map((m) => {
      const vals = rawHistory.map((d) => d[m]).filter((v) => v != null);
      if (vals.length === 0) return "";
      const avg = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
      const max = Math.max(...vals).toFixed(1);
      const min = Math.min(...vals).toFixed(1);
      return `${METRICS[m].label.replace(/\(.*\)/, "")}: 均${avg} / 高${max} / 低${min}`;
    }).filter(Boolean).join("　|　");
    $("#chart-summary").text(summary);
  }
}

// ---------- 数据表分页 ----------
function renderTable() {
  const total = rawHistory.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;

  const start = (currentPage - 1) * PAGE_SIZE;
  const pageRows = rawHistory.slice(start, start + PAGE_SIZE);

  const tbody = $("#history-table");
  if (pageRows.length === 0) {
    tbody.html('<tr><td colspan="5" class="text-center text-muted py-3">暂无数据</td></tr>');
  } else {
    tbody.html(pageRows.map((d) => `
      <tr>
        <td class="text-nowrap">${d.time}</td>
        <td>${d.soil_moisture ?? "--"}</td>
        <td>${d.temperature ?? "--"}</td>
        <td>${d.humidity ?? "--"}</td>
        <td>${d.light != null ? d.light.toLocaleString() : "--"}</td>
      </tr>
    `).join(""));
  }

  $("#table-info").text(`共 ${total} 条聚合记录`);
  $("#page-info").text(`第 ${currentPage} / ${totalPages} 页`);
  renderPagination(totalPages);
}

function renderPagination(totalPages) {
  const ul = $("#pagination").empty();
  const addLi = (label, page, disabled, active) => {
    const li = $("<li>").addClass("page-item" + (disabled ? " disabled" : "") + (active ? " active" : ""));
    li.append($("<a>").addClass("page-link").attr("href", "#").text(label).on("click", (e) => {
      e.preventDefault();
      if (!disabled && !active) {
        currentPage = page;
        renderTable();
      }
    }));
    ul.append(li);
  };
  addLi("上一页", currentPage - 1, currentPage <= 1, false);
  const maxBtn = Math.min(totalPages, 7);
  let startPage = Math.max(1, currentPage - 3);
  if (startPage + maxBtn - 1 > totalPages) startPage = Math.max(1, totalPages - maxBtn + 1);
  for (let i = startPage; i < startPage + maxBtn && i <= totalPages; i++) {
    addLi(i, i, false, i === currentPage);
  }
  addLi("下一页", currentPage + 1, currentPage >= totalPages, false);
}

// ---------- 数据加载 ----------
function loadHistory() {
  $.get(API_BASE + "/api/sensors/history", { hours: currentHours }, function (data) {
    rawHistory = data || [];
    currentPage = 1;
    renderChart();
    renderTable();
  });
}

// ---------- CSV 导出 ----------
function exportCSV() {
  if (rawHistory.length === 0) return;
  const headers = ["时间", "土壤墒情(%)", "温度(°C)", "湿度(%)", "光照(lux)"];
  const rows = rawHistory.map((d) => [
    d.time, d.soil_moisture ?? "", d.temperature ?? "", d.humidity ?? "", d.light ?? ""
  ]);
  const csv = "\uFEFF" + [headers, ...rows].map((r) => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `agrisense_history_${currentHours}h_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------- 事件绑定 ----------
function bindEvents() {
  $("#range-group .btn").on("click", function () {
    $("#range-group .btn").removeClass("active");
    $(this).addClass("active");
    currentHours = parseInt($(this).data("hours"), 10);
    loadHistory();
  });

  $(".metric-btn").on("click", function () {
    const metric = $(this).data("metric");
    if (activeMetrics.includes(metric)) {
      if (activeMetrics.length === 1) return; // 至少保留一个
      activeMetrics = activeMetrics.filter((m) => m !== metric);
      $(this).removeClass("active");
    } else {
      activeMetrics.push(metric);
      $(this).addClass("active");
    }
    renderChart();
  });

  $("#btn-export").on("click", exportCSV);
}

// ---------- 初始化 ----------
$(document).ready(function () {
  initChart();
  bindEvents();
  loadHistory();

  $(window).on("resize", () => historyChart && historyChart.resize());
});
