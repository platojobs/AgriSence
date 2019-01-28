// AgriSense CMS 后台内容管理
// 依赖: dashboard.js (API_BASE, getAuthToken, getCurrentUser)

const CATEGORIES_KNOWLEDGE = ["种植技术", "病虫害防治", "水肥管理", "智慧农业"];
const CATEGORIES_NEWS = ["政策动态", "行业动态", "科技前沿", "市场行情"];

let currentTab = "knowledge";
let fbStatusFilter = "";

function isAdmin() {
  const u = getCurrentUser();
  return !!(u && u.role === "admin");
}

function showPerm() {
  $("#cms-box").hide();
  $("#perm-box").show();
}

// ---------- Toast ----------
function toast(msg, type) {
  type = type || "success";
  const box = $("#toast-box");
  const alert = $('<div class="alert alert-' + (type === "error" ? "danger" : type) + ' py-1 px-3 mb-2" style="min-width:220px;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.15);">' +
    msg + '</div>').appendTo(box);
  setTimeout(() => alert.fadeOut(300, () => alert.remove()), 2500);
}

// ---------- 通用 AJAX ----------
function ajax(url, opts) {
  opts = opts || {};
  const def = {
    url, dataType: "json", timeout: 6000,
    headers: { "X-Auth-Token": getAuthToken() },
  };
  if (opts.data && typeof opts.data === "object" && opts._isJson) {
    def.contentType = "application/json";
    def.data = JSON.stringify(opts.data);
  } else if (opts.data) {
    def.data = opts.data;
  }
  def.type = opts.method || "GET";
  return $.ajax(def).fail(function (xhr) {
    if (xhr.status === 401 || xhr.status === 403) {
      toast("权限不足，请重新登录", "error");
      setTimeout(() => location.href = "login.html?redirect=cms.html", 1000);
    }
  });
}

// ---------- Tab 切换 ----------
$("#cms-tabs").on("click", ".nav-link", function (e) {
  e.preventDefault();
  const tab = $(this).data("tab");
  currentTab = tab;
  $("#cms-tabs .nav-link").removeClass("active");
  $(this).addClass("active");
  ["knowledge", "news", "feedback", "site"].forEach(t => {
    $("#tab-" + t).toggle(t === tab);
  });
  switch (tab) {
    case "knowledge": loadKnowledge(); break;
    case "news": loadNews(); break;
    case "feedback": loadFeedback(); break;
    case "site": loadSite(); break;
  }
});

// ---------- 知识文章 ----------
function loadKnowledge() {
  ajax(API_BASE + "/api/cms/knowledge").done(d => {
    $("#knowledge-tbody").html(d.map(r => `
      <tr>
        <td>${r.id}</td>
        <td><span class="cat-pill">${r.category || "--"}</span></td>
        <td class="title-cell" title="${r.title}">${r.title}</td>
        <td>${r.author || "--"}</td>
        <td>${r.views || 0}</td>
        <td><small class="text-muted">${r.created_at || ""}</small></td>
        <td>
          <button class="btn btn-xs btn-outline-primary edit-know" data-id="${r.id}">编辑</button>
          <button class="btn btn-xs btn-outline-danger del-know" data-id="${r.id}" data-title="${r.title}">删除</button>
        </td>
      </tr>
    `).join("") || '<tr><td colspan="7" class="text-center text-muted py-3">暂无文章</td></tr>');
  });
}

function openKnowledgeForm(row) {
  row = row || {};
  const isEdit = !!row.id;
  $("#editModalTitle").text(isEdit ? "编辑知识文章" : "新增知识文章");
  const catOpts = CATEGORIES_KNOWLEDGE.map(c =>
    `<option ${c === row.category ? "selected" : ""}>${c}</option>`
  ).join("");
  $("#editModalBody").html(`
    <div class="mb-2 row g-2">
      <div class="col-md-6"><label>分类</label>
        <select class="form-select form-select-sm" id="f-category">${catOpts}</select>
      </div>
      <div class="col-md-6"><label>作者</label>
        <input class="form-control form-control-sm" id="f-author" value="${row.author || "农技专家"}" />
      </div>
    </div>
    <div class="mb-2"><label>标题 *</label>
      <input class="form-control form-control-sm" id="f-title" value="${row.title || ""}" />
    </div>
    <div class="mb-2"><label>摘要（列表显示）</label>
      <input class="form-control form-control-sm" id="f-summary" value="${row.summary || ""}" />
    </div>
    <div class="mb-2"><label>正文 *</label>
      <textarea class="form-control" id="f-content" rows="8">${row.content || ""}</textarea>
    </div>
  `);
  const bs = new bootstrap.Modal($("#editModal")[0]);
  $("#editModalSave").off("click").on("click", function () {
    const payload = {
      category: $("#f-category").val(),
      title: $("#f-title").val().trim(),
      summary: $("#f-summary").val().trim() || ($("#f-content").val() || "").slice(0, 80),
      content: $("#f-content").val(),
      author: $("#f-author").val().trim() || "农技专家",
    };
    if (!payload.title || !payload.content) { toast("标题与正文不能为空", "error"); return; }
    const url = isEdit ? (API_BASE + "/api/cms/knowledge/" + row.id) : (API_BASE + "/api/cms/knowledge");
    ajax(url, { method: isEdit ? "PUT" : "POST", data: payload, _isJson: true })
      .done(() => { bs.hide(); toast(isEdit ? "已更新" : "已新增"); loadKnowledge(); })
      .fail(xhr => toast((xhr.responseJSON && xhr.responseJSON.message) || "保存失败", "error"));
  });
  bs.show();
}

