// AgriSense 历史趋势图：ECharts 渲染过去 24 小时土壤墒情 + 温度
let historyChart = null;

function renderChart(data) {
  if (!historyChart) {
    historyChart = echarts.init(document.getElementById("history-chart"));
  }
  const times = data.map(d => d.time);
  const moisture = data.map(d => d.soil_moisture);
  const temperature = data.map(d => d.temperature);

  historyChart.setOption({
    title: { text: "过去 24 小时土壤墒情趋势", left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { data: ["土壤墒情(%)", "温度(°C)"], bottom: 0 },
    grid: { left: 50, right: 50, top: 50, bottom: 40 },
    xAxis: { type: "category", data: times, boundaryGap: false },
    yAxis: [
      { type: "value", name: "墒情(%)", min: 0, max: 100, position: "left" },
      { type: "value", name: "温度(°C)", position: "right" }
    ],
    series: [
      {
        name: "土壤墒情(%)",
        type: "line",
        smooth: true,
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2, color: "#28a745" },
        itemStyle: { color: "#28a745" },
        data: moisture
      },
      {
        name: "温度(°C)",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: "#fd7e14" },
        itemStyle: { color: "#fd7e14" },
        data: temperature
      }
    ]
  });

  // 更新环境概览统计
  const temps = temperature.filter(v => v !== null && v !== undefined);
  const moistures = moisture.filter(v => v !== null && v !== undefined);
  if (temps.length) {
    $("#max-temp").text(Math.max(...temps).toFixed(1) + "°C");
    $("#min-temp").text(Math.min(...temps).toFixed(1) + "°C");
  }
  if (moistures.length) {
    const avg = moistures.reduce((a, b) => a + b, 0) / moistures.length;
    $("#avg-moisture").text(avg.toFixed(1) + "%");
  }
  $("#data-count").text(data.length + " 条");
}

function loadHistory() {
  $.get(API_BASE + "/api/sensors/history?hours=24", renderChart);
}

$(document).ready(function () {
  loadHistory();
  setInterval(loadHistory, 60000);
});
