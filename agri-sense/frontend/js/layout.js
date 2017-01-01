// AgriSense 共享布局：侧边栏 + 顶栏注入
// 每个页面在 <body> 中放置 <div id="app-root"></div>，并在加载 layout.js 前定义 window.PAGE_CONFIG

const NAV_ITEMS = [
  { section: "监测" },
  { key: "dashboard", label: "仪表盘", icon: "bi-speedometer2", href: "index.html" },
  { key: "realtime", label: "实时监测", icon: "bi-activity", href: "realtime.html" },
  { key: "history", label: "历史分析", icon: "bi-graph-up-arrow", href: "history.html" },
  { key: "screen", label: "数据大屏", icon: "bi-display", href: "screen.html" },
  { section: "管理" },
  { key: "devices", label: "设备管理", icon: "bi-cpu", href: "devices.html" },
  { key: "irrigation", label: "灌溉管理", icon: "bi-water", href: "irrigation.html" },
  { key: "alerts", label: "告警中心", icon: "bi-bell", href: "alerts.html", badge: true },
  { section: "溯源" },
  { key: "trace", label: "溯源管理", icon: "bi-box-seam", href: "trace.html" },
  { key: "disease", label: "病害识别", icon: "bi-bug", href: "disease.html" },
  { section: "资讯" },
  { key: "knowledge", label: "农业知识库", icon: "bi-book", href: "knowledge.html" },
  { key: "news", label: "农业新闻", icon: "bi-newspaper", href: "news.html" },
  { section: "支持" },
  { key: "about", label: "关于我们", icon: "bi-info-circle", href: "about.html" },
  { key: "service", label: "客服中心", icon: "bi-headset", href: "service.html" },
  { key: "faq", label: "问题解答", icon: "bi-question-circle", href: "faq.html" },
  { key: "privacy", label: "隐私政策", icon: "bi-shield-lock", href: "privacy.html" },
];

function buildSidebar(activeKey) {
  let html = '<aside class="app-sidebar">';
  html += '<div class="sidebar-brand">';
  html += '<i class="bi bi-flower1"></i><span class="title">AgriSense</span>';
  html += '<span class="subtitle">智慧农业监测系统</span></div>';
  html += '<nav class="sidebar-nav">';

  NAV_ITEMS.forEach((item) => {
    if (item.section) {
      html += `<div class="nav-section">${item.section}</div>`;
    } else {
      const active = item.key === activeKey ? "active" : "";
      let badge = "";
      if (item.badge) {
        badge = '<span class="nav-badge" id="nav-alert-count">0</span>';
      }
      html += `<a href="${item.href}" class="nav-item ${active}">`;
      html += `<i class="bi ${item.icon}"></i><span>${item.label}</span>${badge}</a>`;
    }
  });

  html += '</nav>';
  html += '<div class="sidebar-footer">v2.2.0 &copy; 2010 AgriSense<br><a href="mobile.html" target="_blank" class="text-light"><i class="bi bi-phone"></i> 移动端</a></div>';
  html += '</aside>';
  return html;
}

function buildTopbar(title, icon) {
  return `
    <header class="app-topbar">
      <div class="page-title"><i class="bi ${icon}"></i>${title}</div>
      <div class="topbar-right">
        <div class="info-block">
          <small>设备编号</small>
          <div id="top-device">--</div>
        </div>
        <div class="info-block">
          <small>最后更新</small>
          <div id="top-update">--</div>
        </div>
        <div class="d-flex align-items-center">
          <span id="connection-status" class="status-dot offline me-2"></span>
          <small>系统运行中</small>
        </div>
      </div>
    </header>
  `;
}

function buildFooter() {
  return `
    <footer class="app-footer">
      <div class="footer-grid">
        <div class="footer-brand">
          <i class="bi bi-flower1"></i><span class="name">AgriSense 智慧农业</span>
          <p>以物联网、大数据与人工智能技术赋能现代农业，提供环境监测、智能灌溉、
          农产品溯源、病害识别等全链路数字化解决方案，让每一亩土地都用数据说话。</p>
        </div>
        <div class="footer-col">
          <h6>产品中心</h6>
          <a href="index.html">监测仪表盘</a>
          <a href="screen.html">数据大屏</a>
          <a href="trace.html">溯源管理</a>
          <a href="disease.html">病害识别</a>
        </div>
        <div class="footer-col">
          <h6>资讯服务</h6>
          <a href="knowledge.html">农业知识库</a>
          <a href="news.html">农业新闻</a>
          <a href="mobile.html">移动端</a>
        </div>
        <div class="footer-col">
          <h6>支持与帮助</h6>
          <a href="about.html">关于我们</a>
          <a href="service.html">客服中心</a>
          <a href="faq.html">问题解答</a>
          <a href="privacy.html">隐私政策与协议</a>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; 2010 AgriSense 智慧农业科技有限公司 版权所有</span>
        <span>让农业更智慧，让丰收更简单</span>
      </div>
    </footer>
  `;
}

function initLayout() {
  const cfg = window.PAGE_CONFIG || {};
  const root = document.getElementById("app-root");
  if (!root) return;

  const originalContent = root.innerHTML;
  root.innerHTML =
    '<div class="app-layout">' +
    buildSidebar(cfg.key) +
    '<div class="app-main">' +
    buildTopbar(cfg.title || "", cfg.icon || "bi-grid") +
    '<div class="app-content" id="page-content"></div>' +
    buildFooter() +
    "</div></div>";

  document.getElementById("page-content").innerHTML = originalContent;

  // 加载未处理告警数到侧边栏徽标
  $.get(API_BASE + "/api/alerts?status=pending", function (alerts) {
    const count = alerts.length;
    if (count > 0) {
      $("#nav-alert-count").text(count);
    } else {
      $("#nav-alert-count").hide();
    }
  });
}

// 立即执行布局注入（本脚本位于 body 末尾，#app-root 已解析完成）。
// 必须在各页面的 $(document).ready 回调之前完成 DOM 迁移，
// 否则 echarts 等组件会初始化在被 innerHTML 替换掉的旧节点上。
initLayout();
