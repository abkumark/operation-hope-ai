const API = '/api/v1';
const chartInstances = {};
let selectedApprovalId = null;
let selectedMgmtTicketId = null;
let selectedMyQueueTicketId = null;
let currentUser = null;
let cachedEngineers = [];
let cachedQueues = {};

/* ─── Landing Page Tabs ─── */
function switchLandingTab(tab) {
  document.querySelectorAll('.landing-tab').forEach((t) => t.classList.remove('active'));
  document.querySelectorAll('.landing-tab-content').forEach((c) => c.classList.remove('active'));
  document.querySelector(`.landing-tab[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');
}

/* ─── Public Ticket Submission ─── */
const SAMPLES = [
  { label: 'Password Reset', subject: 'Cannot reset my password', description: 'I forgot my password for the client portal. I tried the reset link but it says my account does not exist.', name: 'John Davis', lang: 'en' },
  { label: 'Course Video Issue', subject: 'Video not playing', description: 'The course video in Before You Buy module is stuck loading. I tried Chrome and Safari.', name: 'Maria Garcia', lang: 'en' },
  { label: 'HUD Certificate', subject: 'Need HUD Certification', description: 'I completed all courses for homeownership. How do I get my HUD certificate?', name: 'James Wilson', lang: 'en' },
  { label: 'Delta SSO', subject: 'Delta login issue', description: 'I am a Delta employee trying to sign in to Operation HOPE portal but SSO is not working.', name: 'Lisa Chen', lang: 'en' },
  { label: 'Coach Change', subject: 'Need a new coach', description: 'I would like to be reassigned to a different coach. My current coach has not responded in weeks.', name: 'Robert Brown', lang: 'en' },
];

function initSampleChips() {
  const container = document.getElementById('sample-chips');
  if (!container) return;
  container.innerHTML = SAMPLES.map((s, i) => `<button class="chip" type="button" onclick="fillPublicSample(${i})">${s.label}</button>`).join('');
}

function fillPublicSample(idx) {
  const s = SAMPLES[idx];
  document.getElementById('pub-subject').value = s.subject;
  document.getElementById('pub-description').value = s.description;

  // Auto-switch language button to match sample
  const targetLang = s.lang || 'en';
  setLanguage(targetLang);
}

const FORM_LABELS = {
  en: {
    heading: 'Submit a Support Request',
    intro: 'Describe your issue and we will assign it to the right team. You will receive a ticket ID and email updates on progress.',
    name: 'Your Name',
    namePlaceholder: 'Full name',
    email: 'Email Address',
    language: 'Preferred Language',
    langHint: 'You can describe your issue in English or Spanish.',
    subject: 'Subject',
    subjectPlaceholder: 'Brief summary of the issue',
    description: 'Description',
    descPlaceholder: 'Describe your issue in detail...',
    submit: 'Submit Request',
    submitting: 'Submitting...',
    successMsg: 'Ticket submitted successfully!',
  },
  es: {
    heading: 'Enviar una Solicitud de Soporte',
    intro: 'Describa su problema y lo asignaremos al equipo adecuado. Recibirá un número de ticket y actualizaciones por correo electrónico.',
    name: 'Su Nombre',
    namePlaceholder: 'Nombre completo',
    email: 'Correo Electrónico',
    language: 'Idioma Preferido',
    langHint: 'Puede describir su problema en inglés o español.',
    subject: 'Asunto',
    subjectPlaceholder: 'Resumen breve del problema',
    description: 'Descripción',
    descPlaceholder: 'Describa su problema en detalle...',
    submit: 'Enviar Solicitud',
    submitting: 'Enviando...',
    successMsg: '¡Solicitud enviada exitosamente!',
  },
};

function switchFormLanguage(lang) {
  const L = FORM_LABELS[lang] || FORM_LABELS.en;
  const heading = document.querySelector('#tab-help .tab-intro h2');
  const intro = document.querySelector('#tab-help .tab-intro p');
  if (heading) heading.textContent = L.heading;
  if (intro) intro.textContent = L.intro;

  const setLabel = (inputId, text) => {
    const label = document.querySelector(`label[for="${inputId}"]`);
    if (label) label.textContent = text;
  };
  setLabel('pub-name', L.name);
  setLabel('pub-email', L.email);
  setLabel('pub-subject', L.subject);
  setLabel('pub-description', L.description);

  document.getElementById('pub-name').placeholder = L.namePlaceholder;
  document.getElementById('pub-subject').placeholder = L.subjectPlaceholder;
  document.getElementById('pub-description').placeholder = L.descPlaceholder;
  document.getElementById('btn-submit-ticket').textContent = L.submit;

  const hint = document.getElementById('pub-lang-hint');
  if (hint) hint.textContent = L.langHint;
}

/* ─── EN/ES Segmented Button Toggle ─── */
function setLanguage(lang) {
  const hiddenInput = document.getElementById('pub-language');
  hiddenInput.value = lang;

  const enBtn = document.getElementById('lang-btn-en');
  const esBtn = document.getElementById('lang-btn-es');
  if (lang === 'en') {
    enBtn.style.background = '#003E7E';
    enBtn.style.color = '#fff';
    esBtn.style.background = '#fff';
    esBtn.style.color = '#003E7E';
  } else {
    esBtn.style.background = '#c60b1e';
    esBtn.style.color = '#fff';
    enBtn.style.background = '#fff';
    enBtn.style.color = '#003E7E';
  }
  switchFormLanguage(lang);
}

async function submitPublicTicket(e) {
  e.preventDefault();
  const name = document.getElementById('pub-name').value.trim();
  const email = document.getElementById('pub-email').value.trim();
  const phone = (document.getElementById('pub-phone').value || '').trim();
  const subject = document.getElementById('pub-subject').value.trim();
  const description = document.getElementById('pub-description').value.trim();
  const language = document.getElementById('pub-language').value || 'en';
  const L = FORM_LABELS[language] || FORM_LABELS.en;

  if (!name || !email || !subject || !description) {
    showToast('Please fill in all fields.', 'error');
    return;
  }

  const btn = document.getElementById('btn-submit-ticket');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> ${L.submitting}`;

  try {
    const res = await fetch(`${API}/tickets/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, description, submitter_name: name, submitter_email: email, phone_number: phone, language }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Submission failed');
    }
    const data = await res.json();
    document.getElementById('public-ticket-id').textContent = data.ticket_id;
    document.getElementById('public-ticket-email').textContent = email;
    const noteEl = document.getElementById('public-ticket-note');
    noteEl.innerHTML = `Your request is being analyzed by our AI. Save your ticket ID and use <strong>Check Ticket Status</strong> below to track progress.`;
    document.getElementById('instant-resolution-box').style.display = 'none';
    document.getElementById('public-ticket-form').style.display = 'none';
    document.querySelector('#tab-help .sample-chips').style.display = 'none';
    document.getElementById('public-ticket-success').style.display = 'block';
    showToast(L.successMsg, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = L.submit;
  }
}

function resetPublicForm() {
  document.getElementById('public-ticket-form').reset();
  document.getElementById('public-ticket-form').style.display = 'block';
  const chips = document.querySelector('#tab-help .sample-chips');
  if (chips) chips.style.display = 'flex';
  document.getElementById('public-ticket-success').style.display = 'none';
  document.getElementById('instant-resolution-box').style.display = 'none';

  // Reset language back to English
  setLanguage('en');
}

let _feedbackTicketId = '';
let _feedbackEmail = '';

async function lookupTicketStatus(e) {
  e.preventDefault();
  const tid = document.getElementById('lookup-ticket-id').value.trim().toUpperCase();
  const em = document.getElementById('lookup-email').value.trim();
  const box = document.getElementById('lookup-result');
  const fbWidget = document.getElementById('feedback-widget');
  box.style.display = 'block';
  fbWidget.style.display = 'none';
  box.innerHTML = '<span style="font-size:.82rem;color:var(--hope-text-muted)">Looking up...</span>';
  try {
    const d = await apiFetch(`/tickets/status/${encodeURIComponent(tid)}?email=${encodeURIComponent(em)}`);
    const statusColor = d.status === 'Completed' ? '#059669' : d.status === 'Processing' ? '#6366f1' : d.status === 'Open' ? '#d97706' : '#003E7E';
    const esc = (s) => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : '';
    box.innerHTML = `
      <div style="background:var(--hope-bg);border:1px solid var(--hope-border);border-radius:10px;padding:16px;text-align:left">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <strong style="color:var(--hope-navy)">${esc(d.ticket_id)}</strong>
          <span style="background:${statusColor};color:#fff;font-size:.7rem;font-weight:700;padding:2px 10px;border-radius:12px">${esc(d.status)}</span>
        </div>
        <div style="font-size:.82rem;color:var(--hope-text-muted);margin-bottom:4px">${esc(d.category)} &middot; ${new Date(d.submitted_at).toLocaleDateString()}</div>
        <div style="font-size:.84rem;margin-bottom:8px"><strong>Subject:</strong> ${esc(d.subject)}</div>
        ${d.ai_resolution ? `<div style="background:#fff;border:1px solid var(--hope-border);border-radius:8px;padding:12px;font-size:.82rem;line-height:1.7;white-space:pre-wrap"><strong style="color:var(--hope-navy)">Resolution:</strong>\n${esc(d.ai_resolution)}</div>` : '<div style="font-size:.82rem;color:var(--hope-text-muted)">Your ticket is being reviewed by the team.</div>'}
        ${d.assigned_to ? `<div style="font-size:.78rem;color:var(--hope-text-muted);margin-top:8px">Assigned to: ${esc(d.assigned_to)}</div>` : ''}
      </div>`;
    if (d.ai_resolution && !d.has_feedback) {
      _feedbackTicketId = d.ticket_id;
      _feedbackEmail = em;
      fbWidget.style.display = 'block';
      document.getElementById('feedback-thanks').style.display = 'none';
      document.getElementById('feedback-comment').value = '';
      fbWidget.querySelectorAll('button, textarea').forEach(el => el.disabled = false);
    }
  } catch (err) {
    const msg = (err && err.message) ? String(err.message).replace(/</g,'&lt;') : 'Ticket not found or email does not match.';
    box.innerHTML = `<div style="color:#dc2626;font-size:.84rem">${msg}</div>`;
  }
}

async function submitFeedback(helpful) {
  if (!_feedbackTicketId) return;
  const comment = (document.getElementById('feedback-comment').value || '').trim();
  try {
    await apiFetch('/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticket_id: _feedbackTicketId,
        email: _feedbackEmail,
        helpful,
        comment,
      }),
    });
    document.getElementById('feedback-thanks').style.display = 'block';
    document.getElementById('feedback-widget').querySelectorAll('button, textarea').forEach(el => el.disabled = true);
  } catch (err) {
    showToast('Could not submit feedback. Please try again.', 'error');
  }
}

/* ─── Self-Service Knowledge Base Search ─── */
async function searchSelfServiceKB(e) {
  e.preventDefault();
  const query = document.getElementById('ss-kb-query').value.trim();
  const box = document.getElementById('ss-kb-results');
  if (query.length < 3) {
    showToast('Please enter at least 3 characters.', 'error');
    return;
  }
  box.style.display = 'block';
  box.innerHTML = '<span style="font-size:.82rem;color:var(--hope-text-muted)">Searching...</span>';
  try {
    const data = await apiFetch(`/kb/self-service?query=${encodeURIComponent(query)}&limit=5`);
    if (!data.results || data.results.length === 0) {
      box.innerHTML = '<div style="font-size:.84rem;color:var(--hope-text-muted)">No results found. Try different keywords or submit a ticket above.</div>';
      return;
    }
    const esc = (s) => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : '';
    box.innerHTML = data.results.map(r => `
      <div style="background:var(--hope-bg);border:1px solid var(--hope-border);border-radius:10px;padding:14px;margin-bottom:10px;text-align:left">
        <div style="font-weight:600;color:var(--hope-navy);margin-bottom:4px;font-size:.92rem">${esc(r.title)}</div>
        <div style="font-size:.82rem;color:var(--hope-text);line-height:1.6">${esc(r.summary)}</div>
      </div>
    `).join('');
  } catch (err) {
    box.innerHTML = '<div style="color:#dc2626;font-size:.84rem">Search failed. Please try again.</div>';
  }
}

/* ─── Auth ─── */
function getStoredUser() {
  try {
    const data = sessionStorage.getItem('hope_user');
    return data ? JSON.parse(data) : null;
  } catch { return null; }
}

function getAuthToken() {
  return sessionStorage.getItem('hope_token') || '';
}

function authHeaders() {
  const token = getAuthToken();
  const h = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

function storeUser(user, token) {
  sessionStorage.setItem('hope_user', JSON.stringify(user));
  if (token) sessionStorage.setItem('hope_token', token);
}

function clearStoredUser() {
  sessionStorage.removeItem('hope_user');
  sessionStorage.removeItem('hope_token');
}

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value.trim();
  const errorEl = document.getElementById('login-error');
  const btn = document.getElementById('btn-login');

  if (!username || !password) {
    errorEl.textContent = 'Please enter both username and password.';
    errorEl.style.display = 'block';
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Signing in...';
  errorEl.style.display = 'none';

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }

    const user = await res.json();
    currentUser = user;
    storeUser(user, user.access_token);
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Sign In';
  }
}

function handleLogout() {
  currentUser = null;
  clearStoredUser();
  document.getElementById('app-shell').style.display = 'none';
  document.getElementById('landing-page').classList.remove('hidden');
  document.getElementById('login-username').value = '';
  document.getElementById('login-password').value = '';
  document.getElementById('login-error').style.display = 'none';
  switchLandingTab('login');
}

function showApp() {
  document.getElementById('landing-page').classList.add('hidden');
  document.getElementById('app-shell').style.display = '';

  document.getElementById('topbar-user').textContent = currentUser.display_name;
  const roleEl = document.getElementById('topbar-role');
  if (currentUser.role === 'admin') {
    roleEl.textContent = 'Admin';
    roleEl.className = 'topbar-role-badge role-admin';
  } else {
    roleEl.textContent = 'Engineer';
    roleEl.className = 'topbar-role-badge role-engineer';
  }

  const isAdmin = currentUser.role === 'admin';
  const isEngineer = currentUser.role === 'engineer';

  document.querySelectorAll('.nav-item.admin-only').forEach((item) => {
    item.classList.toggle('hidden-nav', !isAdmin);
  });
  document.querySelectorAll('.nav-item.engineer-only').forEach((item) => {
    item.classList.toggle('hidden-nav', !isEngineer);
  });
  document.querySelectorAll('.card.admin-only, .admin-only:not(.nav-item)').forEach((el) => {
    el.style.display = isAdmin ? '' : 'none';
  });

  if (isEngineer) {
    navigateTo('myqueue');
  } else {
    navigateTo('dashboard');
  }
}

function toggleSidebar(open) {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('mobile-overlay');
  sidebar.classList.toggle('open', open);
  overlay.classList.toggle('show', open);
}

function navigateTo(page) {
  document.querySelectorAll('.page-section').forEach((s) => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));

  const section = document.getElementById(`page-${page}`);
  const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (section) section.classList.add('active');
  if (navItem) navItem.classList.add('active');

  document.getElementById('topbar-title').textContent = {
    dashboard: 'Dashboard',
    management: 'Ticket Management',
    myqueue: 'My Queue',
    explorer: 'Ticket Explorer',
    analytics: 'Analytics & Insights',
    knowledge: 'Knowledge Base',
    settings: 'Configuration',
  }[page] || 'Dashboard';

  toggleSidebar(false);

  if (page === 'dashboard') loadDashboard();
  if (page === 'management') loadManagement();
  if (page === 'myqueue') loadMyQueue();
  if (page === 'explorer') loadExplorer();
  if (page === 'analytics') loadAnalytics();
  if (page === 'knowledge') { loadKnowledgeBase(); loadKBDrafts(); }
  if (page === 'settings') loadExpertiseConfig();
}

/* ─── Helpers ─── */
function actionBadge(action) {
  const map = {
    auto_resolve: ['AI Drafted', 'badge-auto'],
    suggest_review: ['Needs Review', 'badge-review'],
    route_to_human: ['Routed to Human', 'badge-human'],
    hr_excluded: ['HR Excluded', 'badge-hr'],
    escalate: ['Escalated', 'badge-escalate'],
  };
  const [label, cls] = map[action] || [action, 'badge-navy'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function approvalBadge(status) {
  if (!status) return '<span class="badge badge-navy">Not Required</span>';
  const labels = {
    pending_approval: ['Pending Approval', 'badge-review'],
    approved: ['Approved', 'badge-auto'],
    sent: ['Sent', 'badge-auto'],
    rejected: ['Rejected', 'badge-escalate'],
    rerouted: ['Rerouted', 'badge-human'],
    auto_resolve: ['AI Drafted', 'badge-auto'],
    suggest_review: ['Needs Review', 'badge-review'],
    route_to_human: ['Manual Handling', 'badge-human'],
    hr_excluded: ['HR Excluded', 'badge-hr'],
    escalate: ['Escalated', 'badge-escalate'],
  };
  const [label, cls] = labels[status] || [status, 'badge-navy'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function confBar(confidence) {
  const pct = Math.round((confidence || 0) * 100);
  const cls = pct >= 85 ? 'conf-high' : pct >= 60 ? 'conf-med' : 'conf-low';
  return `${pct}% <span class="confidence-bar"><span class="confidence-fill ${cls}" style="width:${pct}%"></span></span>`;
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

async function apiFetch(path, opts = {}) {
  try {
    const headers = { ...authHeaders(), ...(opts.headers || {}) };
    const res = await fetch(`${API}${path}`, {
      ...opts,
      headers,
    });
    if (res.status === 401) {
      // Token expired or invalid — force re-login
      handleLogout();
      showToast('Session expired. Please log in again.', 'error');
      throw new Error('Session expired');
    }
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return await res.json();
  } catch (e) {
    showToast(e.message, 'error');
    throw e;
  }
}

function renderInsights(containerId, insights) {
  const container = document.getElementById(containerId);
  if (!insights || insights.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No actionable insights yet.</p></div>';
    return;
  }
  container.innerHTML = insights.map((insight) => `
    <div class="insight-item">
      <h4>${insight.title}</h4>
      <p><strong>${insight.detail}</strong></p>
      <p>${insight.recommendation}</p>
    </div>`).join('');
}

/* ─── Dashboard ─── */
async function loadDashboard() {
  try {
    const [summary, ticketData] = await Promise.all([
      apiFetch('/analytics/summary'),
      apiFetch('/tickets'),
    ]);

    const overview = summary.overview || {};
    const ai = summary.ai_assistance || {};

    document.getElementById('kpi-total').textContent = overview.total || 0;
    document.getElementById('kpi-ai-draft').textContent = `${((ai.draft_rate || 0) * 100).toFixed(1)}%`;
    document.getElementById('kpi-sent').textContent = ai.sent || 0;
    document.getElementById('kpi-pending').textContent = ai.pending_approval || 0;

    const tickets = ticketData.tickets || [];
    const tbody = document.getElementById('recent-tickets');
    if (tickets.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><p>No tickets processed yet.</p></td></tr>';
    } else {
      tbody.innerHTML = tickets.slice(-8).reverse().map((t) => `
        <tr>
          <td><strong>${t.ticket_id}</strong></td>
          <td>${(t.subject || '').substring(0, 40)}${(t.subject || '').length > 40 ? '...' : ''}</td>
          <td>${t.category_name || t.category_id}</td>
          <td>${confBar(t.confidence)}</td>
          <td>${approvalBadge(t.approval_status || t.routing_action)}</td>
        </tr>`).join('');
    }

    renderPieChart('chart-routing', summary.routing_distribution || {}, {
      auto_resolve: '#059669',
      suggest_review: '#d97706',
      route_to_human: '#0284c7',
      hr_excluded: '#db2777',
      escalate: '#dc2626',
    });
    renderInsights('dashboard-insights', summary.actionable_insights || []);
  } catch {}
}

/* ─── Approvals ─── */
async function loadApprovals() {
  try {
    const data = await apiFetch('/approvals?status=pending');
    const approvals = data.approvals || [];
    const tbody = document.getElementById('approval-tbody');
    if (approvals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><p>No approvals pending.</p></td></tr>';
      document.getElementById('approval-empty').style.display = 'block';
      document.getElementById('approval-editor').style.display = 'none';
      return;
    }

    tbody.innerHTML = approvals.map((approval) => `
      <tr onclick="selectApproval('${approval.ticket_id}')" class="${selectedApprovalId === approval.ticket_id ? 'row-selected' : ''}">
        <td><strong>${approval.ticket_id}</strong></td>
        <td>${approval.ai_category}</td>
        <td>${confBar(approval.ai_confidence)}</td>
        <td>${approval.assigned_queue}</td>
        <td>${approvalBadge(approval.status)}</td>
      </tr>`).join('');

    if (!selectedApprovalId && approvals.length) {
      selectApproval(approvals[0].ticket_id);
    }
  } catch {}
}

async function selectApproval(ticketId) {
  selectedApprovalId = ticketId;
  try {
    const [detail, history] = await Promise.all([
      apiFetch(`/approvals/${ticketId}`),
      apiFetch(`/approvals/${ticketId}/history`),
    ]);
    document.getElementById('approval-empty').style.display = 'none';
    document.getElementById('approval-editor').style.display = 'block';
    document.getElementById('approval-ticket-id').value = detail.ticket_id;
    document.getElementById('approval-reviewer').value = currentUser ? currentUser.display_name : '';
    document.getElementById('approval-response').value = detail.final_response || detail.ai_response || '';
    document.getElementById('approval-notes').value = detail.reviewer_notes || '';
    const historyContainer = document.getElementById('approval-history');
    const events = history.events || [];
    historyContainer.innerHTML = events.length
      ? events.map((event) => `
          <div class="history-item">
            <strong>${event.event_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</strong>
            <span>${event.actor} · ${new Date(event.created_at).toLocaleString()}</span>
            <span>${event.details}</span>
          </div>`).join('')
      : '<div class="empty-state"><p>No history yet.</p></div>';
    loadApprovals();
  } catch {}
}

async function approveSelectedApproval() {
  if (!selectedApprovalId) return;
  const reviewer = document.getElementById('approval-reviewer').value.trim();
  const final_response = document.getElementById('approval-response').value.trim();
  if (!reviewer) {
    showToast('Reviewer name is required.', 'error');
    return;
  }
  try {
    await apiFetch(`/approvals/${selectedApprovalId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, final_response, send: true }),
    });
    showToast('Approval completed and marked sent.', 'success');
    selectedApprovalId = null;
    loadApprovals();
    loadDashboard();
  } catch {}
}

