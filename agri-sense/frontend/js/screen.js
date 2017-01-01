// AgriSense 数据大屏：一张图可视化
// 依赖：echarts、jQuery、dashboard.js（API_BASE、fmtTime）

let trendChart = null;
let irrChart = null;

// ---------- 时钟 ----------
function updateClock() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  $("#screen-clock").text(
    `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

// ---------- 大棚俯视图（6x4 = 24 个地块） ----------
function renderGreenhouseMap(latest) {
  const map = $("#gh-map").empty();
  const soil = latest?.soil_moisture ?? 50;
  // 以最新墒情为基准，给每个格子加随机波动，模拟多地块分布
  for (let i = 0; i < 24; i++) {
    const v = Math.max(5, Math.min(95, soil + (Math.random() - 0.5) * 30));
    let cls = "moisture-ok";
    if (v < 30) cls = "moisture-low";
    else if (v < 50) cls = "moisture-mid";
    else if (v > 80) cls = "moisture-high";
    map.append(`<div class="gh-cell ${cls}" title="地块 ${i+1}: ${v.toFixed(0)}%">${v.toFixed(0)}</div>`);
  }
}

// ---------- 设备状态 ----------
function renderDevices(devices) {
  const list = $("#device-status-list").empty();
  (devices || []).forEach((d) => {
    const dot = d.status === "online" ? "device-online" : "device-offline";
    list.append(`<div style="padding:0.3rem 0; font-size:0.8rem;">
      <span class="device-dot ${dot}"></span>${d.name || d.device_id}
      <small class="text-muted ms-1">${d.device_id}</small>
    </div>`);
  });
}

// ---------- 执行器状态 ----------
function renderActuators(actuators) {
  const list = $("#actuator-status-list").empty();
  (actuators || []).forEach((a) => {
    const on = a.status === "on";
    list.append(`<div style="padding:0.3rem 0; font-size:0.8rem; display:flex; justify-content:space-between;">
      <span>${a.label || a.name}</span>
      <span style="color:${on ? '#4caf50' : '#757575'};">${on ? '运行中' : '已关闭'}</span>
    </div>`);
  });
}

// ---------- 告警列表 ----------
const LEVEL_CLS = { critical: "lvl-critical", warning: "lvl-warning", info: "lvl-info" };

function renderAlerts(alerts) {
  const list = $("#screen-alert-list").empty();
  (alerts || []).slice(0, 10).forEach((a) => {
    const lvl = LEVEL_CLS[a.level] || "lvl-info";
    list.append(`<div style="padding:0.4rem 0; border-bottom:1px solid rgba(255,255,255,0.05); font-size:0.78rem;">
      <span class="${lvl}" style="padding:1px 6px; border-radius:3px; font-size:0.65rem; margin-right:6px;">${a.level || 'info'}</span>
      <span style="color:#ccc;">${a.message || a.type}</span>
      <div class="text-muted" style="font-size:0.68rem; margin-top:2px;">${a.created_at} · ${a.device_id || '--'}</div>
    </div>`);
  });

  // 底部滚动条
  const ticker = $("#alert-ticker-inner").empty();
  (alerts || []).slice(0, 8).forEach((a) => {
    const lvl = LEVEL_CLS[a.level] || "lvl-info";
    ticker.append(`<span class="item"><span class="lvl ${lvl}">${a.level}</span>${a.message || a.type}</span>`);
  });
}

// ---------- 趋势图 ----------
function initTrendChart() {
  trendChart = echarts.init(document.getElementById("screen-trend"));
  trendChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["墒情", "温度", "湿度"], textStyle: { color: "#aaa", fontSize: 10 }, top: 0 },
    grid: { left: 40, right: 15, top: 30, bottom: 25 },
    xAxis: { type: "category", data: [], axisLabel: { color: "#888", fontSize: 9 } },
    yAxis: { type: "value", axisLabel: { color: "#888", fontSize: 9 }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } } },
    series: [
      { name: "墒情", type: "line", smooth: true, symbol: "none", data: [], lineStyle: { color: "#a1887f" }, areaStyle: { color: "rgba(161,136,127,0.15)" } },
      { name: "温度", type: "line", smooth: true, symbol: "none", data: [], lineStyle: { color: "#ffb74d" } },
      { name: "湿度", type: "line", smooth: true, symbol: "none", data: [], lineStyle: { color: "#64b5f6" } },
    ],
  });
}

function renderTrend(data) {
  trendChart.setOption({
    xAxis: { data: data.map((d) => d.time) },
    series: [
      { data: data.map((d) => d.soil_moisture) },
      { data: data.map((d) => d.temperature) },
      { data: data.map((d) => d.humidity) },
    ],
  });
}

// ---------- 灌溉统计柱状图 ----------
function initIrrChart() {
  irrChart = echarts.init(document.getElementById("screen-irr-chart"));
  irrChart.setOption({
    grid: { left: 40, right: 15, top: 10, bottom: 25 },
    xAxis: { type: "category", data: ["开启", "停止", "调度"], axisLabel: { color: "#888", fontSize: 10 } },
    yAxis: { type: "value", axisLabel: { color: "#888", fontSize: 10 }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } } },
    series: [{
      type: "bar",
      data: [
        { value: 0, itemStyle: { color: "#4caf50" } },
        { value: 0, itemStyle: { color: "#757575" } },
        { value: 0, itemStyle: { color: "#ffb74d" } },
      ],
      barWidth: "40%",
      label: { show: true, position: "top", color: "#aaa", fontSize: 11 },
    }],
  });
}

function renderIrrStats(logs) {
  let start = 0, stop = 0;
  (logs || []).forEach((l) => {
    if (l.action === "start") start++;
    else if (l.action === "stop") stop++;
  });
  const scheduleCount = 3;
  irrChart.setOption({
    series: [{ data: [
      { value: start, itemStyle: { color: "#4caf50" } },
      { value: stop, itemStyle: { color: "#757575" } },
      { value: scheduleCount, itemStyle: { color: "#ffb74d" } },
    ]}],
  });
}

// ---------- 统一刷新 ----------
function refreshScreen() {
  $.when(
    $.get(API_BASE + "/api/sensors/latest"),
    $.get(API_BASE + "/api/sensors/history", { hours: 24 }),
    $.get(API_BASE + "/api/devices"),
    $.get(API_BASE + "/api/actuators"),
    $.get(API_BASE + "/api/alerts"),
    $.get(API_BASE + "/api/irrigation/logs"),
    $.get(API_BASE + "/api/stats/overview")
  ).done(function (latest, history, devices, actuators, alerts, logs, stats) {
    const d = latest[0];
    $("#s-soil").text(d.soil_moisture != null ? d.soil_moisture + "%" : "--");
    $("#s-temp").text(d.temperature != null ? d.temperature + "°C" : "--");
    $("#s-hum").text(d.humidity != null ? d.humidity + "%" : "--");
    $("#s-light").text(d.light != null ? d.light.toLocaleString() : "--");

    renderGreenhouseMap(d);
    renderDevices(devices[0]);
    renderActuators(actuators[0]);
    renderAlerts(alerts[0]);
    renderTrend(history[0]);
    renderIrrStats(logs[0]);

    const s = stats[0];
    $("#m-alert-count").text(s.alert_count || 0);
    $("#screen-update-time").text(fmtTime(d.timestamp));

    // 平均指标（从历史数据算）
    const hist = history[0] || [];
    if (hist.length > 0) {
      const avg = (key) => {
        const vals = hist.map((x) => x[key]).filter((v) => v != null);
        return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : "--";
      };
      $("#m-avg-soil").text(avg("soil_moisture"));
      $("#m-avg-temp").text(avg("temperature"));
      $("#m-avg-hum").text(avg("humidity"));
    }
  });
}

// ---------- 初始化 ----------
$(document).ready(function () {
  updateClock();
  setInterval(updateClock, 1000);
  initTrendChart();
  initIrrChart();
  refreshScreen();
  setInterval(refreshScreen, 5000);

  $(window).on("resize", () => {
    trendChart && trendChart.resize();
    irrChart && irrChart.resize();
  });
});
