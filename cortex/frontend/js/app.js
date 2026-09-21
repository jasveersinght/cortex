/**
 * CORTEX — Main Application Controller
 * Handles page routing, global utilities, agents page, insights, activity, settings
 */

// ── Page Router ──────────────────────────────────────────── //

function navigateTo(page) {
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  // Show target page
  const target = document.getElementById(`page-${page}`);
  if (target) target.classList.add('active');

  // Update nav links
  document.querySelectorAll('.nav-link').forEach(l => {
    l.classList.toggle('active', l.dataset.page === page);
  });

  // Page-specific init
  if (page === 'agents') renderAgentsPage();
  if (page === 'activity') loadActivityFeed();
  if (page === 'insights') initInsightsPage();
  if (page === 'settings') initSettingsPage();
}

// ── Nav Links ─────────────────────────────────────────────── //

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      navigateTo(link.dataset.page);
    });
  });

  // Initialize home page
  navigateTo('home');

  // Load initial activity in background
  setTimeout(() => {
    if (document.getElementById('page-activity')?.classList.contains('active')) {
      loadActivityFeed();
    }
  }, 1500);
});

// ── Global Utilities ──────────────────────────────────────── //

function showLoader(msg = 'Processing...') {
  const loader = document.getElementById('cortex-loader');
  const msgEl = document.getElementById('loader-message');
  if (loader) loader.style.display = 'flex';
  if (msgEl) msgEl.textContent = msg;
}

function hideLoader() {
  const loader = document.getElementById('cortex-loader');
  if (loader) loader.style.display = 'none';
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

window.showLoader = showLoader;
window.hideLoader = hideLoader;
window.showToast = showToast;

// ── Agents Page ───────────────────────────────────────────── //

function renderAgentsPage() {
  const grid = document.getElementById('agents-grid');
  if (!grid) return;

  const agents = [
    {
      key: 'research',
      icon: '🍎',
      name: 'Research Agent',
      status: 'live',
      statusLabel: 'LIVE',
      desc: 'Discover market intelligence, competitor activity, industry trends, and valuable lead signals.',
      caps: ['Market Research', 'Industry Trends', 'Competitor Watch', 'Opportunity Discovery', 'Lead Intelligence'],
      btnLabel: 'Open Research Workspace',
      workspace: 'research-workspace',
    },
    {
      key: 'content',
      icon: '🍎',
      name: 'Content Agent',
      status: 'soon',
      statusLabel: 'COMING SOON',
      desc: 'Transform research intelligence into powerful marketing content — social posts, blogs, images, videos and multilingual content.',
      caps: ['Social Posts', 'Campaign Copy', 'AI Images', 'Video Scripts', 'Multilingual Content'],
      btnLabel: 'Coming Soon',
      workspace: 'content-workspace',
    },
    {
      key: 'compliance',
      icon: '🍎',
      name: 'Compliance Agent',
      status: 'live',
      statusLabel: 'LIVE',
      desc: 'Check all marketing content against insurance regulatory requirements, brand standards, and compliance rules.',
      caps: ['Claim Checking', 'Risk Detection', 'Compliance Review', 'Suggested Corrections', 'Human Review'],
      btnLabel: 'Open Compliance Workspace',
      workspace: 'compliance-workspace',
    },
  ];

  grid.innerHTML = agents.map(agent => `
    <div class="agent-card ${agent.key}" onclick="navigateTo('home');setTimeout(()=>openAgentWorkspace('${agent.workspace}'),400)">
      <div class="agent-card-icon">${agent.icon}</div>
      <div class="agent-card-header">
        <div class="agent-card-name">${agent.name}</div>
        <span class="agent-card-status ${agent.status === 'live' ? 'live' : 'soon'}">
          ${agent.status === 'live' ? '●' : '◌'} ${agent.statusLabel}
        </span>
      </div>
      <p class="agent-card-desc">${agent.desc}</p>
      <div class="agent-card-caps">
        ${agent.caps.map(c => `<span class="cap-tag">${c}</span>`).join('')}
      </div>
      <div class="agent-card-btn">${agent.status === 'live' ? '▶ ' : ''}${agent.btnLabel}</div>
    </div>
  `).join('');
}

function openAgentWorkspace(workspaceId) {
  const ws = document.getElementById(workspaceId);
  if (ws) ws.dataset.state = 'visible';
}

window.openAgentWorkspace = openAgentWorkspace;
window.navigateTo = navigateTo;

// ── Activity Feed ─────────────────────────────────────────── //

let activityData = [];
let activityFilter = 'all';

async function loadActivityFeed() {
  const feed = document.getElementById('activity-feed');
  if (!feed) return;

  feed.innerHTML = `<div class="empty-state"><div class="loader-ring"></div><p>Loading activity...</p></div>`;

  try {
    activityData = await CORTEX_API.getActivity(40);
    renderActivityFeed();
  } catch (err) {
    feed.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚙️</div>
        <h3>Gateway not connected</h3>
        <p>Start the CORTEX Gateway server to see real agent activity. Error: ${err.message}</p>
      </div>
    `;
  }
}

function renderActivityFeed() {
  const feed = document.getElementById('activity-feed');
  if (!feed) return;

  const filtered = activityFilter === 'all'
    ? activityData
    : activityData.filter(a => a.agent_type === activityFilter);

  if (filtered.length === 0) {
    feed.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📡</div>
        <h3>No activity yet</h3>
        <p>Run research or compliance checks to see activity here.</p>
      </div>
    `;
    return;
  }

  const typeColors = { research: 'research', compliance: 'compliance' };

  feed.innerHTML = filtered.map(a => `
    <div class="activity-item">
      <div class="activity-agent-dot ${typeColors[a.agent_type] || ''}"></div>
      <div class="activity-text">
        <div class="activity-action">${escapeHtml(a.action)}</div>
        <div class="activity-detail">${escapeHtml(a.detail || '')}</div>
      </div>
      <div class="activity-time">${a.timestamp ? formatActivityTime(a.timestamp) : ''}</div>
    </div>
  `).join('');
}

function formatActivityTime(dateStr) {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;

    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Activity refresh
  document.getElementById('activity-refresh-btn')?.addEventListener('click', loadActivityFeed);

  // Activity filter pills
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      activityFilter = pill.dataset.filter;
      renderActivityFeed();
    });
  });
});

