/* Cancan Microstack docs — shared chrome (topbar + sidebar + language toggle).
   Every page includes this script and sets <body data-page="..."> ; the nav is
   rendered identically across pages so the doc set stays consistent. */
(function () {
  // ---- page registry (grouped) ----
  var GROUPS = [
    { zh: '开始', en: 'Getting Started', items: [
      { id: 'home',         href: 'index.html',                zh: '首页',          en: 'Home' },
      { id: 'quickstart',   href: 'quickstart.html',           zh: '快速开始',      en: 'Quick Start' },
      { id: 'concepts',     href: 'concepts.html',             zh: '核心概念',      en: 'Core Concepts' },
    ]},
    { zh: '架构', en: 'Architecture', items: [
      { id: 'architecture', href: 'architecture.html',         zh: '总体架构',      en: 'Architecture' },
      { id: 'cli',          href: 'cli.html',                  zh: 'CLI 参考',      en: 'CLI Reference' },
      { id: 'python-api',   href: 'python-api.html',           zh: 'Python API',    en: 'Python API' },
    ]},
    { zh: '内置服务', en: 'Services', items: [
      { id: 'controllersrv', href: 'service-controllersrv.html', zh: 'controllersrv', en: 'controllersrv' },
      { id: 'infrasrv',      href: 'service-infrasrv.html',      zh: 'infrasrv',      en: 'infrasrv' },
      { id: 'opsbffsrv',     href: 'service-opsbffsrv.html',     zh: 'opsbffsrv',     en: 'opsbffsrv' },
    ]},
    { zh: '工作流引擎', en: 'Workflow Engine', items: [
      { id: 'wf-concepts',   href: 'workflow-concepts.html',    zh: '概念与状态机',  en: 'Concepts & State' },
      { id: 'wf-nodes',      href: 'workflow-nodes.html',       zh: '节点类型',      en: 'Node Types' },
      { id: 'wf-scheduling', href: 'workflow-scheduling.html',  zh: '调度与编排',    en: 'Scheduling' },
      { id: 'wf-api',        href: 'workflow-api.html',         zh: 'API 参考',      en: 'API' },
    ]},
    { zh: '运维能力', en: 'Operations', items: [
      { id: 'adminops',      href: 'adminops-ui.html',          zh: '运维前端',      en: 'Admin Ops UI' },
      { id: 'caddy',         href: 'caddy.html',                zh: 'Caddy 网关',    en: 'Caddy Gateway' },
      { id: 'registry',      href: 'registry-health.html',      zh: '注册与健康',    en: 'Registry & Health' },
      { id: 'logging',       href: 'logging.html',              zh: '日志管道',      en: 'Logging Pipeline' },
    ]},
    { zh: '参考', en: 'Reference', items: [
      { id: 'data-model',    href: 'data-model.html',           zh: '数据模型',      en: 'Data Model' },
      { id: 'api-reference', href: 'api-reference.html',        zh: 'API 索引',      en: 'API Index' },
      { id: 'deployment',    href: 'deployment.html',           zh: '部署与安全',    en: 'Deployment & Security' },
    ]},
  ];

  var current = document.body.getAttribute('data-page') || 'home';

  function t(o) { return '<span class="zh">' + o.zh + '</span><span class="en">' + o.en + '</span>'; }

  // ---- topbar ----
  var topbar = document.createElement('header');
  topbar.className = 'topbar';
  topbar.innerHTML =
    '<button class="menu-btn" id="menuBtn" aria-label="menu">☰</button>' +
    '<a class="brand" href="index.html"><span class="logo">C</span>Cancan&nbsp;Microstack</a>' +
    '<div class="spacer"></div>' +
    '<div class="toplinks">' +
      '<button class="lang-btn" id="langToggle">EN</button>' +
      '<a href="https://github.com/10000ms/cancan_microstack" target="_blank" rel="noopener">GitHub</a>' +
      '<a href="https://pypi.org/project/cancan-microstack/" target="_blank" rel="noopener">PyPI</a>' +
    '</div>';
  document.body.insertBefore(topbar, document.body.firstChild);

  // ---- sidebar ----
  var sidebar = document.getElementById('sidebar');
  if (sidebar) {
    var html = '';
    GROUPS.forEach(function (g) {
      html += '<h4>' + t(g) + '</h4>';
      g.items.forEach(function (it) {
        var cls = it.id === current ? ' class="active"' : '';
        html += '<a href="' + it.href + '"' + cls + '>' + t(it) + '</a>';
      });
    });
    sidebar.innerHTML = html;
  }

  // ---- language toggle ----
  var body = document.body;
  var btn = document.getElementById('langToggle');
  function setLang(lang) {
    body.classList.remove('lang-zh', 'lang-en');
    body.classList.add('lang-' + lang);
    document.documentElement.lang = lang;
    if (btn) btn.textContent = lang === 'zh' ? 'EN' : '中文';
    try { localStorage.setItem('cancan_lang', lang); } catch (e) {}
  }
  var saved = 'zh';
  try { saved = localStorage.getItem('cancan_lang') || 'zh'; } catch (e) {}
  setLang(saved);
  if (btn) btn.addEventListener('click', function () {
    setLang(body.classList.contains('lang-zh') ? 'en' : 'zh');
  });

  // ---- mobile sidebar toggle ----
  var menuBtn = document.getElementById('menuBtn');
  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', function () { sidebar.classList.toggle('open'); });
  }

  // ---- in-page TOC active highlight (for pages with .toc + sections) ----
  var toc = document.querySelectorAll('.onthispage a');
  if (toc.length) {
    var map = {};
    toc.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      if (document.getElementById(id)) map[id] = a;
    });
    var ids = Object.keys(map);
    function onScroll() {
      var pos = window.scrollY + 110, cur = null;
      ids.forEach(function (id) { var el = document.getElementById(id); if (el && el.offsetTop <= pos) cur = id; });
      toc.forEach(function (a) { a.classList.remove('active'); });
      if (cur && map[cur]) map[cur].classList.add('active');
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