async function rejectSelectedApproval() {
  if (!selectedApprovalId) return;
  const reviewer = document.getElementById('approval-reviewer').value.trim();
  const notes = document.getElementById('approval-notes').value.trim();
  if (!reviewer) {
    showToast('Reviewer name is required.', 'error');
    return;
  }
  try {
    await apiFetch(`/approvals/${selectedApprovalId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, notes }),
    });
    showToast('Draft rejected.', 'info');
    selectedApprovalId = null;
    loadApprovals();
    loadDashboard();
  } catch {}
}

/* ─── Ticket Management ─── */
function statusBadge(status) {
  if (status === 'Completed') return '<span class="badge badge-status-approved">Completed</span>';
  if (status === 'Assigned') return '<span class="badge badge-status-assigned">Assigned</span>';
  if (status === 'WorkInProgress') return '<span class="badge badge-status-pendingapproval">Work In Progress</span>';
  if (status === 'Processing') return '<span class="badge badge-navy">Processing</span>';
  if (status === 'Escalated') return '<span class="badge badge-escalate">Escalated</span>';
  return '<span class="badge badge-status-open">Open</span>';
}

function renderQueueMembers(members, assignedTo) {
  if (!members || members.length === 0) return '<span style="color:var(--hope-text-muted)">—</span>';
  return members.map((m) => {
    const isAssigned = assignedTo === m.username;
    const cls = isAssigned ? 'badge badge-expert' : 'badge badge-queue-member';
    return `<span class="${cls}" title="${m.username}">${m.display_name}</span>`;
  }).join(' ');
}

async function loadManagement() {
  try {
    const data = await apiFetch('/tickets');
    let tickets = data.tickets || [];
    const filter = document.getElementById('mgmt-status-filter').value;
    if (filter) tickets = tickets.filter((t) => t.status === filter);
    const tbody = document.getElementById('mgmt-tbody');
    document.getElementById('mgmt-count').textContent = `${tickets.length} tickets`;
    if (tickets.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><p>No tickets to display.</p></td></tr>';
      document.getElementById('mgmt-empty').style.display = 'block';
      document.getElementById('mgmt-editor').style.display = 'none';
      return;
    }
    tbody.innerHTML = tickets.reverse().map((t) => `
      <tr onclick="selectMgmtTicket('${t.ticket_id}')" class="${selectedMgmtTicketId === t.ticket_id ? 'row-selected' : ''}">
        <td><strong>${t.ticket_id}</strong></td>
        <td title="${(t.subject || '').replace(/"/g, '&quot;')}">${(t.subject || '').substring(0, 35)}${(t.subject || '').length > 35 ? '...' : ''}</td>
        <td>${statusBadge(t.status)}</td>
        <td>${renderQueueMembers(t.queue_members, t.assigned_to)}</td>
        <td>${t.category_name || t.category_id}</td>
        <td>${confBar(t.confidence)}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="event.stopPropagation();selectMgmtTicket('${t.ticket_id}')">Review</button>
        </td>
      </tr>`).join('');
  } catch {}
}

async function selectMgmtTicket(ticketId) {
  selectedMgmtTicketId = ticketId;
  try {
    const detail = await apiFetch(`/tickets/${ticketId}`);
    document.getElementById('mgmt-empty').style.display = 'none';
    document.getElementById('mgmt-editor').style.display = 'block';

    document.getElementById('mgmt-r-id').textContent = detail.ticket_id;
    const statusEl = document.getElementById('mgmt-r-status');
    statusEl.textContent = detail.status || 'Open';
    const statusClassMap = {
      Completed: 'badge badge-status-approved',
      Assigned: 'badge badge-status-assigned',
      WorkInProgress: 'badge badge-status-pendingapproval',
    };
    statusEl.className = statusClassMap[detail.status] || 'badge badge-status-open';
    document.getElementById('mgmt-r-category').textContent = detail.classification?.category_name || detail.classification?.category_id || '';
    document.getElementById('mgmt-r-subject').textContent = detail.subject;
    document.getElementById('mgmt-r-description').textContent = detail.description;
    document.getElementById('mgmt-r-submitter').textContent = detail.submitter || '';
    document.getElementById('mgmt-resolution-text').value = detail.ai_resolution || '';

    // Show translate button if ticket is in Spanish
    const mgmtTranslateContainer = document.getElementById('mgmt-translate-container');
    const mgmtTranslationResult = document.getElementById('mgmt-translation-result');
    if (mgmtTranslateContainer) {
      const ticketLang = (detail.classification?.language || 'en').toLowerCase();
      const hasResolution = !!detail.ai_resolution;
      mgmtTranslateContainer.style.display = (ticketLang === 'es' && hasResolution) ? '' : 'none';
      mgmtTranslationResult.style.display = 'none';
      const btn = document.getElementById('btn-mgmt-translate');
      if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Translate to English'; }
    }

    const similarRow = document.getElementById('mgmt-similar-badges');
    const ids = detail.similar_ticket_ids || [];
    if (ids.length > 0) {
      similarRow.innerHTML = '<span class="mgmt-field-label" style="margin:0">Referenced tickets:</span> ' +
        ids.map((id) => `<span class="badge badge-navy">${id}</span>`).join('');
    } else {
      similarRow.innerHTML = '<span class="mgmt-field-label" style="margin:0">No similar tickets found</span>';
    }

    const queueMembers = detail.routing?.queue_members || [];
    const queueName = detail.routing?.queue || '';
    await populateEngineerDropdown(queueMembers, queueName);
    const assignSelect = document.getElementById('mgmt-assign-select');
    assignSelect.value = detail.assigned_to || '';
    const assignedInfo = document.getElementById('mgmt-assigned-info');
    if (detail.assigned_to) {
      assignedInfo.textContent = `Currently assigned to: ${detail.assigned_to}`;
      assignedInfo.style.display = 'block';
    } else {
      assignedInfo.style.display = 'none';
    }

    loadManagement();
  } catch {}
}

async function populateEngineerDropdown(queueMembers, queueName) {
  if (cachedEngineers.length === 0) {
    try {
      const data = await apiFetch('/users/engineers');
      cachedEngineers = data.engineers || [];
    } catch { return; }
  }
  const select = document.getElementById('mgmt-assign-select');
  const memberUsernames = new Set((queueMembers || []).map((m) => m.username));

  let html = '<option value="">-- Select an engineer --</option>';
  if (queueMembers && queueMembers.length > 0) {
    html += `<optgroup label="${queueName || 'Queue'} Team">`;
    html += queueMembers.map((m) =>
      `<option value="${m.username}">${m.display_name} (${m.username})</option>`
    ).join('');
    html += '</optgroup>';
    const others = cachedEngineers.filter((e) => !memberUsernames.has(e.username));
    if (others.length > 0) {
      html += '<optgroup label="Other Engineers">';
      html += others.map((e) =>
        `<option value="${e.username}">${e.display_name} (${e.username})</option>`
      ).join('');
      html += '</optgroup>';
    }
  } else {
    html += cachedEngineers.map((e) =>
      `<option value="${e.username}">${e.display_name} (${e.username})</option>`
    ).join('');
  }
  select.innerHTML = html;
}

async function routeToEngineer() {
  if (!selectedMgmtTicketId) return;
  const engineer = document.getElementById('mgmt-assign-select').value;
  if (!engineer) {
    showToast('Please select an engineer.', 'error');
    return;
  }
  try {
    await apiFetch(`/tickets/${selectedMgmtTicketId}/assign`, {
      method: 'POST',
      body: JSON.stringify({ assigned_to: engineer }),
    });
    showToast(`Ticket ${selectedMgmtTicketId} routed to ${engineer}.`, 'success');
    selectMgmtTicket(selectedMgmtTicketId);
  } catch {}
}

async function resolveSelectedTicket() {
  if (!selectedMgmtTicketId) return;
  const resolution = document.getElementById('mgmt-resolution-text').value.trim();
  if (!resolution) {
    showToast('Resolution cannot be empty.', 'error');
    return;
  }
  const reviewer = currentUser ? currentUser.display_name : 'Admin';
  try {
    await apiFetch(`/tickets/${selectedMgmtTicketId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, ai_resolution: resolution || null }),
    });
    showToast(`Ticket ${selectedMgmtTicketId} resolved.`, 'success');
    selectedMgmtTicketId = null;
    document.getElementById('mgmt-empty').style.display = 'block';
    document.getElementById('mgmt-editor').style.display = 'none';
    loadManagement();
    loadDashboard();
  } catch {}
}