$("#btn-knowledge-add").on("click", () => openKnowledgeForm(null));
$(document).on("click", ".edit-know", function () {
  const id = $(this).data("id");
  ajax(API_BASE + "/api/cms/knowledge").done(list => {
    const row = list.find(r => r.id === id);
    openKnowledgeForm(row);
  });
});
$(document).on("click", ".del-know", function () {
  const id = $(this).data("id"), title = $(this).data("title");
  if (!confirm("确认删除知识文章：" + title + "？此操作不可撤销。")) return;
  ajax(API_BASE + "/api/cms/knowledge/" + id, { method: "DELETE" })
    .done(() => { toast("已删除"); loadKnowledge(); });
});

// ---------- 新闻 ----------
function loadNews() {
  ajax(API_BASE + "/api/cms/news").done(d => {
    $("#news-tbody").html(d.map(r => `
      <tr>
        <td>${r.id}</td>
        <td>${r.is_top ? '<span class="top-pill">置顶</span>' : ""}</td>
        <td><span class="cat-pill">${r.category || "--"}</span></td>
        <td class="title-cell" title="${r.title}">${r.title}</td>
        <td>${r.source || "--"}</td>
        <td>${r.views || 0}</td>
        <td><small class="text-muted">${r.created_at || ""}</small></td>
        <td>
          <button class="btn btn-xs btn-outline-warning top-news" data-id="${r.id}" data-top="${r.is_top}">${r.is_top ? "取消置顶" : "置顶"}</button>
          <button class="btn btn-xs btn-outline-primary edit-news" data-id="${r.id}">编辑</button>
          <button class="btn btn-xs btn-outline-danger del-news" data-id="${r.id}" data-title="${r.title}">删除</button>
        </td>
      </tr>
    `).join("") || '<tr><td colspan="8" class="text-center text-muted py-3">暂无新闻</td></tr>');
  });
}

function openNewsForm(row) {
  row = row || {};
  const isEdit = !!row.id;
  $("#editModalTitle").text(isEdit ? "编辑新闻" : "新增新闻");
  const catOpts = CATEGORIES_NEWS.map(c =>
    `<option ${c === row.category ? "selected" : ""}>${c}</option>`
  ).join("");
  $("#editModalBody").html(`
    <div class="mb-2 row g-2">
      <div class="col-md-5"><label>分类</label>
        <select class="form-select form-select-sm" id="f-category">${catOpts}</select>
      </div>
      <div class="col-md-5"><label>来源</label>
        <input class="form-control form-control-sm" id="f-source" value="${row.source || "AgriSense 资讯"}" />
      </div>
      <div class="col-md-2 d-flex align-items-end"><label class="form-check-label">
        <input class="form-check-input" type="checkbox" id="f-top" ${row.is_top ? "checked" : ""}> 置顶
      </label></div>
    </div>
    <div class="mb-2"><label>标题 *</label>
      <input class="form-control form-control-sm" id="f-title" value="${row.title || ""}" />
    </div>
    <div class="mb-2"><label>摘要</label>
      <input class="form-control form-control-sm" id="f-summary" value="${row.summary || ""}" />
    </div>
    <div class="mb-2"><label>正文 *</label>
      <textarea class="form-control" id="f-content" rows="8">${row.content || ""}</textarea>
    </div>
  `);
  const bs = new bootstrap.Modal($("#editModal")[0]);
  $("#editModalSave").off("click").on("click", function () {
    const payload = {
      category: $("#f-category").val(),
      title: $("#f-title").val().trim(),
      summary: $("#f-summary").val().trim() || ($("#f-content").val() || "").slice(0, 80),
      content: $("#f-content").val(),
      source: $("#f-source").val().trim() || "AgriSense 资讯",
      is_top: $("#f-top").prop("checked"),
    };
    if (!payload.title || !payload.content) { toast("标题与正文不能为空", "error"); return; }
    const url = isEdit ? (API_BASE + "/api/cms/news/" + row.id) : (API_BASE + "/api/cms/news");
    ajax(url, { method: isEdit ? "PUT" : "POST", data: payload, _isJson: true })
      .done(() => { bs.hide(); toast(isEdit ? "已更新" : "已新增"); loadNews(); });
  });
  bs.show();
}

