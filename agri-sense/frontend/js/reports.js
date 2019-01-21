// AgriSense 数据统计报表
// 依赖: dashboard.js (API_BASE, getAuthToken, getCurrentUser)、ECharts

let currentDays = 14;
const charts = {};

// ---------- 权限校验 ----------
function isOperator() {
  const u = getCurrentUser();
  return !!(u && u.role && (u.role === "operator" || u.role === "admin"));
}

function showPerm() {
  $("#reports-box").hide();
  $("#perm-box").show();
}

function setupCharts() {
  charts.environment = echarts.init(document.getElementById("chart-environment"));
  charts.alertLevel  = echarts.init(document.getElementById("chart-alert-level"));
  charts.alertTrend  = echarts.init(document.getElementById("chart-alert-trend"));
  charts.irrigation  = echarts.init(document.getElementById("chart-irrigation"));
  charts.farm        = echarts.init(document.getElementById("chart-farm"));
  charts.batchStatus = echarts.init(document.getElementById("chart-batch-status"));
  charts.batchCrop   = echarts.init(document.getElementById("chart-batch-crop"));

  window.addEventListener("resize", function () {
    Object.values(charts).forEach(c => c && c.resize());
  });
}

// ---------- 数据拉取 ----------
function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    $.ajax({
      url, dataType: "json", timeout: 6000,
      headers: { "X-Auth-Token": getAuthToken() },
      success: resolve, error: reject,
    });
  });
}

async function loadDashboard() {
  try {
    const d = await fetchJSON(API_BASE + "/api/reports/dashboard?days=" + currentDays);
    $("#stat-readings").text((d.reading_count || 0).toLocaleString());
    $("#stat-moisture").text(d.avg_moisture != null ? d.avg_moisture : "--");
    $("#stat-temp").text(d.avg_temperature != null ? d.avg_temperature : "--");
    $("#stat-irrigation").text((d.irrigation_start || 0) + (d.irrigation_stop ? " / " + d.irrigation_stop : ""));
    $("#stat-alerts").text(d.alert_total || 0);
    $("#stat-batches").text(d.batch_count || 0);
  } catch (e) {
    // 401/403 由全局捕获；网络错误静默
  }
}

async function loadEnvironment() {
  try {
    const d = await fetchJSON(API_BASE + "/api/reports/environment?days=" + currentDays);
    // 环境双 Y 轴：墒情(%) + 温度(°C) + 湿度(%)
    charts.environment.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["平均墒情(%)", "最低墒情", "最高墒情", "平均温度(°C)", "平均湿度(%)"], top: 0 },
      grid: { left: 40, right: 50, top: 40, bottom: 30 },
      xAxis: { type: "category", data: d.labels, boundaryGap: false },
      yAxis: [
        { type: "value", name: "墒情/湿度 (%)", min: 0, max: 100 },
        { type: "value", name: "温度 (°C)" },
      ],
      series: [
        { name: "平均墒情(%)", type: "line", smooth: true, data: d.avg_moisture, itemStyle: { color: "#2e7d32" }, areaStyle: { opacity: 0.15 } },
        { name: "最低墒情", type: "line", smooth: true, data: d.min_moisture, itemStyle: { color: "#9ccc65" }, lineStyle: { type: "dashed", width: 1 } },
        { name: "最高墒情", type: "line", smooth: true, data: d.max_moisture, itemStyle: { color: "#f9a825" }, lineStyle: { type: "dashed", width: 1 } },
        { name: "平均温度(°C)", type: "line", smooth: true, yAxisIndex: 1, data: d.avg_temp, itemStyle: { color: "#e64a19" } },
        { name: "平均湿度(%)", type: "line", smooth: true, data: d.avg_humidity, itemStyle: { color: "#4a9edb" }, lineStyle: { width: 2 } },
      ],
    });
  } catch (e) {}
}