async function saveResolutionEdit() {
  if (!selectedMgmtTicketId) return;
  const resolution = document.getElementById('mgmt-resolution-text').value.trim();
  if (!resolution) { showToast('Resolution cannot be empty.', 'error'); return; }
  try {
    await apiFetch(`/tickets/${selectedMgmtTicketId}/resolution`, {
      method: 'PATCH',
      body: JSON.stringify({ ai_resolution: resolution }),
    });
    showToast('Resolution saved.', 'success');
    selectMgmtTicket(selectedMgmtTicketId);
  } catch {}
}

async function deleteSelectedTicket() {
  if (!selectedMgmtTicketId) return;
  if (!confirm(`Delete ticket ${selectedMgmtTicketId}? This action cannot be undone.`)) return;
  try {
    await apiFetch(`/tickets/${selectedMgmtTicketId}`, { method: 'DELETE' });
    showToast(`Ticket ${selectedMgmtTicketId} deleted.`, 'info');
    selectedMgmtTicketId = null;
    document.getElementById('mgmt-empty').style.display = 'block';
    document.getElementById('mgmt-editor').style.display = 'none';
    loadManagement();
    loadDashboard();
  } catch {}
}

/* ─── My Queue (Engineer) ─── */
async function loadMyQueue() {
  if (!currentUser) return;
  try {
    const data = await apiFetch(`/tickets/my-queue/${currentUser.username}`);
    const tickets = data.tickets || [];
    const tbody = document.getElementById('myqueue-tbody');
    document.getElementById('myqueue-count').textContent = `${tickets.length} tickets`;
    if (tickets.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><p>No tickets assigned to you.</p></td></tr>';
      document.getElementById('myqueue-empty').style.display = 'block';
      document.getElementById('myqueue-editor').style.display = 'none';
      return;
    }
    tbody.innerHTML = tickets.reverse().map((t) => `
      <tr onclick="selectMyQueueTicket('${t.ticket_id}')" class="${selectedMyQueueTicketId === t.ticket_id ? 'row-selected' : ''}">
        <td><strong>${t.ticket_id}</strong></td>
        <td title="${(t.subject || '').replace(/"/g, '&quot;')}">${(t.subject || '').substring(0, 35)}${(t.subject || '').length > 35 ? '...' : ''}</td>
        <td>${statusBadge(t.status)}</td>
        <td>${t.category_name || t.category_id}</td>
        <td>${confBar(t.confidence)}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="event.stopPropagation();selectMyQueueTicket('${t.ticket_id}')">Work</button>
        </td>
      </tr>`).join('');
  } catch {}
}

