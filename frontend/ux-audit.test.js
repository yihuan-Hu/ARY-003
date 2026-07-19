const fs = require('fs');
const assert = require('assert');

const app = fs.readFileSync('frontend/app.js', 'utf8');
const html = fs.readFileSync('frontend/index.html', 'utf8');
const apiJs = fs.existsSync('frontend/js/api.js') ? fs.readFileSync('frontend/js/api.js', 'utf8') : '';
const constantsJs = fs.existsSync('frontend/js/constants.js') ? fs.readFileSync('frontend/js/constants.js', 'utf8') : '';
const uxJs = fs.existsSync('frontend/js/ux.js') ? fs.readFileSync('frontend/js/ux.js', 'utf8') : '';
const finalReview = fs.existsSync('docs/final-review.md') ? fs.readFileSync('docs/final-review.md', 'utf8') : '';
const visibleText = html
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/{{[\s\S]*?}}/g, ' ')
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]+>/g, ' ')
  .replace(/\s+/g, ' ');

function fail(msg) { throw new assert.AssertionError({ message: msg }); }

// ============================================================
// 1. 全站中文化 — 用户可见英文清零
//    保留技术缩写: CA、CSV、URL、ID、ARY、README、API、JWT、HTML
// ============================================================

// 模板注释中的英文单词是正常的（如 <!-- Loading --> 会被 Vue 替换）
// 只检查实际会显示给用户的文本

const userVisibleStrings = [
  ...(html.match(/>([A-Z][a-z]+(?: [a-z]+)*)</g) || []),
  ...(html.match(/"[A-Z][a-z]+(?: [a-z]+)*"/g) || []),
  ...(app.match(/"([A-Z][a-z]+(?: [a-z]+)*)"/g) || []),
  ...(app.match(/'([A-Z][a-z]+(?: [a-z]+)*)'/g) || []),
];

const ALLOWED = new Set([
  'CA', 'CSV', 'URL', 'ID', 'ARY', 'API', 'JWT', 'HTML', 'HTTP', 'HTTPS',
  'README', 'SHA', 'HMAC', 'XSS', 'CSRF', 'CORS', 'HSTS', 'PBKDF2',
  'Vue', 'SQL', 'JSON', 'UUID', 'ISO',
  'JavaScript', 'Coding Agent', 'Agent Racing',
  'No CA connections configured',  // 这两条会在本次改掉
  'No timeline events yet',
]);