$("#btn-news-add").on("click", () => openNewsForm(null));
$(document).on("click", ".edit-news", function () {
  const id = $(this).data("id");
  ajax(API_BASE + "/api/cms/news").done(list => openNewsForm(list.find(r => r.id === id)));
});
$(document).on("click", ".top-news", function () {
  const id = $(this).data("id"), top = $(this).data("top");
  ajax(API_BASE + "/api/cms/news/" + id + "/top",
       { method: "POST", data: { is_top: !top }, _isJson: true })
    .done(() => { toast("已切换置顶"); loadNews(); });
});
$(document).on("click", ".del-news", function () {
  const id = $(this).data("id"), title = $(this).data("title");
  if (!confirm("确认删除新闻：" + title + "？此操作不可撤销。")) return;
  ajax(API_BASE + "/api/cms/news/" + id, { method: "DELETE" })
    .done(() => { toast("已删除"); loadNews(); });
});

// ---------- 客服留言 ----------
function loadFeedback() {
  ajax(API_BASE + "/api/cms/feedback" + (fbStatusFilter ? "?status=" + fbStatusFilter : "")).done(d => {
    $("#feedback-tbody").html(d.map(r => {
      const statusMap = { pending: "status-pending", resolved: "status-resolved", ignored: "status-ignored" };
      const statusLabel = { pending: "待处理", resolved: "已处理", ignored: "已忽略" }[r.status || "pending"];
      return `
        <tr>
          <td>${r.id}</td>
          <td><span class="status-badge ${statusMap[r.status || "pending"]}">${statusLabel}</span></td>
          <td>${r.name || "匿名"}</td>
          <td>${r.contact || "--"}</td>
          <td>${r.type || "--"}</td>
          <td class="title-cell" title="${(r.message || "").replace(/"/g, '&quot;')}">${r.message || ""}</td>
          <td><small class="text-muted">${r.created_at || ""}</small></td>
          <td>
            ${r.status !== "resolved" ? `<button class="btn btn-xs btn-outline-success fb-reply" data-id="${r.id}" data-message="${(r.message || "").slice(0,50).replace(/"/g,'&quot;')}">处理</button>` : ""}
            <button class="btn btn-xs btn-outline-danger fb-del" data-id="${r.id}">删除</button>
          </td>
        </tr>`;
    }).join("") || '<tr><td colspan="8" class="text-center text-muted py-3">暂无留言</td></tr>');
  });
}

$("#fb-status-group .btn").on("click", function () {
  $("#fb-status-group .btn").removeClass("active");
  $(this).addClass("active");
  fbStatusFilter = $(this).data("status");
  loadFeedback();
});

$(document).on("click", ".fb-reply", function () {
  const id = $(this).data("id");
  const message = $(this).data("message");
  $("#editModalTitle").text("处理客服留言 #" + id);
  $("#editModalBody").html(`
    <div class="mb-2"><label>留言内容</label>
      <div class="p-2 bg-light small rounded">${message}</div>
    </div>
    <div class="mb-2"><label>回复内容</label>
      <textarea class="form-control" id="f-reply" rows="3" placeholder="请输入回复..."></textarea>
    </div>
    <div class="mb-2"><label>处理后状态</label>
      <select class="form-select form-select-sm" id="f-fbstatus">
        <option value="resolved">已处理</option>
        <option value="ignored">已忽略</option>
      </select>
    </div>
  `);
  const bs = new bootstrap.Modal($("#editModal")[0]);
  $("#editModalSave").off("click").on("click", function () {
    ajax(API_BASE + "/api/cms/feedback/" + id + "/mark", {
      method: "POST", _isJson: true,
      data: { status: $("#f-fbstatus").val(), reply: $("#f-reply").val() },
    }).done(() => { bs.hide(); toast("已处理"); loadFeedback(); });
  });
  bs.show();
});

$(document).on("click", ".fb-del", function () {
  const id = $(this).data("id");
  if (!confirm("确认删除该留言？")) return;
  ajax(API_BASE + "/api/cms/feedback/" + id, { method: "DELETE" })
    .done(() => { toast("已删除"); loadFeedback(); });
});

// ---------- 站点信息 ----------
function loadSite() {
  ajax(API_BASE + "/api/cms/site").done(d => {
    $("#site-tbody").html(d.map(r => `
      <tr>
        <td><code>${r.key}</code></td>
        <td>${r.title}</td>
        <td class="title-cell" title="${(r.content || "").replace(/"/g,'&quot;')}">${(r.content || "").slice(0, 80)}${(r.content || "").length > 80 ? "..." : ""}</td>
        <td><small class="text-muted">${r.updated_at || r.created_at || ""}</small></td>
        <td>
          <button class="btn btn-xs btn-outline-primary edit-site" data-key="${r.key}">编辑</button>
          <button class="btn btn-xs btn-outline-danger del-site" data-key="${r.key}">删除</button>
        </td>
      </tr>
    `).join("") || '<tr><td colspan="5" class="text-center text-muted py-3">暂无条目</td></tr>');
  });
}

const SITE_KEY_OPTS = [
  { k: "about", t: "关于我们" },
  { k: "faq", t: "问题解答" },
  { k: "privacy", t: "隐私政策" },
  { k: "service", t: "客服中心" },
  { k: "terms", t: "服务条款" },
  { k: "contact", t: "联系方式" },
];

function openSiteForm(row) {
  row = row || {};
  const isEdit = !!row.key;
  $("#editModalTitle").text(isEdit ? "编辑站点条目" : "新增站点条目");
  const keyOpts = SITE_KEY_OPTS.map(o =>
    `<option value="${o.k}" ${o.k === row.key ? "selected" : ""}>${o.k} — ${o.t}</option>`
  ).join("");
  $("#editModalBody").html(`
    <div class="mb-2 row g-2">
      <div class="col-md-6"><label>Key（唯一标识）</label>
        ${isEdit ? `<input class="form-control form-control-sm" value="${row.key}" disabled />` :
                   `<select class="form-select form-select-sm" id="f-key"><option value="">自定义</option>${keyOpts}</select>`}
      </div>
      <div class="col-md-6"><label>标题</label>
        <input class="form-control form-control-sm" id="f-title" value="${row.title || ""}" />
      </div>
    </div>
    ${isEdit ? "" : `<div class="mb-2"><label>自定义 Key（如选择"自定义"）</label>
      <input class="form-control form-control-sm" id="f-key-custom" placeholder="例如 partners, team..." /></div>`}
    <div class="mb-2"><label>正文（支持纯文本或 Markdown） *</label>
      <textarea class="form-control" id="f-content" rows="10">${row.content || ""}</textarea>
    </div>
  `);
  const bs = new bootstrap.Modal($("#editModal")[0]);
  $("#editModalSave").off("click").on("click", function () {
    let key;
    if (isEdit) key = row.key;
    else {
      key = $("#f-key").val() || $("#f-key-custom").val().trim();
      if (!key) { toast("请选择或填写 Key", "error"); return; }
    }
    const title = $("#f-title").val().trim();
    const content = $("#f-content").val();
    if (!title || !content) { toast("标题与正文不能为空", "error"); return; }
    ajax(API_BASE + "/api/cms/site/" + encodeURIComponent(key), {
      method: "PUT", _isJson: true, data: { title, content },
    }).done(() => { bs.hide(); toast("已保存"); loadSite(); });
  });
  bs.show();
}

$("#btn-site-add").on("click", () => openSiteForm(null));
$(document).on("click", ".edit-site", function () {
  const key = $(this).data("key");
  ajax(API_BASE + "/api/cms/site").done(list => openSiteForm(list.find(r => r.key === key)));
});
$(document).on("click", ".del-site", function () {
  const key = $(this).data("key");
  if (!confirm("确认删除站点条目：" + key + "？此操作不可撤销。")) return;
  ajax(API_BASE + "/api/cms/site/" + encodeURIComponent(key), { method: "DELETE" })
    .done(() => { toast("已删除"); loadSite(); });
});

// ---------- 启动 ----------
$(function () {
  if (!isAdmin()) { showPerm(); return; }
  loadKnowledge();
});
