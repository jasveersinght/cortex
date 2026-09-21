/**
 * CORTEX — Tree Interaction Module
 * Handles apple click/hover, agent panel display, workspace routing
 */

const AGENT_DEFINITIONS = {
  research: {
    icon: '🍎',
    name: 'Research Agent',
    colorClass: 'research',
    description: 'Discover market intelligence, competitor activity, industry trends, and valuable lead signals from across the web.',
    status: 'live',
    statusLabel: 'LIVE',
    capabilities: ['Market Research', 'Industry Trends', 'Competitor Watch', 'Opportunity Discovery', 'Lead Intelligence'],
    action: 'Open Research Workspace',
    actionClass: 'research-btn',
    workspace: 'research-workspace',
    recentActivity: [
      { text: 'Competitor research completed', time: 'Waiting for backend', color: '#ff6b3a' },
      { text: 'Market trends identified', time: '', color: '#ff6b3a' },
    ],
  },
  content: {
    icon: '🍎',
    name: 'Content Agent',
    colorClass: 'content',
    description: 'Transform research intelligence into powerful marketing — social posts, campaigns, blogs, images, videos and multilingual content.',
    status: 'soon',
    statusLabel: 'COMING SOON',
    capabilities: ['Social Content', 'AI Images', 'Video Scripts', 'Blogs', 'Multilingual'],
    action: 'Coming Soon',
    actionClass: 'content-btn',
    workspace: 'content-workspace',
    recentActivity: [],
  },
  compliance: {
    icon: '🍎',
    name: 'Compliance Agent',
    colorClass: 'compliance',
    description: 'Check all marketing content against insurance regulatory requirements, brand standards, and JA Assure compliance rules.',
    status: 'live',
    statusLabel: 'LIVE',
    capabilities: ['Claim Checking', 'Risk Detection', 'Compliance Review', 'Suggested Corrections', 'Human Review'],
    action: 'Open Compliance Workspace',
    actionClass: 'compliance-btn',
    workspace: 'compliance-workspace',
    recentActivity: [
      { text: 'Compliance check run', time: 'Waiting for backend', color: '#4ade80' },
    ],
  },
};

let activeApple = null;
let activePanel = null;

function renderAgentPanel(agentKey) {
  const def = AGENT_DEFINITIONS[agentKey];
  if (!def) return;

  const panel = document.getElementById('agent-panel');
  const content = document.getElementById('panel-content');

  // Build recent activity HTML
  let recentHtml = '';
  if (def.recentActivity.length > 0) {
    recentHtml = `
      <p class="panel-recent-title">Recent Activity</p>
      <div class="panel-recent-list">
        ${def.recentActivity.map(a => `
          <div class="panel-recent-item">
            <div class="panel-recent-dot" style="background:${a.color}"></div>
            <span class="panel-recent-text">${a.text}</span>
            <span class="panel-recent-time">${a.time}</span>
          </div>
        `).join('')}
      </div>
    `;

    // Try to load real activity
    loadRecentActivityForPanel(agentKey, content);
  }

  content.innerHTML = `
    <div class="panel-agent-header">
      <span class="panel-agent-icon">${def.icon}</span>
      <div>
        <div class="panel-agent-name">${def.name}</div>
        <div class="panel-agent-status ${def.status}">● ${def.statusLabel}</div>
      </div>
    </div>
    <p class="panel-agent-desc">${def.description}</p>
    <p class="panel-caps-title">Capabilities</p>
    <div class="panel-caps-list">
      ${def.capabilities.map(c => `<span class="panel-cap">${c}</span>`).join('')}
    </div>
    ${recentHtml}
    <button class="panel-action-btn ${def.actionClass}" id="panel-action-btn">
      ▶ ${def.action}
    </button>
  `;

  // Wire up action button
  const actionBtn = document.getElementById('panel-action-btn');
  if (actionBtn && def.status === 'live') {
    actionBtn.addEventListener('click', () => {
      openWorkspace(def.workspace);
    });
  }

  // Show panel
  panel.dataset.state = 'visible';
  activePanel = agentKey;
}

