// AgriSense 农业新闻页：头条 + 分类过滤 + 列表 + 阅读弹窗
// 依赖：jQuery、dashboard.js（API_BASE）

let newsModal = null;
let allNews = [];
let currentCat = "";

const CAT_CLASS = {
  "政策动态": "c-policy",
  "行业动态": "c-industry",
  "科技前沿": "c-tech",
  "市场行情": "c-market",
};

function renderCounts() {
  $("#c-all").text(allNews.length);
  $("#c-policy").text(allNews.filter((n) => n.category === "政策动态").length);
  $("#c-industry").text(allNews.filter((n) => n.category === "行业动态").length);
  $("#c-tech").text(allNews.filter((n) => n.category === "科技前沿").length);
  $("#c-market").text(allNews.filter((n) => n.category === "市场行情").length);
}

function renderHeadline() {
  // 头条取当前过滤下第一条置顶新闻，无置顶则取第一条
  const list = allNews.filter((n) => !currentCat || n.category === currentCat);
  const top = list.find((n) => n.is_top) || list[0];
  const wrap = $("#headline-wrap");
  if (!top) {
    wrap.html('<div class="sensor-card h-100 text-center text-muted py-5">暂无头条</div>');
    return;
  }
  wrap.html(`
    <div class="headline h-100" data-id="${top.id}">
      <span class="tag"><i class="bi bi-lightning-charge"></i> 今日头条</span>
      <h5>${top.title}</h5>
      <div class="sub">${top.summary || ""}</div>
      <div class="mt-3" style="font-size:12px;opacity:.75">
        ${top.category} · ${top.source || ""} · <i class="bi bi-eye"></i> ${top.views || 0} · ${(top.created_at || "").slice(0, 10)}
      </div>
    </div>
  `);
}

function renderList() {
  const list = allNews.filter((n) => !currentCat || n.category === currentCat);
  const box = $("#news-list");
  if (list.length === 0) {
    box.html('<div class="text-center text-muted py-4"><i class="bi bi-inbox"></i> 暂无新闻</div>');
    return;
  }
  box.html(list.map((n) => `
    <div class="news-item" data-id="${n.id}">
      <div class="n-body">
        <div class="n-title">${n.is_top ? '<span class="top-flag">置顶</span>' : ''}${n.title}</div>
        <div class="n-summary">${n.summary || ""}</div>
        <div class="n-meta">
          <span class="n-cat ${CAT_CLASS[n.category] || 'c-industry'}">${n.category}</span>
          <span>${n.source || ""}</span>
          <span class="ms-2"><i class="bi bi-eye"></i> ${n.views || 0}</span>
          <span class="ms-2">${(n.created_at || "").slice(0, 10)}</span>
        </div>
      </div>
    </div>
  `).join(""));
}

function openNews(id) {
  $.get(API_BASE + "/api/news/" + id, function (n) {
    $("#m-title").text(n.title);
    $("#m-cat").html(`<span class="n-cat ${CAT_CLASS[n.category] || 'c-industry'}">${n.category}</span>`);
    $("#m-source").html('<i class="bi bi-rss"></i> ' + (n.source || "--"));
    $("#m-views").html('<i class="bi bi-eye"></i> ' + (n.views || 0));
    $("#m-date").text((n.created_at || "").slice(0, 10));
    $("#m-content").text(n.content || "");
    newsModal.show();
    const local = allNews.find((x) => x.id === id);
    if (local) local.views = n.views;
    renderList();
  });
}

function loadNews() {
  $.get(API_BASE + "/api/news", function (data) {
    allNews = data || [];
    renderCounts();
    renderHeadline();
    renderList();
  });
}

$(document).ready(function () {
  newsModal = new bootstrap.Modal("#news-modal");
  loadNews();

  $("#cat-list .btn").on("click", function () {
    $("#cat-list .btn").removeClass("active");
    $(this).addClass("active");
    currentCat = $(this).data("cat") || "";
    renderHeadline();
    renderList();
  });

  $(document).on("click", ".news-item", function () {
    openNews(parseInt($(this).data("id"), 10));
  });
  $(document).on("click", ".headline", function () {
    const id = parseInt($(this).data("id"), 10);
    if (id) openNews(id);
  });
});
