// AgriSense 个人中心：个人信息 / 修改密码 / 登录历史 / 会话管理
$(function () {

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function showPerm() {
    $("#perm-box").removeClass("d-none");
    $("#profile-box").addClass("d-none");
  }

  // ---------- 个人信息 ----------
  function loadProfile() {
    $.ajax({
      url: API_BASE + "/api/auth/me",
      dataType: "json",
      timeout: 6000,
      success: function (res) {
        const u = res.user || {};
        $("#p-name").text(u.display_name || u.username || "--");
        $("#p-username").text(u.username || "--");
        $("#p-username2").text(u.username || "--");
        $("#p-role").text(u.role_label || u.role || "--")
          .removeClass("role-admin role-operator role-viewer")
          .addClass("role-" + (u.role || "viewer"));
        $("#p-lastlogin").text(u.last_login || "首次登录");
        $("#p-created").text(u.created_at || "--");
        $("#p-status").text(u.status === "active" ? "正常" : "已禁用");
        $("#profile-box").removeClass("d-none");
        $("#perm-box").addClass("d-none");
      },
      error: function () {
        showPerm();
      },
    });
  }

  // ---------- 登录历史 ----------
  function renderLogs(logs) {
    if (!logs.length) {
      $("#log-tbody").html('<tr><td colspan="4" class="text-center text-muted py-4">暂无登录记录</td></tr>');
      return;
    }
    const rows = logs.map(function (log) {
      const badge = log.success
        ? '<span class="log-ok">成功</span>'
        : '<span class="log-fail">失败</span>';
      return "<tr>" +
        "<td>" + escapeHtml(log.created_at) + "</td>" +
        "<td>" + escapeHtml(log.ip || "--") + "</td>" +
        '<td><span class="ua-text text-muted" title="' + escapeHtml(log.user_agent) + '">' +
          escapeHtml(log.user_agent || "--") + "</span></td>" +
        "<td>" + badge + "</td>" +
        "</tr>";
    }).join("");
    $("#log-tbody").html(rows);
  }

  function loadLogs() {
    $.ajax({
      url: API_BASE + "/api/auth/login_history",
      dataType: "json",
      timeout: 6000,
      success: function (res) {
        renderLogs(res.logs || []);
      },
      error: function () {
        $("#log-tbody").html('<tr><td colspan="4" class="text-center text-muted py-4">加载失败</td></tr>');
      },
    });
  }

  // ---------- 修改密码 ----------
  function pwdMsg(text, ok) {
    $("#pwd-alert").toggleClass("d-none", !!ok || !text).text(ok ? "" : text);
    $("#pwd-ok").toggleClass("d-none", !ok).text(ok ? text : "");
  }

  $("#pwd-submit").on("click", function () {
    const oldPwd = $("#pwd-old").val();
    const newPwd = $("#pwd-new").val();
    const newPwd2 = $("#pwd-new2").val();

    if (!oldPwd) { pwdMsg("请输入原密码"); return; }
    if (newPwd.length < 6) { pwdMsg("新密码至少 6 个字符"); return; }
    if (newPwd !== newPwd2) { pwdMsg("两次输入的新密码不一致"); return; }

    $.ajax({
      url: API_BASE + "/api/auth/change_password",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
      dataType: "json",
      success: function () {
        pwdMsg("密码修改成功", true);
        $("#pwd-old, #pwd-new, #pwd-new2").val("");
      },
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        pwdMsg(res.message || "修改失败，请稍后重试");
      },
    });
  });

  // ---------- 退出其他设备 ----------
  $("#btn-logout-others").on("click", function () {
    if (!confirm("确定退出其他所有设备上的登录会话吗？当前浏览器不受影响。")) return;
    $.ajax({
      url: API_BASE + "/api/auth/logout_others",
      method: "POST",
      dataType: "json",
      success: function (res) {
        alert(res.removed > 0
          ? "已退出 " + res.removed + " 个其他会话。"
          : "没有其他在线会话。");
      },
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        alert(res.message || "操作失败");
      },
    });
  });

  if (!getAuthToken()) {
    showPerm();
    return;
  }
  loadProfile();
  loadLogs();
});
