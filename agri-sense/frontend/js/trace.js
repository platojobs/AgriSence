// AgriSense 溯源管理页：批次列表 + 溯源时间线 + 农事日志 + 二维码
// 依赖：jQuery、dashboard.js（API_BASE）

let batchModal = null;
let logModal = null;
let currentBatchNo = null;

const QUALITY_MAP = {
  pending:     { label: "待质检", cls: "q-pending" },
  qualified:   { label: "合格",   cls: "q-qualified" },
  unqualified: { label: "不合格", cls: "q-unqualified" },
};

const LOG_TYPE_ICON = {
  "施肥": "bi-bag", "打药": "bi-moisture", "除草": "bi-scissors",
  "灌溉": "bi-water", "采收": "bi-basket", "巡检": "bi-eyeglasses", "其他": "bi-journal",
};

function qualityBadge(status) {
  const q = QUALITY_MAP[status] || QUALITY_MAP.pending;
  return `<span class="quality-pill ${q.cls}">${q.label}</span>`;
}

// ---------- 批次 ----------
function renderBatches(batches) {
  const tbody = $("#batches-table");
  if (!batches || batches.length === 0) {
    tbody.html('<tr><td colspan="6" class="text-center text-muted py-3">暂无批次</td></tr>');
    return;
  }
  tbody.html(batches.map((b) => `
    <tr>
      <td><code>${b.batch_no}</code></td>
      <td>${b.crop_name || "--"}</td>
      <td>${b.sowing_date || "--"}</td>
      <td>${b.harvest_date || "--"}</td>
      <td>${qualityBadge(b.quality_status)}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-primary btn-view-batch" data-no="${b.batch_no}">
          <i class="bi bi-eye"></i> 溯源
        </button>
      </td>
    </tr>
  `).join(""));
}

function loadBatches() {
  $.get(API_BASE + "/api/traceability/batches", renderBatches);
}

function viewBatch(batchNo) {
  currentBatchNo = batchNo;
  $("#detail-batch-no").text("— " + batchNo);
  $.get(API_BASE + "/api/traceability/batches/" + encodeURIComponent(batchNo), function (data) {
    const batch = data.batch || {};
    const timeline = data.timeline || [];

    $("#timeline-empty").addClass("d-none");
    $("#timeline-box").removeClass("d-none").html(timeline.length
      ? timeline.map((t) => `
        <div class="tl-item ${t.type}">
          <div class="tl-date">${t.date || "--"}</div>
          <div class="tl-label">
            <i class="bi ${LOG_TYPE_ICON[t.label] || 'bi-circle'}"></i> ${t.label || "--"}
          </div>
          <div class="tl-desc">${t.desc || ""}</div>
        </div>
      `).join("")
      : '<div class="text-muted">暂无时间线数据</div>');

    // 质检操作
    $("#detail-quality-actions").removeClass("d-none");

    // 二维码
    $("#qr-empty").addClass("d-none");
    $("#qr-box-wrap").removeClass("d-none");
    const traceUrl = location.origin + location.pathname + "?batch=" + encodeURIComponent(batchNo);
    $("#qr-img").attr("src", "https://api.qrserver.com/v1/create-qr-code/?data=" + encodeURIComponent(traceUrl) + "&size=150x150");
    $("#qr-caption").text("扫码查看 " + batchNo + " 溯源详情");
    $("#qr-batch-input").val(batchNo);
  });
}

function saveBatch() {
  const payload = {
    batch_no: $("#f-batch-no").val().trim(),
    crop_name: $("#f-crop-name").val().trim(),
    sowing_date: $("#f-sowing-date").val(),
    harvest_date: $("#f-harvest-date").val() || null,
    quality_status: $("#f-quality").val(),
    notes: $("#f-notes").val(),
  };
  if (!payload.batch_no) { alert("批次号不能为空"); return; }
  $.ajax({
    url: API_BASE + "/api/traceability/batches",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function () {
      batchModal.hide();
      $("#batch-form")[0].reset();
      loadBatches();
    },
    error: function () { alert("保存失败"); },
  });
}

