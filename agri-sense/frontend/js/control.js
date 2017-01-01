// AgriSense 灌溉控制：阈值保存、手动启停、日志刷新

// 阈值表单提交
$("#threshold-form").on("submit", function (e) {
  e.preventDefault();
  const low = $("#threshold-low").val();
  const high = $("#threshold-high").val();
  $.post(API_BASE + "/api/thresholds", { low: low, high: high })
    .done(function () {
      alert("阈值已保存");
    })
    .fail(function () {
      alert("阈值保存失败");
    });
});

// 手动灌溉
$("#btn-start").on("click", function () {
  $.post(API_BASE + "/api/irrigation/manual", { action: "start" })
    .done(function () {
      loadLogs();
    })
    .fail(function () {
      alert("手动灌溉失败");
    });
});

// 停止灌溉
$("#btn-stop").on("click", function () {
  $.post(API_BASE + "/api/irrigation/manual", { action: "stop" })
    .done(function () {
      loadLogs();
    })
    .fail(function () {
      alert("停止灌溉失败");
    });
});

// 刷新灌溉日志
function loadLogs() {
  $.get(API_BASE + "/api/irrigation/logs")
    .done(function (logs) {
      const $tbody = $("#log-table");
      $tbody.empty();
      if (!logs || logs.length === 0) {
        $tbody.append('<tr><td colspan="3" class="text-center text-muted">暂无日志</td></tr>');
        return;
      }
      logs.forEach(function (log) {
        const actionText = log.action === "start" ? "开启灌溉" : (log.action === "stop" ? "停止灌溉" : log.action);
        const actionClass = log.action === "start" ? "badge bg-success" : (log.action === "stop" ? "badge bg-secondary" : "badge bg-light text-dark");
        const $tr = $("<tr>").append(
          $("<td>").append($('<span class="' + actionClass + '">').text(actionText)),
          $("<td>").text(log.reason || "--"),
          $("<td>").text(log.created_at || "--")
        );
        $tbody.append($tr);
      });
    })
    .fail(function () {
      // 静默失败，避免频繁弹窗
    });
}

$(document).ready(function () {
  loadLogs();
  setInterval(loadLogs, 10000);
});
