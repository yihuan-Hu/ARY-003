const sampleData = window.ARY_SAMPLE_DATA;
const pageButtons = document.querySelectorAll("[data-page]");
const pagePanels = document.querySelectorAll("[data-page-panel]");
let currentHomeRaceId = sampleData?.raceGroups?.featuredRaceId;
let homeRaceCarouselTimer;

function setPage(pageName) {
  pagePanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.pagePanel === pageName);
  });
  pageButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.page === pageName);
  });
  requestAnimationFrame(resizeAll);
}

function getRace(id) {
  return sampleData?.races?.find((race) => race.id === id);
}

function getWork(id) {
  return sampleData?.works?.find((work) => work.id === id);
}

function getRider(id) {
  return sampleData?.riders?.find((rider) => rider.id === id);
}

function getProjection(raceId) {
  return sampleData?.liveProjections?.find((projection) => projection.raceId === raceId);
}

function statusText(status) {
  return {
    registration: "报名中",
    running: "进行中",
    judging: "评审中",
    completed: "已完成",
    archived: "已归档",
    upcoming: "即将开放",
  }[status] || status;
}

function domainText(domain) {
  return {
    "self-dogfood": "Self-dogfood",
    travel: "大湾区旅行",
    finance: "金融投研",
    commerce: "网商网购",
    health: "健康管理",
    government: "电子政务",
    medical: "医疗随访",
    media: "自媒体运营",
    "e-commerce": "网商网购",
    "content-ops": "自媒体运营",
  }[domain] || domain;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const resultCardCopy = {
  "genesis-dogfood-race": "第一场创世赛跑出了平台自己的起点，也留下了可以反复观看的冲线样本。",
  "gov-service-navigator": "把复杂办事路线跑成一张清晰通关图，让严肃场景也有了可展示的赛道作品。",
  "merchant-copilot": "小店主的选品、上新和复盘节奏被带进赛场，等待第一批 Rider 入场。",
  "health-habit-coach": "运动、睡眠和饮食被拆成每日可坚持的小目标，健康赛道正在集结。",
  "media-ops-agent": "选题、脚本、发布和复盘都已交卷，评审席正在寻找最稳的内容节奏。",
  "medical-followup-assistant": "随访提醒、复诊准备和问题清单即将开跑，医疗赛道保持克制而清晰。",
};

function text(selector, value) {
  const node = document.querySelector(selector);
  if (node && value !== undefined && value !== null) node.textContent = value;
}

function html(selector, value) {
  const node = document.querySelector(selector);
  if (node && value !== undefined && value !== null) node.innerHTML = value;
}

const homeRaceAssets = {
  "bay-area-happy-trip": {
    workTitle: "GBA WanderMate",
    workMeta: "湾区开心游 / Mira Chen / 三条湾区路线已经上墙：早茶、海岸、夜景，预算和交通都标清。",
    riderName: "Mira Chen",
    riderMeta: "HKU CS / local reasoning / route planning / prompt debugging",
  },
  "smart-investment-analyst": {
    workTitle: "Risk Briefing Notebook",
    workMeta: "智能投研助理 / Owen Xu / 财报摘要、风险边界和术语解释已进入作品墙。",
    riderName: "Owen Xu",
    riderMeta: "FinTech Studio / financial literacy / risk explanation / retrieval",
  },
};

function renderHomeRace(raceId) {
  const race = getRace(raceId);
  if (!race) return;
  currentHomeRaceId = race.id;
  const projection = getProjection(race.id);
  const submitLabel = race.live?.submitLeft || "提交开放";
  const riskSignals = projection?.headlineMetrics?.riskSignals ?? race.live?.riskSignals ?? 0;
  const asset = homeRaceAssets[race.id] || homeRaceAssets["bay-area-happy-trip"];

  html(".hero-copy h1", escapeHtml(race.title));
  text(".hero-subtitle", `赛题：${race.challenge}`);
  html(
    ".hero-meta",
    `<span><b>${race.metrics.riders}</b> riders</span>
     <span><b>${race.metrics.activeRiders}</b> active</span>
     <span><b>${race.metrics.submittedWorks}</b> works</span>
     <span><b>${riskSignals}</b> signals</span>`,
  );
  html(
    ".hero-actions",
    `<button type="button" data-page="live">${escapeHtml(race.primaryCta)}</button>
     <button type="button" data-page="race">查看赛题</button>`,
  );
  html(
    ".benefit-row",
    `<article>
       <span class="icon-card">Work</span>
       <div>
         <h2>${escapeHtml(asset.workTitle)}</h2>
         <p>${escapeHtml(asset.workMeta)}</p>
         <button type="button" data-page="works">查看作品</button>
       </div>
     </article>
     <article>
       <span class="icon-card">Rider</span>
       <div>
         <h2>${escapeHtml(asset.riderName)}</h2>
         <p>${escapeHtml(asset.riderMeta)}</p>
         <button type="button" data-page="rider">查看档案</button>
       </div>
     </article>`,
  );
  document.querySelectorAll("[data-live-race]").forEach((button) => {
    button.classList.toggle("active", button.dataset.liveRace === race.id);
    button.setAttribute("aria-current", button.dataset.liveRace === race.id ? "true" : "false");
  });
}

function renderHomeLiveSwitcher() {
  html(
    ".hero-live-switcher",
    `${sampleData.raceGroups.liveRaceIds
       .map((raceId, index) => {
         const race = getRace(raceId);
         return `<button class="${index === 0 ? "active" : ""}" type="button" data-live-race="${escapeHtml(race.id)}" aria-label="切换到${escapeHtml(race.title)}" aria-current="${index === 0 ? "true" : "false"}"></button>`;
       })
       .join("")}`,
  );
}

function rotateHomeLiveRace() {
  const liveRaceIds = sampleData?.raceGroups?.liveRaceIds || [];
  if (liveRaceIds.length < 2 || !document.querySelector(".page-home.active")) return;
  const currentIndex = Math.max(0, liveRaceIds.indexOf(currentHomeRaceId));
  const nextRaceId = liveRaceIds[(currentIndex + 1) % liveRaceIds.length];
  renderHomeRace(nextRaceId);
  requestAnimationFrame(resizeAll);
}

function restartHomeRaceCarousel() {
  window.clearInterval(homeRaceCarouselTimer);
  homeRaceCarouselTimer = window.setInterval(rotateHomeLiveRace, 6800);
}

// ---- Works 筛选（全局作用域，供点击事件调用） ----

var allWorksFilter = [];

function renderWorkCards(works) {
  html(
    ".work-grid",
    works
      .map(function (work) {
        var race = getRace(work.raceId);
        var badge = "作品";
        if (work.awardIds && work.awardIds.length) badge = "已获奖";
        else if (race && race.status === "judging") badge = "评审中";
        else if (work.status === "submitted" || work.status === "published") badge = "精选";
        var heroClass = badge === "精选" ? " hero-work" : "";
        return '<article class="work-card' + heroClass + '"><span>' + badge + '</span><h2>' + escapeHtml(work.title) + '</h2><p>' + escapeHtml(work.summary) + '</p><b>' + escapeHtml(race ? race.title : "") + ' / ' + escapeHtml(work.status) + '</b><button type="button">查看详情</button></article>';
      })
      .join(""),
  );
}

function renderWorksFiltered(filterText) {
  var filtered;
  if (filterText === "精选") {
    filtered = allWorksFilter.filter(function (w) {
      return w.status === "submitted" || w.status === "published" || (w.awardIds && w.awardIds.length);
    });
  } else if (filterText === "已获奖") {
    filtered = allWorksFilter.filter(function (w) { return w.awardIds && w.awardIds.length; });
  } else if (filterText === "评审中") {
    filtered = allWorksFilter.filter(function (w) { var r = getRace(w.raceId); return r && r.status === "judging"; });
  } else {
    filtered = allWorksFilter;
  }
  renderWorkCards(filtered);
}

function renderPrototypeData() {
  if (!sampleData) return;

  const featuredRace = getRace(sampleData.raceGroups.featuredRaceId);
  const featuredProjection = getProjection(featuredRace.id);
  const genesisRace = getRace("genesis-dogfood-race");
  const govRace = getRace("gov-service-navigator");
  const mediaRace = getRace("media-ops-agent");
  const medicalRace = getRace("medical-followup-assistant");
  const merchantRace = getRace("merchant-copilot");
  const healthRace = getRace("health-habit-coach");
  const profile = sampleData.profiles[0];
  const awardedWork = getWork("work-ary-forge");

  renderHomeLiveSwitcher();
  renderHomeRace(featuredRace.id);
  text(".featured-race .card-head span", "Open Registration");
  text(".featured-race .card-head b", "Open");
  text(".featured-race h3", merchantRace.title);
  text(".featured-race p", "小商家经营 Agent 赛道正在报名，选品、上新、客服和复盘将进入下一轮 Race。");
  html(
    ".featured-race .mini-stats",
    `<span><b>${merchantRace.metrics.applicants}</b> applicants</span>
     <span><b>${merchantRace.metrics.capacity}</b> seats</span>
     <span><b>Open</b> status</span>`,
  );
  html(
    ".featured-race .card-actions",
    `<button type="button" data-page="cooperation">报名入口</button>
     <button type="button" data-page="cooperation">办赛合作</button>`,
  );
  html(
    ".latest-results-list",
    `<div class="card-head"><span>Latest Results</span><b>Published</b></div>
     <div><span>${escapeHtml(genesisRace.title)}</span><b>最佳自举作品</b></div>
     <div><span>${escapeHtml(govRace.title)}</span><b>最佳可信流程</b></div>`,
  );
  html(
    ".past-races-list",
    `<div class="card-head"><span>Past Races</span><b>Archive</b></div>
     <div><span>${escapeHtml(mediaRace.title)}</span><b>${statusText(mediaRace.status)}</b></div>
     <div><span>${escapeHtml(medicalRace.title)}</span><b>${statusText(medicalRace.status)}</b></div>`,
  );
  html(
    ".cooperation-teaser",
    `<div class="card-head"><span>开放报名 / 合作入口</span><b>Open</b></div>
     <div><span>${escapeHtml(merchantRace.title)}</span><b>${statusText(merchantRace.status)}</b></div>
     <div><span>${escapeHtml(healthRace.title)}</span><b>${statusText(healthRace.status)}</b></div>`,
  );

  text(".page-race .section-kicker", `${featuredRace.title} / 正在骑行 / 作品提交开放`);
  text(".race-hero-panel h1", "让 Agent 带你玩转大湾区");
  text(".race-summary", "从早茶、海岸线、展馆到夜色街区，Rider 正在训练自己的旅行 Agent，把一次周末出发变成可展示的智能体作品。");
  html(
    ".race-state-grid",
    `<article class="state-card active"><span>报名席</span><b>已锁定</b><p>${featuredRace.metrics.riders} 位 Rider 入场</p></article>
     <article class="state-card active"><span>赛道</span><b>进行中</b><p>${featuredRace.metrics.activeRiders} 位正在骑行</p></article>
     <article class="state-card active"><span>提交</span><b>开放</b><p>剩余 ${featuredRace.live.submitLeft}</p></article>
     <article class="state-card"><span>评审席</span><b>待开席</b><p>18 份作品待分配</p></article>
     <article class="state-card"><span>颁奖</span><b>未揭晓</b><p>冠军席仍在等待</p></article>`,
  );
  html(
    ".race-content-grid",
    `<article class="glass-card"><span>今日赛题</span><h2>一日湾区畅游</h2><p>早茶路线、亲子馆展、海边日落，都要有理由、有预算、有备用方案。</p></article>
     <article class="glass-card"><span>赛程</span><h2>4 小时冲刺</h2><p>10:00 开跑，14:00 冲刺，16:00 前把 Demo、路线故事和亮点片段送上作品墙。</p></article>
     <article class="glass-card"><span>骑手阵容</span><h2>${featuredRace.metrics.riders} 名 Rider</h2><p>${featuredRace.metrics.activeRiders} 位在线，${featuredRace.live.costWatchRiders} 位进入成本观察，${featuredRace.live.riskSignals} 个现场提醒。</p></article>
     <article class="glass-card"><span>现场看点</span><h2>路线、预算、惊喜点</h2><p>每隔几分钟，赛道都会冒出新的路线、分数和即将冲线的作品。</p></article>`,
  );

  text(".page-live .page-label span", "Live Hall / Riding Now");
  text(".page-live .section-kicker", `${featuredRace.title} / 现场骑行`);
  text(".page-live .live-header h1", `${featuredRace.title} Agent 正在骑行`);
  html(
    ".live-metrics",
    `<article><span>Riders</span><b>${featuredRace.metrics.riders} / ${featuredRace.metrics.activeRiders} active</b><p>湾区赛道保持高速。</p></article>
     <article><span>Records</span><b>${featuredRace.metrics.sessions}</b><p>路线、问答、修正和作品片段持续进场。</p></article>
     <article><span>Cost</span><b>${featuredRace.live.totalCost}</b><p>${featuredRace.live.costWatchRiders} 位 Rider 需要控制预算。</p></article>
     <article><span>Signals</span><b>${featuredRace.live.riskSignals} alerts</b><p>冲线、停滞、成本和提交提醒。</p></article>`,
  );
  html(
    ".event-stream",
    featuredProjection.eventStream.map((event) => `<article><b>${escapeHtml(event.time)}</b><span>${escapeHtml(event.text)}</span></article>`).join(""),
  );
  html(
    ".leaderboard-panel ol",
    featuredProjection.processLeaderboard
      .map((item) => `<li><span>${String(item.rank).padStart(2, "0")}</span><b>${escapeHtml(item.name)}</b><em>${item.score}</em></li>`)
      .join(""),
  );

  // 初始渲染全部作品
  allWorksFilter = ["work-gba-wander", "work-localjoy", "work-ary-forge", "work-media-loop"].map(getWork);
  renderWorkCards(allWorksFilter);

  text(".page-works .module-title .section-kicker", "湾区开心游 / 作品墙");
  text(".page-works .module-title h1", "湾区开心游作品墙");
  text(".page-works .module-summary", "4 个作品 / 2 个已完成 / 1 个评审中");
  html(
    ".asset-matrix",
    `<h2>作品橱窗</h2>
     <div><span>主作品</span><b>名称 / Rider / 赛道</b></div>
     <div><span>Demo 展示</span><b>可观看片段</b></div>
     <div><span>路线故事</span><b>从想法到结果</b></div>
     <div><span>亮点时刻</span><b>关键突破记录</b></div>
     <div><span>评委摘录</span><b>可公开反馈</b></div>`,
  );

  text(".page-results .module-title .section-kicker", `${genesisRace.title} / 已发布`);
  text(".page-results .module-title h1", "创世骑行挑战赛赛果");
  text(".page-results .module-summary", "1 个冠军作品 / 3 个入围作品 / 164 个现场片段");
  html(
    ".award-grid",
    `<article class="award-card result-card--completed">
       <span>最佳自举作品</span>
       <b>ARY Forge Console</b>
       <p>${escapeHtml(genesisRace.title)} / Sara Li</p>
       <div class="award-meta"><em>${escapeHtml(domainText(genesisRace.domain))}</em><em>${statusText(genesisRace.status)}</em><em>${genesisRace.metrics.evidenceRefs} highlights</em></div>
       <small>${escapeHtml(resultCardCopy[genesisRace.id])}</small>
     </article>
     <article class="award-card">
       <span>入围作品</span>
       <b>Genesis Track Kit</b>
       <p>创世骑行挑战赛 / Team Blue</p>
       <div class="award-meta"><em>Shortlist</em><em>Top 3</em><em>42 highlights</em></div>
       <small>把第一场比赛的节奏、作品和点评都留了下来。</small>
     </article>
     <article class="award-card">
       <span>骑行能力亮点</span>
       <b>成本控制 / 纠偏 / 协作</b>
       <p>Sara Li / 26 sessions</p>
       <div class="award-meta"><em>Skill</em><em>92%</em><em>$38.20</em></div>
       <small>Sara Li 在三项能力维度保持稳定。</small>
     </article>
     <article class="award-card">
       <span>评审总结</span>
       <b>Review 已发布</b>
       <p>3 个高光案例 / 2 条评委摘录</p>
       <div class="award-meta"><em>Report</em><em>Published</em><em>164 refs</em></div>
       <small>复盘内容进入 Review 页面，不混入进行中赛事。</small>
     </article>`,
  );
  html(
    ".result-aside",
    `<h2>Winning Works</h2>
     <div><b>01</b><span>ARY Forge Console</span><em>Winner</em></div>
     <div><b>02</b><span>Genesis Track Kit</span><em>Shortlist</em></div>
     <div><b>03</b><span>Review Board</span><em>Shortlist</em></div>
     <button type="button" data-page="review">查看 Review</button>`,
  );

  const review = sampleData.reviews.find((item) => item.raceId === genesisRace.id);
  text(".page-review .section-kicker", `${genesisRace.title} / 已发布`);
  text(".page-review .module-title h1", "创世骑行挑战赛复盘");
  text(".page-review .module-summary", `${review.featuredCases.length} 个高光案例 / ${review.judgeComments.length} 条评委摘录 / ${genesisRace.metrics.evidenceRefs} 个现场片段`);
  text(".quote-card p", "我们希望最后留下的，不是一句“我用过 AI 写代码”，而是一份能被打开、被观看、被继续追赶的赛场作品。");
  html(
    ".review-card-grid",
    `<article><span>冠军理由</span><b>ARY Forge 的冲线瞬间</b><p>${escapeHtml(resultCardCopy[genesisRace.id])}</p></article>
     <article><span>高光案例</span><b>${review.featuredCases.length} 个创世故事</b><p>${review.featuredCases.map(escapeHtml).join(" / ")}</p></article>
     <article><span>评委摘录</span><b>${review.judgeComments.length} 条公开点评</b><p>${escapeHtml(review.judgeComments[0])}</p></article>
     <article><span>现场片段</span><b>${genesisRace.metrics.evidenceRefs} 个高光记录</b><p>从混沌起跑到产品成形，关键节点都被留下。</p></article>
     <article><span>下一场</span><b>${escapeHtml(featuredRace.title)}</b><p>旅行赛道正在进行，优秀作品会进入下一轮展示。</p></article>`,
  );

  text(".page-rider .module-title .section-kicker", "Rider / 湾区开心游");
  text(".page-rider .module-title h1", profile.displayName);
  text(".page-rider .module-summary", `${profile.stats.projects} projects / ${profile.stats.sessions} sessions / ${profile.stats.completion} completion`);
  text(".profile-card h2", profile.displayName);
  text(".profile-card p", profile.headline);
  html(
    ".profile-stats",
    `<span><b>${profile.stats.projects}</b> projects</span><span><b>${profile.stats.sessions}</b> sessions</span><span><b>${profile.stats.completion}</b> completion</span>`,
  );
  html(
    ".portfolio-grid",
    `<article><span>Race checkpoint</span><b>${escapeHtml(featuredRace.title)}</b></article>
     <article><span>项目作品</span><b>${escapeHtml(getWork(profile.featuredWorkIds[0])?.title || "Featured Work")}</b></article>
     <article><span>Riding Replay</span><b>Route correction replay</b></article>
     <article><span>过程记录</span><b>偏好建模 → 路线验证</b></article>
     <article><span>评审反馈</span><b>产品清晰，拆解到位</b></article>
     <article><span>能力标签</span><b>${profile.skillTags.slice(0, 3).map(escapeHtml).join(" / ")}</b></article>
     <article><span>成本控制</span><b>$42.80 / 稳定</b></article>
     <article><span>风险处理</span><b>2 次路线纠偏</b></article>`,
  );

  text(".page-cooperation .section-kicker", "报名 / 办赛 / 赞助");
  text(".page-cooperation .module-title h1", "下一场 Race 如何加入");
  text(".page-cooperation .module-summary", `${merchantRace.title} 与 ${healthRace.title} 正在报名；企业、学校和社区可以发起自己的 Agent Racing 赛道。`);
  html(
    ".cooperation-grid",
    `<article class="glass-card"><span>报名参赛</span><h2>${escapeHtml(merchantRace.title)}</h2><p>${escapeHtml(merchantRace.summary)}</p><button type="button" data-page="race">${escapeHtml(merchantRace.secondaryCta)}</button></article>
     <article class="glass-card"><span>发起赛事</span><h2>定制 Race Track</h2><p>围绕真实业务挑战组织 Rider、评委、作品墙和现场展示。</p><button type="button" data-page="console">进入工作台</button></article>
     <article class="glass-card"><span>赞助合作</span><h2>${escapeHtml(awardedWork.title)}</h2><p>支持赛题、奖项、导师点评和赛后公开资产沉淀。</p><button type="button" data-page="home">返回赛事</button></article>`,
  );

  text(".console-main .section-kicker", `Organizer View / ${featuredRace.title}`);
  text(".console-main h1", "湾区开心游指挥席");
  html(
    ".ops-grid",
    `<article><span>赛道</span><b>Running</b><p>作品提交开放</p></article>
     <article><span>报名席</span><b>${featuredRace.metrics.riders} / 41</b><p>Rider 已入场</p></article>
     <article><span>连接</span><b>34 / ${featuredRace.metrics.riders}</b><p>2 位证据缺口</p></article>
     <article><span>作品</span><b>${featuredRace.metrics.submittedWorks}</b><p>已上墙</p></article>
     <article><span>评审风险</span><b>6</b><p>待评审前检查</p></article>
     <article><span>播报</span><b>draft</b><p>赛后整理中</p></article>`,
  );
  const tasks = sampleData.consoleTasks.find((task) => task.raceId === featuredRace.id)?.items || [];
  html(".ops-table", tasks.map((task) => `<div><b>${escapeHtml(task.label)}</b><span>${task.count}</span><em>${escapeHtml(task.severity)}</em></div>`).join(""));

  text(".screen-top span", `${featuredRace.title} / Bay Area Happy Trip`);
  text(".screen-output h1", "Live Riding Board");
  html(
    ".screen-metrics",
    `<span><b>${featuredRace.metrics.activeRiders}</b> active riders</span>
     <span><b>${featuredRace.metrics.sessions}</b> sessions</span>
     <span><b>${featuredRace.live.costWatchRiders}</b> cost watch</span>
     <span><b>${featuredRace.live.submitLeft}</b> submit left</span>`,
  );
  text(".screen-control h2", "Display Preview");
  text(".screen-control div span", "Output only");
  text(".screen-control div b", "由 Screen Console 控制");
  text(".screen-control div p", "本页只表达现场输出，控制面保留在工作台。");
}

document.addEventListener("click", (event) => {
  const liveRaceButton = event.target.closest("[data-live-race]");
  if (liveRaceButton) {
    renderHomeRace(liveRaceButton.dataset.liveRace);
    restartHomeRaceCarousel();
    requestAnimationFrame(resizeAll);
    return;
  }

  const galleryDrawerButton = event.target.closest("[data-gallery-drawer-toggle]");
  if (galleryDrawerButton) {
    const drawer = galleryDrawerButton.closest(".gallery-drawer");
    const shouldOpen = !drawer.classList.contains("open");
    drawer.classList.toggle("open", shouldOpen);
    drawer.querySelectorAll("[data-gallery-drawer-toggle]").forEach((button) => {
      button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    });
    return;
  }

  const worksFilter = event.target.closest(".works-toolbar button");
  if (worksFilter) {
    document.querySelectorAll(".works-toolbar button").forEach(function (btn) { btn.classList.remove("active"); });
    worksFilter.classList.add("active");
    renderWorksFiltered(worksFilter.textContent.trim());
    return;
  }

  const button = event.target.closest("[data-page]");
  if (!button) return;
  setPage(button.dataset.page);
});

const canvases = [
  { node: document.querySelector("#homeCanvas"), theme: "home" },
  { node: document.querySelector("#liveCanvas"), theme: "live" },
  { node: document.querySelector("#screenCanvas"), theme: "screen" },
].filter((item) => item.node);

const riderColors = ["#075bec", "#13a7ff", "#ffb12b", "#ff4b72"];
const riders = (sampleData?.riders || [])
  .filter((rider) => rider.raceId === sampleData?.raceGroups?.featuredRaceId)
  .slice(0, 4)
  .map((rider, index) => ({
    name: rider.name.split(" ")[0],
    color: riderColors[index] || "#075bec",
    lane: 0.18 + index * 0.2,
    speed: 0.0001 - index * 0.000008,
    phase: 0.08 + index * 0.22,
  }));

function resizeCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * scale));
  canvas.height = Math.max(1, Math.floor(rect.height * scale));
  canvas.getContext("2d").setTransform(scale, 0, 0, scale, 0, 0);
}