async function selectMyQueueTicket(ticketId) {
  selectedMyQueueTicketId = ticketId;
  try {
    const detail = await apiFetch(`/tickets/${ticketId}`);
    document.getElementById('myqueue-empty').style.display = 'none';
    document.getElementById('myqueue-editor').style.display = 'block';

    document.getElementById('mq-r-id').textContent = detail.ticket_id;
    const statusEl = document.getElementById('mq-r-status');
    statusEl.textContent = detail.status || 'Assigned';
    const statusClassMap = {
      Completed: 'badge badge-status-approved',
      Assigned: 'badge badge-status-assigned',
      WorkInProgress: 'badge badge-status-pendingapproval',
    };
    statusEl.className = statusClassMap[detail.status] || 'badge badge-status-open';
    document.getElementById('mq-r-category').textContent = detail.classification?.category_name || detail.classification?.category_id || '';
    document.getElementById('mq-r-subject').textContent = detail.subject;
    document.getElementById('mq-r-description').textContent = detail.description;
    document.getElementById('mq-r-submitter').textContent = detail.submitter || '';
    document.getElementById('mq-ai-suggestion').textContent = detail.ai_resolution || 'No AI suggestion available.';
    document.getElementById('mq-resolution-text').value = '';

    // Show translate button if ticket is in Spanish
    const mqTranslateContainer = document.getElementById('mq-translate-container');
    const mqTranslationResult = document.getElementById('mq-translation-result');
    if (mqTranslateContainer) {
      const ticketLang = (detail.classification?.language || 'en').toLowerCase();
      const hasResolution = !!detail.ai_resolution;
      mqTranslateContainer.style.display = (ticketLang === 'es' && hasResolution) ? '' : 'none';
      mqTranslationResult.style.display = 'none';
      const btn = document.getElementById('btn-mq-translate');
      if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Translate to English'; }
    }

    loadMyQueue();
  } catch {}
}

async function submitEngineerResolution() {
  if (!selectedMyQueueTicketId || !currentUser) return;
  const resolution = document.getElementById('mq-resolution-text').value.trim();
  if (!resolution) {
    showToast('Please enter your resolution.', 'error');
    return;
  }
  try {
    await apiFetch(`/tickets/${selectedMyQueueTicketId}/engineer-resolve`, {
      method: 'POST',
      body: JSON.stringify({ engineer: currentUser.username, resolution }),
    });
    showToast('Resolution submitted. Ticket sent back to admin for final approval.', 'success');
    selectedMyQueueTicketId = null;
    document.getElementById('myqueue-empty').style.display = 'block';
    document.getElementById('myqueue-editor').style.display = 'none';
    loadMyQueue();
  } catch {}
}

/* ─── Explorer ─── */
let explorerTicketsCache = [];
let selectedExplorerTicketId = null;

async function loadExplorer() {
  try {
    const data = await apiFetch('/tickets');
    explorerTicketsCache = (data.tickets || []).slice().reverse();
    filterExplorer();
  } catch {}
}

