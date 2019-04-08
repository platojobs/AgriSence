// AgriSense 设备分组：分组卡片 + 设备归属分配 + 分区统计
$(function () {

  const user = getCurrentUser();
  const canEdit = user && (user.role === "operator" || user.role === "admin");
  const canDelete = user && user.role === "admin";
  const groupModal = new bootstrap.Modal(document.getElementById("groupModal"));

  let groups = [];
  let deviceFilter = "";

  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function statusBadge(status) {
    return status === "online"
      ? '<span class="badge bg-success">在线</span>'
      : '<span class="badge bg-secondary">离线</span>';
  }

  // ---------- 分组卡片 ----------
  function renderGroups(list) {
    if (!list.length) {
      $("#group-cards").html('<div class="col-12 text-center text-muted py-4">' +
        '<i class="bi bi-inbox" style="font-size:36px"></i><div class="mt-2">暂无分组，点击右上角新建</div></div>');
      return;
    }
    $("#group-cards").html(list.map(function (g) {
      let actions = "";
      if (canEdit) {
        actions += '<button class="btn btn-outline-primary btn-sm btn-edit" data-id="' + g.id + '">' +
          '<i class="bi bi-pencil"></i> 编辑</button> ';
      }
      if (canDelete) {
        actions += '<button class="btn btn-outline-danger btn-sm btn-del" data-id="' + g.id + '" data-name="' +
          escapeHtml(g.name) + '"><i class="bi bi-trash"></i> 删除</button>';
      }
      return '<div class="col-12 col-md-6 col-xl-4"><div class="sensor-card group-card">' +
        '<div class="d-flex align-items-start">' +
          '<div><div class="g-name"><i class="bi bi-house-door text-success"></i> ' + escapeHtml(g.name) + "</div>" +
          '<div class="g-loc"><i class="bi bi-geo-alt"></i> ' + escapeHtml(g.location || "未填写位置") + "</div></div>" +
          '<div class="ms-auto text-end"><span class="badge bg-success">' + (g.online_count || 0) + " 在线</span>" +
          '<div class="g-meta">共 ' + (g.device_count || 0) + " 台设备</div></div>" +
        "</div>" +
        '<div class="g-desc">' + escapeHtml(g.description || "—") + "</div>" +
        '<div class="g-meta"><i class="bi bi-person-badge"></i> 负责人：' +
          escapeHtml(g.leader || "未指定") + "</div>" +
        (actions ? '<div class="g-actions">' + actions + "</div>" : "") +
      "</div></div>";
    }).join(""));
  }

  // ---------- 加载分组 ----------
  function loadGroups(done) {
    $.getJSON(API_BASE + "/api/device-groups")
      .done(function (res) {
        groups = res.groups || [];
        const s = res.stats || {};
        $("#st-groups").text(s.groups || 0);
        $("#st-online").text(s.online || 0);
        $("#st-devices").text(s.devices || 0);
        $("#st-ungrouped").text(s.ungrouped || 0);
        renderGroups(groups);
        if (typeof done === "function") done();
      })
      .fail(function (xhr) {
        if (xhr.status === 401 || xhr.status === 403) {
          $("#perm-box").removeClass("d-none");
          $("#grp-box").addClass("d-none");
        }
      });
  }

  // ---------- 加载设备 ----------
  function loadDevices() {
    $.getJSON(API_BASE + "/api/devices").done(function (list) {
      if (deviceFilter === "ungrouped") {
        list = list.filter(function (d) { return !d.group_id; });
      }
      if (!list.length) {
        $("#device-list").html('<tr><td colspan="6" class="text-center text-muted py-4">暂无设备</td></tr>');
        return;
      }
      $("#device-list").html(list.map(function (d) {
        let select = '<span class="text-muted">—</span>';
        if (canEdit) {
          const opts = ['<option value="">未分组</option>'].concat(
            groups.map(function (g) {
              const sel = Number(d.group_id) === Number(g.id) ? " selected" : "";
              return '<option value="' + g.id + '"' + sel + ">" + escapeHtml(g.name) + "</option>";
            })
          );
          select = '<select class="form-select form-select-sm dev-group" data-id="' +
            escapeHtml(d.device_id) + '">' + opts.join("") + "</select>";
        } else {
          select = escapeHtml(d.group_name || "未分组");
        }
        return "<tr>" +
          "<td><code>" + escapeHtml(d.device_id) + "</code></td>" +
          "<td>" + escapeHtml(d.name || "-") + "</td>" +
          "<td>" + escapeHtml(d.location || "-") + "</td>" +
          "<td>" + statusBadge(d.status) + "</td>" +
          "<td>" + escapeHtml(d.group_name || "未分组") + "</td>" +
          "<td>" + select + "</td>" +
        "</tr>";
      }).join(""));
    });
  }

  // ---------- 负责人下拉（operator/admin） ----------
  function loadLeaders(selected) {
    $.getJSON(API_BASE + "/api/tickets/assignable").done(function (res) {
      const opts = ['<option value="">暂不指定</option>'].concat(
        (res.users || []).map(function (u) {
          const sel = u.username === selected ? " selected" : "";
          return '<option value="' + escapeHtml(u.username) + '"' + sel + ">" +
            escapeHtml(u.display_name) + "（" + escapeHtml(u.role_label) + "）</option>";
        })
      );
      $("#f-leader").html(opts.join(""));
    });
  }

  // ---------- 新建 / 编辑 ----------
  $("#btn-new-group").on("click", function () {
    $("#modal-title").text("新建分组");
    $("#f-id, #f-name, #f-location, #f-description").val("");
    loadLeaders("");
    groupModal.show();
  });

  $("#group-cards").on("click", ".btn-edit", function () {
    const id = Number($(this).data("id"));
    const g = groups.find(function (x) { return Number(x.id) === id; });
    if (!g) return;
    $("#modal-title").text("编辑分组");
    $("#f-id").val(g.id);
    $("#f-name").val(g.name);
    $("#f-location").val(g.location || "");
    $("#f-description").val(g.description || "");
    loadLeaders(g.leader || "");
    groupModal.show();
  });

  $("#btn-save-group").on("click", function () {
    const id = $("#f-id").val();
    const payload = {
      name: $("#f-name").val().trim(),
      location: $("#f-location").val().trim(),
      description: $("#f-description").val(),
      leader: $("#f-leader").val(),
    };
    if (!payload.name) { alert("请填写分组名称"); return; }
    $.ajax({
      url: API_BASE + "/api/device-groups" + (id ? "/" + id : ""),
      type: id ? "PUT" : "POST",
      contentType: "application/json",
      data: JSON.stringify(payload),
      success: function () {
        groupModal.hide();
        loadGroups();
        loadDevices();
      },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "保存失败");
      },
    });
  });

  // ---------- 删除分组 ----------
  $("#group-cards").on("click", ".btn-del", function () {
    const id = $(this).data("id");
    const name = $(this).data("name");
    if (!confirm("确认删除分组「" + name + "」？组内设备将转为未分组。")) return;
    $.ajax({
      url: API_BASE + "/api/device-groups/" + id,
      type: "DELETE",
      success: function () { loadGroups(); loadDevices(); },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "删除失败");
      },
    });
  });

  // ---------- 分配设备 ----------
  $("#device-list").on("change", ".dev-group", function () {
    const deviceId = $(this).data("id");
    const groupId = $(this).val();
    $.ajax({
      url: API_BASE + "/api/devices/" + encodeURIComponent(deviceId) + "/group",
      type: "PUT",
      contentType: "application/json",
      data: JSON.stringify({ group_id: groupId === "" ? null : Number(groupId) }),
      success: function () { loadGroups(); loadDevices(); },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.message) || "分配失败");
      },
    });
  });

  $("[data-filter]").on("click", function () {
    $("[data-filter]").removeClass("active");
    $(this).addClass("active");
    deviceFilter = $(this).data("filter");
    loadDevices();
  });

  if (!user) {
    $("#perm-box").removeClass("d-none");
  } else {
    $("#grp-box").removeClass("d-none");
    if (!canEdit) $("#btn-new-group").hide();
    // 设备表的分组下拉依赖分组数据，先加载分组再渲染设备
    loadGroups(loadDevices);
  }
});
