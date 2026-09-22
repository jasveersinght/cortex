/**
 * CORTEX — Application Controller
 * Manages: Navigation, 7 Glowing Apples → Agent Side Panel, Live Workspaces, Environment Initialization
 */

const GATEWAY  = localStorage.getItem('cortex_gateway')  || 'http://localhost:8001';
const RESEARCH = localStorage.getItem('cortex_research') || 'http://localhost:8000';

// ── 7 Agent Definitions ───────────────────────────────── //
const AGENTS = {
  research: {
    icon: '🍎',
    name: 'Discover Agent',
    status: 'live',
    desc: 'Surface market trends, competitor moves, and lead intelligence in SEA insurance markets.',
    caps: ['Market Research', 'Industry Trends', 'Competitor Watch', 'Lead Intelligence'],
    activities: [
      { dot: '#4ade80', text: 'Found 5 new industry trends', time: '2h ago' },
      { dot: '#38bdf8', text: 'Monitored 12 competitor updates', time: '5h ago' },
      { dot: '#ff4d4d', text: 'Generated opportunity report', time: '1d ago' },
    ],
    workspace: 'ws-research',
    btnLabel: '▶ Run Discovery Agent',
  },
  analyze: {
    icon: '🍎',
    name: 'Analyze Agent',
    status: 'live',
    desc: 'Deep-dive analysis across research data — surfaces key patterns, market signals, anomalies, and strategic implications powered by Groq AI.',
    caps: ['Pattern Recognition', 'Trend Correlation', 'Signal Detection', 'Anomaly Analysis'],
    activities: [
      { dot: '#a78bfa', text: 'Detected digital adoption surge pattern', time: '1h ago' },
      { dot: '#a78bfa', text: 'Identified trust gap vs competitors', time: '3h ago' },
    ],
    workspace: 'ws-analyze',
    btnLabel: '🔬 Open Analyze Workspace',
  },
  content: {
    icon: '🍎',
    name: 'Create Agent',
    status: 'live',
    desc: 'Transform research insights into multi-platform campaign content — LinkedIn, Instagram, X — with A/B variants and visual concepts powered by Gemini.',
    caps: ['Campaign Strategy', 'Platform Content', 'A/B Variants', 'Visual Concepts'],
    activities: [
      { dot: '#fbbf24', text: 'Generated LinkedIn campaign for Term Insurance', time: '2h ago' },
      { dot: '#fb923c', text: 'Created 3 A/B variants for Instagram', time: '4h ago' },
      { dot: '#fbbf24', text: 'Built visual concept brief for SME campaign', time: '1d ago' },
    ],
    workspace: 'ws-content',
    btnLabel: '🍎 Open Content Studio',
  },
  engage: {
    icon: '🍎',
    name: 'Engage Agent',
    status: 'live',
    desc: 'Generate a 2-week AI-powered publishing calendar with optimal posting times, content types, hashtag strategies, and engagement tactics across all platforms.',
    caps: ['Publishing Calendar', 'Engagement Tactics', 'Hashtag Strategy', 'KPI Targets'],
    activities: [
      { dot: '#38bdf8', text: 'Generated 2-week LinkedIn calendar for JA Assure', time: '30m ago' },
      { dot: '#38bdf8', text: 'Scheduled Instagram reel strategy', time: '2h ago' },
    ],
    workspace: 'ws-engage',
    btnLabel: '📅 Open Engage Calendar',
  },
  strategize: {
    icon: '🍎',
    name: 'Strategize Agent',
    status: 'live',
    desc: 'Build AI-generated strategic roadmaps from market intelligence — pillars, phased plans, KPIs, ROI projections, and risk mitigation strategies.',
    caps: ['Strategic Roadmap', 'KPI Framework', 'ROI Projection', 'Risk Planning'],
    activities: [
      { dot: '#818cf8', text: 'Built Q1 2025 roadmap for Market Growth', time: '1h ago' },
    ],
    workspace: 'ws-strategize',
    btnLabel: '📐 Open Strategy Builder',
  },
  automate: {
    icon: '🍎',
    name: 'Automate Agent',
    status: 'soon',
    desc: 'Wire up automated workflows that trigger intelligence tasks based on market events and conditions.',
    caps: ['Alerts', 'Workflows', 'Event Triggers', 'Scheduled Runs'],
    activities: [],
    workspace: null,
    btnLabel: 'Coming Soon',
  },
  compliance: {
    icon: '🍎',
    name: 'Monitor Agent',
    status: 'live',
    desc: 'Evaluate marketing content against MAS regulatory standards, brand guidelines, and claims accuracy.',
    caps: ['Claims Check', 'Regulatory Review', 'Brand Compliance', 'Risk Scoring'],
    activities: [
      { dot: '#4ade80', text: 'Checked LinkedIn post — Highly Recommended', time: '3h ago' },
      { dot: '#fbbf24', text: 'Reviewed ad copy — Needs Revision', time: '6h ago' },
      { dot: '#ff4d4d', text: 'Flagged promotional email — Suspicious', time: '1d ago' },
    ],
    workspace: 'ws-compliance',
    btnLabel: '🍎 Open Monitor Workspace',
  },
};

// ── Navigation ────────────────────────────────────────── //
function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
  const target = document.getElementById(`page-${page}`);
  if (target) target.style.display = 'block';

  document.querySelectorAll('.nav-link').forEach(l => {
    l.classList.toggle('active', l.dataset.page === page);
  });

  if (page === 'agents') renderAgentsPage();
  if (page === 'insights') initInsightsPage();
  if (page === 'settings') initSettingsPage();
}

document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    navigateTo(link.dataset.page);
  });
});

// ── 7 Hanging Apples Click Logic ──────────────────────── //
let activeAppleItem = null;

function setupAppleClickEvents() {
  document.querySelectorAll('.apple-item').forEach(apple => {
    apple.addEventListener('click', () => {
      const agentKey = apple.dataset.agent;
      const agent = AGENTS[agentKey];
      if (!agent) return;

      if (activeAppleItem) activeAppleItem.classList.remove('active');

      const sidePanel = document.getElementById('agent-side-panel');

      if (activeAppleItem === apple && sidePanel.dataset.state === 'visible') {
        closeSidePanel();
        activeAppleItem = null;
        return;
      }

      apple.classList.add('active');
      activeAppleItem = apple;
      openSidePanel(agentKey, agent);
    });
  });
}

function openSidePanel(key, agent) {
  const panel = document.getElementById('agent-side-panel');
  const inner = document.getElementById('panel-inner');

  const activitiesHtml = agent.activities.length
    ? agent.activities.map(a => `
        <div class="panel-activity">
          <div class="pa-dot" style="background:${a.dot}"></div>
          <div class="pa-text">${a.text}</div>
          <div class="pa-time">${a.time}</div>
        </div>`).join('')
    : '<div class="pa-text" style="color:rgba(255,255,255,0.35);font-size:12px">No recent activity yet.</div>';

  const capsHtml = agent.caps.map(c => `<span class="panel-cap">${c}</span>`).join('');
  const btnDisabled = agent.status === 'soon' ? 'disabled' : '';
  const btnClick    = agent.workspace ? `openWorkspace('${agent.workspace}')` : '';

  inner.innerHTML = `
    <button class="panel-close-btn" onclick="closeSidePanel()">✕</button>
    <div class="panel-agent-row">
      <span class="panel-agent-icon">${agent.icon}</span>
      <div class="panel-agent-info">
        <div class="panel-agent-name">${agent.name}</div>
      </div>
    </div>
    <div class="panel-agent-desc">${agent.desc}</div>
    <div class="panel-caps">${capsHtml}</div>
    ${agent.activities.length ? `<div class="panel-section-label">Recent Activity</div><div class="panel-activities">${activitiesHtml}</div>` : ''}
    <button class="panel-open-btn" onclick="${btnClick}" ${btnDisabled}>
      ${agent.btnLabel}
    </button>
  `;

  panel.dataset.state = 'visible';
}

function closeSidePanel() {
  const panel = document.getElementById('agent-side-panel');
  if (panel) panel.dataset.state = 'hidden';
  if (activeAppleItem) { activeAppleItem.classList.remove('active'); activeAppleItem = null; }
}

window.closeSidePanel = closeSidePanel;

// ── Workspace Modals ───────────────────────────────────── //
function openWorkspace(id) {
  const ws = document.getElementById(id);
  if (ws) {
    ws.dataset.state = 'visible';
    if (id === 'ws-research')   loadResearchHistory();
    if (id === 'ws-compliance') loadComplianceHistory();
    if (id === 'ws-content')    loadContentHistory();
  }
}