function filterExplorer() {
  const search = (document.getElementById('explorer-search').value || '').toLowerCase();
  const statusFilter = document.getElementById('explorer-status-filter').value;
  let tickets = explorerTicketsCache;
  if (statusFilter) tickets = tickets.filter((t) => t.status === statusFilter);
  if (search) tickets = tickets.filter((t) =>
    (t.ticket_id || '').toLowerCase().includes(search) ||
    (t.subject || '').toLowerCase().includes(search) ||
    (t.submitter || '').toLowerCase().includes(search) ||
    (t.category_name || '').toLowerCase().includes(search)
  );
  renderExplorerTable(tickets);
}

function renderExplorerTable(tickets) {
  const tbody = document.getElementById('explorer-tbody');
  document.getElementById('explorer-count').textContent = `${tickets.length} tickets`;
  if (tickets.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><p>No tickets match your filter.</p></td></tr>';
    return;
  }
  tbody.innerHTML = tickets.map((t) => `
    <tr onclick="selectExplorerTicket('${t.ticket_id}')" class="${selectedExplorerTicketId === t.ticket_id ? 'row-selected' : ''}" style="cursor:pointer">
      <td><strong>${t.ticket_id}</strong></td>
      <td title="${(t.subject || '').replace(/"/g, '&quot;')}">${(t.subject || '').substring(0, 40)}${(t.subject || '').length > 40 ? '...' : ''}</td>
      <td>${t.category_name || t.category_id}</td>
      <td>${confBar(t.confidence)}</td>
      <td>${statusBadge(t.status)}</td>
    </tr>`).join('');
}

function urgencyBadge(urgency) {
  const map = { low: 'Low', medium: 'Medium', high: 'High', critical: 'Critical' };
  const label = map[urgency] || urgency;
  return `<span class="badge badge-urgency-${urgency || 'medium'}">${label}</span>`;
}

function sentimentBadge(sentiment) {
  const map = { positive: 'Positive', neutral: 'Neutral', negative: 'Negative', frustrated: 'Frustrated' };
  const label = map[sentiment] || sentiment;
  return `<span class="badge badge-sentiment-${sentiment || 'neutral'}">${label}</span>`;
}

function switchExpTab(tab) {
  document.querySelectorAll('.exp-tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.exp-tab-content').forEach((c) => c.classList.toggle('active', c.id === `exp-tab-${tab}`));
}

function toggleKBExpand(el) {
  el.closest('.exp-kb-item').classList.toggle('expanded');
}

async function selectExplorerTicket(ticketId) {
  selectedExplorerTicketId = ticketId;
  filterExplorer();
  switchExpTab('overview');
  try {
    const d = await apiFetch(`/tickets/${ticketId}`);
    document.getElementById('explorer-empty').style.display = 'none';
    document.getElementById('explorer-detail').style.display = 'block';

    document.getElementById('exp-ticket-id').textContent = d.ticket_id;
    document.getElementById('exp-status').innerHTML = statusBadge(d.status);
    document.getElementById('exp-urgency').innerHTML = urgencyBadge(d.classification?.urgency);
    document.getElementById('exp-sentiment').innerHTML = sentimentBadge(d.classification?.sentiment);
    document.getElementById('exp-subject').textContent = d.subject || '';
    document.getElementById('exp-submitter').textContent = d.submitter || 'Unknown';
    const ts = d.processed_at ? new Date(d.processed_at).toLocaleString() : '';
    document.getElementById('exp-timestamp').textContent = ts || '';

    // Calculate and display ticket age / open duration
    const durationEl = document.getElementById('exp-duration');
    if (durationEl && d.processed_at) {
      const created = new Date(d.processed_at);
      const now = new Date();
      const diffMs = now - created;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);
      let durationStr;
      if (diffDays > 0) {
        const remHours = diffHours % 24;
        durationStr = `${diffDays}d ${remHours}h`;
      } else if (diffHours > 0) {
        const remMins = diffMins % 60;
        durationStr = `${diffHours}h ${remMins}m`;
      } else {
        durationStr = `${diffMins}m`;
      }
      const isCompleted = d.status === 'Completed';
      const durationColor = isCompleted ? '#059669' : diffHours >= 24 ? '#dc2626' : diffHours >= 4 ? '#d97706' : '#64748b';
      durationEl.innerHTML = `<span style="color:${durationColor};font-weight:600;font-size:.82rem;">${isCompleted ? '✓ Resolved' : '⏱ Open for'} ${durationStr}</span>`;
    }

    document.getElementById('exp-proc-time').textContent = `${(d.processing_time_ms || 0).toFixed(0)}ms`;
    document.getElementById('exp-description').textContent = d.description || '';

    document.getElementById('exp-category').textContent = d.classification?.category_name || '';
    document.getElementById('exp-confidence').innerHTML = confBar(d.classification?.confidence);
    document.getElementById('exp-language').textContent = (d.classification?.language || 'en').toUpperCase();
    document.getElementById('exp-queue').textContent = d.routing?.queue || '';
    document.getElementById('exp-summary').textContent = d.classification?.summary || 'No summary available.';

    document.getElementById('exp-routing-action').innerHTML = actionBadge(d.routing?.action);
    document.getElementById('exp-routing-queue').textContent = d.routing?.queue || '';
    document.getElementById('exp-assigned-to').textContent = d.assigned_to || '—';
    document.getElementById('exp-requires-approval').textContent = d.routing?.requires_approval ? 'Yes' : 'No';
    document.getElementById('exp-routing-reason').textContent = d.routing?.reason || '';

    const qmContainer = document.getElementById('exp-queue-members');
    const queueMembers = d.routing?.queue_members || [];
    if (qmContainer) {
      if (queueMembers.length > 0) {
        qmContainer.innerHTML = queueMembers.map((m) => {
          const isAssigned = d.assigned_to === m.username;
          const cls = isAssigned ? 'badge badge-expert' : 'badge badge-queue-member';
          return `<span class="${cls}" title="${m.username}">${m.display_name}</span>`;
        }).join(' ');
      } else {
        qmContainer.innerHTML = '<span style="font-size:.78rem;color:var(--hope-text-muted)">No queue members configured.</span>';
      }
    }

    document.getElementById('exp-ai-resolution').textContent = d.ai_resolution || 'No AI resolution generated.';

    // Show translate button for Spanish tickets
    const translateContainer = document.getElementById('exp-translate-container');
    const translationResult = document.getElementById('exp-translation-result');
    if (translateContainer) {
      const ticketLang = (d.classification?.language || 'en').toLowerCase();
      translateContainer.style.display = (ticketLang === 'es' && d.ai_resolution) ? '' : 'none';
      translationResult.style.display = 'none';
      const btn = document.getElementById('btn-translate-resolution');
      if (btn) { btn.disabled = false; btn.dataset.state = ''; btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Translate to English'; }
    }

    const similarContainer = document.getElementById('exp-similar-tickets');
    const simIds = d.similar_ticket_ids || [];
    if (simIds.length > 0) {
      try {
        const simData = await apiFetch(`/tickets/${ticketId}/similar`);
        const simTickets = simData.similar || [];
        if (simTickets.length > 0) {
          similarContainer.innerHTML = simTickets.map((s) => `
            <div class="exp-similar-item" onclick="selectExplorerTicket('${s.ticket_id}')">
              <span class="exp-similar-id">${s.ticket_id}</span>
              <span class="exp-similar-subject">${s.subject}</span>
              <span class="exp-similar-sim">${(s.similarity * 100).toFixed(0)}%</span>
              ${statusBadge(s.status)}
            </div>`).join('');
        } else {
          similarContainer.innerHTML = simIds.map((id) =>
            `<div class="exp-similar-item" onclick="selectExplorerTicket('${id}')"><span class="exp-similar-id">${id}</span></div>`
          ).join('');
        }
      } catch {
        similarContainer.innerHTML = simIds.map((id) =>
          `<div class="exp-similar-item" onclick="selectExplorerTicket('${id}')"><span class="exp-similar-id">${id}</span></div>`
        ).join('');
      }
    } else {
      similarContainer.innerHTML = '<span style="font-size:.78rem;color:var(--hope-text-muted)">No historical matches.</span>';
    }

    const kbSection = document.getElementById('exp-kb-section');
    const kbList = document.getElementById('exp-kb-articles');
    const kbArticles = d.kb_articles_used || [];
    const uniqueKB = [...new Set(kbArticles)];
    if (uniqueKB.length > 0) {
      kbSection.style.display = '';
      kbList.innerHTML = uniqueKB.map((a) => {
        const fname = a.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_');
        return `<div class="exp-kb-item" id="kb-exp-${fname}">
          <div class="exp-kb-item-header" onclick="toggleKBExpand(this); loadKBInline(this, '${a}')">
            <span class="exp-kb-item-title">${a}</span>
            <span class="exp-kb-item-toggle">&#9660;</span>
          </div>
          <div class="exp-kb-item-body">
            <div class="kb-content-box">Loading...</div>
          </div>
        </div>`;
      }).join('');
    } else {
      kbSection.style.display = 'none';
    }

    const responseSection = document.getElementById('exp-response-section');
    const responseText = document.getElementById('exp-response-text');
    if (d.response_text) {
      responseSection.style.display = '';
      responseText.textContent = d.response_text;
    } else {
      responseSection.style.display = 'none';
    }

    const recContainer = document.getElementById('exp-recommend-list');
    try {
      const rec = await apiFetch(`/tickets/${ticketId}/recommend-engineer`);
      const recs = rec.recommendations || [];
      if (recs.length > 0) {
        recContainer.innerHTML = recs.map((r, i) => `
          <div class="recommend-card ${i === 0 ? 'top-pick' : ''}">
            <span class="recommend-rank">${i + 1}</span>
            <span class="recommend-name">${r.display_name}</span>
            <div class="recommend-meta">
              ${r.is_expert ? '<span class="badge badge-expert">Expert</span>' : ''}
              <span class="recommend-load">${r.open_tickets} ticket${r.open_tickets !== 1 ? 's' : ''}</span>
            </div>
          </div>`).join('');
      } else {
        recContainer.innerHTML = '<span style="font-size:.78rem;color:var(--hope-text-muted)">No engineers available.</span>';
      }
    } catch {
      recContainer.innerHTML = '<span style="font-size:.78rem;color:var(--hope-text-muted)">Could not load recommendations.</span>';
    }
  } catch {}
}

