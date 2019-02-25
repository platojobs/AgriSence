// AgriSense 数据导出中心：CSV 下载（operator 及以上，audit_logs 仅 admin）
$(function () {

  const TYPE_META = {
    sensor_readings:      { icon: "bi-thermometer-half", color: "#e8f5e9", fg: "#2e7d32", desc: "土壤墒情 / 温湿度 / 光照历史读数" },
    irrigation_logs:      { icon: "bi-water",            color: "#e0f7fa", fg: "#00838f", desc: "手动与自动灌溉操作记录" },
    alerts:               { icon: "bi-bell",             color: "#fff8e1", fg: "#f9a825", desc: "阈值告警与处理状态记录" },
    farm_logs:            { icon: "bi-clipboard-check",  color: "#f3e8fd", fg: "#7b1fa2", desc: "播种、施肥、采收等农事记录" },
    traceability_batches: { icon: "bi-box-seam",         color: "#fdeaea", fg: "#c0392b", desc: "农产品溯源批次与质检状态" },
    audit_logs:           { icon: "bi-journal-check",    color: "#e3f2fd", fg: "#1565c0", desc: "后台关键变更操作审计（仅管理员）" },
  };

  function showPerm(text) {
    $("#perm-box").removeClass("d-none");
    $("#export-box").addClass("d-none");
    if (text) $("#perm-text").text(text);
  }

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function loadTypes() {
    $.getJSON(API_BASE + "/api/export/types")
      .done(function (res) {
        if (!res.types || !res.types.length) {
          $("#type-grid").html('<div class="col-12 text-center text-muted py-5">暂无可导出的数据类型</div>');
          return;
        }
        const html = res.types.map(function (t) {
          const m = TYPE_META[t.type] || { icon: "bi-file-earmark", color: "#f3f4f6", fg: "#6b7280", desc: "" };
          return (
            '<div class="col-md-6 col-lg-4">' +
              '<div class="type-card">' +
                '<div class="type-icon" style="background:' + m.color + ';color:' + m.fg + '">' +
                  '<i class="bi ' + m.icon + '"></i></div>' +
                '<div class="type-label">' + escapeHtml(t.label) +
                  (t.min_role === "admin" ? ' <span class="badge bg-primary-subtle text-primary" style="font-size:10px">管理员</span>' : "") +
                '</div>' +
                '<div class="text-muted mb-2" style="font-size:12px">' + escapeHtml(m.desc) + '</div>' +
                '<div class="d-flex align-items-end justify-content-between">' +
                  '<div><span class="type-count">' + (t.count || 0).toLocaleString() + '</span> <span class="type-role">条记录</span></div>' +
                  '<button class="btn btn-success btn-sm btn-export" data-type="' + t.type + '" data-label="' + escapeHtml(t.label) + '">' +
                    '<i class="bi bi-download"></i> 导出 CSV</button>' +
                '</div>' +
              '</div>' +
            '</div>'
          );
        }).join("");
        $("#type-grid").html(html);
      })
      .fail(function (xhr) {
        const msg = (xhr.responseJSON && xhr.responseJSON.message) || "无权限访问";
        if (xhr.status === 401 || xhr.status === 403) showPerm(msg);
      });
  }

  function exportCsv(type, label, $btn) {
    const params = [];
    const start = $("#f-start").val();
    const end = $("#f-end").val();
    const limit = $("#f-limit").val();
    if (start) params.push("start_date=" + start);
    if (end) params.push("end_date=" + end);
    if (limit) params.push("limit=" + limit);
    const url = API_BASE + "/api/export/" + type + (params.length ? "?" + params.join("&") : "");

    $btn.prop("disabled", true).html('<span class="spinner-border spinner-border-sm"></span> 导出中...');

    $.ajax({
      url: url,
      method: "GET",
      xhrFields: { responseType: "blob" },
    })
      .done(function (blob, status, xhr) {
        const cd = xhr.getResponseHeader("Content-Disposition") || "";
        const m = cd.match(/filename=([^;]+)/);
        const filename = m ? m[1].trim() : type + ".csv";
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
        if (typeof showToast === "function") showToast("已导出「" + label + "」", "success");
      })
      .fail(function (xhr) {
        // blob 错误响应需要转文本解析
        if (xhr.response && xhr.response instanceof Blob) {
          const reader = new FileReader();
          reader.onload = function () {
            try {
              const j = JSON.parse(reader.result);
              alert(j.message || "导出失败");
            } catch (e) { alert("导出失败"); }
          };
          reader.readAsText(xhr.response);
        } else {
          alert("导出失败");
        }
      })
      .always(function () {
        $btn.prop("disabled", false).html('<i class="bi bi-download"></i> 导出 CSV');
      });
  }

  $("#type-grid").on("click", ".btn-export", function () {
    exportCsv($(this).data("type"), $(this).data("label"), $(this));
  });

  $("#btn-clear").on("click", function () {
    $("#f-start").val("");
    $("#f-end").val("");
    $("#f-limit").val("10000");
  });

  // 权限入口：operator 及以上
  const user = getCurrentUser();
  if (!user) {
    showPerm("请先登录后再使用数据导出功能。");
  } else if (user.role !== "operator" && user.role !== "admin") {
    showPerm("当前为访客角色，数据导出需要操作员及以上权限。");
  } else {
    $("#export-box").removeClass("d-none");
    loadTypes();
  }
});