function setQuality(status) {
  if (!currentBatchNo) return;
  $.ajax({
    url: API_BASE + "/api/traceability/batches/" + encodeURIComponent(currentBatchNo) + "/quality",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify({ quality_status: status }),
    success: function () {
      loadBatches();
      viewBatch(currentBatchNo);
    },
    error: function () { alert("更新失败"); },
  });
}

// ---------- 农事日志 ----------
function renderLogs(logs) {
  const tbody = $("#logs-table");
  if (!logs || logs.length === 0) {
    tbody.html('<tr><td colspan="5" class="text-center text-muted py-3">暂无农事日志</td></tr>');
    return;
  }
  tbody.html(logs.map((l) => `
    <tr>
      <td class="text-nowrap">${l.created_at || "--"}</td>
      <td><span class="badge bg-info text-dark"><i class="bi ${LOG_TYPE_ICON[l.type] || 'bi-journal'}"></i> ${l.type || "--"}</span></td>
      <td>${l.description || "--"}</td>
      <td>${l.operator || "--"}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-danger btn-del-log" data-id="${l.id}">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>
  `).join(""));
}

function loadLogs() {
  $.get(API_BASE + "/api/farm-logs", renderLogs);
}

function saveLog() {
  const payload = {
    type: $("#f-log-type").val(),
    description: $("#f-log-desc").val().trim(),
    operator: $("#f-log-operator").val().trim() || "系统",
  };
  if (!payload.description) { alert("请填写描述"); return; }
  $.ajax({
    url: API_BASE + "/api/farm-logs",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function () {
      logModal.hide();
      $("#log-form")[0].reset();
      $("#f-log-operator").val("系统");
      loadLogs();
      if (currentBatchNo) viewBatch(currentBatchNo);
    },
    error: function () { alert("保存失败"); },
  });
}

function deleteLog(id) {
  if (!confirm("确认删除该农事日志？")) return;
  $.ajax({
    url: API_BASE + "/api/farm-logs/" + id,
    method: "DELETE",
    success: function () {
      loadLogs();
      if (currentBatchNo) viewBatch(currentBatchNo);
    },
    error: function () { alert("删除失败"); },
  });
}

// ---------- 二维码 ----------
function genQr() {
  const no = $("#qr-batch-input").val().trim();
  if (!no) { alert("请输入批次号"); return; }
  const traceUrl = location.origin + location.pathname + "?batch=" + encodeURIComponent(no);
  $("#qr-img").attr("src", "https://api.qrserver.com/v1/create-qr-code/?data=" + encodeURIComponent(traceUrl) + "&size=150x150");
  $("#qr-caption").text("扫码查看 " + no + " 溯源详情");
}

// ---------- 初始化 ----------
$(document).ready(function () {
  batchModal = new bootstrap.Modal("#batch-modal");
  logModal = new bootstrap.Modal("#log-modal");
  loadBatches();
  loadLogs();

  $("#btn-add-batch").on("click", () => batchModal.show());
  $("#btn-save-batch").on("click", saveBatch);
  $("#btn-add-log").on("click", () => logModal.show());
  $("#btn-save-log").on("click", saveLog);
  $("#btn-gen-qr").on("click", genQr);

  $(document).on("click", ".btn-view-batch", function () {
    viewBatch($(this).data("no"));
  });
  $(document).on("click", ".btn-del-log", function () {
    deleteLog(parseInt($(this).data("id"), 10));
  });
  $(document).on("click", ".btn-quality", function () {
    setQuality($(this).data("status"));
  });

  // URL 带 batch 参数时自动打开
  const params = new URLSearchParams(location.search);
  const preBatch = params.get("batch");
  if (preBatch) {
    setTimeout(() => viewBatch(preBatch), 300);
  }
});