function resizeAll() {
  canvases.forEach(({ node }) => resizeCanvas(node));
}

function racePoint(progress, lane, width, height, theme) {
  const yBase = theme === "home" ? 0.63 : 0.55;
  return {
    x: width * (0.06 + progress * 0.88),
    y:
      height *
      (yBase +
        Math.sin(progress * Math.PI * 2.8 + lane * 3.6) * 0.16 +
        Math.cos(progress * Math.PI * 1.35) * 0.08 +
        (lane - 0.5) * 0.18),
  };
}

function drawSpeedLines(ctx, width, height, dark) {
  ctx.save();
  ctx.globalAlpha = dark ? 0.42 : 0.3;
  for (let i = 0; i < 34; i += 1) {
    const y = height * (0.12 + i * 0.026);
    const start = -width * 0.12 + i * 17;
    const end = width * (0.92 + (i % 6) * 0.02);
    const gradient = ctx.createLinearGradient(start, y, end, y - 60);
    gradient.addColorStop(0, "rgba(22,140,255,0)");
    gradient.addColorStop(0.45, dark ? "rgba(48,216,255,0.42)" : "rgba(22,140,255,0.26)");
    gradient.addColorStop(1, "rgba(22,140,255,0)");
    ctx.strokeStyle = gradient;
    ctx.lineWidth = i % 5 === 0 ? 5 : 2;
    ctx.beginPath();
    ctx.moveTo(start, y);
    ctx.lineTo(end, y - height * 0.22);
    ctx.stroke();
  }
  ctx.restore();
}

