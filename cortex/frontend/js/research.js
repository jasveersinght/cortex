/**
 * CORTEX — Research Agent Workspace
 * Connects to Ja_assure_vertex Research API
 */

let selectedResearchType = 'market_research';
let currentResearchRunId = null;

function initResearch() {
  // Type pills
  const pills = document.querySelectorAll('#r-type-pills .type-pill');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      selectedResearchType = pill.dataset.value;
    });
  });

  // Run button
  document.getElementById('research-run-btn')?.addEventListener('click', runResearch);

  // Load history on open
  loadResearchHistory();
}

async function runResearch() {
  const brand = document.getElementById('r-brand')?.value?.trim();
  const market = document.getElementById('r-market')?.value;
  const objective = document.getElementById('r-objective')?.value?.trim();
  const competitorsRaw = document.getElementById('r-competitors')?.value?.trim();
  const lookback = parseInt(document.getElementById('r-lookback')?.value || '30');

  if (!brand) {
    showToast('Please enter a research topic or brand name.', 'error');
    return;
  }

  const competitors = competitorsRaw
    ? competitorsRaw.split(',').map(c => c.trim()).filter(Boolean)
    : [];

  const btn = document.getElementById('research-run-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="loader-ring" style="width:18px;height:18px;border-width:2px;margin:0 auto"></div>';

  showLoader('Running Research Agent...');

  try {
    const result = await CORTEX_API.runResearch({
      brand,
      market,
      research_type: selectedResearchType,
      objective: objective || null,
      competitors,
      lookback_days: lookback,
      force_refresh: false,
      max_sources: 20,
    });

    currentResearchRunId = result.research_run_id;
    renderResearchResults(result);
    showToast(`Research complete — ${result.findings_count || 0} findings discovered`, 'success');
  } catch (err) {
    showToast(`Research Agent error: ${err.message}`, 'error');
    console.error('Research error:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">▶</span> Run Research';
    hideLoader();
  }
}

function renderResearchResults(result) {
  const resultsEl = document.getElementById('research-results');
  const metaEl = document.getElementById('research-meta');
  const gridEl = document.getElementById('findings-grid');

  resultsEl.style.display = 'block';

  // Meta info
  const statusBadge = result.cache_hit
    ? '<span style="color:#4ade80">✓ Cached</span>'
    : result.status === 'COMPLETED'
    ? '<span style="color:#4ade80">✓ Completed</span>'
    : `<span style="color:#f59e0b">${result.status}</span>`;

  metaEl.innerHTML = `
    ${statusBadge} &nbsp;·&nbsp;
    ${result.sources_checked || 0} sources checked &nbsp;·&nbsp;
    ${result.findings_count || 0} findings &nbsp;·&nbsp;
    Confidence: ${result.confidence_score ?? 'N/A'}%
    ${result.cache_hit ? '' : `&nbsp;·&nbsp; ${result.tavily_calls || 0} Tavily calls`}
  `;

  // Render findings
  const findings = result.findings || [];
  if (findings.length === 0) {
    gridEl.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">🔬</div>
        <h3>No findings yet</h3>
        <p>${result.error_message || 'The research run completed but no findings were returned.'}</p>
      </div>
    `;
    return;
  }

  gridEl.innerHTML = findings.map(f => `
    <div class="finding-card">
      <span class="finding-type-badge">${formatFindingType(f.finding_type)}</span>
      <div class="finding-title">${escapeHtml(f.title)}</div>
      <div class="finding-summary">${escapeHtml(f.summary)}</div>
      ${f.why_it_matters ? `<div class="finding-why">${escapeHtml(f.why_it_matters)}</div>` : ''}
      ${f.opportunity ? `<div class="finding-summary" style="color:var(--color-gold-light);margin-top:8px">💡 ${escapeHtml(f.opportunity)}</div>` : ''}
      <div class="finding-scores">
        <div class="finding-score">
          Confidence
          <div class="score-bar"><div class="score-fill" style="width:${f.confidence_score || 0}%"></div></div>
          ${f.confidence_score || 0}%
        </div>
        <div class="finding-score">
          Importance
          <div class="score-bar"><div class="score-fill" style="width:${f.importance_score || 0}%"></div></div>
          ${f.importance_score || 0}%
        </div>
      </div>
      ${f.entities?.length ? `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">${f.entities.map(e => `<span class="cap-tag">${escapeHtml(e)}</span>`).join('')}</div>` : ''}
      <div style="margin-top:8px;font-size:10px;color:var(--text-muted)">
        ${f.change_status} &nbsp;·&nbsp; ${f.supporting_evidence_ids?.length || 0} sources
      </div>
    </div>
  `).join('');

  // Scroll to results
  resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function loadResearchHistory() {
  const historyEl = document.getElementById('research-history');
  if (!historyEl) return;

  try {
    const statuses = await CORTEX_API.getResearchStatus();
    if (!statuses || statuses.length === 0) {
      historyEl.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">No research history yet. Run your first research above.</p>';
      return;
    }

    historyEl.innerHTML = statuses.slice(0, 10).map(s => {
      const statusColor = s.status === 'COMPLETED' ? '#4ade80' : s.status === 'FAILED' ? '#f87171' : '#f59e0b';
      return `
        <div class="history-item" data-run-id="${s.latest_run_id || ''}">
          <div class="history-dot" style="background:${statusColor}"></div>
          <div class="history-item-text">
            <div class="history-item-title">${escapeHtml(s.research_type)} — ${escapeHtml(s.brand)} · ${escapeHtml(s.market)}</div>
            <div class="history-item-meta">${s.findings_count || 0} findings &nbsp;·&nbsp; ${s.status || 'unknown'}</div>
          </div>
          <div class="history-item-time">${s.completed_at ? timeAgo(s.completed_at) : ''}</div>
        </div>
      `;
    }).join('');

    // Click on history item to load that run
    historyEl.querySelectorAll('.history-item[data-run-id]').forEach(item => {
      const runId = item.dataset.runId;
      if (!runId || runId === 'null') return;
      item.addEventListener('click', async () => {
        showLoader('Loading research run...');
        try {
          const run = await CORTEX_API.getResearchRun(runId);
          renderResearchResults(run);
        } catch (err) {
          showToast(`Could not load run: ${err.message}`, 'error');
        } finally {
          hideLoader();
        }
      });
    });
  } catch {
    historyEl.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">Research Agent not connected. Start the Research Agent server to see history.</p>';
  }
}

// ── Utilities ──────────────────────────────────────────── //

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

function timeAgo(dateStr) {
  return window.CORTEX_TREE?.timeAgo(dateStr) || '';
}

document.addEventListener('DOMContentLoaded', initResearch);
