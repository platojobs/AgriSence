// AgriSense 工单管理：列表 + 统计 + 新建/编辑/流转/删除
$(function () {

  const TYPE_LABEL = { alert: "告警工单", ops: "运维工单", inspect: "巡检工单" };
  const PRIORITY_LABEL = { low: "低", medium: "中", high: "高", urgent: "紧急" };
  const STATUS_LABEL = { open: "待处理", processing: "处理中", resolved: "已解决", closed: "已关闭" };
  const STATUS_FLOW = { open: "processing", processing: "resolved" }; // 快捷下一步

  let filterStatus = "";
  let scope = ""; // "" | todo | mine
  let keyword = "";

  const user = getCurrentUser();
  const canEdit = user && (user.role === "operator" || user.role === "admin");
  const canDelete = user && user.role === "admin";
  const editModal = new bootstrap.Modal(document.getElementById("ticketModal"));
  const detailModal = new bootstrap.Modal(document.getElementById("detailModal"));

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ---------- 统计 ----------
  function loadStats() {
    $.getJSON(API_BASE + "/api/tickets/stats").done(function (res) {
      const s = res.stats || {};
      const bs = s.by_status || {}, bp = s.by_priority || {};
      $("#st-total").text(s.total || 0);
      $("#st-open").text(bs.open || 0);
      $("#st-processing").text(bs.processing || 0);
      $("#st-resolved").text(bs.resolved || 0);
      $("#st-urgent").text(bp.urgent || 0);
      $("#st-unassigned").text(s.open_unassigned || 0);
    });
  }

  // ---------- 列表 ----------
  function load() {
    let url = API_BASE + "/api/tickets?";
    if (filterStatus) url += "status=" + filterStatus + "&";
    if (scope === "todo") url += "todo=1&";
    if (scope === "mine") url += "mine=1&";
    if (keyword) url += "keyword=" + encodeURIComponent(keyword) + "&";

    $.getJSON(url)
      .done(function (res) {
        const items = res.tickets || [];
        if (!items.length) {
          $("#ticket-list").html('<tr><td colspan="9" class="text-center text-muted py-5">' +
            '<i class="bi bi-inbox" style="font-size:40px"></i><div class="mt-2">暂无工单</div></td></tr>');
          return;
        }
        $("#ticket-list").html(items.map(function (t) {
          const next = STATUS_FLOW[t.status];
          let ops = '<button class="btn btn-outline-secondary btn-sm btn-detail" data-id="' + t.id + '">详情</button> ';
          if (canEdit) {
            ops += '<button class="btn btn-outline-primary btn-sm btn-edit" data-id="' + t.id + '">编辑</button> ';
            if (next) {
              ops += '<button class="btn btn-outline-success btn-sm btn-flow" data-id="' + t.id +
                '" data-status="' + next + '">' + STATUS_LABEL[next] + '</button> ';
            }
          }
          if (canDelete) {
            ops += '<button class="btn btn-outline-danger btn-sm btn-del" data-id="' + t.id + '">删除</button>';
          }
          return "<tr>" +
            '<td class="t-no">' + escapeHtml(t.ticket_no) + "</td>" +
            '<td class="t-title">' + escapeHtml(t.title) + "</td>" +
            '<td><span class="badge badge-type-' + escapeHtml(t.type) + '">' + (TYPE_LABEL[t.type] || t.type) + "</span></td>" +
            '<td><span class="badge badge-priority-' + escapeHtml(t.priority) + '">' + (PRIORITY_LABEL[t.priority] || t.priority) + "</span></td>" +
            '<td><span class="badge badge-status-' + escapeHtml(t.status) + '">' + (STATUS_LABEL[t.status] || t.status) + "</span></td>" +
            "<td>" + escapeHtml(t.assignee || "—") + "</td>" +
            "<td>" + escapeHtml(t.creator || "—") + "</td>" +
            "<td>" + escapeHtml(t.created_at || "") + "</td>" +
            "<td>" + ops + "</td>" +
          "</tr>";
        }).join(""));
      })
      .fail(function (xhr) {
        if (xhr.status === 401 || xhr.status === 403) {
          $("#perm-box").removeClass("d-none");
          $("#ticket-box").addClass("d-none");
        }
      });
  }

  // ---------- 指派人下拉 ----------
  function loadAssignees(selected) {
    if (!canEdit) return;
    $.getJSON(API_BASE + "/api/tickets/assignable").done(function (res) {
      const opts = ['<option value="">暂不指派</option>'].concat(
        (res.users || []).map(function (u) {
          const sel = u.username === selected ? " selected" : "";
          return '<option value="' + escapeHtml(u.username) + '"' + sel + ">" +
            escapeHtml(u.display_name) + "（" + escapeHtml(u.role_label) + "）</option>";
        })
      );
      $("#f-assignee").html(opts.join(""));
    });
  }

  // ---------- 新建 / 编辑 ----------
  $("#btn-new").on("click", function () {
    $("#modal-title").text("新建工单");
    $("#f-id, #f-title, #f-desc, #f-resolution").val("");
    $("#f-type").val("ops");
    $("#f-priority").val("medium");
    $("#wrap-status, #wrap-resolution").addClass("d-none");
    loadAssignees("");
    editModal.show();
  });

  $("#ticket-list").on("click", ".btn-edit", function () {
    const id = $(this).data("id");
    $.getJSON(API_BASE + "/api/tickets/" + id).done(function (res) {
      const t = res.ticket;
      $("#modal-title").text("编辑工单 " + t.ticket_no);
      $("#f-id").val(t.id);
      $("#f-title").val(t.title);
      $("#f-desc").val(t.description || "");
      $("#f-type").val(t.type);
      $("#f-priority").val(t.priority);
      $("#f-status").val(t.status);
      $("#f-resolution").val(t.resolution || "");
      $("#wrap-status, #wrap-resolution").removeClass("d-none");
      loadAssignees(t.assignee || "");
      editModal.show();
    });
  });

  $("#btn-save").on("click", function () {
    const id = $("#f-id").val();
    const payload = {
      title: $("#f-title").val().trim(),
      description: $("#f-desc").val(),
      type: $("#f-type").val(),
      priority: $("#f-priority").val(),
      assignee: $("#f-assignee").val(),
    };
    if (!payload.title) { alert("请填写工单标题"); return; }
    if (id) {
      payload.status = $("#f-status").val();
      payload.resolution = $("#f-resolution").val();
    }
    $.ajax({
      url: API_BASE + "/api/tickets" + (id ? "/" + id : ""),
      type: id ? "PUT" : "POST",
      contentType: "application/json",
      data: JSON.stringify(payload),
      success: function () { editModal.hide(); load(); loadStats(); },
      error: function (xhr) {
        const msg = xhr.responseJSON && xhr.responseJSON.message;
        alert(msg || "保存失败");
      },
    });
  });

  // ---------- 快捷流转 ----------
  $("#ticket-list").on("click", ".btn-flow", function () {
    const id = $(this).data("id");
    const status = $(this).data("status");
    $.ajax({
      url: API_BASE + "/api/tickets/" + id,
      type: "PUT",
      contentType: "application/json",
      data: JSON.stringify({ status: status }),
      success: function () { load(); loadStats(); },
      error: function (xhr) {
        const msg = xhr.responseJSON && xhr.responseJSON.message;
        alert(msg || "操作失败");
      },
    });
  });

  // ---------- 删除 ----------
  $("#ticket-list").on("click", ".btn-del", function () {
    if (!confirm("确认删除该工单？")) return;
    $.ajax({
      url: API_BASE + "/api/tickets/" + $(this).data("id"),
      type: "DELETE",
      success: function () { load(); loadStats(); },
    });
  });

  // ---------- 详情 ----------
  $("#ticket-list").on("click", ".btn-detail", function () {
    $.getJSON(API_BASE + "/api/tickets/" + $(this).data("id")).done(function (res) {
      const t = res.ticket;
      function row(k, v) {
        return '<tr><th style="width:90px" class="text-muted">' + k + "</th><td>" + v + "</td></tr>";
      }
      $("#detail-body").html('<table class="table table-sm mb-0"><tbody>' +
        row("单号", escapeHtml(t.ticket_no)) +
        row("标题", escapeHtml(t.title)) +
        row("类型", TYPE_LABEL[t.type] || escapeHtml(t.type)) +
        row("优先级", PRIORITY_LABEL[t.priority] || escapeHtml(t.priority)) +
        row("状态", STATUS_LABEL[t.status] || escapeHtml(t.status)) +
        row("指派人", escapeHtml(t.assignee || "—")) +
        row("创建人", escapeHtml(t.creator || "—")) +
        (t.alert_id ? row("关联告警", "#" + t.alert_id) : "") +
        row("描述", escapeHtml(t.description || "—").replace(/\n/g, "<br>")) +
        (t.resolution ? row("处理结果", escapeHtml(t.resolution).replace(/\n/g, "<br>")) : "") +
        row("创建时间", escapeHtml(t.created_at || "—")) +
        row("更新时间", escapeHtml(t.updated_at || "—")) +
        (t.closed_at ? row("关闭时间", escapeHtml(t.closed_at)) : "") +
      "</tbody></table>");
      detailModal.show();
    });
  });

  // ---------- 过滤 ----------
  $("[data-status]").on("click", function () {
    $("[data-status]").removeClass("active");
    $(this).addClass("active");
    filterStatus = $(this).data("status");
    load();
  });
  $("[data-scope]").on("click", function () {
    $("[data-scope]").removeClass("active");
    $(this).addClass("active");
    scope = $(this).data("scope");
    load();
  });
  $("#btn-search").on("click", function () { keyword = $("#kw").val().trim(); load(); });
  $("#kw").on("keydown", function (e) { if (e.which === 13) { keyword = $(this).val().trim(); load(); } });

  if (!user) {
    $("#perm-box").removeClass("d-none");
  } else {
    $("#ticket-box").removeClass("d-none");
    if (!canEdit) $("#btn-new").hide();
    load();
    loadStats();
  }
});
