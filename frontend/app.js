// =============================================
// ARY Frontend Application (Vue 3)
// =============================================

// DEBUG: 全局错误捕获，显示在页面上方便定位问题
window.onerror = function(msg, url, line, col, err) {
  document.body.innerHTML = '<div style="padding:40px;font-family:monospace;color:red;background:#fff;max-width:900px;margin:40px auto;border:2px solid red;border-radius:8px;word-break:break-all"><h2>JS Error</h2><p><b>Message:</b> ' + msg + '</p><p><b>File:</b> ' + url + '</p><p><b>Line:</b> ' + line + ':' + col + '</p><p><b>Stack:</b><pre>' + (err ? err.stack : 'N/A') + '</pre></p><button onclick="location.reload()" style="padding:10px 20px;font-size:16px;cursor:pointer">Reload</button></div>';
  return true;
};

const API_BASE = window.ARY_API_BASE || '';

let _csrfToken = null;

function api(path, options = {}) {
  const token = localStorage.getItem('ary_token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET' && _csrfToken) {
    headers['X-CSRF-Token'] = _csrfToken;
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' })
    .then(async (r) => {
      // 从 GET 响应中提取 CSRF token
      if (method === 'GET') {
        const csrfFromHeader = r.headers.get('X-CSRF-Token');
        if (csrfFromHeader) _csrfToken = csrfFromHeader;
      }
      const ct = r.headers.get('content-type') || '';
      const isJson = ct.includes('application/json');
      const data = isJson ? await r.json().catch(() => null) : null;
      if (!r.ok || !isJson) {
        const msg =
          data?.error?.message ||
          data?.message ||
          data?.error ||
          (!isJson ? `Unexpected response (status ${r.status})` : `HTTP ${r.status}`);
        const err = new Error(msg);
        err.status = r.status;
        err.data = data;
        throw err;
      }
      return data;
    });
}

// =============================================
// XSS 防护工具函数
// =============================================
// HTML 转义防 XSS
function escapeHtml(str) {
  if (!str) return '';
  if (typeof str !== 'string') str = String(str);
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// 安全 URL 校验 — 只允许 http/https 协议，防止 javascript: 注入
function safeUrl(url) {
  if (!url) return '#';
  const trimmed = String(url).trim();
  const lower = trimmed.toLowerCase();
  if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('vbscript:')) {
    return '#';
  }
  if (lower.startsWith('http://') || lower.startsWith('https://') || lower.startsWith('/') || lower.startsWith('#')) {
    return trimmed;
  }
  return '#'; // 拒绝相对路径和未知协议
}

// 输入净化 — 去除控制字符，限制长度
function sanitizeInput(str, maxLen = 5000) {
  if (!str) return '';
  if (typeof str !== 'string') str = String(str);
  // 移除 null 字节和控制字符（保留换行和制表符用于 textarea）
  let cleaned = str.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
  // 限制长度
  if (cleaned.length > maxLen) cleaned = cleaned.substring(0, maxLen);
  return cleaned.trim();
}

const { createApp, ref, reactive, computed, onMounted, watch } = Vue;

const app = createApp({
  setup() {
    // ---- State ----
    const currentPage = ref('home');
    const pageParams = reactive({});
    const isFullScreen = computed(() => currentPage.value === 'live');

    // Auth
    const isLoggedIn = ref(false);
    const currentUser = ref(null);
    const token = ref(localStorage.getItem('ary_token') || '');

    const isRider = computed(() => currentUser.value?.roles?.includes('rider'));
    const isOrganizer = computed(() => currentUser.value?.roles?.includes('organizer'));
    const isAdmin = computed(() => currentUser.value?.roles?.includes('admin'));
    const isJudge = computed(() => currentUser.value?.roles?.includes('judge'));

    // Loading states
    const loading = reactive({
      races: false, race: false, login: false, registerAuth: false, profile: false,
      registrations: false, dashboard: false, raceProject: false,
      works: false, work: false, judge: false, leaderboard: false,
      rider: false, adminRaces: false,
      live: false, caWizard: false, caConnections: false,
      caHandshake: false, timeline: false,
    });

    // Home
    const races = ref([]);
    const featuredRace = ref(null);
    const stats = ref(null);
    const raceFilter = reactive({ search: '', status: '' });

    // Race detail
    const currentRace = ref(null);

    // Login
    const loginForm = reactive({ username: '', password: '' });
    const loginError = ref('');

    // Register Auth
    const registerForm = reactive({ username: '', password: '', confirm_password: '', role: 'rider' });
    const registerAuthError = ref('');
    const registerAuthSuccess = ref('');

    // Profile
    const profile = ref(null);
    const profileForm = reactive({ display_name: '', school_org: '', bio: '' });

    // Registration
    const registerRaceId = ref(null);
    const registerError = ref('');
    const registerSuccess = ref(false);

    // My registrations
    const myRegistrations = ref([]);

    // Dashboard
    const myRaceProjects = ref([]);
    const judgeInvitations = ref([]);

    // RaceProject
    const currentRaceProjectId = ref(null);
    const raceProject = ref(null);
    const raceProjectWorks = ref([]);
    const showCreateWork = ref(false);
    const workForm = reactive({ title: '', description: '', repo_url: '', demo_url: '' });
    const nextActions = ref(null);
    const readiness = ref(null);

    // Works
    const publicWorks = ref([]);
    const worksRaceFilter = ref('');

    // Work detail
    const currentWork = ref(null);
    const integrityResult = ref(null);

    // Judge
    const judgeAssignments = ref([]);
    const judgmentForms = reactive({});

    // Leaderboard
    const leaderboard = ref([]);
    const leaderboardRaceId = ref('');

    // Rider
    const riderIdLookup = ref('');
    const riderProfile = ref(null);

    // Live
    const liveRaceId = ref(null);
    const liveRaceData = ref(null);
    const liveEntries = ref([]);

    // CA Wizard
    const caWizardSteps = ['Policy', 'Configure', 'Handshake'];
    const caWizardStep = ref(0);
    const caPolicy = ref(null);
    const caWizardForm = reactive({ ca_type: '', api_endpoint: '', api_key: '', config: '' });
    const caWizardRegisteredId = ref(null);
    const caHandshakeResult = ref(null);

    // CA Connections
    const caConnections = ref([]);

    // Timeline
    const timelineEntries = ref([]);

    // Admin
    const adminTab = ref('races');
    const adminRaces = ref([]);
    const adminRegistrations = reactive({});
    const createRaceForm = reactive({ name: '', description: '', theme: '', rules: '', judging_mode: 'blind' });
    const awardRaceId = ref('');
    const awards = ref([]);
    const awardForm = reactive({ title: '', position: 1, work_id: null, description: '' });

    // Error
    const errorTitle = ref('');
    const errorMessage = ref('');

    // ---- 全局状态覆盖：错误类型枚举 ----
    const pageState = reactive({
      // 每页独立状态: 'loading' | 'empty' | 'success' | 'error' | 'unauthorized' | 'forbidden' | 'not-found' | 'offline' | null
      home: null, race: null, login: null, profile: null,
      register: null, 'register-auth': null, registrations: null, dashboard: null,
      raceProject: null, caWizard: null, works: null,
      work: null, judge: null, leaderboard: null,
      riders: null, live: null, admin: null,
    });

    // 网络状态检测
    const isOffline = ref(!navigator.onLine);
    window.addEventListener('online', () => { isOffline.value = false; });
    window.addEventListener('offline', () => { isOffline.value = true; });

    // 通用错误处理 — 根据 HTTP 状态码映射到页面状态
    function handlePageError(page, err) {
      const status = err.status || 0;
      if (!navigator.onLine) {
        pageState[page] = 'offline';
      } else if (status === 401) {
        pageState[page] = 'unauthorized';
      } else if (status === 403) {
        pageState[page] = 'forbidden';
      } else if (status === 404) {
        pageState[page] = 'not-found';
      } else {
        pageState[page] = 'error';
      }
      // 保存错误详情到全局
      errorTitle.value = err.message || 'Error';
      errorMessage.value = err.data?.detail || err.data?.message || `HTTP ${status}`;
    }

    // 重置页面状态
    function resetPageState(page) {
      pageState[page] = null;
      errorTitle.value = '';
      errorMessage.value = '';
    }

    // 设置页面状态为 loading
    function setLoading(page) {
      pageState[page] = 'loading';
    }

    // 设置页面状态为 success 或 empty
    function setSuccess(page, data) {
      const isEmpty = !data || (Array.isArray(data) && data.length === 0);
      pageState[page] = isEmpty ? 'empty' : 'success';
    }

    function responseData(res) {
      return res?.data !== undefined ? res.data : res;
    }

    function responseItems(res) {
      const data = responseData(res);
      if (Array.isArray(res?.items)) return res.items;
      if (Array.isArray(data?.items)) return data.items;
      if (Array.isArray(data)) return data;
      return [];
    }

    function statusLabel(status) {
      const labels = {
        draft: '草稿',
        published: '已发布',
        registration: '报名中',
        submitted: '已提交',
        approved: '已通过',
        rejected: '已拒绝',
        running: '进行中',
        submitting: '作品提交',
        judging: '评审中',
        completed: '已完成',
        archived: '已归档',
      };
      return labels[status] || status || '未知';
    }

    function nextRaceActionLabel(status) {
      const labels = {
        draft: '下一步：发布赛事，让参赛者能看到赛事详情。',
        published: '下一步：开放报名，开始收集参赛申请。',
        registration: '下一步：审核报名，通过后可启动比赛。',
        running: '下一步：开放作品提交，让骑手提交参赛作品。',
        submitting: '下一步：开始评审，锁定作品并通知评委。',
        judging: '下一步：完成评审并发布最终结果。',
        completed: '下一步：归档赛事，锁定历史结果。',
        archived: '赛事已归档，状态不可再推进。',
      };
      return labels[status] || '暂无可执行的状态动作。';
    }

    function getRaceProjectIdFromRegistration(reg) {
      return reg?.race_project_id || reg?.raceProjectId || reg?.race_project?.id || reg?.raceProject?.id || null;
    }

    // ---- Navigation ----
    function navigate(page, param) {
      currentPage.value = page;
      if (param !== undefined) pageParams.id = param;
      else delete pageParams.id;
      handlePageLoad(page);
    }

    function handlePageLoad(page) {
      switch (page) {
        case 'home': loadRaces(); loadStats(); break;
        case 'race': loadRaceDetail(); break;
        case 'profile': loadProfile(); break;
        case 'registrations': loadMyRegistrations(); break;
        case 'dashboard': loadDashboard(); break;
        case 'race-project': loadRaceProject(); break;
        case 'ca-wizard': loadCAWizard(); break;
        case 'works': loadPublicWorks(); break;
        case 'work': loadWorkDetail(); break;
        case 'judge': loadJudgeAssignments(); break;
        case 'leaderboard': loadRaces(); break;
        case 'riders': resetPageState('riders'); break;
        case 'admin': loadAdminRaces(); break;
        case 'live': liveRaceId.value = pageParams.id || ''; loadLiveData(); break;
        case 'register-auth': registerAuthError.value = ''; registerAuthSuccess.value = ''; break;
      }
    }

    // ---- API: Auth ----
    async function doLogin() {
      loading.login = true;
      loginError.value = '';
      try {
        const res = await api('/api/v1/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username: loginForm.username, password: loginForm.password }),
        });
        const t = res.token || res.data?.token;
        if (t) {
          localStorage.setItem('ary_token', t);
          token.value = t;
          isLoggedIn.value = true;
          currentUser.value = res.user || res.data?.user;
          navigate('home');
        }
      } catch (e) {
        loginError.value = e.message || 'Login failed';
      } finally {
        loading.login = false;
      }
    }

    async function doRegisterAuth() {
      loading.registerAuth = true;
      registerAuthError.value = '';
      registerAuthSuccess.value = '';
      try {
        const res = await api('/api/v1/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            username: registerForm.username,
            password: registerForm.password,
            confirm_password: registerForm.confirm_password,
            role: registerForm.role,
          }),
        });
        const t = res.token || res.data?.token;
        if (t) {
          localStorage.setItem('ary_token', t);
          token.value = t;
          isLoggedIn.value = true;
          currentUser.value = res.user || res.data?.user;
          registerAuthSuccess.value = 'Registration successful! Redirecting...';
          setTimeout(() => navigate('home'), 1000);
        }
      } catch (e) {
        registerAuthError.value = e.message || 'Registration failed';
      } finally {
        loading.registerAuth = false;
      }
    }

    async function logout() {
      try {
        await api('/api/v1/auth/logout', { method: 'POST' });
      } catch (_) { /* ignore */ }
      localStorage.removeItem('ary_token');
      token.value = '';
      isLoggedIn.value = false;
      currentUser.value = null;
      navigate('home');
    }

    async function checkAuth() {
      if (!token.value) return;
      try {
        const res = await api('/api/v1/auth/me');
        currentUser.value = res.data || res;
        isLoggedIn.value = true;
      } catch (_) {
        localStorage.removeItem('ary_token');
        token.value = '';
        isLoggedIn.value = false;
      }
    }

    // ---- API: Public ----
    async function loadRaces() {
      loading.races = true;
      resetPageState('home');
      setLoading('home');
      try {
        const params = new URLSearchParams();
        if (raceFilter.search) params.set('q', raceFilter.search);
        if (raceFilter.status) params.set('status', raceFilter.status);
        const res = await api(`/api/v1/public/races?${params}`);
        races.value = res.items || res.data?.items || [];
        if (races.value.length > 0) featuredRace.value = races.value[0];
        setSuccess('home', races.value);
      } catch (e) {
        races.value = [];
        handlePageError('home', e);
        console.error('Load races failed:', e);
      } finally {
        loading.races = false;
      }
    }

    async function loadStats() {
      try {
        const res = await api('/api/v1/public/stats');
        stats.value = res.data || res;
      } catch (_) { /* ignore */ }
    }

    async function loadRaceDetail() {
      loading.race = true;
      resetPageState('race');
      setLoading('race');
      try {
        const res = await api(`/api/v1/public/races/${pageParams.id}`);
        currentRace.value = res.data || res;
        setSuccess('race', currentRace.value);
      } catch (e) {
        currentRace.value = null;
        handlePageError('race', e);
      } finally {
        loading.race = false;
      }
    }

    async function loadPublicWorks() {
      loading.works = true;
      resetPageState('works');
      setLoading('works');
      try {
        if (worksRaceFilter.value) {
          const res = await api(`/api/v1/public/races/${worksRaceFilter.value}/works`);
          publicWorks.value = res.data || res || [];
        } else {
          publicWorks.value = [];
        }
        setSuccess('works', publicWorks.value);
      } catch (e) {
        publicWorks.value = [];
        handlePageError('works', e);
      } finally {
        loading.works = false;
      }
    }

    async function loadWorkDetail() {
      loading.work = true;
      resetPageState('work');
      setLoading('work');
      try {
        const res = await api(`/api/v1/organizer/works/${pageParams.id}`);
        currentWork.value = res.data || res;
        setSuccess('work', currentWork.value);
      } catch (e) {
        currentWork.value = null;
        handlePageError('work', e);
      } finally {
        loading.work = false;
      }
    }

    async function verifyIntegrity(workId) {
      try {
        const res = await api(`/api/v1/public/works/${workId}/integrity`);
        integrityResult.value = res.data || res;
      } catch (e) {
        integrityResult.value = { valid: false, error: e.message };
      }
    }

    async function loadLeaderboard() {
      if (!leaderboardRaceId.value) { leaderboard.value = []; pageState.leaderboard = null; return; }
      loading.leaderboard = true;
      resetPageState('leaderboard');
      setLoading('leaderboard');
      try {
        const res = await api(`/api/v1/public/races/${leaderboardRaceId.value}/leaderboard`);
        const data = responseData(res);
        leaderboard.value = data?.rankings || data?.items || (Array.isArray(data) ? data : []);
        setSuccess('leaderboard', leaderboard.value);
      } catch (e) {
        leaderboard.value = [];
        handlePageError('leaderboard', e);
      } finally { loading.leaderboard = false; }
    }

    async function loadRiderProfile() {
      if (!riderIdLookup.value) { riderProfile.value = null; pageState.riders = null; return; }
      loading.rider = true;
      resetPageState('riders');
      setLoading('riders');
      try {
        const res = await api(`/api/v1/public/riders/${riderIdLookup.value}`);
        riderProfile.value = res.data || res;
        setSuccess('riders', riderProfile.value);
      } catch (e) {
        riderProfile.value = null;
        handlePageError('riders', e);
      } finally { loading.rider = false; }
    }

    function openRiderProfile(userId) {
      if (!userId) return;
      riderIdLookup.value = String(userId);
      currentPage.value = 'riders';
      loadRiderProfile();
    }

    // ---- API: Profile ----
    async function loadProfile() {
      if (!isLoggedIn.value) { pageState.profile = 'unauthorized'; return; }
      loading.profile = true;
      resetPageState('profile');
      setLoading('profile');
      try {
        const res = await api('/api/v1/auth/profile');
        profile.value = res.data || res;
        profileForm.display_name = profile.value.display_name || '';
        profileForm.school_org = profile.value.school_org || '';
        profileForm.bio = profile.value.bio || '';
        setSuccess('profile', profile.value);
      } catch (e) {
        profile.value = null;
        handlePageError('profile', e);
      } finally { loading.profile = false; }
    }

    async function updateProfile() {
      try {
        await api('/api/v1/auth/profile', {
          method: 'PUT',
          body: JSON.stringify({ ...profileForm }),
        });
        loadProfile();
      } catch (e) {
        alert('Update failed: ' + e.message);
      }
    }

    // ---- API: Registration ----
    function registerForRace(raceId) {
      registerRaceId.value = raceId;
      registerSuccess.value = false;
      registerError.value = '';
      resetPageState('register');
      navigate('register');
    }

    async function doRegister() {
      loading.register = true;
      registerError.value = '';
      resetPageState('register');
      try {
        await api(`/api/v1/rider/races/${registerRaceId.value}/registrations`, { method: 'POST' });
        registerSuccess.value = true;
        pageState.register = 'success';
      } catch (e) {
        registerError.value = e.message || 'Registration failed';
        handlePageError('register', e);
      } finally {
        loading.register = false;
      }
    }

    async function loadMyRegistrations() {
      loading.registrations = true;
      resetPageState('registrations');
      setLoading('registrations');
      try {
        const res = await api('/api/v1/rider/registrations');
        myRegistrations.value = responseItems(res);
        setSuccess('registrations', myRegistrations.value);
      } catch (e) {
        myRegistrations.value = [];
        handlePageError('registrations', e);
      } finally { loading.registrations = false; }
    }

    // ---- API: Dashboard / RaceProject ----
    async function loadRaceProjectForRegistration(reg) {
      let fullReg = reg;
      if (!getRaceProjectIdFromRegistration(fullReg)) {
        try {
          const detailRes = await api(`/api/v1/rider/registrations/${reg.id}`);
          fullReg = responseData(detailRes);
        } catch (_) { /* Detail endpoint may be unavailable for older data. */ }
      }

      const embeddedProject = fullReg?.race_project || fullReg?.raceProject;
      const raceProjectId = getRaceProjectIdFromRegistration(fullReg);
      if (!raceProjectId && !embeddedProject?.id) return null;

      try {
        const rpRes = await api(`/api/v1/rider/race-projects/${raceProjectId || embeddedProject.id}`);
        return { ...responseData(rpRes), registration: fullReg };
      } catch (_) {
        return embeddedProject?.id ? { ...embeddedProject, registration: fullReg } : null;
      }
    }

    async function loadDashboardJudgeAssignments() {
      try {
        const res = await api('/api/v1/judge/assignments');
        judgeAssignments.value = responseItems(res);
      } catch (_) {
        judgeAssignments.value = [];
      }
    }

    async function loadJudgeInvitations() {
      try {
        const res = await api('/api/v1/judge-invitations');
        judgeInvitations.value = responseItems(res);
      } catch (_) {
        judgeInvitations.value = [];
      }
    }

    async function acceptJudgeInvitation(invitationId) {
      try {
        await api(`/api/v1/judge-invitations/${invitationId}/accept`, { method: 'POST' });
        await checkAuth();
        await loadDashboard();
        navigate('judge');
      } catch (e) { alert('接受邀请失败：' + e.message); }
    }

    async function rejectJudgeInvitation(invitationId) {
      try {
        await api(`/api/v1/judge-invitations/${invitationId}/reject`, { method: 'POST' });
        await loadDashboard();
      } catch (e) { alert('拒绝邀请失败：' + e.message); }
    }

    async function loadDashboard() {
      if (!isLoggedIn.value) { pageState.dashboard = 'unauthorized'; return; }
      loading.dashboard = true;
      resetPageState('dashboard');
      setLoading('dashboard');
      try {
        let regs = [];
        try {
          const res = await api('/api/v1/rider/registrations');
          regs = responseItems(res);
        } catch (_) {
          regs = [];
        }
        myRegistrations.value = regs;
        const approved = regs.filter(r => r.status === 'approved');
        const projects = [];
        for (const reg of approved) {
          const project = await loadRaceProjectForRegistration(reg);
          if (project) projects.push(project);
        }
        await Promise.all([loadJudgeInvitations(), loadDashboardJudgeAssignments()]);
        myRaceProjects.value = projects;
        const hasDashboardItems = regs.length || projects.length || judgeInvitations.value.length || judgeAssignments.value.length;
        pageState.dashboard = hasDashboardItems ? 'success' : 'empty';
      } catch (e) {
        myRegistrations.value = [];
        myRaceProjects.value = [];
        judgeInvitations.value = [];
        judgeAssignments.value = [];
        handlePageError('dashboard', e);
      } finally { loading.dashboard = false; }
    }

    async function loadRaceProject() {
      currentRaceProjectId.value = pageParams.id;
      loading.raceProject = true;
      resetPageState('raceProject');
      setLoading('raceProject');
      try {
        const res = await api(`/api/v1/rider/race-projects/${pageParams.id}`);
        raceProject.value = res.data || res;
        // Load works
        const wRes = await api(`/api/v1/rider/race-projects/${pageParams.id}/works`);
        raceProjectWorks.value = wRes.data || wRes || [];
        // Load CA connections
        loadCAConnections();
        setSuccess('raceProject', raceProject.value);
      } catch (e) {
        raceProject.value = null;
        handlePageError('raceProject', e);
      } finally { loading.raceProject = false; }
    }

    async function createWork() {
      try {
        await api(`/api/v1/rider/race-projects/${currentRaceProjectId.value}/works`, {
          method: 'POST',
          body: JSON.stringify({ ...workForm }),
        });
        showCreateWork.value = false;
        Object.assign(workForm, { title: '', description: '', repo_url: '', demo_url: '' });
        loadRaceProject();
      } catch (e) { alert('Create work failed: ' + e.message); }
    }

    async function submitWork(workId) {
      try {
        await api(`/api/v1/rider/works/${workId}/submit`, { method: 'POST' });
        loadRaceProject();
      } catch (e) { alert('Submit failed: ' + e.message); }
    }

    async function deleteWork(workId) {
      if (!confirm('Delete this work?')) return;
      try {
        await api(`/api/v1/rider/works/${workId}`, { method: 'DELETE' });
        loadRaceProject();
      } catch (e) { alert('Delete failed: ' + e.message); }
    }

    async function loadNextActions() {
      try {
        const res = await api(`/api/v1/rider/race-projects/${currentRaceProjectId.value}/next-actions`);
        nextActions.value = res.data || res;
      } catch (e) { alert('Failed: ' + e.message); }
    }

    async function loadReadiness() {
      try {
        const res = await api(`/api/v1/rider/race-projects/${currentRaceProjectId.value}/review-readiness`);
        readiness.value = res.data || res;
      } catch (e) { alert('Failed: ' + e.message); }
    }

    // ---- API: Judge ----
    async function loadJudgeAssignments() {
      loading.judge = true;
      resetPageState('judge');
      setLoading('judge');
      try {
        const res = await api('/api/v1/judge/assignments');
        judgeAssignments.value = responseItems(res);
        judgeAssignments.value.forEach(a => {
          if (!judgmentForms[a.work_id]) {
            judgmentForms[a.work_id] = {
              technical_score: 5, innovation_score: 5,
              presentation_score: 5, completeness_score: 5, comment: ''
            };
          }
        });
        setSuccess('judge', judgeAssignments.value);
      } catch (e) {
        judgeAssignments.value = [];
        handlePageError('judge', e);
      } finally { loading.judge = false; }
    }

    async function submitJudgment(workId) {
      try {
        const body = { ...judgmentForms[workId] };
        await api(`/api/v1/judge/works/${workId}/judgments`, {
          method: 'POST', body: JSON.stringify(body)
        });
        alert('Judgment submitted!');
        loadJudgeAssignments();
      } catch (e) { alert('Submit judgment failed: ' + e.message); }
    }

    // ---- API: CA Wizard ----
    async function loadCAWizard() {
      currentRaceProjectId.value = pageParams.id;
      loading.caWizard = true;
      resetPageState('caWizard');
      setLoading('caWizard');
      caWizardStep.value = 0;
      caWizardRegisteredId.value = null;
      caHandshakeResult.value = null;
      caWizardForm.ca_type = '';
      caWizardForm.api_endpoint = '';
      caWizardForm.api_key = '';
      caWizardForm.config = '';
      try {
        const res = await api(`/api/v1/rider/race-projects/${pageParams.id}/ca-policy`);
        caPolicy.value = res.data || res;
        setSuccess('caWizard', caPolicy.value);
      } catch (e) {
        caPolicy.value = { ca_policy: 'rider_choice' };
        // CA wizard loads policy first; handle error but allow continue
        handlePageError('caWizard', e);
      } finally {
        loading.caWizard = false;
      }
    }

    async function registerCAConnection() {
      try {
        const body = {
          ca_type: caWizardForm.ca_type,
          api_endpoint: caWizardForm.api_endpoint,
          api_key: caWizardForm.api_key,
          config: caWizardForm.config ? JSON.parse(caWizardForm.config) : {},
        };
        const res = await api(`/api/v1/rider/race-projects/${currentRaceProjectId.value}/ca-connections`, {
          method: 'POST', body: JSON.stringify(body),
        });
        const data = res.data || res;
        caWizardRegisteredId.value = data.id;
        caWizardStep.value = 2;
      } catch (e) { alert('Register CA failed: ' + e.message); }
    }

    async function doCAHandshake() {
      if (!caWizardRegisteredId.value) return;
      loading.caHandshake = true;
      try {
        const res = await api(`/api/v1/rider/ca-connections/${caWizardRegisteredId.value}/handshake`, { method: 'POST' });
        caHandshakeResult.value = res.data || res;
      } catch (e) {
        caHandshakeResult.value = { success: false, message: e.message, error_type: 'handshake_failed' };
      } finally { loading.caHandshake = false; }
    }

    async function loadCAConnections() {
      loading.caConnections = true;
      try {
        const res = await api(`/api/v1/rider/race-projects/${currentRaceProjectId.value}/ca-connections`);
        caConnections.value = res.data || res || [];
      } catch (_) { caConnections.value = []; }
      finally { loading.caConnections = false; }
    }

    async function deleteCAConnection(caId) {
      if (!confirm('Remove this CA connection?')) return;
      try {
        await api(`/api/v1/rider/ca-connections/${caId}`, { method: 'DELETE' });
        loadCAConnections();
      } catch (e) { alert('Failed: ' + e.message); }
    }

    // ---- API: Timeline ----
    async function loadTimeline() {
      loading.timeline = true;
      try {
        const res = await api(`/api/v1/rider/race-projects/${currentRaceProjectId.value}/timeline`);
        timelineEntries.value = res.data || res || [];
      } catch (_) { timelineEntries.value = []; }
      finally { loading.timeline = false; }
    }

    // ---- API: Live Hall ----
    async function loadLiveData() {
      if (!liveRaceId.value) { pageState.live = null; return; }
      loading.live = true;
      resetPageState('live');
      setLoading('live');
      try {
        // 加载赛事基本信息
        const raceRes = await api(`/api/v1/public/races/${liveRaceId.value}`);
        liveRaceData.value = raceRes.data || raceRes;
        // 尝试加载 live 数据
        try {
          const liveRes = await api(`/api/v1/public/races/${liveRaceId.value}/live`);
          const liveData = liveRes.data || liveRes;
          if (liveData) Object.assign(liveRaceData.value, liveData);
        } catch (_) { /* live endpoint may not exist yet */ }
        // 加载参赛者列表
        try {
          const entriesRes = await api(`/api/v1/public/races/${liveRaceId.value}/live/entries`);
          liveEntries.value = entriesRes.data || entriesRes || [];
        } catch (_) { liveEntries.value = []; }
        setSuccess('live', liveRaceData.value);
      } catch (e) {
        liveRaceData.value = null;
        liveEntries.value = [];
        handlePageError('live', e);
      } finally { loading.live = false; }
    }

    // ---- Computed: Live Hall ----
    const riskClass = computed(() => {
      const high = liveRaceData.value?.risk_distribution?.high || 0;
      if (high > 3) return 'check-fail';
      if (high > 0) return 'check-warn';
      return 'check-pass';
    });

    function caBarPercent(type, count) {
      const max = Math.max(1, ...Object.values(liveRaceData.value?.ca_distribution || { 1: 1 }));
      return Math.round((count / max) * 100);
    }

    // ---- API: Admin/Organizer ----
    async function loadAdminRaces() {
      if (!isLoggedIn.value) { pageState.admin = 'unauthorized'; return; }
      if (!isOrganizer.value && !isAdmin.value) {
        adminRaces.value = [];
        pageState.admin = 'empty';
        return;
      }
      loading.adminRaces = true;
      resetPageState('admin');
      setLoading('admin');
      try {
        const res = await api('/api/v1/organizer/races');
        adminRaces.value = responseItems(res);
        setSuccess('admin', adminRaces.value);
      } catch (e) {
        adminRaces.value = [];
        handlePageError('admin', e);
      } finally { loading.adminRaces = false; }
    }

    async function transitionRace(raceId, action) {
      try {
        await api(`/api/v1/organizer/races/${raceId}/${action}`, { method: 'POST' });
        loadAdminRaces();
      } catch (e) { alert(`Transition failed: ${e.message}`); }
    }

    async function loadAdminRegistrations(raceId) {
      try {
        const res = await api(`/api/v1/organizer/races/${raceId}/registrations`);
        adminRegistrations[raceId] = responseItems(res);
      } catch (_) { adminRegistrations[raceId] = []; }
    }

    async function approveReg(regId) {
      try {
        await api(`/api/v1/organizer/registrations/${regId}/approve`, { method: 'POST' });
        alert('Approved!');
      } catch (e) { alert('Failed: ' + e.message); }
    }

    async function rejectReg(regId) {
      try {
        await api(`/api/v1/organizer/registrations/${regId}/reject`, { method: 'POST' });
        alert('Rejected!');
      } catch (e) { alert('Failed: ' + e.message); }
    }

    async function createRace() {
      try {
        await api('/api/v1/organizer/races', {
          method: 'POST', body: JSON.stringify({ ...createRaceForm })
        });
        alert('Race created!');
        adminTab.value = 'races';
        loadAdminRaces();
      } catch (e) {
        const msg = e.message || 'Unknown error';
        alert('Create race failed: ' + msg);
        if (e.status === 401 || e.status === 403) {
          localStorage.removeItem('ary_token');
          token.value = '';
          isLoggedIn.value = false;
          currentUser.value = null;
          navigate('login');
        }
      }
    }

    async function exportCSV(raceId, type) {
      try {
        const res = await fetch(`${API_BASE}/api/v1/organizer/races/${raceId}/export/${type}`, {
          headers: { 'Authorization': `Bearer ${token.value}` }
        });
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `race_${raceId}_${type}.csv`;
        a.click(); URL.revokeObjectURL(url);
      } catch (e) { alert('Export failed: ' + e.message); }
    }

    async function loadAwards() {
      if (!awardRaceId.value) return;
      try {
        const res = await api(`/api/v1/organizer/races/${awardRaceId.value}/awards`);
        awards.value = res.data || res || [];
      } catch (_) { awards.value = []; }
    }

    async function createAward() {
      try {
        await api(`/api/v1/organizer/races/${awardRaceId.value}/awards`, {
          method: 'POST', body: JSON.stringify({ ...awardForm })
        });
        loadAwards();
      } catch (e) { alert('Create award failed: ' + e.message); }
    }

    async function deleteAward(awardId) {
      try {
        await api(`/api/v1/organizer/awards/${awardId}`, { method: 'DELETE' });
        loadAwards();
      } catch (e) { alert('Delete award failed: ' + e.message); }
    }

    // ---- XSS 安全渲染 ----
    // Vue 3 默认对 {{ }} 模板绑定进行 HTML 转义，但 v-html 是危险的。
    // 所有用户输入数据均使用双花括号绑定，不使用 v-html，确保 XSS 安全。
    // escapeHtml 函数用于需要手动处理的场景（如直接 DOM 操作）。

    // ---- Init ----
    onMounted(() => {
      checkAuth();
      loadRaces();
      loadStats();
    });

    // Watch page param changes
    watch(() => pageParams.id, () => {
      if (currentPage.value === 'race') loadRaceDetail();
      if (currentPage.value === 'race-project') loadRaceProject();
      if (currentPage.value === 'work') loadWorkDetail();
    });

    return {
      currentPage, pageParams, isFullScreen, navigate,
      // Auth
      isLoggedIn, currentUser, token, isRider, isOrganizer, isAdmin, isJudge,
      loginForm, loginError, doLogin,
      registerForm, registerAuthError, registerAuthSuccess, doRegisterAuth,
      logout,
      // Loading
      loading,
      // Home
      races, featuredRace, stats, raceFilter, loadRaces,
      // Race
      currentRace, loadRaceDetail,
      // Profile
      profile, profileForm, loadProfile, updateProfile,
      // Registration
      registerRaceId, registerError, registerSuccess, registerForRace, doRegister,
      myRegistrations, loadMyRegistrations,
      // Dashboard
      myRaceProjects, judgeInvitations, loadDashboard,
      acceptJudgeInvitation, rejectJudgeInvitation,
      // RaceProject
      currentRaceProjectId, raceProject, raceProjectWorks,
      showCreateWork, workForm, createWork, submitWork, deleteWork,
      nextActions, loadNextActions, readiness, loadReadiness,
      // Works
      publicWorks, worksRaceFilter, loadPublicWorks,
      currentWork, integrityResult, loadWorkDetail, verifyIntegrity,
      // Judge
      judgeAssignments, judgmentForms, loadJudgeAssignments, submitJudgment,
      // Leaderboard
      leaderboard, leaderboardRaceId, loadLeaderboard,
      // Rider
      riderIdLookup, riderProfile, loadRiderProfile, openRiderProfile,
      // Live
      liveRaceId, liveRaceData, liveEntries, loadLiveData, riskClass, caBarPercent,
      // CA Wizard
      caWizardSteps, caWizardStep, caPolicy, caWizardForm,
      caWizardRegisteredId, caHandshakeResult,
      loadCAWizard, registerCAConnection, doCAHandshake,
      caConnections, loadCAConnections, deleteCAConnection,
      // Timeline
      timelineEntries, loadTimeline,
      // Admin
      adminTab, adminRaces, adminRegistrations, createRaceForm,
      awardRaceId, awards, awardForm,
      loadAdminRaces, transitionRace, loadAdminRegistrations,
      approveReg, rejectReg, createRace, exportCSV,
      loadAwards, createAward, deleteAward,
      // Error & Page State
      errorTitle, errorMessage,
      pageState, isOffline, resetPageState,
      // Utils
      escapeHtml, safeUrl, sanitizeInput, statusLabel, nextRaceActionLabel,
    };
  },
});

app.mount('#app');