function closeWorkspace(id) {
  const ws = document.getElementById(id);
  if (ws) ws.dataset.state = 'hidden';
}

window.openWorkspace = openWorkspace;
window.closeWorkspace = closeWorkspace;

document.querySelectorAll('.ws-overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.dataset.state = 'hidden';
  });
});

// ── Agents Grid Page ──────────────────────────────────── //
function renderAgentsPage() {
  const grid = document.getElementById('agents-grid');
  if (!grid) return;
  grid.innerHTML = Object.entries(AGENTS).map(([key, a]) => `
    <div class="agent-card" onclick="handleAgentCardClick('${key}','${a.workspace || ''}')">
      <div class="ac-icon">${a.icon}</div>
      <div class="ac-name">${a.name}</div>
      <span class="ac-status ${a.status}">${a.status === 'live' ? '● LIVE' : '◌ COMING SOON'}</span>
      <p class="ac-desc">${a.desc}</p>
      <div class="ac-caps">${a.caps.map(c => `<span class="ac-cap">${c}</span>`).join('')}</div>
      <div class="ac-btn">${a.status === 'live' && !a.btnLabel.startsWith('▶') ? '▶ ' : ''}${a.btnLabel}</div>
    </div>
  `).join('');
}

function handleAgentCardClick(key, ws) {
  if (!ws) return;
  navigateTo('home');
  setTimeout(() => openWorkspace(ws), 400);
}

window.handleAgentCardClick = handleAgentCardClick;

// ── Research Workspace Logic ──────────────────────────── //
async function loadResearchHistory() {
  const el = document.getElementById('research-history');
  if (!el) return;
  el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px">Loading history...</div>';
  try {
    const resp = await fetch(`${GATEWAY}/research/status`);
    const data = await resp.json();
    if (!data.length) { el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px;padding:12px 0">No research runs yet.</div>'; return; }
    el.innerHTML = data.slice(0, 8).map(r => {
      const rid = r.latest_run_id || r.id || r.research_run_id;
      return `
      <div class="history-item" onclick="viewResearchRun('${rid}')">
        <div class="hi-dot" style="background:#4ade80"></div>
        <div class="hi-info">
          <div class="hi-title">${esc(r.brand || '—')} · ${esc((r.research_type||'').replace(/_/g,' '))}</div>
          <div class="hi-sub">${esc(r.market || '')} · ${r.findings_count || 0} findings</div>
        </div>
        <span class="hi-status ${r.status?.toLowerCase()==='completed'?'done':'pending'}">${r.status?.toUpperCase()||'—'}</span>
      </div>
    `}).join('');
  } catch {
    el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px;padding:12px 0">Research Agent offline (port 8000).</div>';
  }
}

document.getElementById('research-run-btn')?.addEventListener('click', async () => {
  const brand     = document.getElementById('r-brand')?.value?.trim();
  const market    = document.getElementById('r-market')?.value;
  const rtype     = document.getElementById('r-type')?.value;
  const objective = document.getElementById('r-objective')?.value?.trim();

  if (!brand) { showToast('Please enter a brand name.', 'error'); return; }

  showLoader('Running discovery session...');
  const resultsEl = document.getElementById('research-results');
  resultsEl.classList.add('hidden');

  try {
    const resp = await fetch(`${GATEWAY}/research/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand, market, research_type: rtype, objective, force_refresh: true }),
    });
    const data = await resp.json();
    hideLoader();

    const findings = data.findings || [];
    resultsEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <strong style="color:#fff;font-size:15px">Intelligence Findings</strong>
        <span style="font-size:12px;color:rgba(255,255,255,0.5)">${findings.length} result${findings.length!==1?'s':''} · ${esc(data.market||market)}</span>
      </div>
      ${findings.length
        ? `<div class="findings-grid">${findings.map(f => `
            <div class="finding-card">
              <span class="finding-type-badge">${esc((f.finding_type||'').replace(/_/g,' '))}</span>
              <div class="finding-title">${esc(f.title || 'Market Insight')}</div>
              <div class="finding-summary">${esc(f.summary || f.description || '')}</div>
              ${f.why_it_matters ? `<div class="finding-why">${esc(f.why_it_matters)}</div>` : ''}
              <div class="score-bar"><div class="score-fill" style="width:${f.confidence_score||80}%"></div></div>
            </div>`).join('')}</div>`
        : '<div style="color:rgba(255,255,255,0.45);font-size:13px">No findings returned.</div>'}
    `;
    resultsEl.classList.remove('hidden');
    showToast(`Discovery session complete — ${findings.length} findings.`, 'success');
    loadResearchHistory();
  } catch (e) {
    hideLoader();
    showToast('Research Agent engine offline.', 'error');
  }
});

async function viewResearchRun(id) {
  if (!id || id === 'undefined') return;
  showLoader('Loading run...');
  try {
    const resp = await fetch(`${GATEWAY}/research/${id}`);
    const data = await resp.json();
    hideLoader();
    const findings = data.findings || [];
    const resultsEl = document.getElementById('research-results');
    resultsEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <strong style="color:#fff;font-size:15px">${esc(data.brand || 'Research Run')} · ${esc((data.research_type||'').replace(/_/g,' '))}</strong>
        <span style="font-size:12px;color:rgba(255,255,255,0.5)">${findings.length} findings · ${esc(data.market||'')}</span>
      </div>
      ${findings.length ? `<div class="findings-grid">${findings.map(f => `
        <div class="finding-card">
          <span class="finding-type-badge">${esc((f.finding_type||'').replace(/_/g,' '))}</span>
          <div class="finding-title">${esc(f.title || 'Market Insight')}</div>
          <div class="finding-summary">${esc(f.summary || f.description || '')}</div>
          ${f.why_it_matters ? `<div class="finding-why">${esc(f.why_it_matters)}</div>` : ''}
          <div class="score-bar"><div class="score-fill" style="width:${f.confidence_score||80}%"></div></div>
        </div>`).join('')}</div>` : '<div style="color:rgba(255,255,255,0.45)">No findings.</div>'}
    `;
    resultsEl.classList.remove('hidden');
  } catch { hideLoader(); }
}

window.viewResearchRun = viewResearchRun;

// ── Compliance Workspace Logic ────────────────────────── //
async function loadComplianceHistory() {
  const el = document.getElementById('compliance-history');
  if (!el) return;
  el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px">Loading checks...</div>';
  try {
    const resp = await fetch(`${GATEWAY}/compliance/history?limit=8`);
    const data = await resp.json();
    if (!data.length) { el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px;padding:12px 0">No compliance checks yet.</div>'; return; }
    const tierColors = { highly_recommended:'#4ade80', recommended_review:'#fbbf24', vigilant:'#fb923c', suspicious:'#ff4d4d' };
    el.innerHTML = data.map(r => `
      <div class="history-item" onclick="viewComplianceAsset(${r.id})">
        <div class="hi-dot" style="background:${tierColors[r.tier]||'#888'}"></div>
        <div class="hi-info">
          <div class="hi-title">${esc(r.brand)} · ${esc(r.content_type||'').replace(/_/g,' ')}</div>
          <div class="hi-sub">Score: ${r.confidence_score||'—'} · ${r.platform||''}</div>
        </div>
        <span class="hi-status ${r.status==='approved'?'done':'pending'}">${(r.tier||'pending').replace(/_/g,' ')}</span>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px;padding:12px 0">Compliance gateway offline.</div>';
  }
}

document.getElementById('compliance-run-btn')?.addEventListener('click', async () => {
  const content  = document.getElementById('c-content')?.value?.trim();
  const ctype    = document.getElementById('c-type')?.value;
  const platform = document.getElementById('c-platform')?.value;
  const region   = document.getElementById('c-region')?.value;

  if (!content) { showToast('Please paste content to check.', 'error'); return; }

  showLoader('Running Compliance Gate...');
  const resultsEl = document.getElementById('compliance-results');
  resultsEl.classList.add('hidden');

  try {
    const resp = await fetch(`${GATEWAY}/compliance/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body_text: content, content_type: ctype, platform, region }),
    });
    const data = await resp.json();
    hideLoader();

    const tierMap = { highly_recommended:'tier-green', recommended_review:'tier-amber', vigilant:'tier-orange', suspicious:'tier-red' };
    const tierCls = tierMap[data.tier] || 'tier-amber';

    const lensHtml = Object.entries(data.lens_results || {}).map(([name, l]) => `
      <div class="lens-card">
        <div class="lens-name">${name.replace(/_/g,' ')}</div>
        <div class="lens-score" style="color:${l.score>=75?'#4ade80':l.score>=50?'#fbbf24':'#ff4d4d'}">${l.score}</div>
        <div class="lens-reason">${esc(l.reason||'')}</div>
      </div>
    `).join('');

    const scoreVal = (data.confidence_score !== undefined && data.confidence_score !== null) ? data.confidence_score : (data.score ?? '—');

    resultsEl.innerHTML = `
      <div class="tier-card ${tierCls}">
        <div class="tier-title">${data.tier_label || data.tier}</div>
        <div class="tier-score">Confidence Score: ${scoreVal} / 100</div>
      </div>
      ${lensHtml ? `<div class="lens-grid">${lensHtml}</div>` : ''}
      <div class="review-row">
        <button class="rev-btn approve" onclick="reviewAsset(${data.asset_id},'approved')">✓ Approve</button>
        <button class="rev-btn reject"  onclick="reviewAsset(${data.asset_id},'rejected')">✕ Reject</button>
      </div>
    `;
    resultsEl.classList.remove('hidden');
    showToast(`Compliance check complete — ${data.tier_label||data.tier}`, data.tier==='highly_recommended'?'success':'info');
    loadComplianceHistory();
  } catch (e) {
    hideLoader();
    showToast('Compliance Gateway offline.', 'error');
  }
});

async function reviewAsset(id, decision) {
  try {
    await fetch(`${GATEWAY}/compliance/review/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision }),
    });
    showToast(`Asset marked as ${decision}.`, decision==='approved'?'success':'error');
    loadComplianceHistory();
  } catch {}
}