async function loadAlerts() {
  try {
    const d = await fetchJSON(API_BASE + "/api/reports/alerts?days=" + currentDays);
    // 等级饼图
    const levelColors = { "严重": "#c0392b", "警告": "#e67e22", "提示": "#4a9edb" };
    charts.alertLevel.setOption({
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      series: [{
        type: "pie", radius: ["45%", "70%"], center: ["50%", "45%"],
        label: { formatter: "{b}: {c} ({d}%)", fontSize: 12 },
        data: d.level_distribution.map(l => ({
          name: l.name, value: l.value,
          itemStyle: { color: levelColors[l.name] || "#999" },
        })),
      }],
    });

    // 趋势柱状 + 折线
    charts.alertTrend.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category", data: d.labels },
      yAxis: { type: "value", minInterval: 1 },
      series: [
        {
          name: "告警数", type: "bar", data: d.trend,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#e67e22" }, { offset: 1, color: "#fde8c0" },
            ]),
          },
        },
        {
          name: "趋势", type: "line", smooth: true, data: d.trend,
          itemStyle: { color: "#c0392b" }, lineStyle: { width: 2, type: "dashed" },
        },
      ],
    });
  } catch (e) {}
}

async function loadIrrigation() {
  try {
    const d = await fetchJSON(API_BASE + "/api/reports/irrigation?days=" + currentDays);
    charts.irrigation.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category", data: d.labels },
      yAxis: { type: "value", minInterval: 1 },
      series: [{
        name: "启动次数", type: "bar", data: d.daily_start,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#4a9edb" }, { offset: 1, color: "#b3d7ea" },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
      }],
    });

    // 日志列表
    const html = (d.recent || []).slice(0, 12).map(log => {
      const cls = log.action === "start" ? "tag-start" : "tag-stop";
      return `<div class="r-irr-row">
        <span class="${cls}">${log.action === "start" ? "启动" : "停止"}</span>
        <span class="reason">${log.reason || ""}</span>
        <span class="ts">${log.created_at || ""}</span>
      </div>`;
    }).join("");
    $("#irr-log-list").html(html || '<div class="text-muted text-center py-3">暂无灌溉日志</div>');
  } catch (e) {}
}

async function loadFarmAndBatch() {
  try {
    const [farm, batch] = await Promise.all([
      fetchJSON(API_BASE + "/api/reports/farm"),
      fetchJSON(API_BASE + "/api/reports/batch"),
    ]);

    // 农事活动水平条形图
    charts.farm.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 60, right: 20, top: 10, bottom: 20 },
      xAxis: { type: "value", minInterval: 1 },
      yAxis: { type: "category", data: farm.map(f => f.name), inverse: true },
      series: [{
        type: "bar", data: farm.map(f => f.value),
        itemStyle: { color: "#2e7d32", borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right" },
      }],
    });

    // 批次质量状态饼图
    const statusColors = { "已合格": "#2e7d32", "不合格": "#c0392b", "待质检": "#e67e22", "已采收": "#4a9edb" };
    charts.batchStatus.setOption({
      tooltip: { trigger: "item" },
      legend: { bottom: 0 },
      series: [{
        type: "pie", radius: ["40%", "65%"], center: ["50%", "45%"],
        label: { formatter: "{b}: {c} ({d}%)", fontSize: 12 },
        data: batch.status_distribution.map(s => ({
          name: s.name, value: s.value,
          itemStyle: { color: statusColors[s.name] || "#999" },
        })),
      }],
    });

    // 作物类型柱状
    charts.batchCrop.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category", data: batch.crop_distribution.map(c => c.name) },
      yAxis: { type: "value", minInterval: 1 },
      series: [{
        type: "bar", data: batch.crop_distribution.map(c => c.value),
        itemStyle: { color: "#66bb6a", borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: "top" },
      }],
    });
  } catch (e) {}
}

function loadAll() {
  loadDashboard();
  loadEnvironment();
  loadAlerts();
  loadIrrigation();
  loadFarmAndBatch();
}

$(function () {
  if (!isOperator()) { showPerm(); return; }

  // 日期范围切换
  $("#days-group .btn").on("click", function () {
    $("#days-group .btn").removeClass("active");
    $(this).addClass("active");
    currentDays = parseInt($(this).data("days"), 10);
    loadAll();
  });

  $("#btn-refresh").on("click", loadAll);

  // 等 DOM 渲染后初始化 ECharts
  setupCharts();
  loadAll();
});