async function translateResolution() {
  _translatePanelText(
    selectedExplorerTicketId,
    () => document.getElementById('exp-ai-resolution').textContent,
    'btn-translate-resolution', 'exp-translation-result', 'exp-translated-text'
  );
}

/* ─── Generic bidirectional translate helper for management / myqueue panels ─── */
async function _translatePanelText(ticketId, textSource, btnId, resultDivId, textDivId) {
  if (!ticketId) return;
  const btn = document.getElementById(btnId);
  const resultDiv = document.getElementById(resultDivId);
  const textDiv = document.getElementById(textDivId);
  if (!btn || !resultDiv || !textDiv) return;

  // Toggle: if already showing translation, hide it and swap label
  if (resultDiv.style.display !== 'none' && resultDiv.style.display !== '') {
    // Currently showing English → offer to show original (Spanish)
    if (btn.dataset.state === 'translated') {
      resultDiv.style.display = 'none';
      btn.dataset.state = 'original';
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Translate to English';
      return;
    }
  }

  // If we already translated, just show it again
  if (textDiv.textContent && btn.dataset.state === 'original') {
    resultDiv.style.display = '';
    btn.dataset.state = 'translated';
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Show Original (Spanish)';
    return;
  }

  const originalText = typeof textSource === 'function' ? textSource() : textSource;
  if (!originalText) return;

  btn.disabled = true;
  btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Translating...';

  try {
    const data = await apiFetch(`/tickets/${ticketId}/translate`, {
      method: 'POST',
      body: JSON.stringify({ text: originalText, source_language: 'es', target_language: 'en' }),
    });
    textDiv.textContent = data.translated_text;
    resultDiv.style.display = '';
    btn.dataset.state = 'translated';
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Show Original (Spanish)';
  } catch (err) {
    showToast('Translation failed. Please try again.', 'error');
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/></svg> Translate to English';
  }
}

async function translateMgmtResolution() {
  _translatePanelText(
    selectedMgmtTicketId,
    () => document.getElementById('mgmt-resolution-text').value,
    'btn-mgmt-translate', 'mgmt-translation-result', 'mgmt-translated-text'
  );
}

async function translateMqResolution() {
  _translatePanelText(
    selectedMyQueueTicketId,
    () => document.getElementById('mq-ai-suggestion').textContent,
    'btn-mq-translate', 'mq-translation-result', 'mq-translated-text'
  );
}

async function loadKBInline(headerEl, articleTitle) {
  const body = headerEl.closest('.exp-kb-item').querySelector('.exp-kb-item-body .kb-content-box');
  if (body.dataset.loaded) return;
  try {
    const articles = await apiFetch('/kb/articles');
    const match = (articles.articles || []).find((a) => a.title === articleTitle);
    if (match) {
      const detail = await apiFetch(`/kb/articles/${encodeURIComponent(match.filename)}`);
      body.innerHTML = `<div class="exp-sub-heading" style="margin-bottom:4px">Resolution Steps</div>
        <div style="white-space:pre-wrap;margin-bottom:10px">${detail.resolution_steps || 'N/A'}</div>
        <div class="exp-sub-heading" style="margin-bottom:4px">Response Template</div>
        <div style="white-space:pre-wrap">${detail.response_template || 'N/A'}</div>`;
      body.dataset.loaded = 'true';
    } else {
      body.textContent = 'Article not found in KB.';
    }
  } catch {
    body.textContent = 'Failed to load article.';
  }
}

/* ─── Analytics ─── */
async function loadAnalytics() {
  try {
    const [report, trends] = await Promise.all([
      apiFetch('/analytics/summary'),
      apiFetch('/analytics/trends'),
    ]);

    const overview = report.overview || {};
    const ai = report.ai_assistance || {};
    const aiHuman = trends.ai_vs_human || {};

    document.getElementById('an-total').textContent = overview.total || 0;
    document.getElementById('an-ai-resolved').textContent = `${aiHuman.ai_pct || 0}%`;
    document.getElementById('an-human-resolved').textContent = `${aiHuman.human_pct || 0}%`;
    document.getElementById('an-sent-rate').textContent = `${((ai.sent_rate || 0) * 100).toFixed(1)}%`;
    document.getElementById('an-pending-count').textContent = ai.pending_approval || 0;

    renderPieChart('chart-ai-human', {
      'AI Resolved': aiHuman.ai_resolved || 0,
      'Human Resolved': aiHuman.human_resolved || 0,
      'Pending': aiHuman.pending || 0,
    }, {
      'AI Resolved': '#059669',
      'Human Resolved': '#003E7E',
      'Pending': '#d97706',
    });

    renderTopRecurring(trends.top_recurring_issues || []);

    renderBarChart('chart-categories', report.category_distribution || {}, '#003E7E');
    renderPieChart('chart-queues', report.queue_distribution || {}, {
      'IT Support': '#003E7E',
      'L&D': '#C9A961',
      'Marketing': '#059669',
      'Leadership': '#7c3aed',
    });

    renderEngineerPerformance(trends.engineer_performance || []);
    renderTrainingAlerts(trends.training_alerts || []);

    const gaps = report.knowledge_gaps || [];
    const gapTbody = document.getElementById('gap-tbody');
    if (gaps.length === 0) {
      gapTbody.innerHTML = '<tr><td colspan="4" class="empty-state"><p>No knowledge gaps detected.</p></td></tr>';
    } else {
      gapTbody.innerHTML = gaps.map((g) => `
        <tr>
          <td><strong>${g.category_name}</strong></td>
          <td>${confBar(g.avg_confidence)}</td>
          <td>${g.ticket_count}</td>
          <td>${g.recommendation}</td>
        </tr>`).join('');
    }

    renderInsights('analytics-insights', report.actionable_insights || []);

    renderLDInsights(trends.ld_insights || {});
    renderProductInsights(trends.product_insights || {});

    // Time-based trends
    renderTimeTrends(trends.time_trends || {});

    // Feedback summary
    renderFeedbackSummary(report.resolution_feedback || {});

    // Program knowledge gaps
    renderProgramGaps(report.program_knowledge_gaps || []);

    // Submitter knowledge gaps
    renderSubmitterGaps(report.submitter_knowledge_gaps || []);
  } catch (e) { console.error('Analytics load error:', e); }
}

function renderTopRecurring(items) {
  const container = document.getElementById('an-top-recurring');
  if (!items || items.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>Not enough data for trend analysis.</p></div>';
    return;
  }
  container.innerHTML = items.map((item, idx) => {
    const spike = item.is_spiking ? '<span class="badge badge-spike">SPIKE</span>' : '';
    return `
      <div class="recurring-item">
        <div class="recurring-rank">${idx + 1}</div>
        <div class="recurring-info">
          <div class="recurring-label">${item.label}${spike}</div>
          <div class="recurring-meta">${item.count} tickets &middot; ${item.sample_subjects.slice(0, 2).join(', ')}</div>
        </div>
        <div class="recurring-bar-wrap">
          <span class="recurring-pct">${item.percentage}%</span>
        </div>
      </div>`;
  }).join('');
}

function renderEngineerPerformance(engineers) {
  const tbody = document.getElementById('an-engineer-tbody');
  if (!engineers || engineers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><p>No engineer data yet.</p></td></tr>';
    return;
  }
  tbody.innerHTML = engineers.map((e) => {
    const rate = e.assigned_count > 0 ? Math.round((e.resolved_count / e.assigned_count) * 100) : 0;
    return `
      <tr>
        <td><strong>${e.display_name}</strong> <span style="color:var(--hope-text-muted);font-size:.75rem">(${e.username})</span></td>
        <td>${e.assigned_count}</td>
        <td>${e.resolved_count}</td>
        <td>${e.open_count}</td>
        <td>
          ${rate}%
          <span class="perf-bar"><span class="perf-fill" style="width:${rate}%"></span></span>
        </td>
      </tr>`;
  }).join('');
}