async function viewComplianceAsset(id) {
  showLoader('Loading asset audit...');
  try {
    const resp = await fetch(`${GATEWAY}/compliance/asset/${id}`);
    const data = await resp.json();
    hideLoader();

    const tierMap = { highly_recommended:'tier-green', recommended_review:'tier-amber', vigilant:'tier-orange', suspicious:'tier-red' };
    const tierCls = tierMap[data.tier] || 'tier-amber';
    const resultsEl = document.getElementById('compliance-results');
    const scoreVal = (data.confidence_score !== undefined && data.confidence_score !== null) ? data.confidence_score : (data.score ?? '—');

    resultsEl.innerHTML = `
      <div class="tier-card ${tierCls}">
        <div class="tier-title">${(data.tier||'').replace(/_/g,' ')}</div>
        <div class="tier-score">Score: ${scoreVal} / 100 · ${data.brand || 'JA Assure'}</div>
      </div>
    `;
    resultsEl.classList.remove('hidden');
  } catch { hideLoader(); }
}

window.reviewAsset = reviewAsset;
window.viewComplianceAsset = viewComplianceAsset;

// ── Content Agent Workspace Logic ───────────────── //

// Keep a local log of generated campaigns for history
let contentHistory = JSON.parse(localStorage.getItem('cortex_content_history') || '[]');

async function loadContentHistory() {
  const el = document.getElementById('content-history');
  if (!el) return;
  if (!contentHistory.length) {
    el.innerHTML = '<div style="color:rgba(255,255,255,0.4);font-size:13px;padding:12px 0">No content generated yet.</div>';
    return;
  }
  el.innerHTML = contentHistory.slice().reverse().slice(0, 8).map((h, i) => `
    <div class="history-item" onclick="viewContentHistoryItem(${contentHistory.length - 1 - i})">
      <div class="hi-dot" style="background:#fbbf24"></div>
      <div class="hi-info">
        <div class="hi-title">${esc(h.campaign?.title || 'Campaign')}</div>
        <div class="hi-sub">${esc(h._product || '')} · ${(h._platforms||[]).join(', ')}</div>
      </div>
      <span class="hi-status done">GENERATED</span>
    </div>
  `).join('');
}

