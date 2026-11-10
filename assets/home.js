window.__HOMEMAP__ = {"cats":{"basic":["A01","A02","A03","A04","A05","A06","A07","A08","A09","A10","A11"],"select":["B01","B02","B03","B04","B05","B06","B07","B08","B09"],"loop":["C01","C02","C03","C04","C05","C06","C07","C08","C09","C10","C11","C12","C13","C14","C15","C16"],"array1":["D01","D02","D03","D04","D05","D06","D07","D08","D09","D10","D11","D12","D13","D14","D15","D16"],"array2":["E01","E02","E03","E04","E05","E06","E07","E08","E09"],"mix":["F01","F02","F03","F04","F05","F06","F07","F08","F09","F10","F11","F12","F13"]},"exams":["M1","M2","M3","M4","M5","M6"]};
/* 主页交互：读取本机 localStorage 记录，刷新 KPI、分类进度与模拟卷状态。
   window.__HOMEMAP__ 由 build_site.py 注入（题号 → 分类的映射）。 */
(function () {
  'use strict';
  var KEY = 'cd_review_v2';
  var HM = window.__HOMEMAP__ || { cats: {}, exams: [] };

  function readStore() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; }
  }
  var store = readStore();
  var answers = store.answers || {};
  var status = store.status || {};
  var wrong = store.wrong || {};

  function answeredCount(ids) {
    var n = 0;
    for (var i = 0; i < ids.length; i++) {
      var a = answers[ids[i]];
      if (a && a.text && String(a.text).trim()) n++;
    }
    return n;
  }
  function doneCount(ids) {
    var n = 0;
    for (var i = 0; i < ids.length; i++) if (status[ids[i]] === 'done') n++;
    return n;
  }

  /* KPI */
  var totalAnswered = 0;
  Object.keys(HM.cats).forEach(function (c) { totalAnswered += answeredCount(HM.cats[c]); });
  var ka = document.getElementById('kpiAnswered');
  if (ka) ka.textContent = totalAnswered;
  var kw = document.getElementById('kpiWrong');
  if (kw) kw.textContent = Object.keys(wrong).length;

  /* 分类卡片进度条 */
  var cards = document.querySelectorAll('[data-cat-card]');
  for (var i = 0; i < cards.length; i++) {
    var cat = cards[i].getAttribute('data-cat-card');
    var ids = HM.cats[cat] || [];
    var a = answeredCount(ids), d = doneCount(ids);
    var bar = cards[i].querySelector('.bar > i');
    if (bar) bar.style.width = (ids.length ? Math.round(a * 100 / ids.length) : 0) + '%';
    var txt = cards[i].querySelector('[data-cat-progress]');
    if (txt) txt.textContent = a + '/' + ids.length + ' 已做 · ' + d + ' 已掌握';
  }

  /* 模拟卷状态 */
  var exams = store.exams || {};
  var tiles = document.querySelectorAll('[data-exam-tile]');
  for (var j = 0; j < tiles.length; j++) {
    var id = tiles[j].getAttribute('data-exam-tile');
    var ses = exams[id];
    var pill = tiles[j].querySelector('[data-exam-status]');
    if (!pill) continue;
    if (ses && ses.submittedAt) { pill.textContent = '已交卷'; pill.className = 'pill ok'; }
    else if (ses) { pill.textContent = '进行中'; pill.className = 'pill warn'; }
    else { pill.textContent = '未开始'; pill.className = 'pill'; }
  }
})();
