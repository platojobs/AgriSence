// AgriSense 气象服务页：当前天气 / 24 小时趋势 / 7 天预报 / 天气驱动灌溉建议
$(function () {
  let currentCity = "杭州";
  let chart = null;
  const REFRESH_MS = 300000; // 5 分钟刷新一次

  const DECISION_MAP = {
    start: { text: "建议灌溉", cls: "status-start", color: "#c0392b" },
    stop: { text: "停止灌溉", cls: "status-stop", color: "#2e7d32" },
    hold: { text: "暂不灌溉", cls: "status-hold", color: "#f0a830" },
  };

  function renderCurrent(d) {
    const c = d.current;
    $("#w-city").text(d.city);
    $("#w-temp").text(c.temp.toFixed(1));
    $("#w-text").text(c.text);
    $("#w-icon").attr("class", "bi " + c.icon).css("color", c.color);
    $("#w-feels").text(c.feels_like);
    $("#w-update").text(c.update_time);
    $("#w-hum").text(c.humidity);
    $("#w-wind").text(c.wind.toFixed(1));
    $("#w-pressure").text(c.pressure);
    $("#w-rain-mm").text(c.rain_mm.toFixed(1));
    $("#w-vis").text(c.visibility);
    $("#w-uv").text(c.uv);
    $("#w-rain-pill").text("降水 " + c.rain_prob + "%");
    $("#w-source").text(d.source);
  }

  function renderFarmingIndex(fi) {
    const color = fi.level === "good" ? "#2e7d32" : (fi.level === "normal" ? "#f0a830" : "#c0392b");
    $("#fi-ring").css("background", color);
    $("#fi-score").text(fi.score);
    $("#fi-text").text(fi.text);
    $("#fi-tips").html(fi.tips.map(function (t) {
      return '<div class="tip-item"><i class="bi bi-check2-circle text-success me-1"></i>' + t + "</div>";
    }).join(""));
  }

  function renderIrrigation(irr) {
    const map = DECISION_MAP[irr.decision] || DECISION_MAP.hold;
    const $pill = $("#irr-pill");
    $pill.removeClass("status-start status-stop status-hold")
      .addClass(map.cls)
      .text(map.text)
      .css("background", map.color + "1a")
      .css("color", map.color);

    $("#irr-soil").text(irr.soil_moisture === null || irr.soil_moisture === undefined ? "--" : irr.soil_moisture);
    $("#irr-decision").text(irr.decision_text || "--");
    $("#irr-tip").text(irr.tip || "--");
    $("#irr-rain-prob").text(irr.rain_prob);
    $("#irr-rain-mm").text(irr.rain_mm);
    $("#irr-threshold").text(irr.threshold_low + "% ~ " + irr.threshold_high + "%");
  }

  function renderChart(hourly) {
    const times = hourly.map(function (h) { return h.time; });
    const temps = hourly.map(function (h) { return h.temp; });
    const probs = hourly.map(function (h) { return h.rain_prob; });

    if (!chart) {
      chart = echarts.init(document.getElementById("w-chart"));
    }
    chart.setOption({
      grid: { left: 46, right: 52, top: 36, bottom: 30 },
      tooltip: { trigger: "axis" },
      legend: { data: ["气温 ℃", "降水概率 %"], right: 10, top: 0, textStyle: { fontSize: 11 } },
      xAxis: {
        type: "category",
        data: times,
        axisLabel: { fontSize: 11, interval: 2 },
        axisLine: { lineStyle: { color: "#cdd6d1" } },
      },
      yAxis: [
        {
          type: "value", name: "℃", nameTextStyle: { fontSize: 11 },
          axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: "#f0f3f1" } },
        },
        {
          type: "value", name: "%", max: 100, nameTextStyle: { fontSize: 11 },
          axisLabel: { fontSize: 11 }, splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "气温 ℃",
          type: "line",
          smooth: true,
          data: temps,
          symbolSize: 5,
          lineStyle: { width: 2.5, color: "#f0a830" },
          itemStyle: { color: "#f0a830" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(240,168,48,.28)" },
              { offset: 1, color: "rgba(240,168,48,.02)" },
            ]),
          },
        },
        {
          name: "降水概率 %",
          type: "line",
          yAxisIndex: 1,
          smooth: true,
          data: probs,
          symbolSize: 3,
          lineStyle: { width: 1.6, type: "dashed", color: "#4a9edb" },
          itemStyle: { color: "#4a9edb" },
        },
      ],
    });
  }

  function renderDays(daily) {
    let minAll = Math.min.apply(null, daily.map(function (d) { return d.temp_min; }));
    let maxAll = Math.max.apply(null, daily.map(function (d) { return d.temp_max; }));
    const span = Math.max(1, maxAll - minAll);

    const html = daily.map(function (d, idx) {
      const left = ((d.temp_min - minAll) / span) * 100;
      const width = Math.max(6, ((d.temp_max - d.temp_min) / span) * 100);
      const label = idx === 0 ? "今天" : (idx === 1 ? "明天" : d.weekday);
      return '<div class="day-row">' +
        '<div class="day-name">' + label + '<div class="w-sub">' + d.date.slice(5) + "</div></div>" +
        '<div class="day-icon"><i class="bi ' + d.icon + '" style="color:' + d.color + '"></i></div>' +
        '<div class="small text-muted" style="width:66px">' + d.text + "</div>" +
        '<div class="day-bar"><span style="left:' + left + "%;width:" + width + '%"></span></div>' +
        '<div class="day-temp"><b>' + Math.round(d.temp_max) + "°</b> / " + Math.round(d.temp_min) + "°</div>" +
        '<div class="day-rain"><i class="bi bi-droplet"></i> ' + d.rain_prob + "%</div>" +
        "</div>";
    }).join("");

    $("#w-days").html(html);
  }

  function renderAlerts(alerts) {
    if (!alerts || alerts.length === 0) {
      $("#w-alerts").html('<div class="text-center text-muted small py-4">' +
        '<i class="bi bi-shield-check fs-4 d-block mb-2 text-success"></i>近 3 天无气象预警，生产环境良好</div>');
      return;
    }
    $("#w-alerts").html(alerts.map(function (a) {
      return '<div class="alert-row"><span class="alert-badge ' + a.level + '">' + a.type + "</span>" +
        "<span>" + a.message + "</span></div>";
    }).join(""));
  }

  function loadWeather(city) {
    $.ajax({
      url: API_BASE + "/api/weather?city=" + encodeURIComponent(city),
      dataType: "json",
      timeout: 6000,
      success: function (d) {
        renderCurrent(d);
        renderFarmingIndex(d.farming_index);
        renderIrrigation(d.irrigation);
        renderChart(d.hourly);
        renderDays(d.daily);
        renderAlerts(d.alerts);
      },
      error: function () {
        $("#w-text").text("气象数据加载失败");
        $("#w-alerts").html('<div class="text-danger small py-3">无法连接后端服务，请检查 5001 端口</div>');
      },
    });
  }

  $("#city-group").on("click", ".btn", function () {
    $("#city-group .btn").removeClass("active");
    $(this).addClass("active");
    currentCity = $(this).data("city");
    loadWeather(currentCity);
  });

  $(window).on("resize", function () {
    if (chart) chart.resize();
  });

  loadWeather(currentCity);
  setInterval(function () { loadWeather(currentCity); }, REFRESH_MS);
});