function renderContentResults(data, product, platforms) {
  const resultsEl = document.getElementById('content-results');
  if (!resultsEl) return;

  const d = data.data || data;
  const campaign = d.campaign || {};
  const messaging = d.messaging || {};
  const ab = d.ab_variants || [];
  const visual = d.visual || {};

  // Platform tabs with crisp SVG logos
  const platformKeys = ['linkedin', 'instagram', 'x'];
  const platformSvgIcons = {
    linkedin: `<svg width="15" height="15" viewBox="0 0 24 24" fill="#0077b5" style="vertical-align:middle"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/></svg>`,
    instagram: `<svg width="15" height="15" viewBox="0 0 24 24" fill="#e1306c" style="vertical-align:middle"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>`,
    x: `<svg width="15" height="15" viewBox="0 0 24 24" fill="#ffffff" style="vertical-align:middle"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`
  };
  const platformNames = { linkedin: 'LinkedIn', instagram: 'Instagram', x: 'X (Twitter)' };

  const platformTabsHtml = platformKeys.map(p => `
    <button class="platform-tab" data-platform="${p}" style="color: #ffffff; display: inline-flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.05); padding: 8px 16px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); cursor: pointer; transition: all 0.2s;" onclick="switchContentTab('${p}')">${platformSvgIcons[p]} <span style="font-weight: 500; font-size: 13px;">${platformNames[p]}</span></button>
  `).join('');

  const bannerTitle = visual.headline || campaign.title || product;

  const platformContentHtml = platformKeys.map(p => {
    const pc = d[p] || {};
    const title = pc.headline || bannerTitle;
    const subtitle = pc.hook || visual.concept || messaging.hook || '';
    const ctaText = pc.cta || visual.cta || 'Learn More →';

    let imgUrl = '';
    let cardMarkup = '';

    if (p === 'instagram') {
      // 1:1 Aspect Ratio (Instagram Square Post)
      imgUrl = visual.image_url || `https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=800&h=800&q=80`;
      cardMarkup = `
        <div class="insta-mockup-card" style="width:100%;max-width:440px;margin:0 auto 20px auto;background:#0b1329;border:1px solid rgba(225,48,108,0.3);border-radius:18px;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.6);">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:rgba(15,23,42,0.95);border-bottom:1px solid rgba(255,255,255,0.06);">
            <div style="display:flex;align-items:center;gap:10px;">
              <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#e1306c,#f59e0b);padding:2px;display:flex;align-items:center;justify-content:center;">
                <div style="width:100%;height:100%;border-radius:50%;background:#090d16;display:flex;align-items:center;justify-content:center;font-size:16px;">🍎</div>
              </div>
              <div>
                <div style="font-size:13px;font-weight:700;color:#ffffff;display:flex;align-items:center;gap:4px;">ja_assure_official <svg width="12" height="12" viewBox="0 0 24 24" fill="#38bdf8"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);">Sponsored · Instagram Post (1:1)</div>
              </div>
            </div>
            <div style="color:rgba(255,255,255,0.6);font-weight:bold;">•••</div>
          </div>
          <!-- 1:1 Aspect Ratio Canvas -->
          <div style="position:relative;width:100%;aspect-ratio:1 / 1;overflow:hidden;background:linear-gradient(135deg,#1e1b4b,#0f172a);">
            <img src="${imgUrl}" onerror="this.style.opacity='0';" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.65;filter:brightness(0.85);transition:opacity 0.3s;">
            <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0.15) 0%,rgba(9,13,22,0.92) 100%);display:flex;flex-direction:column;justify-content:space-between;padding:24px;z-index:2;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="background:rgba(225,48,108,0.25);border:1px solid rgba(225,48,108,0.5);backdrop-filter:blur(8px);color:#fff;font-size:10px;font-weight:700;letter-spacing:1px;padding:4px 12px;border-radius:20px;text-transform:uppercase;">INSTAGRAM 1:1 TEMPLATE</span>
                <span style="font-size:11px;color:#fbbf24;font-weight:600;">✨ JA Assure AI</span>
              </div>
              <div>
                <div style="font-family:'Cormorant Garamond',serif;font-size:25px;font-weight:700;color:#ffffff;line-height:1.2;text-shadow:0 2px 12px rgba(0,0,0,0.9);">${esc(title)}</div>
                <div style="font-size:13px;color:rgba(255,255,255,0.9);margin-top:8px;text-shadow:0 1px 6px rgba(0,0,0,0.9);font-weight:400;">${esc(subtitle)}</div>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:11px;color:#fbbf24;font-style:italic">Swipe for details 👉</span>
                <button style="padding:7px 16px;border-radius:18px;background:linear-gradient(135deg,#e1306c,#f59e0b);color:#fff;font-size:11px;font-weight:700;border:none;box-shadow:0 4px 14px rgba(225,48,108,0.4);cursor:pointer">${esc(ctaText)}</button>
              </div>
            </div>
          </div>
          <div style="padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid rgba(255,255,255,0.06);">
            <div style="display:flex;gap:16px;font-size:14px;color:#fff;"><span>❤️ 1.4K</span> <span>💬 84</span> <span>✈️ Share</span></div>
            <span style="font-size:14px;">🔖</span>
          </div>
        </div>
      `;
    } else if (p === 'linkedin') {
      // 1.91:1 Aspect Ratio (LinkedIn Document/Article Banner)
      imgUrl = visual.image_url || `https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&h=627&q=80`;
      cardMarkup = `
        <div class="linkedin-mockup-card" style="width:100%;max-width:580px;margin:0 auto 20px auto;background:#0b1329;border:1px solid rgba(0,119,181,0.3);border-radius:14px;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.6);">
          <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;background:rgba(15,23,42,0.95);border-bottom:1px solid rgba(255,255,255,0.06);">
            <div style="width:38px;height:38px;border-radius:6px;background:#0077b5;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:bold;color:#fff;">JA</div>
            <div>
              <div style="font-size:13px;font-weight:700;color:#ffffff;">JA Assure Insurance Group</div>
              <div style="font-size:10px;color:rgba(255,255,255,0.5);">18,920 followers · Promoted · LinkedIn (1.91:1)</div>
            </div>
          </div>
          <!-- LinkedIn Intro Hook snippet -->
          <div style="padding:12px 16px;font-size:13px;color:#e2e8f0;line-height:1.5;background:rgba(15,23,42,0.6);border-bottom:1px solid rgba(255,255,255,0.04);">${esc(pc.hook || subtitle)}</div>
          <!-- 1.91:1 Aspect Ratio Banner -->
          <div style="position:relative;width:100%;aspect-ratio:1.91 / 1;overflow:hidden;background:linear-gradient(135deg,#0f172a,#1e293b);">
            <img src="${imgUrl}" onerror="this.style.opacity='0';" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.65;filter:brightness(0.8);transition:opacity 0.3s;">
            <div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(9,13,22,0.95) 0%,rgba(9,13,22,0.45) 100%);padding:20px;display:flex;flex-direction:column;justify-content:space-between;z-index:2;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="background:rgba(0,119,181,0.3);border:1px solid rgba(0,119,181,0.6);color:#38bdf8;font-size:10px;font-weight:700;padding:4px 10px;border-radius:4px;letter-spacing:1px;">LINKEDIN 1.91:1 BANNER</span>
              </div>
              <div>
                <div style="font-size:20px;font-weight:700;color:#ffffff;line-height:1.3;">${esc(title)}</div>
              </div>
              <div>
                <button style="padding:6px 14px;border-radius:14px;background:#0077b5;color:#fff;font-size:11px;font-weight:600;border:none;cursor:pointer">${esc(ctaText)}</button>
              </div>
            </div>
          </div>
          <div style="padding:10px 16px;display:flex;justify-content:space-between;color:rgba(255,255,255,0.7);font-size:12px;border-top:1px solid rgba(255,255,255,0.06);">
            <span>👍 💬 482 reactions</span>
            <span>36 comments</span>
          </div>
        </div>
      `;
    } else {
      // 16:9 Aspect Ratio (X / Twitter Card)
      imgUrl = visual.image_url || `https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&h=675&q=80`;
      cardMarkup = `
        <div class="x-mockup-card" style="width:100%;max-width:560px;margin:0 auto 20px auto;background:#0b1329;border:1px solid rgba(255,255,255,0.2);border-radius:14px;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.6);">
          <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;background:rgba(15,23,42,0.95);border-bottom:1px solid rgba(255,255,255,0.06);">
            <div style="width:34px;height:34px;border-radius:50%;background:#ffffff;color:#000;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:bold;">🍎</div>
            <div>
              <div style="font-size:13px;font-weight:700;color:#ffffff;display:flex;align-items:center;gap:4px;">JA Assure <span style="color:rgba(255,255,255,0.5);font-weight:400;">@JA_Assure · Promoted</span></div>
            </div>
          </div>
          <!-- X Thread Hook Header Text -->
          <div style="padding:12px 16px;font-size:13.5px;color:#f8fafc;line-height:1.5;background:rgba(15,23,42,0.6);border-bottom:1px solid rgba(255,255,255,0.04);">${esc(pc.hook || subtitle)}</div>
          <!-- 16:9 Aspect Ratio Tweet Media Canvas -->
          <div style="position:relative;width:100%;aspect-ratio:16 / 9;overflow:hidden;background:linear-gradient(135deg,#0f172a,#1e293b);">
            <img src="${imgUrl}" onerror="this.style.opacity='0';" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.65;filter:brightness(0.85);transition:opacity 0.3s;">
            <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0.2) 0%,rgba(9,13,22,0.92) 100%);padding:18px;display:flex;flex-direction:column;justify-content:space-between;z-index:2;">
              <span style="background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);color:#fff;font-size:10px;font-weight:700;padding:4px 10px;border-radius:10px;width:fit-content;">X 16:9 MEDIA CARD · THREAD 🧵</span>
              <div>
                <div style="font-size:19px;font-weight:700;color:#ffffff;line-height:1.3;">${esc(title)}</div>
              </div>
            </div>
          </div>
          <div style="padding:10px 16px;display:flex;justify-content:space-between;color:rgba(255,255,255,0.6);font-size:12px;border-top:1px solid rgba(255,255,255,0.06);">
            <span>💬 42</span> <span>🔁 128</span> <span>❤️ 650</span> <span>📊 24.5K</span>
          </div>
        </div>
      `;
    }

    const pAbVariants = (pc.ab_variants && pc.ab_variants.length) ? pc.ab_variants : (ab.length ? ab.map((v, i) => {
      const platformPrefix = p === 'linkedin' ? ['B2B / Professional', 'Thought Leadership', 'Case Study'][i % 3]
                           : p === 'instagram' ? ['Visual Carousel', 'Behind-the-Scenes', 'Lifestyle Story'][i % 3]
                           : ['Punchy Thread', 'Hot Take / Poll', 'Data Snippet'][i % 3];
      return {
        angle: `${platformPrefix} (${v.angle || 'Strategic Angle'})`,
        hook: v.hook || pc.hook || subtitle,
        message: v.message || pc.caption || pc.body || title
      };
    }) : [
      { angle: p === 'linkedin' ? 'B2B Leadership' : p === 'instagram' ? 'Visual Storytelling' : 'Thread Hook', hook: pc.hook || title, message: pc.cta || subtitle },
      { angle: p === 'linkedin' ? 'Data Case Study' : p === 'instagram' ? 'Carousel Guide' : 'Poll & Debate', hook: `Did you know? ${subtitle}`, message: pc.headline || title }
    ]);

    const pAbColors = [
      { label: '#818cf8', bg: 'rgba(129, 140, 248, 0.12)', border: 'rgba(129, 140, 248, 0.3)' },
      { label: '#fbbf24', bg: 'rgba(251, 191, 36, 0.12)', border: 'rgba(251, 191, 36, 0.3)' },
      { label: '#34d399', bg: 'rgba(52, 211, 153, 0.12)', border: 'rgba(52, 211, 153, 0.3)' }
    ];

    const pAbHtml = pAbVariants.map((v, i) => {
      const c = pAbColors[i % pAbColors.length];
      return `
        <div class="ab-card" style="border-left: 3px solid ${c.label};">
          <div class="ab-label" style="color:${c.label};background:${c.bg};border:1px solid ${c.border}">${platformNames[p]} Variant ${String.fromCharCode(65+i)}</div>
          ${v.angle   ? `<div class="ab-row"><span style="color:#94a3b8">Angle:</span> <strong style="color:#ffffff">${esc(v.angle)}</strong></div>` : ''}
          ${v.hook    ? `<div class="ab-row"><span style="color:#94a3b8">Hook:</span> <em style="color:#fef08a;font-style:normal">${esc(v.hook)}</em></div>` : ''}
          ${v.message ? `<div class="ab-row"><span style="color:#94a3b8">Message:</span> <span style="color:#e2e8f0">${esc(v.message)}</span></div>` : ''}
        </div>
      `;
    }).join('');

    return `
      <div class="platform-panel" id="cpanel-${p}" style="display:none">
        ${cardMarkup}
        ${pc.headline  ? `<div class="cp-row"><span class="cp-label" style="color:#38bdf8;background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.3)">Headline</span><div class="cp-val" style="font-size:16px;font-weight:600;color:#ffffff">${esc(pc.headline)}</div></div>` : ''}
        ${pc.hook      ? `<div class="cp-row"><span class="cp-label" style="color:#fbbf24;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.3)">Hook</span><div class="cp-val" style="font-size:14.5px;font-weight:500;color:#fef08a">${esc(pc.hook)}</div></div>` : ''}
        ${pc.cta       ? `<div class="cp-row"><span class="cp-label" style="color:#4ade80;background:rgba(74,222,128,0.12);border:1px solid rgba(74,222,128,0.3)">Call to Action (CTA)</span><div class="cp-val" style="font-size:14px;font-weight:600;color:#86efac">${esc(pc.cta)}</div></div>` : ''}
        ${pc.caption   ? `<div class="cp-row"><span class="cp-label" style="color:#a78bfa;background:rgba(167,139,250,0.12);border:1px solid rgba(167,139,250,0.3)">Caption</span><div class="cp-val" style="white-space:pre-wrap;font-size:14px;line-height:1.6;color:#f1f5f9">${esc(pc.caption)}</div></div>` : ''}
        ${pc.body      ? `<div class="cp-row"><span class="cp-label" style="color:#cbd5e1;background:rgba(203,213,225,0.12);border:1px solid rgba(203,213,225,0.3)">Body</span><div class="cp-val" style="white-space:pre-wrap;font-size:14px;line-height:1.6;color:#f1f5f9">${esc(pc.body)}</div></div>` : ''}
        ${pc.hashtags  ? `<div class="cp-row"><span class="cp-label" style="color:#f472b6;background:rgba(244,114,182,0.12);border:1px solid rgba(244,114,182,0.3)">Hashtags</span><div class="cp-val" style="color:#f472b6;font-weight:500;font-size:13.5px">${esc(Array.isArray(pc.hashtags)?pc.hashtags.join(' '):pc.hashtags)}</div></div>` : ''}

        <!-- Platform-Specific A/B Variants -->
        <div style="margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);">
          <div class="cs-label" style="color:#fbbf24;margin-bottom:12px;">🎯 ${platformNames[p]} A/B Testing Variants</div>
          <div class="ab-grid">${pAbHtml}</div>
        </div>

        ${!Object.keys(pc).length ? '<div style="color:rgba(255,255,255,0.4);font-size:13px;padding:12px 0">No content generated for this platform.</div>' : ''}
      </div>
    `;
  }).join('');

  resultsEl.innerHTML = `
    <div class="content-campaign-header">
      <div class="ccampaign-title">${esc(campaign.title || 'AI-Generated Campaign')}</div>
      <div class="ccampaign-meta">${esc(campaign.objective || '')} ${campaign.audience ? '· ' + esc(campaign.audience) : ''}</div>
    </div>

    ${messaging.core_message ? `
    <div class="content-section">
      <div class="cs-label">Core Message</div>
      <div class="cs-val">${esc(messaging.core_message)}</div>
    </div>` : ''}

    <div class="content-section">
      <div class="cs-label">Platform Content, Media Templates &amp; A/B Variants</div>
      <div class="platform-tabs" style="display:flex;gap:12px;margin-bottom:16px;">${platformTabsHtml}</div>
      <div class="platform-panels">${platformContentHtml}</div>
    </div>

    <div class="review-row" style="margin-top:16px">
      <button class="rev-btn approve" onclick="copyContentToClipboard()">📋 Copy Campaign Brief</button>
    </div>
  `;
  resultsEl.classList.remove('hidden');

  // Activate first platform tab
  const firstTab = resultsEl.querySelector('.platform-tab');
  if (firstTab) {
    const p = firstTab.dataset.platform || 'linkedin';
    switchContentTab(p);
  }
}