function renderTrainingAlerts(alerts) {
  const container = document.getElementById('an-training-alerts');
  if (!alerts || alerts.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No training alerts detected.</p></div>';
    return;
  }
  container.innerHTML = alerts.map((a) => `
    <div class="training-alert-item">
      <h4>${a.category_name}</h4>
      <div class="alert-count">${a.how_to_count} how-to tickets out of ${a.total_in_category}</div>
      <p>${a.recommendation}</p>
    </div>`).join('');
}

function renderLDInsights(ld) {
  document.getElementById('ld-total').textContent = ld.total || 0;
  document.getElementById('ld-howto-pct').textContent = `${ld.how_to_pct || 0}%`;
  document.getElementById('ld-feedback').textContent = ld.feedback_count || 0;
  const cats = ld.categories || [];
  const catBox = document.getElementById('ld-categories');
  if (cats.length === 0) {
    catBox.innerHTML = '<div class="empty-state"><p>No L&D data yet.</p></div>';
  } else {
    catBox.innerHTML = cats.map((c, i) => `
      <div class="recurring-item">
        <div class="recurring-rank">${i + 1}</div>
        <div class="recurring-info"><div class="recurring-label">${c.name}</div></div>
        <div class="recurring-bar-wrap"><span class="recurring-pct">${c.count}</span></div>
      </div>`).join('');
  }
  const recs = ld.recommendations || [];
  const recBox = document.getElementById('ld-recs');
  if (recs.length === 0) {
    recBox.innerHTML = '<div class="empty-state"><p>No recommendations yet.</p></div>';
  } else {
    recBox.innerHTML = recs.map((r) => `
      <div class="insight-item" style="border-left:3px solid var(--hope-gold);padding:8px 12px;margin-bottom:8px;font-size:.82rem;background:var(--hope-bg);border-radius:8px">
        ${r}
      </div>`).join('');
  }
}

function renderProductInsights(pi) {
  document.getElementById('pi-bugs').textContent = pi.bug_count || 0;
  document.getElementById('pi-user-err').textContent = `${pi.user_error_pct || 0}%`;
  document.getElementById('pi-bug-pct').textContent = `${pi.bug_pct || 0}%`;
  const friction = pi.friction_points || [];
  const fBox = document.getElementById('pi-friction');
  if (friction.length === 0) {
    fBox.innerHTML = '<div class="empty-state"><p>No friction data yet.</p></div>';
  } else {
    fBox.innerHTML = friction.map((f, i) => `
      <div class="recurring-item">
        <div class="recurring-rank">${i + 1}</div>
        <div class="recurring-info">
          <div class="recurring-label">${f.name}</div>
          <div class="recurring-meta">${f.count} tickets &middot; ${f.reason}</div>
        </div>
      </div>`).join('');
  }
  const gaps = pi.feature_gaps || [];
  const gBox = document.getElementById('pi-gaps');
  if (gaps.length === 0) {
    gBox.innerHTML = '<div class="empty-state"><p>No feature gap data yet.</p></div>';
  } else {
    gBox.innerHTML = gaps.map((g, i) => `
      <div class="recurring-item">
        <div class="recurring-rank">${i + 1}</div>
        <div class="recurring-info">
          <div class="recurring-label">${g.name}</div>
          <div class="recurring-meta">${g.low_confidence_count} low-confidence out of ${g.total} &middot; ${g.reason}</div>
        </div>
      </div>`).join('');
  }
}