function drawBackground(ctx, width, height, theme) {
  const dark = theme === "screen";
  ctx.clearRect(0, 0, width, height);
  const bg = ctx.createLinearGradient(0, 0, width, height);
  bg.addColorStop(0, dark ? "#06164a" : "#ffffff");
  bg.addColorStop(0.55, dark ? "#08215f" : "#eef7ff");
  bg.addColorStop(1, dark ? "#02091e" : "#dcecff");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);
  drawSpeedLines(ctx, width, height, dark);

  const horizon = dark ? height * 0.7 : height * 0.62;
  ctx.strokeStyle = dark ? "rgba(255,255,255,0.16)" : "rgba(7,91,236,0.18)";
  ctx.lineWidth = 2;
  for (let i = 0; i < 10; i += 1) {
    ctx.beginPath();
    ctx.moveTo(width * 0.04, horizon + i * 18);
    ctx.quadraticCurveTo(width * 0.52, horizon - 110 + i * 6, width * 0.96, horizon + i * 22);
    ctx.stroke();
  }
}

function drawTrack(ctx, width, height, theme) {
  const dark = theme === "screen";
  ctx.strokeStyle = dark ? "rgba(48,216,255,0.72)" : "rgba(7,91,236,0.52)";
  ctx.lineWidth = theme === "screen" ? 6 : 4;
  ctx.beginPath();
  ctx.moveTo(width * 0.08, height * 0.82);
  ctx.bezierCurveTo(width * 0.24, height * 0.22, width * 0.48, height * 0.86, width * 0.68, height * 0.42);
  ctx.bezierCurveTo(width * 0.78, height * 0.22, width * 0.88, height * 0.44, width * 0.95, height * 0.26);
  ctx.stroke();
}