async function loadRecentActivityForPanel(agentKey, contentEl) {
  try {
    const activity = await CORTEX_API.getActivity(5);
    const filtered = activity.filter(a => a.agent_type === agentKey).slice(0, 3);
    if (filtered.length === 0) return;

    const listEl = contentEl.querySelector('.panel-recent-list');
    if (!listEl) return;

    listEl.innerHTML = filtered.map(a => `
      <div class="panel-recent-item">
        <div class="panel-recent-dot" style="background:${agentKey === 'research' ? '#ff6b3a' : '#4ade80'}"></div>
        <span class="panel-recent-text">${a.action.replace(/^[^\s]+\s/, '')}</span>
        <span class="panel-recent-time">${a.timestamp ? timeAgo(a.timestamp) : ''}</span>
      </div>
    `).join('');
  } catch {
    // Keep placeholder content
  }
}

function closePanel() {
  const panel = document.getElementById('agent-panel');
  panel.dataset.state = 'hidden';
  panel.style.opacity = '0';
  panel.style.pointerEvents = 'none';

  // Deselect apple visual
  if (activeApple) {
    activeApple.classList.remove('apple-selected');
    activeApple = null;
  }
  activePanel = null;
}

function openWorkspace(workspaceId) {
  // Close panel first
  const panel = document.getElementById('agent-panel');
  panel.dataset.state = 'hidden';
  panel.style.opacity = '0';
  panel.style.pointerEvents = 'none';

  // Open workspace
  const ws = document.getElementById(workspaceId);
  if (ws) {
    ws.dataset.state = 'visible';
  }
}

function closeWorkspace(workspaceId) {
  const ws = document.getElementById(workspaceId);
  if (ws) {
    ws.dataset.state = 'hidden';
  }
}

function initTree() {
  const apples = document.querySelectorAll('.apple-group');

  apples.forEach(apple => {
    const agentKey = apple.dataset.agent;

    // Hover effects via CSS — SVG-compatible pointer events
    apple.style.cursor = 'pointer';

    apple.addEventListener('mouseenter', () => {
      // Leaves nearby rustle
      const leaves = document.querySelectorAll('.tree-leaf');
      leaves.forEach((leaf, i) => {
        if (i % 3 === 0) {
          leaf.style.animationDuration = '1.5s';
          setTimeout(() => { leaf.style.animationDuration = ''; }, 1000);
        }
      });
    });

    apple.addEventListener('click', (e) => {
      e.stopPropagation();

      // Click animation
      apple.classList.add('clicked');
      setTimeout(() => apple.classList.remove('clicked'), 300);

      if (activePanel === agentKey) {
        closePanel();
        return;
      }

      // Update active apple visual
      if (activeApple) activeApple.classList.remove('apple-selected');
      activeApple = apple;
      apple.classList.add('apple-selected');

      renderAgentPanel(agentKey);
    });
  });

  // Close panel on background click
  document.querySelector('.cortex-tree')?.addEventListener('click', (e) => {
    if (!e.target.closest('.apple-group') && !e.target.closest('.agent-panel')) {
      closePanel();
    }
  });

  // Close button
  document.getElementById('panel-close')?.addEventListener('click', closePanel);

  // Workspace close buttons
  ['research', 'compliance', 'content'].forEach(key => {
    const btnId = `${key}-close`;
    const wsId = `${key}-workspace`;
    document.getElementById(btnId)?.addEventListener('click', () => closeWorkspace(wsId));
  });
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const then = new Date(dateStr);
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

document.addEventListener('DOMContentLoaded', initTree);

window.CORTEX_TREE = {
  openWorkspace,
  closeWorkspace,
  renderAgentPanel,
  AGENT_DEFINITIONS,
  timeAgo,
};
