// AgriSense 农业知识库页：分类过滤 + 搜索 + 卡片网格 + 阅读弹窗
// 依赖：jQuery、dashboard.js（API_BASE）

let articleModal = null;
let allArticles = [];
let currentCat = "";
let keyword = "";

const CAT_ICON = {
  "种植技术": "bi-flower2",
  "病虫害防治": "bi-bug",
  "水肥管理": "bi-droplet",
  "智慧农业": "bi-cpu",
};

function renderStats() {
  $("#cnt-all").text(allArticles.length);
  $("#cnt-plant").text(allArticles.filter((a) => a.category === "种植技术").length);
  $("#cnt-pest").text(allArticles.filter((a) => a.category === "病虫害防治").length);
  $("#cnt-smart").text(allArticles.filter((a) => a.category === "智慧农业").length);
}

function renderGrid() {
  const list = allArticles.filter((a) => {
    const matchCat = !currentCat || a.category === currentCat;
    const matchKw = !keyword || (a.title || "").includes(keyword);
    return matchCat && matchKw;
  });
  const grid = $("#article-grid");
  if (list.length === 0) {
    grid.html('<div class="col-12 text-center text-muted py-4"><i class="bi bi-inbox"></i> 没有匹配的文章</div>');
    return;
  }
  grid.html(list.map((a) => `
    <div class="col-md-6 col-xl-4">
      <div class="sensor-card k-card h-100" data-id="${a.id}">
        <div class="d-flex align-items-center mb-2">
          <i class="bi ${CAT_ICON[a.category] || 'bi-journal-text'} fs-5 text-success me-2"></i>
          <span class="k-cat">${a.category}</span>
        </div>
        <div class="fw-bold mb-2">${a.title}</div>
        <div class="k-summary mb-3">${a.summary || ""}</div>
        <div class="k-meta d-flex">
          <span><i class="bi bi-person"></i> ${a.author || "--"}</span>
          <span class="ms-3"><i class="bi bi-eye"></i> ${a.views || 0}</span>
          <span class="ms-auto">${(a.created_at || "").slice(0, 10)}</span>
        </div>
      </div>
    </div>
  `).join(""));
}

function openArticle(id) {
  $.get(API_BASE + "/api/knowledge/" + id, function (a) {
    $("#m-title").text(a.title);
    $("#m-cat").text(a.category);
    $("#m-author").html('<i class="bi bi-person"></i> ' + (a.author || "--"));
    $("#m-views").html('<i class="bi bi-eye"></i> ' + (a.views || 0));
    $("#m-date").text((a.created_at || "").slice(0, 10));
    $("#m-content").text(a.content || "");
    articleModal.show();
    // 阅读量已 +1，刷新本地数据
    const local = allArticles.find((x) => x.id === id);
    if (local) local.views = a.views;
    renderGrid();
  });
}

function loadArticles() {
  $.get(API_BASE + "/api/knowledge", function (data) {
    allArticles = data || [];
    renderStats();
    renderGrid();
  });
}

$(document).ready(function () {
  articleModal = new bootstrap.Modal("#article-modal");
  loadArticles();

  $("#cat-filter .btn").on("click", function () {
    $("#cat-filter .btn").removeClass("active");
    $(this).addClass("active");
    currentCat = $(this).data("cat") || "";
    renderGrid();
  });

  $("#search-input").on("input", function () {
    keyword = $(this).val().trim();
    renderGrid();
  });

  $(document).on("click", ".k-card", function () {
    openArticle(parseInt($(this).data("id"), 10));
  });
});