function drawRiderMarker(ctx, rider, width, height, time, theme, index) {
  const dark = theme === "screen";
  const progress = (rider.phase + time * rider.speed) % 1;
  const point = racePoint(progress, rider.lane, width, height, theme);
  const tail = racePoint(Math.max(0, progress - 0.09), rider.lane, width, height, theme);
  const radius = theme === "screen" ? 16 : 11;
  const trail = ctx.createLinearGradient(tail.x, tail.y, point.x, point.y);
  trail.addColorStop(0, "rgba(255,255,255,0)");
  trail.addColorStop(1, rider.color);
  ctx.strokeStyle = trail;
  ctx.lineWidth = theme === "screen" ? 8 : 5;
  ctx.beginPath();
  ctx.moveTo(tail.x, tail.y);
  ctx.lineTo(point.x, point.y);
  ctx.stroke();
  ctx.fillStyle = "rgba(255,255,255,0.95)";
  ctx.beginPath();
  ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = rider.color;
  ctx.lineWidth = 5;
  ctx.stroke();
  ctx.fillStyle = dark ? "#ffffff" : "#06164a";
  ctx.font = `950 ${theme === "screen" ? 24 : 15}px Arial, sans-serif`;
  ctx.fillText(rider.name, point.x + radius + 8, point.y - radius - index);
}