function switchContentTab(platform) {
  document.querySelectorAll('.platform-tab').forEach(t => {
    t.classList.remove('active');
    t.style.background = 'rgba(255,255,255,0.05)';
    t.style.borderColor = 'rgba(255,255,255,0.1)';
  });
  document.querySelectorAll('.platform-panel').forEach(p => p.style.display = 'none');
  const tab = document.querySelector(`.platform-tab[data-platform="${platform}"]`);
  const panel = document.getElementById(`cpanel-${platform}`);
  if (tab) {
    tab.classList.add('active');
    tab.style.background = 'rgba(255,255,255,0.18)';
    tab.style.borderColor = 'rgba(255,255,255,0.4)';
  }
  if (panel) panel.style.display = 'block';
}
window.switchContentTab = switchContentTab;

function copyContentToClipboard() {
  const resultsEl = document.getElementById('content-results');
  if (!resultsEl) return;
  const text = resultsEl.innerText;
  navigator.clipboard.writeText(text).then(() => showToast('Campaign brief copied!', 'success')).catch(() => showToast('Copy failed', 'error'));
}
window.copyContentToClipboard = copyContentToClipboard;

function viewContentHistoryItem(idx) {
  const h = contentHistory[idx];
  if (!h) return;
  renderContentResults(h, h._product, h._platforms);
}
window.viewContentHistoryItem = viewContentHistoryItem;

document.getElementById('content-generate-btn')?.addEventListener('click', async () => {
  const topic    = document.getElementById('ct-topic')?.value?.trim();
  const finding  = document.getElementById('ct-finding')?.value?.trim();
  const product  = document.getElementById('ct-product')?.value?.trim() || 'Term Insurance';
  const audience = document.getElementById('ct-audience')?.value?.trim() || 'Young Professionals';
  const goal     = document.getElementById('ct-goal')?.value;
  const tone     = document.getElementById('ct-tone')?.value;

  const checkboxes = document.querySelectorAll('.platform-checkbox:checked');
  const platforms  = Array.from(checkboxes).map(c => c.value);

  if (!topic)   { showToast('Please enter a research topic.', 'error'); return; }
  if (!finding) { showToast('Please enter a key research finding.', 'error'); return; }
  if (!platforms.length) { showToast('Select at least one platform.', 'error'); return; }

  showLoader('Generating campaign content with Gemini...');
  const resultsEl = document.getElementById('content-results');
  resultsEl.classList.add('hidden');

  const contentDirectUrl = localStorage.getItem('cortex_content') || 'http://localhost:8002';
  const gatewayUrl       = localStorage.getItem('cortex_gateway') || 'http://localhost:8001';
  const payload = {
    research_insight: { topic, key_finding: finding, opportunity: '', source: 'Research Agent' },
    product, target_audience: audience,
    campaign_goal: goal, platforms, language: 'English', tone, content_format: 'Campaign',
  };

  let resp, data;
  try {
    // Try direct Content Agent on port 8002 first
    resp = await fetch(`${contentDirectUrl}/api/content/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    data = await resp.json();
  } catch (e1) {
    try {
      // Fallback to CORTEX Gateway on port 8001
      resp = await fetch(`${gatewayUrl}/content/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      data = await resp.json();
    } catch (e2) {
      hideLoader();
      showToast('Content Agent offline. Please start server on port 8002.', 'error');
      return;
    }
  }

  hideLoader();

  if (!resp || !resp.ok || !data.success) {
    showToast(data?.detail || 'Content generation failed.', 'error');
    return;
  }

  // Save to local history
  const entry = { ...data, _product: product, _platforms: platforms, _ts: new Date().toISOString() };
  contentHistory.push(entry);
  if (contentHistory.length > 20) contentHistory.shift();
  localStorage.setItem('cortex_content_history', JSON.stringify(contentHistory));

  renderContentResults(data, product, platforms);
  showToast('Campaign content generated!', 'success');
  loadContentHistory();
});

