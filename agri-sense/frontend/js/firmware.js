// AgriSense 固件管理：版本列表 + 上传 + 下载 + 设为最新 + 删除
$(function () {

  const user = getCurrentUser();
  const isAdmin = user && user.role === "admin";
  const uploadModal = new bootstrap.Modal(document.getElementById("uploadModal"));

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function fmtSize(bytes) {
    if (!bytes) return "0 B";
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(2) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
  }

  function load() {
    const model = $("#f-filter-model").val().trim();
    const url = API_BASE + "/api/firmware" + (model ? "?model=" + encodeURIComponent(model) : "");
    $.getJSON(url)
      .done(function (res) {
        const items = res.firmware || [];
        if (!items.length) {
          $("#fw-list").html('<tr><td colspan="9" class="text-center text-muted py-5">' +
            '<i class="bi bi-inbox" style="font-size:40px"></i><div class="mt-2">暂无固件</div></td></tr>');
          return;
        }
        $("#fw-list").html(items.map(function (f) {
          let ops = '<a class="btn btn-outline-success btn-sm" href="' + API_BASE +
            "/api/firmware/" + f.id + '/download"><i class="bi bi-download"></i> 下载</a> ';
          if (isAdmin) {
            if (!f.is_latest) {
              ops += '<button class="btn btn-outline-primary btn-sm btn-latest" data-id="' + f.id +
                '"><i class="bi bi-star"></i> 设为最新</button> ';
            }
            ops += '<button class="btn btn-outline-danger btn-sm btn-del" data-id="' + f.id +
              '"><i class="bi bi-trash"></i></button>';
          }
          return "<tr>" +
            '<td class="fw-ver">v' + escapeHtml(f.version) +
              (f.is_latest ? ' <span class="badge fw-latest">最新</span>' : "") + "</td>" +
            "<td><code>" + escapeHtml(f.device_model) + "</code></td>" +
            "<td>" + escapeHtml(f.filename || "-") + "</td>" +
            "<td>" + fmtSize(f.size) + "</td>" +
            '<td class="fw-checksum" title="' + escapeHtml(f.checksum || "") + '">' +
              escapeHtml((f.checksum || "").slice(0, 10)) + "…</td>" +
            '<td style="max-width:220px;white-space:pre-line">' + escapeHtml(f.changelog || "—") + "</td>" +
            "<td>" + (f.downloads || 0) + "</td>" +
            "<td>" + escapeHtml(f.created_at || "") + "</td>" +
            "<td>" + ops + "</td>" +
          "</tr>";
        }).join(""));
      })
      .fail(function (xhr) {
        if (xhr.status === 401 || xhr.status === 403) {
          $("#perm-box").removeClass("d-none");
          $("#fw-box").addClass("d-none");
        }
      });
  }

  // ---------- 上传 ----------
  $("#btn-upload").on("click", function () {
    $("#f-version").val("");
    $("#f-file").val("");
    $("#f-changelog").val("");
    uploadModal.show();
  });

  $("#btn-do-upload").on("click", function () {
    const version = $("#f-version").val().trim();
    const model = $("#f-model").val().trim();
    const file = $("#f-file")[0].files[0];
    if (!version || !model) { alert("请填写版本号与设备型号"); return; }
    if (!file) { alert("请选择固件文件"); return; }
    const fd = new FormData();
    fd.append("version", version);
    fd.append("device_model", model);
    fd.append("changelog", $("#f-changelog").val());
    fd.append("file", file);
    $.ajax({
      url: API_BASE + "/api/firmware",
      type: "POST",
      data: fd,
      processData: false,
      contentType: false,
      success: function () { uploadModal.hide(); load(); },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "上传失败");
      },
    });
  });

  // ---------- 设为最新 ----------
  $("#fw-list").on("click", ".btn-latest", function () {
    $.post(API_BASE + "/api/firmware/" + $(this).data("id") + "/set_latest")
      .done(load)
      .fail(function () { alert("操作失败"); });
  });

  // ---------- 删除 ----------
  $("#fw-list").on("click", ".btn-del", function () {
    if (!confirm("确认删除该固件？文件将一并删除。")) return;
    $.ajax({
      url: API_BASE + "/api/firmware/" + $(this).data("id"),
      type: "DELETE",
      success: load,
      error: function () { alert("删除失败"); },
    });
  });

  $("#btn-filter").on("click", load);
  $("#f-filter-model").on("keydown", function (e) { if (e.which === 13) load(); });

  if (!user) {
    $("#perm-box").removeClass("d-none");
  } else {
    $("#fw-box").removeClass("d-none");
    if (!isAdmin) $("#btn-upload").hide();
    load();
  }
});
