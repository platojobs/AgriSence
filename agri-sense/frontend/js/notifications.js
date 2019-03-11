// AgriSense 通知中心：我的通知列表 + 已读管理
$(function () {

  let filter = "all"; // all | unread

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function typeIcon(t) {
    return t === "alert" ? "bi-exclamation-triangle" : "bi-info-circle";
  }

  function load() {
    const url = API_BASE + "/api/notifications?limit=100" + (filter === "unread" ? "&unread=1" : "");
    $.getJSON(url)
      .done(function (res) {
        const items = res.notifications || [];
        $("#unread-badge").text((res.unread || 0) + " 条未读");
        if (!items.length) {
          $("#notif-list").html('<div class="text-center text-muted py-5">' +
            '<i class="bi bi-inbox" style="font-size:40px"></i><div class="mt-2">' +
            (filter === "unread" ? "没有未读通知" : "暂无通知") + "</div></div>");
          return;
        }
        $("#notif-list").html(items.map(function (n) {
          const unread = !n.is_read;
          return '<div class="n-item' + (unread ? " unread" : "") + '">' +
            '<div class="n-icon ' + escapeHtml(n.type || "info") + '"><i class="bi ' + typeIcon(n.type) + '"></i></div>' +
            '<div style="flex:1;min-width:0">' +
              '<div class="n-title">' + (unread ? '<span class="unread-dot"></span>' : "") + escapeHtml(n.title) + "</div>" +
              '<div class="n-content">' + escapeHtml(n.content) + "</div>" +
              '<div class="n-time"><i class="bi bi-clock"></i> ' + escapeHtml(n.created_at || "") + "</div>" +
            "</div>" +
            (unread
              ? '<div class="n-actions"><button class="btn btn-outline-success btn-sm btn-read" data-id="' + n.id + '">标为已读</button></div>'
              : "") +
          "</div>";
        }).join(""));
      })
      .fail(function (xhr) {
        if (xhr.status === 401 || xhr.status === 403) {
          $("#perm-box").removeClass("d-none");
          $("#notif-box").addClass("d-none");
        }
      });
  }

  $("#notif-list").on("click", ".btn-read", function () {
    const id = $(this).data("id");
    $.post(API_BASE + "/api/notifications/" + id + "/read").always(load);
  });

  $("#btn-read-all").on("click", function () {
    $.post(API_BASE + "/api/notifications/read_all").always(load);
  });

  $("[data-filter]").on("click", function () {
    $("[data-filter]").removeClass("active");
    $(this).addClass("active");
    filter = $(this).data("filter");
    load();
  });

  const user = getCurrentUser();
  if (!user) {
    $("#perm-box").removeClass("d-none");
  } else {
    $("#notif-box").removeClass("d-none");
    load();
  }
});
