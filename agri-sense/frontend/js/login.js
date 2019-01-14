// AgriSense 登录页逻辑
$(function () {
  const params = new URLSearchParams(location.search);
  const redirect = params.get("redirect") || "index.html";

  function showError(msg) {
    $("#login-alert").removeClass("d-none").text(msg);
  }

  // 已登录则展示快捷入口
  const current = typeof getCurrentUser === "function" ? getCurrentUser() : null;
  if (current && typeof getAuthToken === "function" && getAuthToken()) {
    $("#login-alert")
      .removeClass("d-none alert-danger")
      .addClass("alert-success")
      .html('当前已登录：<b>' + (current.display_name || current.username) + "</b>（" +
        roleLabel(current.role) + "），可直接 <a href=\"" + redirect + '">进入系统</a>');
  }

  // 演示账号一键填充
  $(".demo-chip").on("click", function () {
    $("#username").val($(this).data("u"));
    $("#password").val($(this).data("p"));
    $("#username").trigger("focus");
  });

  $("#login-form").on("submit", function (e) {
    e.preventDefault();
    const username = $("#username").val().trim();
    const password = $("#password").val();
    if (!username || !password) {
      showError("请填写用户名和密码");
      return;
    }

    const $btn = $("#login-btn").prop("disabled", true).text("登录中...");
    $.ajax({
      url: API_BASE + "/api/auth/login",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ username: username, password: password }),
      dataType: "json",
      timeout: 8000,
      success: function (res) {
        setAuth(res.token, res.user);
        location.href = redirect;
      },
      error: function (xhr) {
        const res = xhr.responseJSON || {};
        showError(res.message || "登录失败，请检查后端服务是否启动");
        $btn.prop("disabled", false).text("登 录");
      },
    });
  });
});