// ── Analyze Agent Workspace Logic ─────────────────────── //
document.getElementById('analyze-run-btn')?.addEventListener('click', async () => {
  const brand   = document.getElementById('an-brand')?.value?.trim() || 'JA Assure';
  const market  = document.getElementById('an-market')?.value;
  const rtype   = document.getElementById('an-type')?.value;
  const focus   = document.getElementById('an-focus')?.value?.trim();
  const rawText = document.getElementById('an-findings')?.value?.trim();

  // Parse pasted findings into objects if provided
  let findings = [];
  if (rawText) {
    findings = rawText.split('\n').filter(l => l.trim()).map((l, i) => ({
      finding_type: 'insight',
      title: `Finding ${i + 1}`,
      summary: l.replace(/^[-*•]\s*/, '').trim()
    }));
  } else {
    // Try to auto-pull from recent research runs
    try {
      const r = await fetch(`${GATEWAY}/research/status`);
      const statuses = await r.json();
      for (const s of statuses.slice(0, 3)) {
        if (s.latest_run_id && s.status === 'COMPLETED') {
          const rr = await fetch(`${GATEWAY}/research/${s.latest_run_id}`);
          const run = await rr.json();
          findings = [...findings, ...(run.findings || []).slice(0, 4)];
          if (findings.length >= 6) break;
        }
      }
    } catch {}
  }

  showLoader('Running pattern analysis with Groq AI...');
  const resultsEl = document.getElementById('analyze-results');
  resultsEl.classList.add('hidden');

  try {
    const resp = await fetch(`${GATEWAY}/analyze/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand, market, research_type: rtype, focus, findings }),
    });
    const data = await resp.json();
    hideLoader();

    if (!data.success) { showToast(data.detail || 'Analysis failed.', 'error'); return; }
    const d = data.data;

    const strengthColor = s => s === 'high' ? '#4ade80' : s === 'medium' ? '#fbbf24' : '#94a3b8';
    const dirColor = dir => dir === 'bullish' ? '#4ade80' : dir === 'bearish' ? '#ff4d4d' : '#fbbf24';
    const dirIcon = dir => dir === 'bullish' ? '▲' : dir === 'bearish' ? '▼' : '◆';

    resultsEl.innerHTML = `
      <div style="display:flex;gap:12px;margin-bottom:20px">
        <div style="flex:1;padding:16px;background:rgba(74,222,128,0.08);border:1px solid rgba(74,222,128,0.2);border-radius:14px;text-align:center">
          <div style="font-size:28px;font-weight:700;color:#4ade80">${d.opportunity_score}<span style="font-size:14px;color:rgba(255,255,255,0.5)">/100</span></div>
          <div style="font-size:11px;letter-spacing:1px;color:rgba(255,255,255,0.5);margin-top:4px">OPPORTUNITY SCORE</div>
        </div>
        <div style="flex:1;padding:16px;background:rgba(255,77,77,0.08);border:1px solid rgba(255,77,77,0.2);border-radius:14px;text-align:center">
          <div style="font-size:28px;font-weight:700;color:#ff4d4d">${d.risk_score}<span style="font-size:14px;color:rgba(255,255,255,0.5)">/100</span></div>
          <div style="font-size:11px;letter-spacing:1px;color:rgba(255,255,255,0.5);margin-top:4px">RISK SCORE</div>
        </div>
      </div>
      <div style="padding:16px;background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.2);border-radius:14px;margin-bottom:20px">
        <div style="font-size:10px;letter-spacing:2px;color:#a78bfa;margin-bottom:8px">ANALYST VERDICT</div>
        <div style="font-size:14px;color:#fff;font-style:italic">&ldquo;${esc(d.analyst_verdict)}&rdquo;</div>
      </div>
      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">EXECUTIVE SUMMARY</div>
      <div style="font-size:13px;color:rgba(255,255,255,0.75);line-height:1.6;margin-bottom:20px">${esc(d.analysis_summary)}</div>

      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">KEY PATTERNS</div>
      <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px">
        ${(d.key_patterns || []).map(p => `
          <div style="padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <div style="font-size:14px;font-weight:600;color:#fff">${esc(p.pattern)}</div>
              <span style="font-size:10px;padding:2px 8px;border-radius:10px;background:rgba(255,255,255,0.06);color:${strengthColor(p.strength)}">${(p.strength||'').toUpperCase()}</span>
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:6px">${esc(p.description)}</div>
            <div style="font-size:11px;color:#a78bfa">→ ${esc(p.implication)}</div>
          </div>`).join('')}
      </div>

      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">MARKET SIGNALS</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px">
        ${(d.market_signals || []).map(s => `
          <div style="padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px">
            <div style="font-size:12px;font-weight:600;color:#fff;margin-bottom:4px">
              <span style="color:${dirColor(s.direction)}">${dirIcon(s.direction)} </span>${esc(s.signal)}
            </div>
            <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:6px">${esc(s.rationale)}</div>
            <div style="height:3px;background:rgba(255,255,255,0.08);border-radius:2px">
              <div style="height:100%;width:${s.confidence||0}%;background:${dirColor(s.direction)};border-radius:2px"></div>
            </div>
            <div style="font-size:10px;color:rgba(255,255,255,0.3);margin-top:3px">Confidence: ${s.confidence}%</div>
          </div>`).join('')}
      </div>

      ${(d.anomalies || []).length ? `
      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">ANOMALIES DETECTED</div>
      ${d.anomalies.map(a => `
        <div style="padding:14px;background:rgba(251,191,36,0.06);border:1px solid rgba(251,191,36,0.25);border-radius:12px;margin-bottom:10px">
          <div style="font-size:12px;font-weight:600;color:#fbbf24;margin-bottom:4px">⚠ ${esc(a.anomaly)}</div>
          <div style="font-size:11px;color:rgba(255,255,255,0.6)">→ ${esc(a.action)}</div>
        </div>`).join('')}` : ''}
    `;
    resultsEl.classList.remove('hidden');
    showToast('Pattern analysis complete.', 'success');
  } catch (e) {
    hideLoader();
    showToast('Analyze Agent failed. Check backend on port 8001.', 'error');
  }
});

// ── Strategize Agent Workspace Logic ──────────────────── //
document.getElementById('strategize-run-btn')?.addEventListener('click', async () => {
  const brand    = document.getElementById('st-brand')?.value?.trim() || 'JA Assure';
  const market   = document.getElementById('st-market')?.value;
  const goal     = document.getElementById('st-goal')?.value;
  const timeframe= document.getElementById('st-timeframe')?.value;
  const budget   = document.getElementById('st-budget')?.value;
  const summary  = document.getElementById('st-summary')?.value?.trim();

  showLoader('Building strategic roadmap with Groq AI...');
  const resultsEl = document.getElementById('strategize-results');
  resultsEl.classList.add('hidden');

  try {
    const resp = await fetch(`${GATEWAY}/strategize/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand, market, goal, timeframe, budget_tier: budget, analysis_summary: summary }),
    });
    const data = await resp.json();
    hideLoader();

    if (!data.success) { showToast(data.detail || 'Strategy build failed.', 'error'); return; }
    const d = data.data;

    const priorityColors = { P1: '#4ade80', P2: '#fbbf24', P3: '#94a3b8' };
    const riskColor = l => l === 'high' ? '#ff4d4d' : l === 'medium' ? '#fbbf24' : '#4ade80';

    resultsEl.innerHTML = `
      <div style="padding:20px;background:rgba(79,70,229,0.08);border:1px solid rgba(79,70,229,0.3);border-radius:16px;margin-bottom:20px">
        <div style="font-size:20px;font-weight:600;color:#fff;margin-bottom:6px">${esc(d.strategy_title)}</div>
        <div style="font-size:13px;color:rgba(255,255,255,0.65);line-height:1.6">${esc(d.executive_brief)}</div>
        <div style="margin-top:12px;display:flex;gap:16px">
          <div style="font-size:12px;color:rgba(255,255,255,0.4)">Confidence: <span style="color:#818cf8;font-weight:600">${d.confidence_score}%</span></div>
          <div style="font-size:12px;color:rgba(255,255,255,0.4)">ROI Base: <span style="color:#4ade80;font-weight:600">${esc(d.roi_projection?.base || '')}</span></div>
        </div>
      </div>

      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">STRATEGIC PILLARS</div>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px">
        ${(d.strategic_pillars || []).map(p => `
          <div style="padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-left:3px solid ${priorityColors[p.priority]||'#818cf8'};border-radius:12px;display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div style="font-size:13px;font-weight:600;color:#fff;margin-bottom:3px">${esc(p.pillar)}</div>
              <div style="font-size:12px;color:rgba(255,255,255,0.55)">${esc(p.description)}</div>
            </div>
            <div style="text-align:right;flex-shrink:0;margin-left:12px">
              <div style="font-size:10px;color:${priorityColors[p.priority]||'#818cf8'};font-weight:700">${p.priority}</div>
              <div style="font-size:10px;color:rgba(255,255,255,0.35);margin-top:2px">${esc(p.owner)}</div>
            </div>
          </div>`).join('')}
      </div>

      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">ROADMAP PHASES</div>
      <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:20px">
        ${(d.roadmap_phases || []).map((phase, i) => `
          <div style="padding:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
              <div style="font-size:13px;font-weight:600;color:#818cf8">${esc(phase.phase)}</div>
              <div style="font-size:11px;color:rgba(255,255,255,0.4);background:rgba(255,255,255,0.05);padding:2px 10px;border-radius:10px">${esc(phase.duration)}</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:8px">
              ${(phase.key_actions || []).map(a => `<div style="font-size:12px;color:rgba(255,255,255,0.65)">✓ ${esc(a)}</div>`).join('')}
            </div>
            <div style="font-size:11px;color:#4ade80">🏁 ${esc(phase.milestone)}</div>
          </div>`).join('')}
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
        <div>
          <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">KPI TARGETS</div>
          ${(d.kpis || []).map(k => `
            <div style="padding:12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;margin-bottom:8px">
              <div style="font-size:12px;font-weight:600;color:#fff;margin-bottom:2px">${esc(k.metric)}</div>
              <div style="font-size:13px;color:#4ade80;font-weight:600">${esc(k.target)}</div>
              <div style="font-size:10px;color:rgba(255,255,255,0.35)">Baseline: ${esc(k.baseline)}</div>
            </div>`).join('')}
        </div>
        <div>
          <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">ROI PROJECTIONS</div>
          <div style="padding:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;margin-bottom:8px">
            <div style="display:flex;flex-direction:column;gap:10px">
              <div><div style="font-size:10px;color:rgba(255,255,255,0.4)">Conservative</div><div style="font-size:14px;color:#94a3b8;font-weight:600">${esc(d.roi_projection?.conservative)}</div></div>
              <div><div style="font-size:10px;color:rgba(255,255,255,0.4)">Base Case</div><div style="font-size:14px;color:#4ade80;font-weight:600">${esc(d.roi_projection?.base)}</div></div>
              <div><div style="font-size:10px;color:rgba(255,255,255,0.4)">Optimistic</div><div style="font-size:14px;color:#fbbf24;font-weight:600">${esc(d.roi_projection?.optimistic)}</div></div>
            </div>
          </div>
        </div>
      </div>

      ${(d.risks || []).length ? `
      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">RISK REGISTER</div>
      ${d.risks.map(r => `
        <div style="padding:14px;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:12px;margin-bottom:8px">
          <div style="font-size:12px;font-weight:600;color:#f87171;margin-bottom:4px">${esc(r.risk)}</div>
          <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:4px">Likelihood: <span style="color:${riskColor(r.likelihood)}">${r.likelihood}</span> · Impact: <span style="color:${riskColor(r.impact)}">${r.impact}</span></div>
          <div style="font-size:11px;color:rgba(255,255,255,0.6)">Mitigation: ${esc(r.mitigation)}</div>
        </div>`).join('')}` : ''}
    `;
    resultsEl.classList.remove('hidden');
    showToast('Strategic roadmap built!', 'success');
  } catch (e) {
    hideLoader();
    showToast('Strategize Agent failed. Check backend on port 8001.', 'error');
  }
});

