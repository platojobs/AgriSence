// AgriSense 设备管理页：设备 CRUD
// 依赖：jQuery、dashboard.js（API_BASE、fmtTime）

let deviceModal = null;
let editingId = null;

const STATUS_MAP = {
  online:      { label: "在线",   cls: "bg-success" },
  offline:     { label: "离线",   cls: "bg-secondary" },
  maintenance: { label: "维护中", cls: "bg-warning text-dark" },
};

function statusBadge(status) {
  const s = STATUS_MAP[status] || STATUS_MAP.offline;
  return `<span class="badge ${s.cls}">${s.label}</span>`;
}

function renderDevices(devices) {
  const tbody = $("#devices-table");
  if (!devices || devices.length === 0) {
    tbody.html('<tr><td colspan="6" class="text-center text-muted py-3">暂无设备</td></tr>');
    return;
  }
  tbody.html(devices.map((d) => {
    const lastSeen = d.last_seen ? fmtTime(d.last_seen) : "从未";
    return `<tr>
      <td><i class="bi bi-hdd-network me-1"></i>${d.name || d.device_id}</td>
      <td><code>${d.device_id}</code></td>
      <td>${d.location || "--"}</td>
      <td>${statusBadge(d.status)}</td>
      <td class="text-nowrap">${lastSeen}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-primary btn-edit" data-id="${d.device_id}">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger btn-delete" data-id="${d.device_id}">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`;
  }).join(""));
}

function loadDevices() {
  $.get(API_BASE + "/api/devices", function (data) {
    renderDevices(data);
  });
}

function openAddModal() {
  editingId = null;
  $("#device-modal-title").html('<i class="bi bi-plus-lg"></i> 新增设备');
  $("#device-form")[0].reset();
  $("#f-device-code").prop("disabled", false);
  deviceModal.show();
}

function openEditModal(device) {
  editingId = device.device_id;
  $("#device-modal-title").html('<i class="bi bi-pencil"></i> 编辑设备');
  $("#f-device-code").val(device.device_id).prop("disabled", true);
  $("#f-name").val(device.name || "");
  $("#f-location").val(device.location || "");
  $("#f-status").val(device.status || "offline");
  deviceModal.show();
}

function saveDevice() {
  const code = $("#f-device-code").val().trim();
  if (!code) { alert("设备编号不能为空"); return; }
  const payload = {
    device_id: code,
    name: $("#f-name").val().trim() || code,
    location: $("#f-location").val().trim(),
    status: $("#f-status").val(),
  };
  $.ajax({
    url: API_BASE + "/api/devices",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function () {
      deviceModal.hide();
      loadDevices();
    },
    error: function (xhr) {
      alert("保存失败：" + (xhr.responseJSON?.message || "未知错误"));
    },
  });
}

function deleteDevice(id) {
  if (!confirm(`确认删除设备 ${id} 吗？`)) return;
  $.ajax({
    url: API_BASE + "/api/devices/" + encodeURIComponent(id),
    method: "DELETE",
    success: loadDevices,
    error: function () { alert("删除失败"); },
  });
}

$(document).ready(function () {
  deviceModal = new bootstrap.Modal("#device-modal");

  loadDevices();
  setInterval(loadDevices, 30000);

  $("#btn-add-device").on("click", openAddModal);
  $("#btn-save-device").on("click", saveDevice);

  $(document).on("click", ".btn-edit", function () {
    const id = $(this).data("id");
    $.get(API_BASE + "/api/devices", function (list) {
      const d = list.find((x) => x.device_id === id);
      if (d) openEditModal(d);
    });
  });

  $(document).on("click", ".btn-delete", function () {
    deleteDevice($(this).data("id"));
  });
});
