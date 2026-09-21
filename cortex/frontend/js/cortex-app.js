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
    status: 'soon',
    desc: 'Deep-dive analysis across research data, surfacing patterns and strategic signals from market intelligence.',
    caps: ['Pattern Recognition', 'Trend Correlation', 'Data Synthesis'],
    activities: [],
    workspace: null,
    btnLabel: 'Coming Soon',
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
    status: 'soon',
    desc: 'Schedule, publish and track content engagement across channels with performance analytics.',
    caps: ['Scheduling', 'Publishing', 'Analytics', 'A/B Testing'],
    activities: [],
    workspace: null,
    btnLabel: 'Coming Soon',
  },
  strategize: {
    icon: '🍎',
    name: 'Strategize Agent',
    status: 'soon',
    desc: 'Build strategic roadmaps from research intelligence, combining market and competitive signals.',
    caps: ['SWOT Analysis', 'Roadmaps', 'Opportunity Mapping'],
    activities: [],
    workspace: null,
    btnLabel: 'Coming Soon',
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
    if (id === 'ws-research') loadResearchHistory();
    if (id === 'ws-compliance') loadComplianceHistory();
    if (id === 'ws-content') loadContentHistory();
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
    <button class="platform-tab" data-platform="${p}" onclick="switchContentTab('${p}')">${platformSvgIcons[p]} <span>${platformNames[p]}</span></button>
  `).join('');

  const platformContentHtml = platformKeys.map(p => {
    const pc = d[p] || {};
    return `
      <div class="platform-panel" id="cpanel-${p}" style="display:none">
        ${pc.headline  ? `<div class="cp-row"><span class="cp-label">Headline</span><div class="cp-val">${esc(pc.headline)}</div></div>` : ''}
        ${pc.caption   ? `<div class="cp-row"><span class="cp-label">Caption</span><div class="cp-val">${esc(pc.caption)}</div></div>` : ''}
        ${pc.hook      ? `<div class="cp-row"><span class="cp-label">Hook</span><div class="cp-val">${esc(pc.hook)}</div></div>` : ''}
        ${pc.cta       ? `<div class="cp-row"><span class="cp-label">CTA</span><div class="cp-val">${esc(pc.cta)}</div></div>` : ''}
        ${pc.body      ? `<div class="cp-row"><span class="cp-label">Body</span><div class="cp-val" style="white-space:pre-wrap">${esc(pc.body)}</div></div>` : ''}
        ${pc.hashtags  ? `<div class="cp-row"><span class="cp-label">Hashtags</span><div class="cp-val" style="color:#fbbf24">${esc(Array.isArray(pc.hashtags)?pc.hashtags.join(' '):pc.hashtags)}</div></div>` : ''}
        ${!Object.keys(pc).length ? '<div style="color:rgba(255,255,255,0.4);font-size:13px">No content generated for this platform.</div>' : ''}
      </div>
    `;
  }).join('');

  const abHtml = ab.length ? ab.map((v, i) => `
    <div class="ab-card">
      <div class="ab-label">Variant ${String.fromCharCode(65+i)}</div>
      ${v.angle   ? `<div class="ab-row"><span>Angle:</span> ${esc(v.angle)}</div>` : ''}
      ${v.hook    ? `<div class="ab-row"><span>Hook:</span> ${esc(v.hook)}</div>` : ''}
      ${v.message ? `<div class="ab-row"><span>Message:</span> ${esc(v.message)}</div>` : ''}
    </div>`).join('') : '<div style="color:rgba(255,255,255,0.4);font-size:13px">No A/B variants generated.</div>';

  const bannerTitle = visual.headline || campaign.title || product;
  const bannerImage = visual.image_url || 'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=800&q=80';

  const visualHtml = `
    <div class="visual-concept-card" style="display:flex;flex-direction:column;gap:14px">
      <div class="post-banner-preview" style="position:relative;width:100%;height:220px;border-radius:14px;overflow:hidden;background:linear-gradient(135deg,rgba(15,23,42,0.9),rgba(30,41,59,0.95));border:1px solid rgba(255,255,255,0.15);box-shadow:0 12px 30px rgba(0,0,0,0.5)">
        <img src="${bannerImage}" alt="Post Banner" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0.35;filter:brightness(0.8)">
        <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;justify-content:space-between;padding:20px;background:linear-gradient(180deg,rgba(0,0,0,0.3) 0%,rgba(0,0,0,0.85) 100%)">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:#d4e8a0;background:rgba(212,232,160,0.15);padding:4px 10px;border-radius:12px;border:1px solid rgba(212,232,160,0.3)">JA ASSURE · ${esc(product)}</span>
            <span style="font-size:11px;color:rgba(255,255,255,0.7)">✨ AI Post Graphic</span>
          </div>
          <div>
            <div style="font-family:'Cormorant Garamond',serif;font-size:24px;font-weight:600;color:#ffffff;line-height:1.2;text-shadow:0 2px 10px rgba(0,0,0,0.8)">${esc(bannerTitle)}</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.75);margin-top:4px">${esc(visual.concept || messaging.hook || '')}</div>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:11px;color:#fbbf24;font-style:italic">Mood: ${esc(visual.mood || 'Premium, Trustworthy')}</span>
            <button style="padding:6px 14px;border-radius:16px;background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff;font-size:11px;font-weight:600;box-shadow:0 4px 12px rgba(245,158,11,0.4)">${esc(visual.cta || 'Learn More →')}</button>
          </div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12px;color:rgba(255,255,255,0.7)">
        ${visual.concept     ? `<div><strong style="color:#fff">Concept:</strong> ${esc(visual.concept)}</div>` : ''}
        ${visual.composition ? `<div><strong style="color:#fff">Composition:</strong> ${esc(visual.composition)}</div>` : ''}
      </div>
    </div>`;

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
      <div class="cs-label">Generated Social Post Visual Banner</div>
      ${visualHtml}
    </div>

    <div class="content-section">
      <div class="cs-label">Platform Content</div>
      <div class="platform-tabs">${platformTabsHtml}</div>
      <div class="platform-panels">${platformContentHtml}</div>
    </div>

    <div class="content-section">
      <div class="cs-label">A/B Variants</div>
      <div class="ab-grid">${abHtml}</div>
    </div>

    <div class="review-row" style="margin-top:16px">
      <button class="rev-btn approve" onclick="copyContentToClipboard()">📋 Copy Campaign Brief</button>
    </div>
  `;
  resultsEl.classList.remove('hidden');

  // Activate first platform tab
  const firstTab = resultsEl.querySelector('.platform-tab');
  if (firstTab) { firstTab.classList.add('active'); document.getElementById('cpanel-linkedin').style.display = 'block'; }
}

function switchContentTab(platform) {
  document.querySelectorAll('.platform-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.platform-panel').forEach(p => p.style.display = 'none');
  const tab = document.querySelector(`.platform-tab[data-platform="${platform}"]`);
  const panel = document.getElementById(`cpanel-${platform}`);
  if (tab) tab.classList.add('active');
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