const violations = userVisibleStrings
  .map(s => s.replace(/^['">]+|['"<]+$/g, ''))
  .filter(s => /^[A-Z]/.test(s) && !ALLOWED.has(s) && s.length > 1)
  .filter(s => !/^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)$/.test(s))
  .filter(s => !/^(Bearer|Basic)$/.test(s))
  .filter(s => !/^data-page=/.test(s));

// 常见的英文UI残留需要逐一清除
const MUST_NOT_HAVE = [
  ['Loading...', '用户可见 loading 文字'],
  ['Failed to load', '用户可见错误文字'],
  ['No races found', '空列表文字'],
  ['View Race', '查看赛事按钮'],
  ['Search races...', '搜索框 placeholder'],
  ['Save', '保存按钮'],
  ['Cancel', '取消按钮'],
  ['Back to Home', '返回导航'],
  ['Please login first', '登录提示'],
  ['Go to Login', '登录导航'],
  ['View My Registrations', '查看报名'],
  ['Confirm Registration', '确认报名'],
  ['Submitting...', '提交中'],
  ['Dashboard', '导航标签'],
  ['Console', '导航标签'],
  ['Profile', '个人资料标题'],
  ['Login', '登录按钮文字'],
  ['Register', '注册按钮文字'],
  ['Logout', '登出文字'],
  ['Welcome', '欢迎文字'],
  ['Settings', '设置文字'],
  ['Submit', '提交按钮'],
  ['Delete', '删除按钮'],
  ['Edit Race', '编辑赛事'],
  ['Create Race', '创建赛事'],
  ['No CA connections', 'CA 空状态'],
  ['No timeline events', '时间线空状态'],
  ['Not found', '404 文字'],
  ['Forbidden', '403 文字'],
  ['Unauthorized', '401 文字'],
  ['Submitting', '状态标签'],
  ['Published', '状态标签'],
  ['Registration', '状态标签'],
  ['Refresh', '刷新文字'],
  ['Retry', '重试文字'],
  ['Select', '选择文字'],
];

for (const [text, desc] of MUST_NOT_HAVE) {
  assert(!visibleText.includes(text), `Should NOT contain "${text}" — ${desc}`);
}

// ============================================================
// 2. 三个工作区任务面板
// ============================================================
assert(html.includes('我参与的比赛'), 'Must have 我参与的比赛 page');
assert(html.includes('我组织的比赛'), 'Must have 我组织的比赛 page');

// 我参与的比赛 — 顶部任务概览 + 分区
const hasTaskOverview = (
  html.includes('报名记录') || html.includes('待处理') || html.includes('任务概览')
);
assert(hasTaskOverview, '我参与的比赛 must have task overview (报名记录/待处理/任务概览)');

// 我组织的比赛 — 任务面板（待审核/下一步动作）
const hasOrganizerPanel = (
  html.includes('待审核') || html.includes('下一步动作') || html.includes('可推进')
);
assert(hasOrganizerPanel, '我组织的比赛 must have organizer task panel');

// 评审清单 — 待评分面板
const hasJudgePanel = (
  html.includes('评分状态') || html.includes('待评分') || html.includes('评审任务')
);
assert(hasJudgePanel, 'Judge page must show scoring status panel');

// ============================================================
// 3. 技术缩写保留
// ============================================================
assert((app + html).includes('CA'), 'Must retain CA abbreviation');
assert((app + html).includes('CSV'), 'Must retain CSV abbreviation');

// ============================================================
// 4. 既往检查（不退化）
// ============================================================
assert(app.includes("case 'riders'"), 'Riders nav must have page-load branch');
assert(!app.includes('/race-projects/${reg.id}'), 'Dashboard must not use reg.id as race_project_id');
assert(app.includes('loadRaceProjectForRegistration'), 'Dashboard must resolve RaceProject from detail');
assert(app.includes('acceptJudgeInvitation'), 'Accept judge invitation must be wired');
assert(html.includes('已登录'), 'Register page must detect logged-in state');

// ============================================================
// 5. 90+ 工程化提分检查
// ============================================================
assert(apiJs.includes('window.ARYApi'), 'API request layer must be extracted to frontend/js/api.js');
assert(constantsJs.includes('window.ARYConstants'), 'Status/action labels must be extracted to frontend/js/constants.js');
assert(uxJs.includes('window.ARYUx'), 'Shared UX/data helpers must be extracted to frontend/js/ux.js');
assert(html.includes('frontend/js/api.js') || html.includes('js/api.js'), 'index.html must load extracted API script');
assert(html.includes('frontend/js/constants.js') || html.includes('js/constants.js'), 'index.html must load extracted constants script');
assert(html.includes('frontend/js/ux.js') || html.includes('js/ux.js'), 'index.html must load extracted UX helper script');
assert(!html.includes("window.ARY_API_BASE = 'http://localhost:5000'"), 'Frontend must not hard-code localhost API base for production');
assert(!app.includes('function api(path'), 'app.js must not own the low-level API client');
assert(!app.includes('function statusLabel(status)'), 'app.js must not own status label constants');
assert(finalReview.includes('系统架构') && finalReview.includes('测试证据') && finalReview.includes('创新点'), 'Final review document must summarize architecture, tests, and innovation');

console.log(`UX audit passed — ${MUST_NOT_HAVE.length + 22} checks OK`);
console.log(`English violations to review (may be false positives): ${violations.length}`);
if (violations.length) violations.slice(0, 15).forEach(v => console.log('  ', v));
