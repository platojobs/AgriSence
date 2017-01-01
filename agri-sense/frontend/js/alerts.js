// AgriSense 告警中心页：告警列表 + 处理 + 告警规则管理
// 依赖：jQuery、dashboard.js（API_BASE）

let ruleModal = null;
let editingRuleId = null;
let currentAlertStatus = "";

const LEVEL_MAP = {
  info:     { label: "提示", cls: "bg-info" },
  warning:  { label: "警告", cls: "bg-warning text-dark" },
  critical: { label: "严重", cls: "bg-danger" },
};

const METRIC_LABELS = {
  soil_moisture: "土壤墒情", temperature: "温度", humidity: "湿度", light: "光照",
};
const CONDITION_LABELS = { lt: "<", gt: ">", "<": "<", ">": ">" };

function levelBadge(level) {
  const l = LEVEL_MAP[level] || LEVEL_MAP.warning;
  return `<span class="badge ${l.cls}">${l.label}</span>`;
}

function statusBadge(status) {
  return status === "handled"
    ? '<span class="badge bg-success">已处理</span>'
    : '<span class="badge bg-danger">待处理</span>';
}

// ---------- 告警 ----------
function renderAlerts(alerts) {
  const tbody = $("#alerts-table");
  if (!alerts || alerts.length === 0) {
    tbody.html('<tr><td colspan="7" class="text-center text-muted py-3">暂无告警</td></tr>');
    return;
  }
  tbody.html(alerts.map((a) => `
    <tr>
      <td class="text-nowrap">${a.created_at || "--"}</td>
      <td>${levelBadge(a.level)}</td>
      <td>${a.type || "--"}</td>
      <td><code>${a.device_id || "--"}</code></td>
      <td>${a.message || "--"}</td>
      <td>${statusBadge(a.status)}</td>
      <td class="text-end">
        ${a.status === "pending"
          ? `<button class="btn btn-sm btn-success btn-handle" data-id="${a.id}"><i class="bi bi-check2"></i> 处理</button>`
          : `<small class="text-muted">${a.handled_at || ""}</small>`}
      </td>
    </tr>
  `).join(""));
}

function loadAlerts() {
  $.get(API_BASE + "/api/alerts", { status: currentAlertStatus }, function (data) {
    renderAlerts(data);
    // 统计（全量）
    $.get(API_BASE + "/api/alerts", function (all) {
      $("#cnt-pending").text(all.filter((a) => a.status === "pending").length);
      $("#cnt-handled").text(all.filter((a) => a.status === "handled").length);
      $("#cnt-warning").text(all.filter((a) => a.level === "warning").length);
      $("#cnt-critical").text(all.filter((a) => a.level === "critical").length);
    });
  });
}

function handleAlert(id) {
  $.ajax({
    url: API_BASE + "/api/alerts/" + id + "/handle",
    method: "POST",
    success: loadAlerts,
    error: function () { alert("操作失败"); },
  });
}

// ---------- 规则 ----------
function renderRules(rules) {
  const tbody = $("#rules-table");
  if (!rules || rules.length === 0) {
    tbody.html('<tr><td colspan="6" class="text-center text-muted py-3">暂无规则</td></tr>');
    return;
  }
  tbody.html(rules.map((r) => `
    <tr>
      <td>${METRIC_LABELS[r.metric] || r.metric}</td>
      <td>${CONDITION_LABELS[r.condition] || r.condition}</td>
      <td>${r.threshold}</td>
      <td>${levelBadge(r.level)}</td>
      <td>${r.enabled ? '<i class="bi bi-toggle-on text-success"></i>' : '<i class="bi bi-toggle-off text-muted"></i>'}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-primary btn-rule-edit" data-id="${r.id}"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger btn-rule-del" data-id="${r.id}"><i class="bi bi-trash"></i></button>
      </td>
    </tr>
  `).join(""));
}

function loadRules() {
  $.get(API_BASE + "/api/alert-rules", renderRules);
}

function openRuleModal(r) {
  editingRuleId = r ? r.id : null;
  $("#rule-modal-title").html(r ? '<i class="bi bi-pencil"></i> 编辑规则' : '<i class="bi bi-plus-lg"></i> 新增规则');
  $("#f-rule-metric").val(r?.metric || "soil_moisture");
  $("#f-rule-condition").val(r?.condition || "lt");
  $("#f-rule-threshold").val(r?.threshold ?? 30);
  $("#f-rule-level").val(r?.level || "warning");
  $("#f-rule-enabled").prop("checked", r ? !!r.enabled : true);
  ruleModal.show();
}

function saveRule() {
  const payload = {
    metric: $("#f-rule-metric").val(),
    condition: $("#f-rule-condition").val(),
    threshold: parseFloat($("#f-rule-threshold").val()) || 0,
    level: $("#f-rule-level").val(),
    enabled: $("#f-rule-enabled").is(":checked") ? 1 : 0,
  };
  if (editingRuleId) payload.id = editingRuleId;
  $.ajax({
    url: API_BASE + "/api/alert-rules",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function () {
      ruleModal.hide();
      loadRules();
    },
    error: function () { alert("保存失败"); },
  });
}

function deleteRule(id) {
  if (!confirm("确认删除该告警规则？")) return;
  $.ajax({
    url: API_BASE + "/api/alert-rules/" + id,
    method: "DELETE",
    success: loadRules,
    error: function () { alert("删除失败"); },
  });
}

// ---------- 初始化 ----------
$(document).ready(function () {
  ruleModal = new bootstrap.Modal("#rule-modal");
  loadAlerts();
  loadRules();
  setInterval(loadAlerts, 15000);

  $(".alert-filter").on("click", function () {
    $(".alert-filter").removeClass("active");
    $(this).addClass("active");
    currentAlertStatus = $(this).data("status") || "";
    loadAlerts();
  });

  $("#btn-add-rule").on("click", () => openRuleModal(null));
  $("#btn-save-rule").on("click", saveRule);

  $(document).on("click", ".btn-handle", function () {
    handleAlert(parseInt($(this).data("id"), 10));
  });
  $(document).on("click", ".btn-rule-edit", function () {
    const id = parseInt($(this).data("id"), 10);
    $.get(API_BASE + "/api/alert-rules", function (list) {
      const r = list.find((x) => x.id === id);
      if (r) openRuleModal(r);
    });
  });
  $(document).on("click", ".btn-rule-del", function () {
    deleteRule(parseInt($(this).data("id"), 10));
  });
});
