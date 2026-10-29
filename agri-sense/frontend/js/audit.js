// AgriSense 审计日志：仅管理员可用
$(function () {

  // 操作类型 -> 中文标签 + 配色分组
  const ACTION_META = {
    change_password:      ["修改密码", "auth"],
    logout_others:        ["退出其他设备", "auth"],
    user_create:          ["新增用户", "user"],
    user_update:          ["修改用户", "user"],
    user_delete:          ["删除用户", "user"],
    device_upsert:        ["保存设备", "device"],
    device_delete:        ["删除设备", "device"],
    irrigation_manual:    ["手动灌溉", "irr"],
    thresholds_update:    ["修改阈值", "irr"],
    schedule_create:      ["新增调度", "irr"],
    schedule_update:      ["修改调度", "irr"],
    schedule_delete:      ["删除调度", "irr"],
    actuator_control:     ["执行器控制", "device"],
    alert_handle:         ["处理告警", "alert"],
    alert_rule_save:      ["保存告警规则", "alert"],
    alert_rule_delete:    ["删除告警规则", "alert"],
    farm_log_create:      ["新增农事日志", "biz"],
    farm_log_delete:      ["删除农事日志", "biz"],
    batch_create:         ["新增溯源批次", "biz"],
    batch_quality:        ["批次质检", "biz"],
    cms_knowledge_create: ["新增知识文章", "cms"],
    cms_knowledge_update: ["更新知识文章", "cms"],
    cms_knowledge_delete: ["删除知识文章", "cms"],
    cms_news_create:      ["新增新闻", "cms"],
    cms_news_update:      ["更新新闻", "cms"],
    cms_news_delete:      ["删除新闻", "cms"],
    cms_news_top:         ["新闻置顶切换", "cms"],
    cms_feedback_mark:    ["处理留言", "cms"],
    cms_feedback_delete:  ["删除留言", "cms"],
    cms_site_save:        ["保存站点内容", "cms"],
    cms_site_delete:      ["删除站点内容", "cms"],
  };

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function showPerm(text) {
    $("#perm-box").removeClass("d-none");
    $("#audit-box").addClass("d-none");
    if (text) $("#perm-text").text(text);
  }

  function actionBadge(action) {
    const meta = ACTION_META[action] || [action, "biz"];
    return '<span class="act-pill act-' + meta[1] + '">' + escapeHtml(meta[0]) + "</span>";
  }

  function fillActionFilter() {
    const opts = Object.keys(ACTION_META).map(function (a) {
      return '<option value="' + a + '">' + ACTION_META[a][0] + "</option>";
    }).join("");
    $("#f-action").append(opts);
  }

  function renderStats(stats) {
    $("#cnt-total").text(stats.total || 0);
    $("#cnt-today").text(stats.today || 0);
    $("#cnt-users").text(stats.users || 0);
    $("#cnt-actions").text(stats.actions || 0);
  }

  function renderTable(logs) {
    $("#result-count").text("共 " + logs.length + " 条");
    if (!logs.length) {
      $("#audit-tbody").html('<tr><td colspan="6" class="text-center text-muted py-4">暂无审计记录</td></tr>');
      return;
    }
    const rows = logs.map(function (log) {
      return "<tr>" +
        '<td class="text-muted">' + escapeHtml(log.created_at) + "</td>" +
        "<td><b>" + escapeHtml(log.username) + "</b></td>" +
        "<td>" + actionBadge(log.action) + "</td>" +
        "<td>" + escapeHtml(log.target || "--") + "</td>" +
        '<td><span class="detail-text text-muted" title="' + escapeHtml(log.detail) + '">' +
          escapeHtml(log.detail || "--") + "</span></td>" +
        '<td class="text-muted">' + escapeHtml(log.ip || "--") + "</td>" +
        "</tr>";
    }).join("");
    $("#audit-tbody").html(rows);
  }

  function loadLogs() {
    const params = {};
    const action = $("#f-action").val();
    const username = $("#f-username").val().trim();
    const keyword = $("#f-keyword").val().trim();
    if (action) params.action = action;
    if (username) params.username = username;
    if (keyword) params.keyword = keyword;

    $.ajax({
      url: API_BASE + "/api/audit_logs",
      data: params,
      dataType: "json",
      timeout: 6000,
      success: function (res) {
        renderStats(res.stats || {});
        renderTable(res.logs || []);
        $("#audit-box").removeClass("d-none");
        $("#perm-box").addClass("d-none");
      },
      error: function (xhr) {
        if (xhr.status === 401) {
          showPerm("请先使用管理员账号登录后再访问审计日志。");
        } else if (xhr.status === 403) {
          showPerm("当前账号不是管理员，无权访问审计日志。");
        } else {
          showPerm("无法连接后端服务，请确认 5001 端口已启动。");
        }
      },
    });
  }

  $("#btn-search").on("click", loadLogs);
  $("#btn-reset").on("click", function () {
    $("#f-action").val("");
    $("#f-username, #f-keyword").val("");
    loadLogs();
  });
  $("#f-keyword, #f-username").on("keydown", function (e) {
    if (e.key === "Enter") loadLogs();
  });

  const me = typeof getCurrentUser === "function" ? getCurrentUser() : null;
  if (!getAuthToken() || !me || me.role !== "admin") {
    showPerm(getAuthToken()
      ? "当前账号不是管理员，无权访问审计日志。"
      : "审计日志仅对管理员开放，请先登录。");
    return;
  }
  fillActionFilter();
  loadLogs();
});