// ── Engage Agent Workspace Logic ──────────────────────── //
document.getElementById('engage-run-btn')?.addEventListener('click', async () => {
  const brand   = document.getElementById('en-brand')?.value?.trim() || 'JA Assure';
  const audience = document.getElementById('en-audience')?.value?.trim() || 'Young Professionals';
  const freq    = document.getElementById('en-freq')?.value;
  const theme   = document.getElementById('en-theme')?.value?.trim();
  const themesRaw = document.getElementById('en-themes')?.value?.trim();
  const platforms = Array.from(document.querySelectorAll('.en-platform-checkbox:checked')).map(c => c.value);
  const content_themes = themesRaw ? themesRaw.split(',').map(t => t.trim()).filter(Boolean) : [];

  if (!platforms.length) { showToast('Select at least one platform.', 'error'); return; }

  showLoader('Generating engagement calendar with Groq AI...');
  const resultsEl = document.getElementById('engage-results');
  resultsEl.classList.add('hidden');

  try {
    const resp = await fetch(`${GATEWAY}/engage/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand, platforms, audience, frequency: freq, campaign_title: theme, content_themes }),
    });
    const data = await resp.json();
    hideLoader();

    if (!data.success) { showToast(data.detail || 'Engage Agent failed.', 'error'); return; }
    const d = data.data;

    const platformColor = p => ({ LinkedIn: '#0077b5', Instagram: '#e1306c', X: '#94a3b8' }[p] || '#fff');
    const week1 = (d.posting_schedule || []).filter(s => s.week === 1);
    const week2 = (d.posting_schedule || []).filter(s => s.week === 2);

    const renderWeek = (posts) => posts.map(p => `
      <div style="padding:12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;display:flex;gap:12px;align-items:flex-start">
        <div style="flex-shrink:0;text-align:center;min-width:52px">
          <div style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.8)">${esc(p.day)}</div>
          <div style="font-size:10px;color:${platformColor(p.platform)};margin-top:2px">${esc(p.platform)}</div>
        </div>
        <div style="flex:1">
          <div style="font-size:12px;font-weight:600;color:#fff;margin-bottom:2px">${esc(p.content_type)}</div>
          <div style="font-size:11px;color:rgba(255,255,255,0.6);margin-bottom:4px">${esc(p.topic)}</div>
          <div style="display:flex;gap:8px">
            <span style="font-size:10px;color:rgba(255,255,255,0.35)">🕐 ${esc(p.best_time)}</span>
            <span style="font-size:10px;color:#fbbf24">${esc(p.cta)}</span>
          </div>
        </div>
      </div>`).join('');

    resultsEl.innerHTML = `
      <div style="padding:16px;background:rgba(3,105,161,0.1);border:1px solid rgba(3,105,161,0.3);border-radius:14px;margin-bottom:20px">
        <div style="font-size:16px;font-weight:600;color:#fff;margin-bottom:6px">${esc(d.calendar_title)}</div>
        <div style="font-size:13px;color:rgba(255,255,255,0.6);line-height:1.5">${esc(d.engagement_strategy)}</div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
        ${[{label:'Impressions/Week', val:d.kpi_targets?.impression_goal, col:'#38bdf8'},{label:'Engagement Rate', val:d.kpi_targets?.engagement_rate, col:'#4ade80'},{label:'Click-Through', val:d.kpi_targets?.click_through, col:'#fbbf24'},{label:'Follower Growth', val:d.kpi_targets?.follower_growth, col:'#a78bfa'}].map(k =>
          `<div style="padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;text-align:center">
            <div style="font-size:18px;font-weight:700;color:${k.col}">${esc(k.val||'—')}</div>
            <div style="font-size:10px;color:rgba(255,255,255,0.4);margin-top:4px;letter-spacing:1px">${k.label}</div>
          </div>`).join('')}
      </div>

      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">WEEK 1 SCHEDULE</div>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px">${renderWeek(week1)}</div>

      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">WEEK 2 SCHEDULE</div>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px">${renderWeek(week2)}</div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
        <div>
          <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">ENGAGEMENT TACTICS</div>
          ${(d.engagement_tactics || []).map(t => `
            <div style="padding:12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;margin-bottom:8px">
              <div style="font-size:12px;font-weight:600;color:#fff;margin-bottom:2px">${esc(t.tactic)} <span style="color:${platformColor(t.platform)};font-size:10px">(${t.platform})</span></div>
              <div style="font-size:11px;color:rgba(255,255,255,0.55)">${esc(t.description)}</div>
              <div style="font-size:10px;color:rgba(255,255,255,0.3);margin-top:3px">${esc(t.frequency)}</div>
            </div>`).join('')}
        </div>
        <div>
          <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">HASHTAG STRATEGY</div>
          <div style="padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px">
            <div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:4px">Primary</div>
            <div style="font-size:12px;color:#fbbf24;margin-bottom:10px">${(d.hashtag_strategy?.primary||[]).join(' ')}</div>
            <div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:4px">Secondary</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:10px">${(d.hashtag_strategy?.secondary||[]).join(' ')}</div>
            <div style="font-size:10px;color:rgba(255,255,255,0.4);margin-bottom:4px">Trending</div>
            <div style="font-size:12px;color:#38bdf8">${(d.hashtag_strategy?.trending||[]).join(' ')}</div>
          </div>
        </div>
      </div>

      ${(d.optimization_tips || []).length ? `
      <div style="margin-bottom:8px;font-size:10px;letter-spacing:2px;color:rgba(255,255,255,0.4)">OPTIMIZATION TIPS</div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${d.optimization_tips.map(t => `<div style="font-size:12px;color:rgba(255,255,255,0.65);padding:10px 14px;background:rgba(255,255,255,0.03);border-radius:10px;border-left:2px solid #38bdf8">💡 ${esc(t)}</div>`).join('')}
      </div>` : ''}
    `;
    resultsEl.classList.remove('hidden');
    showToast('Engagement calendar generated!', 'success');
  } catch (e) {
    hideLoader();
    showToast('Engage Agent failed. Check backend on port 8001.', 'error');
  }
});

// ── Insights Page Logic ───────────────────────────────── //
function initInsightsPage() {
  document.getElementById('insights-load-btn')?.addEventListener('click', loadInsights);
}

async function loadInsights() {
  const container = document.getElementById('insights-container');
  container.innerHTML = '<div class="empty-state"><div class="loader-spinner"></div><p>Aggregating intelligence...</p></div>';
  try {
    const resp = await fetch(`${GATEWAY}/research/status`);
    const statuses = await resp.json();
    if (!statuses.length) {
      container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔬</div><h3>No research runs found</h3><p>Run a Discovery Agent session first.</p></div>';
      return;
    }
    let findings = [];
    for (const s of statuses.slice(0,4)) {
      if (s.latest_run_id && s.status === 'COMPLETED') {
        try {
          const r = await fetch(`${GATEWAY}/research/${s.latest_run_id}`);
          const run = await r.json();
          (run.findings||[]).forEach(f => { f._brand = run.brand; f._market = run.market; });
          findings = [...findings, ...run.findings||[]];
        } catch {}
      }
    }
    if (!findings.length) {
      container.innerHTML = '<div class="empty-state"><div class="empty-icon">📡</div><h3>No findings yet</h3><p>No completed runs found.</p></div>';
      return;
    }
    container.innerHTML = `<div class="findings-grid">${findings.map(f => `
      <div class="finding-card">
        <div class="finding-badge">${(f.finding_type||'').replace(/_/g,' ')}</div>
        <div class="finding-title">${esc(f.title)}</div>
        <div class="finding-body">${esc(f.summary||'')}</div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:rgba(255,255,255,0.4);margin-top:10px">
          <span>${esc(f._brand||'')} · ${esc(f._market||'')}</span>
          <span>Confidence ${f.confidence_score||0}%</span>
        </div>
        <div class="score-bar"><div class="score-fill" style="width:${f.confidence_score||0}%"></div></div>
      </div>`).join('')}</div>`;
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">⚙️</div><h3>Research Agent offline</h3><p>${e.message}</p></div>`;
  }
}

// ── Settings Page Logic ───────────────────────────────── //
function initSettingsPage() {
  document.getElementById('s-research-url').value = RESEARCH;
  document.getElementById('s-gateway-url').value  = GATEWAY;
  const contentUrlEl = document.getElementById('s-content-url');
  if (contentUrlEl) contentUrlEl.value = localStorage.getItem('cortex_content') || 'http://localhost:8002';
  document.getElementById('settings-save-btn')?.addEventListener('click', () => {
    const g = document.getElementById('s-gateway-url')?.value?.trim();
    const r = document.getElementById('s-research-url')?.value?.trim();
    const ct = document.getElementById('s-content-url')?.value?.trim();
    if (g)  localStorage.setItem('cortex_gateway', g);
    if (r)  localStorage.setItem('cortex_research', r);
    if (ct) localStorage.setItem('cortex_content', ct);
    showToast('Configuration saved.', 'success');
  });
  document.getElementById('health-check-btn')?.addEventListener('click', runHealthChecks);
  runHealthChecks();
}

async function runHealthChecks() {
  let gatewayData = null;
  const gatewayEl    = document.getElementById('check-gateway');
  const researchEl   = document.getElementById('check-research');
  const complianceEl = document.getElementById('check-compliance');
  const contentEl    = document.getElementById('check-content');

  [gatewayEl, researchEl, complianceEl, contentEl].forEach(el => {
    if (el) { el.textContent = 'Checking...'; el.style.color = 'rgba(255,255,255,0.4)'; }
  });

  try {
    const resp = await fetch(`${GATEWAY}/health`, { signal: AbortSignal.timeout(5000) });
    gatewayData = await resp.json();

    if (gatewayEl) {
      const ok = gatewayData?.cortex === 'ok';
      gatewayEl.textContent = ok ? '● Online' : '○ Degraded';
      gatewayEl.style.color = ok ? '#4ade80' : '#fbbf24';
    }
    if (researchEl) {
      const ok = gatewayData?.research_agent === 'ok';
      researchEl.textContent = ok ? '● Online' : '✕ Offline';
      researchEl.style.color = ok ? '#4ade80' : '#ff4d4d';
    }
    if (complianceEl) {
      const ok = gatewayData?.compliance_agent === 'ok';
      complianceEl.textContent = ok ? '● Online' : '○ Degraded';
      complianceEl.style.color = ok ? '#4ade80' : '#fbbf24';
    }
    if (contentEl) {
      const ok = gatewayData?.content_agent === 'ok';
      contentEl.textContent = ok ? '● Online' : '✕ Offline';
      contentEl.style.color = ok ? '#4ade80' : '#ff4d4d';
    }
  } catch {
    if (gatewayEl)    { gatewayEl.textContent    = '✕ Offline'; gatewayEl.style.color    = '#ff4d4d'; }
    if (researchEl)   { researchEl.textContent   = '— Unknown'; researchEl.style.color   = 'rgba(255,255,255,0.4)'; }
    if (complianceEl) { complianceEl.textContent = '— Unknown'; complianceEl.style.color = 'rgba(255,255,255,0.4)'; }
    if (contentEl)    { contentEl.textContent    = '— Unknown'; contentEl.style.color    = 'rgba(255,255,255,0.4)'; }
  }
}

// ── Helpers ───────────────────────────────────────────── //
function createLeaves() {
  const container = document.getElementById('leaves-container');
  if (!container) return;
  const LEAF_COUNT = 24;
  for (let i = 0; i < LEAF_COUNT; i++) {
    const leaf = document.createElement('div');
    leaf.className = 'leaf';
    const size  = 6 + Math.random() * 10;
    const left  = Math.random() * 100;
    const dur   = 8 + Math.random() * 14;
    const delay = Math.random() * 16;
    leaf.style.cssText = `
      width: ${size}px; height: ${size}px;
      left: ${left}%; top: -20px;
      animation-duration: ${dur}s; animation-delay: ${delay}s;
    `;
    container.appendChild(leaf);
  }
}

function showLoader(msg) {
  document.getElementById('global-loader').style.display = 'flex';
  document.getElementById('loader-msg').textContent = msg || 'Processing...';
}
function hideLoader() { document.getElementById('global-loader').style.display = 'none'; }

function showToast(msg, type='info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(20px)'; t.style.transition='all .3s ease'; setTimeout(()=>t.remove(),300); }, 4000);
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Underground Parallax Engine ────────────────────────── //
function initUndergroundParallax() {
  const section = document.getElementById('underground-section');
  const rootsLayer = document.getElementById('prl-roots');
  const cardsLayer = document.getElementById('prl-cards');
  const soilMid = document.getElementById('soil-mid');
  const homePage = document.getElementById('page-home');

  if (!section) return;

  function onScroll() {
    const rect = section.getBoundingClientRect();
    const viewHeight = window.innerHeight;

    // Check if section is approaching or in viewport
    if (rect.top <= viewHeight && rect.bottom >= 0) {
      // Progress from 0 (entry at bottom) to 1 (full scroll)
      const scrolled = Math.max(0, viewHeight - rect.top);
      
      // Depth translations — keep rootsLayer locked at top (0px) so trunk stays connected to ground
      const cardY = scrolled * 0.16;  // card parallax
      const soilY = scrolled * 0.05;

      if (rootsLayer) rootsLayer.style.transform = `translate3d(0, 0px, 0)`;
      if (cardsLayer) cardsLayer.style.transform = `translate3d(0, ${cardY}px, 0)`;
      if (soilMid)    soilMid.style.transform    = `translate3d(0, ${soilY}px, 0)`;
    }
  }

  if (homePage) homePage.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll(); // initial sync
}

function createSoilParticles() {
  const container = document.getElementById('soil-particles');
  if (!container) return;

  const SPORE_COUNT = 36;
  for (let i = 0; i < SPORE_COUNT; i++) {
    const spore = document.createElement('div');
    spore.className = 'soil-spore';
    const left  = Math.random() * 100;
    const top   = Math.random() * 100;
    const size  = 2 + Math.random() * 4;
    const dur   = 5 + Math.random() * 7;
    const delay = Math.random() * 5;

    spore.style.cssText = `
      left: ${left}%; top: ${top}%;
      width: ${size}px; height: ${size}px;
      animation-duration: ${dur}s; animation-delay: ${delay}s;
      opacity: ${0.2 + Math.random() * 0.5};
    `;
    container.appendChild(spore);
  }
}

// ── Init ──────────────────────────────────────────────── //
document.addEventListener('DOMContentLoaded', () => {
  navigateTo('home');
  initEnvironmentEngine();
  createLeaves();
  createSoilParticles();
  initUndergroundParallax();
  setupAppleClickEvents();
});

