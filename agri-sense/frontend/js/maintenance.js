// AgriSense 数据维护：表统计 + 保留策略 + 手动/自动清理 + 维护日志（仅管理员）
$(function () {

  const TABLE_LABELS = {
    sensor_readings: "传感器读数",
    alerts: "告警记录",
    notifications: "站内通知",
    login_logs: "登录日志",
    irrigation_logs: "灌溉日志",
  };
  const ACTION_LABELS = { cleanup: "数据清理", vacuum: "VACUUM 压缩" };

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function fmtSize(bytes) {
    if (bytes === null || bytes === undefined) return "-";
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(2) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
  }

  // ---------- 总览 ----------
  function loadOverview() {
    $.getJSON(API_BASE + "/api/maintenance/overview")
      .done(function (res) {
        const tables = res.tables || [];
        const totalRows = tables.reduce((s, t) => s + t.rows, 0);
        const totalRemovable = tables.reduce((s, t) => s + t.removable, 0);
        $("#st-dbsize").text(fmtSize(res.db_size));
        $("#st-rows").text(totalRows);
        $("#st-removable").text(totalRemovable);
        $("#st-retention").text(res.retention_days + " 天");
        $("#f-retention").val(res.retention_days);
        $("#f-auto").val(String(res.auto_cleanup));
        $("#f-days").attr("placeholder", res.retention_days + " 天");

        // 表下拉
        const opts = ['<option value="all">全部表</option>'].concat(
          tables.map(t => '<option value="' + t.table + '">' + escapeHtml(t.label) + "</option>")
        );
        $("#f-table").html(opts.join(""));

        // 统计表
        $("#table-stats").html(tables.map(function (t) {
          return "<tr>" +
            "<td>" + escapeHtml(t.label) + ' <code style="font-size:11px">' + escapeHtml(t.table) + "</code></td>" +
            "<td>" + t.rows + "</td>" +
            "<td>" + escapeHtml(t.earliest || "—") + "</td>" +
            "<td>" + escapeHtml(t.latest || "—") + "</td>" +
            '<td class="' + (t.removable > 0 ? "removable" : "text-muted") + '">' + t.removable + "</td>" +
          "</tr>";
        }).join(""));
      })
      .fail(function (xhr) {
        if (xhr.status === 401 || xhr.status === 403) {
          $("#perm-box").removeClass("d-none");
          $("#maint-box").addClass("d-none");
        }
      });
  }

  // ---------- 维护日志 ----------
  function loadLogs() {
    $.getJSON(API_BASE + "/api/maintenance/logs?limit=50").done(function (res) {
      const logs = res.logs || [];
      if (!logs.length) {
        $("#log-list").html('<tr><td colspan="8" class="text-center text-muted py-4">暂无维护记录</td></tr>');
        return;
      }
      $("#log-list").html(logs.map(function (l) {
        return "<tr>" +
          "<td>" + escapeHtml(l.created_at || "") + "</td>" +
          "<td>" + (ACTION_LABELS[l.action] || escapeHtml(l.action)) + "</td>" +
          "<td>" + escapeHtml(TABLE_LABELS[l.target_table] || l.target_table || "-") + "</td>" +
          "<td>" + (l.removed_rows || 0) + "</td>" +
          "<td>" + (l.retention_days ? l.retention_days + " 天" : "—") + "</td>" +
          '<td><span class="badge log-mode-' + escapeHtml(l.mode) + '">' +
            (l.mode === "auto" ? "自动" : "手动") + "</span></td>" +
          "<td>" + escapeHtml(l.operator || "-") + "</td>" +
          '<td class="text-muted" style="font-size:12px">' + escapeHtml(l.detail || "") + "</td>" +
        "</tr>";
      }).join(""));
    });
  }

  // ---------- 保存策略 ----------
  $("#btn-save-policy").on("click", function () {
    const payload = {
      settings: {
        data_retention_days: parseInt($("#f-retention").val(), 10),
        auto_cleanup: parseInt($("#f-auto").val(), 10),
      },
    };
    $.ajax({
      url: API_BASE + "/api/settings",
      type: "PUT",
      contentType: "application/json",
      data: JSON.stringify(payload),
      success: function () { alert("保留策略已保存"); loadOverview(); },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "保存失败");
      },
    });
  });

  // ---------- 预览 ----------
  $("#btn-preview").on("click", function () {
    const table = $("#f-table").val();
    const days = parseInt($("#f-days").val(), 10) || parseInt($("#f-retention").val(), 10);
    if (table === "all") {
      let total = 0, done = 0;
      const keys = Object.keys(TABLE_LABELS);
      keys.forEach(function (t) {
        $.getJSON(API_BASE + "/api/maintenance/preview?table=" + t + "&days=" + days)
          .done(function (res) { total += res.removable; })
          .always(function () {
            if (++done === keys.length) {
              alert("按 " + days + " 天保留策略，全部表共可清理 " + total + " 行");
            }
          });
      });
    } else {
      $.getJSON(API_BASE + "/api/maintenance/preview?table=" + table + "&days=" + days)
        .done(function (res) {
          alert("按 " + res.days + " 天保留策略，「" + TABLE_LABELS[table] + "」可清理 " + res.removable + " 行");
        });
    }
  });

  // ---------- 执行清理 ----------
  $("#btn-cleanup").on("click", function () {
    const table = $("#f-table").val();
    const days = parseInt($("#f-days").val(), 10) || parseInt($("#f-retention").val(), 10);
    const name = table === "all" ? "全部表" : TABLE_LABELS[table];
    if (!confirm("确认清理「" + name + "」中 " + days + " 天前的数据？该操作不可恢复。")) return;
    $.ajax({
      url: API_BASE + "/api/maintenance/cleanup",
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ table: table, days: days }),
      success: function (res) {
        alert("清理完成，共删除 " + res.total_removed + " 行");
        loadOverview();
        loadLogs();
      },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "清理失败");
      },
    });
  });

  // ---------- VACUUM ----------
  $("#btn-vacuum").on("click", function () {
    if (!confirm("确认执行 VACUUM 压缩数据库？")) return;
    $.post(API_BASE + "/api/maintenance/vacuum")
      .done(function (res) {
        alert("压缩完成，释放 " + fmtSize(res.saved));
        loadOverview();
        loadLogs();
      })
      .fail(function () { alert("压缩失败"); });
  });

  const user = getCurrentUser();
  if (!user || user.role !== "admin") {
    $("#perm-box").removeClass("d-none");
  } else {
    $("#maint-box").removeClass("d-none");
    loadOverview();
    loadLogs();
  }
});
