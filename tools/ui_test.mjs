/**
 * UI 冒烟测试：用 Chrome DevTools Protocol 驱动无头 Chrome，验证离线网页的核心交互。
 * 用法：node tools/ui_test.mjs [页面路径]
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = path.resolve(import.meta.dirname, '..');
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const HTML = path.resolve(process.argv[2] || path.join(ROOT, '计导期中复习.html'));
const PORT = 9333;
const PROFILE = path.join(ROOT, 'tmp', 'ui-profile');
const SHOT_DIR = path.join(ROOT, 'tmp', 'shots');
const W = 1366, H = 768;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
function test(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
}

if (!PROFILE.startsWith(ROOT + path.sep)) throw new Error('Unsafe test profile path');
fs.rmSync(PROFILE, { recursive: true, force: true });
fs.mkdirSync(SHOT_DIR, { recursive: true });
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--no-default-browser-check', '--disable-extensions', '--mute-audio',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`,
  `--window-size=${W},${H}`, 'about:blank'
], { stdio: 'ignore' });

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}
async function waitFor(fn, timeout = 15000, step = 200) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    try { const v = await fn(); if (v) return v; } catch (e) {}
    await sleep(step);
  }
  throw new Error('waitFor timeout');
}

let ws, msgId = 0;
const pending = new Map();
function send(method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('CDP timeout: ' + method)); } }, 20000);
  });
}
async function evaluate(expr) {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('JS error: ' + JSON.stringify(r.exceptionDetails).slice(0, 500));
  return r.result.value;
}
async function shot(name) {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(SHOT_DIR, name + '.png'), Buffer.from(r.data, 'base64'));
}
async function nav(hash) {
  await evaluate(`location.hash = ${JSON.stringify(hash)}`);
  await sleep(450);
}
async function click(selector) {
  const ok = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return false;el.click();return true;})()`);
  if (!ok) throw new Error('找不到元素: ' + selector);
  await sleep(350);
}
async function type(selector, text) {
  await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return false;el.value=${JSON.stringify(text)};el.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`);
  await sleep(600);
}
async function store() {
  return evaluate('JSON.parse(localStorage.getItem("cd_review_v2")||"{}")');
}

try {
  const targets = await waitFor(async () => {
    const list = await getJSON(`http://127.0.0.1:${PORT}/json/list`);
    return list.find((t) => t.type === 'page');
  });
  ws = new WebSocket(targets.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? reject(new Error(m.error.message)) : resolve(m.result);
    } else if (m.method === 'Page.javascriptDialogOpening') {
      send('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
    }
  };
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });

  const url = pathToFileURL(HTML).href;
  await send('Page.navigate', { url });
  await sleep(1500);

  // 1. 页面加载
  const site = await evaluate('window.__SITE__');
  test('页面加载与数据注入', !!site && site.problems > 0, JSON.stringify(site));
  const errBox = await evaluate(`!!Array.from(document.querySelectorAll('div')).find(d=>d.textContent.includes('页面脚本错误'))`);
  test('无脚本错误提示', !errBox);
  test('桌面首页一屏显示', await evaluate('document.documentElement.scrollHeight <= innerHeight'));
  await shot('01-home');

  // 2. 本地存储可用（file:// 下的 localStorage）
  const lsOk = await evaluate(`(()=>{try{localStorage.setItem('__t','1');localStorage.removeItem('__t');return true}catch(e){return false}})()`);
  test('file:// 下 localStorage 可用', lsOk);

  // 3. 题库：分类过滤 + 搜索 + 作答保存 + 状态 + 错题
  await nav('#/library');
  await click('[data-cat="array1"]');
  const count1 = await evaluate(`document.querySelectorAll('#problemList .problem-summary').length`);
  const rc = await evaluate(`document.getElementById('resultCount').textContent`);
  test('分类过滤（一维数组）', count1 > 0, rc);
  await click('[data-cat="all"]');

  const firstId = await evaluate(`document.querySelector('#problemList .problem-summary .p-id').textContent.trim()`);
  await click('#problemList .problem-summary');
  test('单题作答界面', await evaluate('document.querySelectorAll(".practice-main .problem").length === 1 && !!document.querySelector(".practice-nav")'));
  await click('[data-toggle-list]');
  test('收起列表', await evaluate('document.querySelector(".practice-layout").classList.contains("list-collapsed")'));
  await click('[data-toggle-list]');
  await type(`[data-answer="${firstId}"]`, 'int main(){ /* 我的作答 */ return 0; }');
  let s = await store();
  test('作答自动保存到 localStorage', !!(s.answers && s.answers[firstId] && s.answers[firstId].text.includes('我的作答')), firstId);
  await click(`[data-status="${firstId}"][data-v="done"]`);
  s = await store();
  test('掌握状态保存', s.status && s.status[firstId] === 'done');
  await click(`[data-wrong="${firstId}"]`);
  s = await store();
  test('加入错题本记录题号', !!(s.wrong && s.wrong[firstId]), firstId);
  await shot('02-library');

  // 4. 搜索
  await nav('#/library');
  await type('#searchInput', '排序');
  const searchCount = await evaluate(`document.querySelectorAll('#problemList .problem-summary').length`);
  test('搜索过滤', searchCount >= 1 && searchCount <= 10, `命中 ${searchCount} 题`);
  await type('#searchInput', '');

  // 5. 错题本页面
  await nav('#/wrong');
  const wrongPage = await evaluate(`document.body.innerText`);
  test('错题本页面显示题号', wrongPage.includes(firstId), firstId);
  await shot('03-wrong');

  // 6. 速查手册
  await nav('#/cheatsheet');
  const sheet = await evaluate(`document.querySelectorAll('.sheet-section').length`);
  test('速查手册渲染', sheet > 0, `${sheet} 节`);

  // 7. 模拟考试：开始 → 计时 → 作答 → 交卷 → 答案
  await nav('#/exams');
  const examCards = await evaluate(`document.querySelectorAll('[data-start-exam]').length`);
  test('模拟卷列表', examCards >= 6, `${examCards} 套`);
  await click('[data-start-exam]');
  await sleep(600);
  const inRoom = await evaluate(`!!document.querySelector('.exam-room')`);
  test('进入考场', inRoom);
  const timerTxt = await evaluate(`(document.getElementById('examTimer')||{}).textContent`);
  test('倒计时运行', /^\d{2}:\d{2}$/.test(timerTxt || ''), timerTxt);
  const examQid = await evaluate(`document.querySelector('.exam-main .p-id').textContent.trim()`);
  await type(`[data-answer="${examQid}"]`, '/* 模考作答 */');
  await click('[data-exam-no="2"]');
  const q2 = await evaluate(`document.querySelector('.exam-main .p-id').textContent.trim()`);
  test('考场切题', q2 !== examQid, `${examQid} → ${q2}`);
  await shot('04-exam');
  await click('[data-exam-submit]');
  await sleep(500);
  const submitted = await evaluate(`!!document.querySelector('.exam-submitted')`);
  test('交卷后显示参考答案', submitted);
  await shot('05-exam-submitted');

  // 8. 主题切换
  await nav('#/home');
  const before = await evaluate(`document.documentElement.dataset.theme`);
  await click('#themeBtn');
  const after = await evaluate(`document.documentElement.dataset.theme`);
  test('主题切换', before !== after, `${before} → ${after}`);

  // 9. 刷新后记录仍在
  await send('Page.reload');
  await sleep(1400);
  s = await store();
  test('刷新后数据持久化', !!(s.answers && s.answers[firstId] && s.answers[firstId].text.includes('我的作答')));
  await shot('06-home-reload');

  // 10. 汇总
  const kpi = await evaluate(`document.querySelectorAll('.hero .kpi b').length`);
  test('首页统计渲染', kpi === 3, `${kpi} 项`);

} catch (e) {
  test('测试框架异常', false, e.message);
  console.error(e);
} finally {
  try { chrome.kill(); } catch (e) {}
  const failed = results.filter((r) => !r.ok);
  console.log(`\n===== ${results.length - failed.length}/${results.length} 通过 =====`);
  if (failed.length) {
    console.log('失败项：');
    failed.forEach((f) => console.log(' -', f.name, f.detail));
    process.exitCode = 1;
  }
  process.exit(process.exitCode || 0);
}
