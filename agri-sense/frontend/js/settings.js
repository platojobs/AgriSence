// AgriSense 系统设置：仅管理员可用，批量保存到 settings 表
$(function () {

  // 设置项分组渲染配置
  const GROUPS = {
    "group-irrigation": ["threshold_low", "threshold_high"],
    "group-alert": ["alert_cooldown"],
    "group-site": ["site_name", "refresh_interval"],
  };

  let settingsMeta = []; // 后端返回的 [{key,value,label,type}]

  function showPerm(text) {
    $("#perm-box").removeClass("d-none");
    $("#settings-box").addClass("d-none");
    if (text) $("#perm-text").text(text);
  }

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function render() {
    const byKey = {};
    settingsMeta.forEach(function (s) { byKey[s.key] = s; });

    Object.keys(GROUPS).forEach(function (groupId) {
      const html = GROUPS[groupId].map(function (key) {
        const s = byKey[key];
        if (!s) return "";
        const input = s.type === "str"
          ? '<input type="text" class="form-control form-control-sm setting-input" data-key="' + key + '" value="' + escapeHtml(s.value) + '" />'
          : '<input type="number" class="form-control form-control-sm setting-input" data-key="' + key + '" value="' + escapeHtml(s.value) + '" step="' + (s.type === "float" ? "0.1" : "1") + '" />';
        return (
          '<div class="setting-row">' +
            '<div class="setting-info">' +
              '<div class="setting-label">' + escapeHtml(s.label) + '</div>' +
              '<div class="setting-key">' + key + '</div>' +
            '</div>' + input +
          '</div>'
        );
      }).join("");
      $("#" + groupId).html(html);
    });
  }

  function loadSettings() {
    $.getJSON(API_BASE + "/api/settings")
      .done(function (res) {
        settingsMeta = res.settings || [];
        render();
      })
      .fail(function (xhr) {
        const msg = (xhr.responseJSON && xhr.responseJSON.message) || "无权限访问";
        if (xhr.status === 401 || xhr.status === 403) showPerm(msg);
      });
  }

  function save() {
    const updates = {};
    $(".setting-input").each(function () {
      updates[$(this).data("key")] = $(this).val();
    });

    const $btn = $("#btn-save");
    $btn.prop("disabled", true).html('<span class="spinner-border spinner-border-sm"></span> 保存中...');

    $.ajax({
      url: API_BASE + "/api/settings",
      method: "PUT",
      contentType: "application/json",
      data: JSON.stringify({ settings: updates }),
    })
      .done(function () {
        if (typeof showToast === "function") showToast("设置已保存并立即生效", "success");
        else alert("设置已保存并立即生效");
        loadSettings();
      })
      .fail(function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "保存失败");
      })
      .always(function () {
        $btn.prop("disabled", false).html('<i class="bi bi-check-lg"></i> 保存设置');
      });
  }

  $("#btn-save").on("click", save);
  $("#btn-reload").on("click", loadSettings);

  // 权限入口：仅管理员
  const user = getCurrentUser();
  if (!user) {
    showPerm("请先登录后再访问系统设置。");
  } else if (user.role !== "admin") {
    showPerm("系统设置仅对管理员开放。");
  } else {
    $("#settings-box").removeClass("d-none");
    loadSettings();
  }
});
