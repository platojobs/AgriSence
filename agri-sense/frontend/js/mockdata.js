// AgriSense 模拟数据页：生成 / 预览 / 清空用于演示的历史读数
// 依赖：jQuery、dashboard.js（API_BASE / getCurrentUser）

function fmtTs(ts) {
  if (!ts) return "--";
  if (typeof ts === "number") {
    const d = new Date(ts * 1000);
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  return String(ts).replace("T", " ").slice(0, 16);
}

function isAdmin() {
  return typeof getCurrentUser === "function"
    && (getCurrentUser() || {}).role === "admin";
}

function loadStats() {
  $.get(API_BASE + "/api/mock/stats", function (d) {
    $("#st-total").text(d.total ?? 0);
    $("#st-mock").text(d.mock ?? 0);
    $("#st-from").text(fmtTs(d.earliest));
    $("#st-to").text(fmtTs(d.latest));
  });
}

function loadDevices() {
  $.get(API_BASE + "/api/devices", function (list) {
    const sel = $("#f-device");
    sel.html((list || []).map((dev) =>
      `<option value="${dev.device_id}">${dev.name || dev.device_id}（${dev.device_id}）</option>`
    ).join("") || '<option value="esp32_001">esp32_001</option>');
  });
}

function updatePreview() {
  const days = $("#f-days").val();
  const interval = $("#f-interval").val();
  $.get(API_BASE + "/api/mock/preview", { days: days, interval: interval }, function (d) {
    $("#preview-text").text(
      `预计生成 ${d.rows} 条记录，时间范围 ${fmtTs(d.from)} ~ ${fmtTs(d.to)}`
    );
  }).fail(function (xhr) {
    $("#preview-text").text((xhr.responseJSON && xhr.responseJSON.message) || "参数无效");
  });
}

function generate() {
  const payload = {
    days: parseInt($("#f-days").val(), 10),
    interval: parseInt($("#f-interval").val(), 10),
    device_id: $("#f-device").val(),
  };
  if (!confirm(`确认生成 ${payload.days} 天、${payload.interval} 分钟间隔的模拟数据？`)) return;
  const btn = $("#btn-generate").prop("disabled", true);
  $.ajax({
    url: API_BASE + "/api/mock/generate",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function (res) {
      alert(`已生成 ${res.inserted} 条模拟读数（设备 ${res.device_id}）`);
      loadStats();
    },
    error: function (xhr) {
      alert((xhr.responseJSON && xhr.responseJSON.message) || "生成失败");
    },
    complete: function () { btn.prop("disabled", false); },
  });
}

function clearMock() {
  if (!confirm("确认清空全部模拟数据？真实传感器读数不会被删除。")) return;
  $.ajax({
    url: API_BASE + "/api/mock/clear",
    method: "POST",
    success: function (res) {
      alert(`已清空 ${res.removed} 条模拟读数`);
      loadStats();
    },
    error: function (xhr) {
      alert((xhr.responseJSON && xhr.responseJSON.message) || "清空失败");
    },
  });
}

$(document).ready(function () {
  loadStats();
  loadDevices();
  updatePreview();

  if (!isAdmin()) {
    $("#admin-tip").show();
    $("#btn-generate, #btn-clear").prop("disabled", true);
  }

  $("#f-days, #f-interval").on("change", updatePreview);
  $("#btn-generate").on("click", generate);
  $("#btn-clear").on("click", clearMock);
});