// ── Insights Page ─────────────────────────────────────────── //

let insightsLoaded = false;

function initInsightsPage() {
  document.getElementById('insights-load-btn')?.addEventListener('click', loadInsights);
  document.getElementById('insights-filter')?.addEventListener('change', filterInsights);
}

let allInsights = [];

async function loadInsights() {
  const container = document.getElementById('insights-container');
  container.innerHTML = `<div class="empty-state"><div class="loader-ring"></div><p>Loading intelligence...</p></div>`;

  try {
    const statuses = await CORTEX_API.getResearchStatus();
    if (!statuses || statuses.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔬</div>
          <h3>No research data yet</h3>
          <p>Run a Research Agent session to see market intelligence here.</p>
        </div>
      `;
      return;
    }

    // Load details for the most recent run
    let allFindings = [];
    for (const status of statuses.slice(0, 3)) {
      if (status.latest_run_id && status.status === 'COMPLETED') {
        try {
          const run = await CORTEX_API.getResearchRun(status.latest_run_id);
          const findings = run.findings || [];
          findings.forEach(f => {
            f._brand = run.brand;
            f._market = run.market;
            f._research_type = run.research_type;
            f._run_id = status.latest_run_id;
          });
          allFindings = [...allFindings, ...findings];
        } catch {
          // ignore
        }
      }
    }

    allInsights = allFindings;
    renderInsights(allInsights);
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚙️</div>
        <h3>Research Agent offline</h3>
        <p>Start the Research Agent server to see insights. Error: ${err.message}</p>
      </div>
    `;
  }
}

function filterInsights() {
  const type = document.getElementById('insights-filter')?.value;
  const filtered = type === 'all' ? allInsights : allInsights.filter(f => f._research_type === type);
  renderInsights(filtered);
}

function renderInsights(findings) {
  const container = document.getElementById('insights-container');
  if (!findings || findings.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <h3>No insights for this filter</h3>
        <p>Try a different research type or load more intelligence.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `<div class="findings-grid">${findings.map(f => `
    <div class="finding-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span class="finding-type-badge">${formatFindingType(f.finding_type)}</span>
        <span style="font-size:10px;color:var(--text-muted)">${escapeHtml(f._market || '')}</span>
      </div>
      <div class="finding-title">${escapeHtml(f.title)}</div>
      <div class="finding-summary">${escapeHtml(f.summary)}</div>
      ${f.why_it_matters ? `<div class="finding-why">${escapeHtml(f.why_it_matters)}</div>` : ''}
      ${f.opportunity ? `<div class="finding-summary" style="color:var(--color-gold-light);margin-top:8px">💡 ${escapeHtml(f.opportunity)}</div>` : ''}
      <div class="finding-scores">
        <div class="finding-score">
          Confidence
          <div class="score-bar"><div class="score-fill" style="width:${f.confidence_score||0}%"></div></div>
          ${f.confidence_score||0}%
        </div>
      </div>
    </div>
  `).join('')}</div>`;
}

function formatFindingType(type) {
  if (!type) return 'Finding';
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Settings Page ─────────────────────────────────────────── //

function initSettingsPage() {
  // Pre-fill saved URLs
  const researchInput = document.getElementById('s-research-url');
  const gatewayInput = document.getElementById('s-gateway-url');

  if (researchInput) researchInput.value = CORTEX_API.research;
  if (gatewayInput) gatewayInput.value = CORTEX_API.gateway;

  document.getElementById('settings-save-btn')?.addEventListener('click', () => {
    const research = document.getElementById('s-research-url')?.value?.trim();
    const gateway = document.getElementById('s-gateway-url')?.value?.trim();

    CORTEX_API.updateUrls(gateway, research);
    showToast('Configuration saved.', 'success');
  });

  document.getElementById('health-check-btn')?.addEventListener('click', runHealthChecks);
  runHealthChecks();
}

async function runHealthChecks() {
  const checks = [
    { id: 'check-gateway', fn: () => CORTEX_API.health() },
    { id: 'check-research', fn: () => CORTEX_API.researchHealth() },
    { id: 'check-compliance', fn: () => CORTEX_API.health().then(h => ({ status: h.compliance_agent })) },
  ];

  for (const check of checks) {
    const el = document.getElementById(check.id);
    if (!el) continue;
    el.textContent = 'Checking...';
    el.style.color = 'var(--text-muted)';

    try {
      const result = await check.fn();
      const ok = result?.status === 'ok' || result?.cortex === 'ok' || result?.compliance_agent === 'ok' || result?.status === 'ok';
      el.textContent = ok ? '● Online' : '○ Degraded';
      el.style.color = ok ? '#4ade80' : '#f59e0b';
    } catch {
      el.textContent = '✕ Offline';
      el.style.color = '#f87171';
    }
  }
}
