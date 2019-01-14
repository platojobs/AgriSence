// AgriSense 仪表盘：实时拉取最新传感器读数与灌溉决策
const API_BASE = "http://localhost:5001"; // ★ 用户修改：后端地址

// ---------- 登录态工具（login.html / layout.js / 各页面共用） ----------
function getAuthToken() {
  return localStorage.getItem("agri_token") || "";
}

function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem("agri_user") || "null");
  } catch (e) {
    return null;
  }
}

function setAuth(token, user) {
  localStorage.setItem("agri_token", token);
  localStorage.setItem("agri_user", JSON.stringify(user || {}));
}

function clearAuth() {
  localStorage.removeItem("agri_token");
  localStorage.removeItem("agri_user");
}

function logout() {
  $.ajax({
    url: API_BASE + "/api/auth/logout",
    type: "POST",
    headers: { "X-Auth-Token": getAuthToken() },
    complete: function () {
      clearAuth();
      location.href = "login.html";
    },
  });
}

function roleLabel(role) {
  return { admin: "管理员", operator: "操作员", viewer: "访客" }[role] || role || "";
}

// 所有请求自动携带登录令牌，未登录时不带（接口会返回 401）
$.ajaxSetup({
  beforeSend: function (xhr) {
    const token = getAuthToken();
    if (token) xhr.setRequestHeader("X-Auth-Token", token);
  },
});

function fmtTime(ts) {
  if (!ts) return "--";
  const d = new Date(ts * 1000);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function lightStatus(light) {
  if (light === null || light === undefined) return "--";
  if (light === 0) return "夜间";
  if (light < 10000) return "较弱";
  if (light < 50000) return "适中";
  return "充足";
}

function fetchLatest() {
  $.ajax({
    url: API_BASE + "/api/sensors/latest",
    dataType: "json",
    timeout: 4000,
    success: function (data) {
      $("#connection-status").removeClass("offline").addClass("online");

      // 设备信息
      $("#top-device").text(data.device_id || "--");
      $("#top-update").text(fmtTime(data.timestamp));

      // 土壤墒情
      if (data.soil_moisture !== null && data.soil_moisture !== undefined) {
        $("#soil-value").text(data.soil_moisture);
      } else {
        $("#soil-value").text("--");
      }

      const card = $("#soil-card");
      card.removeClass("warning normal");
      if (data.decision === "start") {
        card.addClass("warning");
      } else {
        card.addClass("normal");
      }
      $("#soil-range").text((data.threshold_low ?? 30) + "% ~ " + (data.threshold_high ?? 70) + "%");

      // 温度
      $("#temp-value").text(data.temperature !== null && data.temperature !== undefined ? data.temperature : "--");
      // 湿度
      $("#hum-value").text(data.humidity !== null && data.humidity !== undefined ? data.humidity : "--");
      // 光照
      if (data.light !== null && data.light !== undefined) {
        $("#light-value").text(data.light.toLocaleString());
      } else {
        $("#light-value").text("--");
      }
      $("#light-status").text(lightStatus(data.light));

      // 灌溉状态
      $("#irrigation-status").text(data.decision_text || "--");
      const pill = $("#irrigation-pill");
      pill.removeClass("status-start status-stop status-hold");
      if (data.decision === "start") pill.addClass("status-start");
      else if (data.decision === "stop") pill.addClass("status-stop");
      else pill.addClass("status-hold");
    },
    error: function () {
      $("#connection-status").removeClass("online").addClass("offline");
      $("#irrigation-status").text("数据暂不可用");
    }
  });
}

function fetchStats() {
  $.get(API_BASE + "/api/stats/overview", function (s) {
    $("#stat-readings").text((s.reading_count || 0).toLocaleString());
    $("#stat-devices").text(s.device_count || 0);
    $("#stat-alerts").text(s.alert_count || 0);
    $("#stat-irrigation").text(s.irrigation_count || 0);
  });
}

// ---------- 执行器状态面板 ----------
const ACTUATOR_ICONS = {
  irrigation_valve: "bi-droplet",
  fertilizer_pump: "bi-eyedropper",
  fan: "bi-fan",
  shade_net: "bi-eyebrow",
};

function renderActuators(list) {
  const panel = $("#actuator-panel");
  if (!list || list.length === 0) {
    panel.html('<div class="col-12 text-center text-muted py-3">暂无执行器</div>');
    return;
  }
  panel.html(list.map((a) => {
    const on = a.status === "on";
    const icon = ACTUATOR_ICONS[a.name] || "bi-gear";
    return `<div class="col-6 col-md-3">
      <div class="sensor-card ${on ? 'border-start-success' : ''}" style="border-left-width:4px;border-left-style:solid;border-left-color:${on ? 'var(--agri-green)' : '#ccc'};">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <i class="bi ${icon}" style="font-size:1.3rem;color:${on ? 'var(--agri-green)' : '#999'};"></i>
            <div class="fw-bold mt-1">${a.label || a.name}</div>
            <small class="text-muted">${a.device_id || "--"}</small>
          </div>
          <div class="form-check form-switch">
            <input class="form-check-input actuator-toggle" type="checkbox"
              data-name="${a.name}" ${on ? "checked" : ""}
              style="width:2.2em;height:1.2em;">
          </div>
        </div>
        <div class="mt-2">
          <span class="badge ${on ? 'bg-success' : 'bg-secondary'}">${on ? "运行中" : "已关闭"}</span>
        </div>
      </div>
    </div>`;
  }).join(""));
}

function loadActuators() {
  $.get(API_BASE + "/api/actuators", renderActuators);
}

function toggleActuator(name, on) {
  $.ajax({
    url: API_BASE + "/api/actuators/" + encodeURIComponent(name) + "/control",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify({ status: on ? "on" : "off" }),
    success: loadActuators,
    error: function () { loadActuators(); },
  });
}

$(document).ready(function () {
  fetchLatest();
  fetchStats();
  loadActuators();
  setInterval(fetchLatest, 5000);
  setInterval(fetchStats, 30000);
  setInterval(loadActuators, 15000);

  $(document).on("change", ".actuator-toggle", function () {
    toggleActuator($(this).data("name"), $(this).is(":checked"));
  });
});