/* ─── Time Trends, Feedback, Program & Submitter Gaps ─── */
function renderTimeTrends(tt) {
  const container = document.getElementById('an-time-trends');
  if (!container) return;
  if (!tt || !tt.weekly_volume || tt.weekly_volume.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>Not enough data for time trends.</p></div>';
    return;
  }
  const wowBadge = tt.wow_change_pct > 0
    ? `<span style="color:#dc2626;font-weight:600">+${tt.wow_change_pct}% WoW</span>`
    : tt.wow_change_pct < 0
      ? `<span style="color:#059669;font-weight:600">${tt.wow_change_pct}% WoW</span>`
      : '<span style="color:var(--hope-text-muted)">No change WoW</span>';
  const busiest = tt.busiest_day ? `Busiest day: <strong>${tt.busiest_day}</strong>` : '';

  container.innerHTML = `
    <div style="display:flex;gap:16px;margin-bottom:12px;font-size:.84rem;align-items:center;flex-wrap:wrap">
      ${wowBadge} ${busiest ? '&middot; ' + busiest : ''}
    </div>
    <canvas id="chart-time-trends" height="200"></canvas>`;

  const labels = tt.weekly_volume.map(w => w.week);
  const data = tt.weekly_volume.map(w => w.count);
  const ctx = document.getElementById('chart-time-trends');
  if (chartInstances['chart-time-trends']) chartInstances['chart-time-trends'].destroy();
  chartInstances['chart-time-trends'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Tickets per Week',
        data,
        borderColor: '#003E7E',
        backgroundColor: 'rgba(0,62,126,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderFeedbackSummary(fb) {
  const container = document.getElementById('an-feedback-summary');
  if (!container) return;
  if (!fb || fb.total === 0) {
    container.innerHTML = '<div class="empty-state"><p>No resolution feedback collected yet.</p></div>';
    return;
  }
  const pct = Math.round(fb.satisfaction_rate * 100);
  const color = pct >= 70 ? '#059669' : pct >= 40 ? '#d97706' : '#dc2626';
  container.innerHTML = `
    <div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center">
      <div style="text-align:center">
        <div style="font-size:2rem;font-weight:700;color:${color}">${pct}%</div>
        <div style="font-size:.78rem;color:var(--hope-text-muted)">Satisfaction Rate</div>
      </div>
      <div style="font-size:.84rem;line-height:1.8">
        <div><strong>${fb.total}</strong> total feedback entries</div>
        <div><span style="color:#059669">${fb.helpful}</span> helpful &middot; <span style="color:#dc2626">${fb.unhelpful}</span> unhelpful</div>
      </div>
    </div>`;
}

function renderProgramGaps(gaps) {
  const container = document.getElementById('an-program-gaps');
  if (!container) return;
  if (!gaps || gaps.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>Not enough data for program analysis.</p></div>';
    return;
  }
  const esc = (s) => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : '';
  container.innerHTML = gaps.map((g, i) => `
    <div class="recurring-item">
      <div class="recurring-rank">${i + 1}</div>
      <div class="recurring-info">
        <div class="recurring-label">${esc(g.queue)}</div>
        <div class="recurring-meta">${g.total_tickets} tickets &middot; ${g.how_to_pct}% how-to &middot; Top: ${esc(g.top_category)}</div>
        ${g.recommendation ? `<div style="font-size:.78rem;color:var(--hope-text-muted);margin-top:2px">${esc(g.recommendation)}</div>` : ''}
      </div>
    </div>`).join('');
}

function renderSubmitterGaps(gaps) {
  const container = document.getElementById('an-submitter-gaps');
  if (!container) return;
  if (!gaps || gaps.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No repeat submitter patterns detected.</p></div>';
    return;
  }
  const esc = (s) => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : '';
  container.innerHTML = `<table class="data-table" style="font-size:.82rem"><thead><tr>
    <th>Submitter</th><th>Category</th><th>Repeat</th><th>Recommendation</th>
  </tr></thead><tbody>${gaps.slice(0, 10).map(g => `<tr>
    <td>${esc(g.submitter_email)}</td>
    <td>${esc(g.category_name)}</td>
    <td><strong>${g.repeat_count}</strong></td>
    <td style="font-size:.78rem">${esc(g.recommendation)}</td>
  </tr>`).join('')}</tbody></table>`;
}

/* ─── Knowledge Base ─── */
let selectedKBArticle = null;

async function loadKnowledgeBase() {
  try {
    const [statusData, articleData] = await Promise.all([
      apiFetch('/kb/status'),
      apiFetch('/kb/articles'),
    ]);

    document.getElementById('kb-article-count').textContent = statusData.article_count || 0;
    document.getElementById('kb-chunk-count').textContent = statusData.chunk_count || 0;
    document.getElementById('kb-persist-dir').textContent = statusData.persist_dir || '-';

    const list = document.getElementById('kb-list');
    const articles = articleData.articles || [];
    document.getElementById('kb-list-count').textContent = `${articles.length} articles`;
    list.innerHTML = articles.map((article) => `
      <div class="kb-item ${selectedKBArticle === article.filename ? 'kb-selected' : ''}" data-filename="${article.filename}" onclick="selectKBArticle('${article.filename}')">
        <div>
          <div class="kb-title">${article.title}</div>
          <div class="kb-meta">${article.category} · ${article.queue} · ${article.auto_resolvable ? 'AI-draft eligible' : 'Human handled'}</div>
        </div>
        <span class="badge badge-navy">${article.ticket_type}</span>
      </div>`).join('');
  } catch (e) {
    console.error('Failed to load knowledge base:', e);
  }
}

async function selectKBArticle(filename) {
  selectedKBArticle = filename;

  document.querySelectorAll('.kb-item').forEach((el) => {
    el.classList.toggle('kb-selected', el.dataset.filename === filename);
  });

  try {
    const d = await apiFetch(`/kb/articles/${encodeURIComponent(filename)}`);
    document.getElementById('kb-detail-empty').style.display = 'none';
    document.getElementById('kb-detail').style.display = 'block';

    document.getElementById('kb-d-title').textContent = d.title;
    document.getElementById('kb-d-type').textContent = d.ticket_type;
    const autoEl = document.getElementById('kb-d-auto');
    autoEl.textContent = d.auto_resolvable ? 'AI-Draft Eligible' : 'Human Only';
    autoEl.className = d.auto_resolvable ? 'badge badge-expert' : 'badge badge-status-open';
    document.getElementById('kb-d-updated').textContent = d.last_updated ? `Updated ${d.last_updated}` : '';
    document.getElementById('kb-d-queue').textContent = d.queue;
    document.getElementById('kb-d-category').textContent = d.category;
    document.getElementById('kb-d-resolution').textContent = d.resolution_steps || 'No resolution steps documented.';
    document.getElementById('kb-d-template').textContent = d.response_template || 'No template available.';

    const notesSection = document.getElementById('kb-d-notes-section');
    const notesEl = document.getElementById('kb-d-notes');
    if (d.internal_notes) {
      notesSection.style.display = '';
      notesEl.textContent = d.internal_notes;
    } else {
      notesSection.style.display = 'none';
    }
  } catch (e) {
    console.error('Failed to load KB article:', e);
  }
}

async function searchKB() {
  const query = document.getElementById('kb-search-input').value.trim();
  if (!query) return;
  try {
    const data = await apiFetch(`/kb/search?query=${encodeURIComponent(query)}&limit=5`);
    const container = document.getElementById('kb-results');
    if (!data.results || data.results.length === 0) {
      container.innerHTML = '<p class="empty-state">No results found.</p>';
      return;
    }
    container.innerHTML = data.results.map((r) => `
      <div class="kb-item">
        <div>
          <div class="kb-title">${r.title || 'Article'}</div>
          <div class="kb-meta">${r.category} · Relevance: ${(r.similarity * 100).toFixed(0)}%</div>
          <div class="kb-meta">${r.content}</div>
        </div>
        <span class="badge badge-gold">${r.category}</span>
      </div>`).join('');
  } catch {}
}

async function reingestKB() {
  const btn = document.getElementById('btn-reingest');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Ingesting...';
  try {
    const data = await apiFetch('/kb/ingest?force=true', { method: 'POST' });
    showToast(`Ingested ${data.documents_added} document chunks.`, 'success');
    loadKnowledgeBase();
  } catch {} finally {
    btn.disabled = false;
    btn.innerHTML = 'Re-ingest KB';
  }
}

/* ─── Configuration: Queue Team Members ─── */
let configEngineers = [];
let configExpertise = {};

async function loadExpertiseConfig() {
  try {
    const [engData, expData, queueData] = await Promise.all([
      apiFetch('/users/engineers'),
      apiFetch('/config/expertise'),
      apiFetch('/queues'),
    ]);
    configEngineers = engData.engineers || [];
    configExpertise = expData.expertise || {};
    cachedQueues = queueData.queues || {};

    const expertByCategory = {};
    for (const [eng, cats] of Object.entries(configExpertise)) {
      for (const cat of cats) {
        if (!expertByCategory[cat]) expertByCategory[cat] = [];
        expertByCategory[cat].push(eng);
      }
    }

    document.querySelectorAll('.config-eng-cell').forEach((cell) => {
      const catId = cell.dataset.category;
      const queueName = cell.dataset.queue;
      const tagContainer = cell.querySelector('.config-eng-tags');
      const queueConfig = cachedQueues[queueName];
      const queueMemberNames = queueConfig ? queueConfig.members.map((m) => m.username) : [];
      const assigned = expertByCategory[catId] || [];

      tagContainer.innerHTML = configEngineers.map((e) => {
        const isMember = queueMemberNames.includes(e.username);
        const isExpert = assigned.includes(e.username);
        if (!isMember && !isExpert) return '';
        const cls = isMember ? 'config-eng-tag active' : 'config-eng-tag';
        const badge = isMember ? '' : ' <span style="font-size:.6rem;opacity:.6">(expert)</span>';
        return `<span class="${cls}" data-eng="${e.username}" data-cat="${catId}" onclick="toggleConfigTag(this)">${e.display_name}${badge}</span>`;
      }).filter(Boolean).join('');

      if (!tagContainer.innerHTML) {
        tagContainer.innerHTML = '<span style="font-size:.75rem;color:var(--hope-text-muted)">No members</span>';
      }
    });
  } catch (e) {
    console.error('Failed to load expertise config:', e);
  }
}

function toggleConfigTag(el) {
  el.classList.toggle('active');
  const eng = el.dataset.eng;
  const cat = el.dataset.cat;
  const activeCats = Array.from(document.querySelectorAll(`.config-eng-tag.active[data-eng="${eng}"]`)).map((t) => t.dataset.cat);
  apiFetch('/config/expertise', {
    method: 'POST',
    body: JSON.stringify({ engineer_username: eng, category_ids: activeCats }),
  }).then(() => {
    showToast(`Updated ${eng}'s expertise.`, 'success');
  }).catch(() => {});
}

/* ─── KB Drafts ─── */
async function loadKBDrafts() {
  try {
    const data = await apiFetch('/kb/drafts');
    const drafts = data.drafts || [];
    const countEl = document.getElementById('kb-drafts-count');
    if (countEl) countEl.textContent = `${drafts.length} drafts`;
    const tbody = document.getElementById('kb-drafts-tbody');
    if (!tbody) return;
    if (drafts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><p>No KB drafts yet.</p></td></tr>';
      return;
    }
    tbody.innerHTML = drafts.map((d) => `
      <tr>
        <td><strong>${d.title}</strong></td>
        <td>${d.ticket_id}</td>
        <td>${d.category || '-'}</td>
        <td><span class="badge ${d.status === 'published' ? 'badge-expert' : 'badge-status-open'}">${d.status}</span></td>
        <td>${new Date(d.created_at).toLocaleDateString()}</td>
        <td>
          ${d.status === 'draft' ? `<button class="btn btn-primary btn-sm" onclick="publishKBDraft(${d.id})">Publish</button>` : ''}
          <button class="btn btn-outline btn-sm btn-danger-outline" onclick="deleteKBDraft(${d.id})">Delete</button>
        </td>
      </tr>`).join('');
  } catch (e) { console.error('KB drafts load error:', e); }
}

async function saveResolutionToKB() {
  if (!selectedMgmtTicketId) return;
  const resolution = document.getElementById('mgmt-resolution-text').value.trim();
  if (!resolution) { showToast('No resolution text to save.', 'error'); return; }
  const subject = document.getElementById('mgmt-r-subject').textContent || selectedMgmtTicketId;
  const category = document.getElementById('mgmt-r-category').textContent || '';
  try {
    await apiFetch('/kb/drafts', {
      method: 'POST',
      body: JSON.stringify({
        ticket_id: selectedMgmtTicketId,
        title: `KB: ${subject}`,
        category: category,
        content: resolution,
        created_by: currentUser ? currentUser.username : '',
      }),
    });
    showToast('Resolution saved as KB draft.', 'success');
    loadKBDrafts();
  } catch (e) { showToast('Failed to save KB draft.', 'error'); }
}

async function publishKBDraft(draftId) {
  try {
    const data = await apiFetch(`/kb/drafts/${draftId}/publish`, { method: 'POST' });
    showToast(`Draft published as ${data.filename}. ${data.documents_ingested} chunks ingested.`, 'success');
    loadKBDrafts();
    loadKnowledgeBase();
  } catch (e) { showToast('Failed to publish draft.', 'error'); }
}

async function deleteKBDraft(draftId) {
  try {
    await apiFetch(`/kb/drafts/${draftId}`, { method: 'DELETE' });
    showToast('Draft deleted.', 'success');
    loadKBDrafts();
  } catch (e) { showToast('Failed to delete draft.', 'error'); }
}

/* ─── Export Reports ─── */
function exportAnalyticsCSV() {
  const link = document.createElement('a');
  link.href = `${API}/analytics/export`;
  link.download = 'hope_ai_report.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('Downloading report...', 'success');
}

/* ─── Charts ─── */
function renderPieChart(canvasId, data, colorMap) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  const labels = Object.keys(data).map((k) => k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
  const values = Object.values(data);
  const colors = Object.keys(data).map((k) => colorMap[k] || '#94a3b8');
  chartInstances[canvasId] = new Chart(canvas, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } } },
      cutout: '55%',
    },
  });
}

function renderBarChart(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
  const labels = Object.keys(data).map((k) => k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
  const values = Object.values(data);
  chartInstances[canvasId] = new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: `${color}22`, borderColor: color, borderWidth: 2, borderRadius: 4 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } },
        x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
      },
    },
  });
}

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', () => navigateTo(item.dataset.page));
  });
  initSampleChips();

  const stored = getStoredUser();
  const token = getAuthToken();
  if (stored && token) {
    // Validate the stored token is still accepted by the server
    fetch(`${API}/tickets?limit=1`, { headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } })
      .then(res => {
        if (res.ok || res.status === 403) {
          // Token is valid (200) or user lacks permission (403) — either way, auth works
          currentUser = stored;
          showApp();
        } else {
          // 401 = token expired or server restarted — force clean re-login
          clearStoredUser();
        }
      })
      .catch(() => {
        // Network error — try anyway with stored session
        currentUser = stored;
        showApp();
      });
  }
});
