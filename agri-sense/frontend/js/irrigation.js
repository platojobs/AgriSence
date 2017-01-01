// AgriSense 灌溉管理页：调度CRUD + 手动控制 + 日志统计
// 依赖：jQuery、dashboard.js（API_BASE、fmtTime）

let scheduleModal = null;
let editingScheduleId = null;

// ---------- 手动控制 ----------
function manualControl(action) {
  $.ajax({
    url: API_BASE + "/api/irrigation/manual",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify({ action: action }),
    success: function () {
      refreshAll();
    },
    error: function (xhr) {
      alert("操作失败：" + (xhr.responseJSON?.message || "未知错误"));
    },
  });
}

function loadStatus() {
  $.get(API_BASE + "/api/irrigation/status", function (s) {
    const pill = $("#irr-status-pill");
    pill.removeClass("status-start status-stop status-hold");
    if (s.decision === "start") pill.addClass("status-start");
    else if (s.decision === "stop") pill.addClass("status-stop");
    else pill.addClass("status-hold");
    $("#irr-status-text").text(s.decision_text || "--");
  });
}

// ---------- 统计 ----------
function loadStats() {
  $.get(API_BASE + "/api/irrigation/logs", function (logs) {
    let start = 0, stop = 0;
    (logs || []).forEach((l) => {
      if (l.action === "start") start++;
      else if (l.action === "stop") stop++;
    });
    $("#stat-start").text(start);
    $("#stat-stop").text(stop);
    $("#stat-total").text(start + stop);
  });
}

// ---------- 调度 ----------
function renderSchedules(list) {
  const tbody = $("#schedule-table");
  if (!list || list.length === 0) {
    tbody.html('<tr><td colspan="5" class="text-center text-muted py-3">暂无调度</td></tr>');
    return;
  }
  tbody.html(list.map((s) => {
    const enabled = s.enabled ? 1 : 0;
    const badge = enabled
      ? '<span class="badge bg-success">已启用</span>'
      : '<span class="badge bg-secondary">已停用</span>';
    return `<tr>
      <td>${s.name || "--"}</td>
      <td><i class="bi bi-clock"></i> ${s.start_time}</td>
      <td>${s.duration} 分钟</td>
      <td>${badge}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-primary btn-sch-edit" data-id="${s.id}">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger btn-sch-del" data-id="${s.id}">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`;
  }).join(""));
}

function loadSchedules() {
  $.get(API_BASE + "/api/irrigation/schedules", renderSchedules);
}

function openScheduleModal(s) {
  editingScheduleId = s ? s.id : null;
  $("#schedule-modal-title").html(s ? '<i class="bi bi-pencil"></i> 编辑调度' : '<i class="bi bi-plus-lg"></i> 新增调度');
  $("#f-sch-name").val(s?.name || "");
  $("#f-sch-start").val(s?.start_time || "06:00");
  $("#f-sch-duration").val(s?.duration || 30);
  $("#f-sch-enabled").prop("checked", s ? !!s.enabled : true);
  scheduleModal.show();
}

function saveSchedule() {
  const payload = {
    name: $("#f-sch-name").val().trim() || "定时灌溉",
    start_time: $("#f-sch-start").val() || "06:00",
    duration: parseInt($("#f-sch-duration").val(), 10) || 30,
    enabled: $("#f-sch-enabled").is(":checked") ? 1 : 0,
  };
  const url = editingScheduleId
    ? API_BASE + "/api/irrigation/schedules/" + editingScheduleId
    : API_BASE + "/api/irrigation/schedules";
  const method = editingScheduleId ? "PUT" : "POST";
  $.ajax({
    url: url,
    method: method,
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function () {
      scheduleModal.hide();
      loadSchedules();
    },
    error: function () { alert("保存失败"); },
  });
}

function deleteSchedule(id) {
  if (!confirm("确认删除该调度？")) return;
  $.ajax({
    url: API_BASE + "/api/irrigation/schedules/" + id,
    method: "DELETE",
    success: loadSchedules,
    error: function () { alert("删除失败"); },
  });
}

// ---------- 日志 ----------
function loadLogs() {
  $.get(API_BASE + "/api/irrigation/logs", function (logs) {
    const tbody = $("#log-body");
    if (!logs || logs.length === 0) {
      tbody.html('<tr><td colspan="3" class="text-center text-muted py-3">暂无日志</td></tr>');
      return;
    }
    tbody.html(logs.map((l) => {
      const badge = l.action === "start"
        ? '<span class="badge bg-success">开启</span>'
        : l.action === "stop"
        ? '<span class="badge bg-secondary">停止</span>'
        : `<span class="badge bg-light text-dark">${l.action}</span>`;
      return `<tr>
        <td class="text-nowrap">${l.created_at}</td>
        <td>${badge}</td>
        <td>${l.reason || "--"}</td>
      </tr>`;
    }).join(""));
  });
}

function refreshAll() {
  loadStatus();
  loadStats();
  loadSchedules();
  loadLogs();
}

// ---------- 初始化 ----------
$(document).ready(function () {
  scheduleModal = new bootstrap.Modal("#schedule-modal");
  refreshAll();
  setInterval(refreshAll, 15000);

  $("#btn-irr-start").on("click", () => manualControl("start"));
  $("#btn-irr-stop").on("click", () => manualControl("stop"));
  $("#btn-add-schedule").on("click", () => openScheduleModal(null));
  $("#btn-save-schedule").on("click", saveSchedule);

  $(document).on("click", ".btn-sch-edit", function () {
    const id = parseInt($(this).data("id"), 10);
    $.get(API_BASE + "/api/irrigation/schedules", function (list) {
      const s = list.find((x) => x.id === id);
      if (s) openScheduleModal(s);
    });
  });
  $(document).on("click", ".btn-sch-del", function () {
    deleteSchedule(parseInt($(this).data("id"), 10));
  });
});