function drawOverlay(ctx, width, height, time, theme) {
  const dark = theme === "screen";
  const signal = Math.round((getRace(sampleData.raceGroups.featuredRaceId)?.live?.ridingSignal || 75) + Math.sin(time / 560) * 4);
  const cardX = theme === "home" ? 28 : 24;
  const cardY = theme === "home" ? 36 : 24;
  const labelY = cardY + (theme === "screen" ? 34 : 26);
  const valueY = cardY + (theme === "screen" ? 80 : 59);
  ctx.fillStyle = dark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.82)";
  ctx.strokeStyle = dark ? "rgba(255,255,255,0.24)" : "rgba(7,91,236,0.22)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(cardX, cardY, theme === "screen" ? 270 : 180, theme === "screen" ? 112 : 78, 4);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = dark ? "#bfe3ff" : "#075bec";
  ctx.font = `950 ${theme === "screen" ? 15 : 12}px Arial, sans-serif`;
  ctx.fillText("RIDING SIGNAL", cardX + 18, labelY);
  ctx.fillStyle = dark ? "#ffffff" : "#075bec";
  ctx.font = `950 italic ${theme === "screen" ? 48 : 30}px Arial, sans-serif`;
  ctx.fillText(`${signal}%`, cardX + 18, valueY);
  text("#signalValue", `${signal}%`);
}

function drawFrame(time) {
  canvases.forEach(({ node, theme }) => {
    const rect = node.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const ctx = node.getContext("2d");
    drawBackground(ctx, rect.width, rect.height, theme);
    drawTrack(ctx, rect.width, rect.height, theme);
    riders.forEach((rider, index) => drawRiderMarker(ctx, rider, rect.width, rect.height, time, theme, index));
    drawOverlay(ctx, rect.width, rect.height, time, theme);
  });
  requestAnimationFrame(drawFrame);
}

if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function roundRect(x, y, width, height, radius) {
    this.moveTo(x + radius, y);
    this.lineTo(x + width - radius, y);
    this.quadraticCurveTo(x + width, y, x + width, y + radius);
    this.lineTo(x + width, y + height - radius);
    this.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    this.lineTo(x + radius, y + height);
    this.quadraticCurveTo(x, y + height, x, y + height - radius);
    this.lineTo(x, y + radius);
    this.quadraticCurveTo(x, y, x + radius, y);
    return this;
  };
}

renderPrototypeData();
restartHomeRaceCarousel();
resizeAll();
window.addEventListener("resize", resizeAll);
requestAnimationFrame(drawFrame);
