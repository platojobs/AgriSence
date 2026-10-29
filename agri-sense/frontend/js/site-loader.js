// site-loader.js
// 把 /api/cms/site/<key> 返回的 HTML 渲染到 #site-content 容器。
// 失败或空响应时保持页面原有的静态内容（默认正文）。

$(function () {
  const key = (window.PAGE_CONFIG && window.PAGE_CONFIG.siteKey) || "";
  if (!key) return;

  const $box = $("#site-content");
  if (!$box.length) return;

  const url = (window.API_BASE || "http://localhost:5001") + "/api/cms/site/" + encodeURIComponent(key);
  $.ajax({
    url, dataType: "json", timeout: 4000,
    headers: { "X-Auth-Token": (localStorage.getItem("agri_token") || "") },
    success: function (data) {
      if (data && data.content && data.content.trim()) {
        $box.html(data.content);
      }
      // 空 content：什么也不做，保留静态默认内容
    },
    error: function () {
      // 断网/接口 404：静默，保留静态内容
    },
  });
});
