// AgriSense 实时监测页：4 个仪表盘 + 实时数据流图 + 最近采集记录
// 依赖：echarts、jQuery、dashboard.js（API_BASE、fmtTime）

const MAX_POINTS = 30;          // 实时图最多保留 30 个采样点
let streamData = [];            // [{time, soil, temp, hum, light}]
let chartGauges = {};           // 4 个仪表盘实例
let streamChart = null;         // 实时数据流图实例

// ---------- 仪表盘通用配置 ----------
function gaugeOption(value, min, max, unit, color, label) {
  return {
    series: [{
      type: "gauge",
      min: min,
      max: max,
      radius: "92%",
      center: ["50%", "58%"],
      startAngle: 210,
      endAngle: -30,
      progress: { show: true, width: 12, itemStyle: { color: color } },
      axisLine: { lineStyle: { width: 12, color: [[1, "#e0e0e0"]] } },
      pointer: { itemStyle: { color: color }, length: "60%", width: 4 },
      axisTick: { show: false },
      splitLine: { length: 8, lineStyle: { color: "#bbb", width: 1 } },
      axisLabel: { color: "#999", fontSize: 9, distance: -18 },
      anchor: { show: true, size: 10, itemStyle: { color: color } },
      title: { show: false },
      detail: {
        valueAnimation: true,
        fontSize: 22,
        fontWeight: 700,
        color: color,
        offsetCenter: [0, "30%"],
        formatter: function (v) { return (v == null ? "--" : v) + " " + unit; },
      },
      data: [{ value: value == null ? 0 : value, name: label }],
    }],
  };
}

function initGauges() {
  chartGauges.soil = echarts.init(document.getElementById("gauge-soil"));
  chartGauges.temp = echarts.init(document.getElementById("gauge-temp"));
  chartGauges.hum = echarts.init(document.getElementById("gauge-hum"));
  chartGauges.light = echarts.init(document.getElementById("gauge-light"));

  chartGauges.soil.setOption(gaugeOption(null, 0, 100, "%", "#8d6e63", "墒情"));
  chartGauges.temp.setOption(gaugeOption(null, 0, 50, "°C", "#ef6c00", "温度"));
  chartGauges.hum.setOption(gaugeOption(null, 0, 100, "%", "#1976d2", "湿度"));
  chartGauges.light.setOption(gaugeOption(null, 0, 100000, "lux", "#f9a825", "光照"));
}

function updateGauges(data) {
  chartGauges.soil.setOption({ series: [{ data: [{ value: data.soil_moisture }] }] });
  chartGauges.temp.setOption({ series: [{ data: [{ value: data.temperature }] }] });
  chartGauges.hum.setOption({ series: [{ data: [{ value: data.humidity }] }] });
  chartGauges.light.setOption({ series: [{ data: [{ value: data.light }] }] });
}

// ---------- 实时数据流图 ----------
function initStreamChart() {
  streamChart = echarts.init(document.getElementById("realtime-chart"));
  streamChart.setOption({
    tooltip: { trigger: "axis" },
    legend: {
      data: ["土壤墒情(%)", "温度(°C)", "湿度(%)", "光照(×100 lux)"],
      top: 0,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 50, right: 50, top: 40, bottom: 30 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: [],
      axisLabel: { fontSize: 10, color: "#888" },
    },
    yAxis: [
      {
        type: "value",
        name: "墒情/温度/湿度",
        nameTextStyle: { fontSize: 10, color: "#888" },
        axisLabel: { fontSize: 10, color: "#888" },
        splitLine: { lineStyle: { color: "#f0f0f0" } },
      },
      {
        type: "value",
        name: "光照(×100)",
        nameTextStyle: { fontSize: 10, color: "#888" },
        axisLabel: { fontSize: 10, color: "#888" },
        splitLine: { show: false },
      },
    ],
    series: [
      { name: "土壤墒情(%)", type: "line", smooth: true, symbol: "none", data: [], lineStyle: { color: "#8d6e63", width: 2 }, areaStyle: { color: "rgba(141,110,99,0.08)" } },
      { name: "温度(°C)", type: "line", smooth: true, symbol: "none", data: [], lineStyle: { color: "#ef6c00", width: 2 } },
      { name: "湿度(%)", type: "line", smooth: true, symbol: "none", data: [], lineStyle: { color: "#1976d2", width: 2 } },
      { name: "光照(×100 lux)", type: "line", smooth: true, symbol: "none", yAxisIndex: 1, data: [], lineStyle: { color: "#f9a825", width: 2 } },
    ],
  });
}

function pushStreamPoint(data) {
  const t = data.timestamp ? fmtTime(data.timestamp).slice(11) : "--:--:--";
  streamData.push({
    time: t,
    soil: data.soil_moisture,
    temp: data.temperature,
    hum: data.humidity,
    light: data.light,
  });
  if (streamData.length > MAX_POINTS) streamData.shift();

  streamChart.setOption({
    xAxis: { data: streamData.map((d) => d.time) },
    series: [
      { data: streamData.map((d) => d.soil) },
      { data: streamData.map((d) => d.temp) },
      { data: streamData.map((d) => d.hum) },
      { data: streamData.map((d) => (d.light != null ? Math.round(d.light / 100) : null)) },
    ],
  });
}

// ---------- 最近采集记录表 ----------
function renderTable(rows) {
  const tbody = $("#realtime-table");
  if (!rows || rows.length === 0) {
    tbody.html('<tr><td colspan="7" class="text-center text-muted py-3">暂无采集记录</td></tr>');
    return;
  }
  const html = rows
    .map((r) => {
      const time = r.timestamp ? fmtTime(r.timestamp) : "--";
      const soil = r.soil_moisture != null ? r.soil_moisture + "%" : "--";
      const temp = r.temperature != null ? r.temperature + "°C" : "--";
      const hum = r.humidity != null ? r.humidity + "%" : "--";
      const light = r.light != null ? r.light.toLocaleString() : "--";
      const raw = r.raw != null ? r.raw : "--";
      const device = r.device_id || "--";
      return `<tr>
        <td class="text-nowrap">${time}</td>
        <td><span class="badge bg-light text-dark">${device}</span></td>
        <td>${soil}</td>
        <td>${temp}</td>
        <td>${hum}</td>
        <td>${light}</td>
        <td class="text-muted">${raw}</td>
      </tr>`;
    })
    .join("");
  tbody.html(html);
}

function loadRecentTable() {
  $.get(API_BASE + "/api/sensors/recent", { limit: 20 }, function (rows) {
    renderTable(rows);
  });
}

// ---------- 统一拉取最新数据 ----------
function refreshRealtime() {
  $.ajax({
    url: API_BASE + "/api/sensors/latest",
    dataType: "json",
    timeout: 4000,
    success: function (data) {
      updateGauges(data);
      pushStreamPoint(data);
    },
  });
  loadRecentTable();
}

// ---------- 初始化 ----------
$(document).ready(function () {
  initGauges();
  initStreamChart();
  refreshRealtime();
  setInterval(refreshRealtime, 5000);

  // 窗口缩放时重绘图表
  $(window).on("resize", function () {
    Object.values(chartGauges).forEach((c) => c && c.resize());
    streamChart && streamChart.resize();
  });
});
