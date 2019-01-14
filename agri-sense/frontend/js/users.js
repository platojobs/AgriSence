// AgriSense 用户管理：仅管理员可用
$(function () {
  let users = [];
  let pwdTargetId = null;

  function isAdmin() {
    const u = typeof getCurrentUser === "function" ? getCurrentUser() : null;
    return u && u.role === "admin" && getAuthToken();
  }

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function showPerm(text) {
    $("#perm-box").removeClass("d-none");
    $("#users-box").addClass("d-none");
    if (text) $("#perm-text").text(text);
  }

  function renderStats() {
    $("#cnt-all").text(users.length);
    $("#cnt-admin").text(users.filter(function (u) { return u.role === "admin"; }).length);
    $("#cnt-operator").text(users.filter(function (u) { return u.role === "operator"; }).length);
    $("#cnt-viewer").text(users.filter(function (u) { return u.role === "viewer"; }).length);
  }

  function renderTable() {
    const me = getCurrentUser() || {};
    if (!users.length) {
      $("#user-tbody").html('<tr><td colspan="7" class="text-center text-muted py-4">暂无用户</td></tr>');
      return;
    }

    const rows = users.map(function (u) {
      const self = u.username === me.username;
      const roleOpts = ["admin", "operator", "viewer"].map(function (r) {
        return '<option value="' + r + '"' + (u.role === r ? " selected" : "") + ">" + roleLabel(r) + "</option>";
      }).join("");

      return '<tr>' +
        "<td>" + u.id + "</td>" +
        "<td><b>" + escapeHtml(u.username) + "</b>" + (self ? ' <span class="badge bg-success" style="font-size:10px">本人</span>' : "") + "</td>" +
        "<td>" + escapeHtml(u.display_name || "--") + "</td>" +
        '<td><select class="form-select form-select-sm role-select" data-id="' + u.id + '">' + roleOpts + "</select></td>" +
        '<td><span class="' + (u.status === "active" ? "st-active" : "st-disabled") + '">' +
          (u.status === "active" ? "正常" : "已禁用") + "</span></td>" +
        '<td class="text-muted">' + escapeHtml(u.last_login || "从未登录") + "</td>" +
        '<td><div class="btn-group btn-group-sm">' +
          '<button class="btn btn-outline-secondary btn-pwd" data-id="' + u.id + '" data-name="' + escapeHtml(u.username) + '"><i class="bi bi-key"></i> 密码</button>' +
          '<button class="btn btn-outline-' + (u.status === "active" ? "warning" : "success") + ' btn-status" data-id="' + u.id +
            '" data-status="' + (u.status === "active" ? "disabled" : "active") + '">' +
            (u.status === "active" ? "禁用" : "启用") + "</button>" +
          '<button class="btn btn-outline-danger btn-del" data-id="' + u.id + '" data-name="' + escapeHtml(u.username) + '"><i class="bi bi-trash"></i></button>' +
        "</div></td></tr>";
    }).join("");

    $("#user-tbody").html(rows);
  }

  function loadUsers() {
    $.ajax({
      url: API_BASE + "/api/users",
      dataType: "json",
      timeout: 6000,
      success: function (list) {
        users = list;
        renderStats();
        renderTable();
        $("#users-box").removeClass("d-none");
        $("#perm-box").addClass("d-none");
      },
      error: function (xhr) {
        if (xhr.status === 401) {
          showPerm("请先使用管理员账号登录后再访问用户管理。");
        } else if (xhr.status === 403) {
          showPerm("当前账号不是管理员，无权访问用户管理。");
        } else {
          showPerm("无法连接后端服务，请确认 5001 端口已启动。");
        }
      },
    });
  }

  function openAddModal() {
    $("#add-username, #add-name, #add-password").val("");
    $("#add-role").val("viewer");
    $("#add-alert").addClass("d-none");
    new bootstrap.Modal(document.getElementById("add-modal")).show();
  }

  // ---------- 事件 ----------
  $("#btn-add-user").on("click", openAddModal);

  $("#add-submit").on("click", function () {
    const payload = {
      username: $("#add-username").val().trim(),
      display_name: $("#add-name").val().trim(),
      password: $("#add-password").val(),
      role: $("#add-role").val(),
    };
    $.ajax({
      url: API_BASE + "/api/users",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify(payload),
      dataType: "json",
      success: function () {
        bootstrap.Modal.getInstance(document.getElementById("add-modal")).hide();
        loadUsers();
      },
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        $("#add-alert").removeClass("d-none").text(res.message || "创建失败");
      },
    });
  });

  // 角色变更
  $(document).on("change", ".role-select", function () {
    const id = $(this).data("id");
    const role = $(this).val();
    $.ajax({
      url: API_BASE + "/api/users/" + id,
      method: "PUT",
      contentType: "application/json",
      data: JSON.stringify({ role: role }),
      success: loadUsers,
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        alert(res.message || "修改角色失败");
        loadUsers();
      },
    });
  });

  // 启用 / 禁用
  $(document).on("click", ".btn-status", function () {
    const id = $(this).data("id");
    const status = $(this).data("status");
    $.ajax({
      url: API_BASE + "/api/users/" + id,
      method: "PUT",
      contentType: "application/json",
      data: JSON.stringify({ status: status }),
      success: loadUsers,
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        alert(res.message || "操作失败");
      },
    });
  });

  // 重置密码
  $(document).on("click", ".btn-pwd", function () {
    pwdTargetId = $(this).data("id");
    $("#pwd-user").text($(this).data("name"));
    $("#pwd-value").val("");
    $("#pwd-alert").addClass("d-none");
    new bootstrap.Modal(document.getElementById("pwd-modal")).show();
  });

  $("#pwd-submit").on("click", function () {
    const password = $("#pwd-value").val();
    $.ajax({
      url: API_BASE + "/api/users/" + pwdTargetId,
      method: "PUT",
      contentType: "application/json",
      data: JSON.stringify({ password: password }),
      success: function () {
        bootstrap.Modal.getInstance(document.getElementById("pwd-modal")).hide();
        alert("密码已重置，请通知用户使用新密码登录。");
      },
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        $("#pwd-alert").removeClass("d-none").text(res.message || "重置失败");
      },
    });
  });

  // 删除
  $(document).on("click", ".btn-del", function () {
    const id = $(this).data("id");
    const name = $(this).data("name");
    if (!confirm("确定删除用户「" + name + "」吗？此操作不可恢复。")) return;
    $.ajax({
      url: API_BASE + "/api/users/" + id,
      method: "DELETE",
      success: loadUsers,
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        alert(res.message || "删除失败");
      },
    });
  });

  if (!isAdmin()) {
    showPerm(getAuthToken()
      ? "当前账号不是管理员，无权访问用户管理。"
      : "用户管理仅对管理员开放，请先登录。");
    return;
  }
  loadUsers();
});
