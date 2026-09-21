/**
 * CORTEX — Compliance Agent Workspace
 * Connects to project1-brain-1 via CORTEX Gateway
 */

let currentAssetId = null;

function initCompliance() {
  document.getElementById('compliance-run-btn')?.addEventListener('click', runCompliance);
  loadComplianceHistory();
}

async function runCompliance() {
  const content = document.getElementById('c-content')?.value?.trim();
  const contentType = document.getElementById('c-type')?.value;
  const brand = document.getElementById('c-brand')?.value;
  const region = document.getElementById('c-region')?.value;

  if (!content) {
    showToast('Please enter content to check for compliance.', 'error');
    return;
  }

  if (content.length < 10) {
    showToast('Content is too short to check.', 'error');
    return;
  }

  const btn = document.getElementById('compliance-run-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="loader-ring" style="width:18px;height:18px;border-width:2px;margin:0 auto"></div>';

  showLoader('Running Compliance Gate — checking 4 lenses...');

  try {
    const result = await CORTEX_API.checkCompliance({
      body_text: content,
      brand,
      region,
      content_type: contentType,
      platform: 'LinkedIn',
    });

    currentAssetId = result.asset_id;
    renderComplianceResult(result);
    showToast(`Compliance check complete — ${result.tier_label}`, result.tier === 'highly_recommended' ? 'success' : 'info');
    loadComplianceHistory();
  } catch (err) {
    showToast(`Compliance Agent error: ${err.message}`, 'error');
    console.error('Compliance error:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🛡️</span> Check Compliance';
    hideLoader();
  }
}

function renderComplianceResult(result) {
  const resultsEl = document.getElementById('compliance-results');
  const cardEl = document.getElementById('compliance-result-card');
  const lensEl = document.getElementById('lens-breakdown');
  const reviewEl = document.getElementById('review-actions');

  resultsEl.style.display = 'block';

  // Color scheme
  const colorMap = {
    highly_recommended: { cls: 'tier-green', scoreCol: '#4ade80', badgeBg: 'rgba(74,222,128,0.15)', badgeCol: '#4ade80', border: 'rgba(74,222,128,0.3)' },
    recommended_review: { cls: 'tier-amber', scoreCol: '#fbbf24', badgeBg: 'rgba(251,191,36,0.15)', badgeCol: '#fbbf24', border: 'rgba(251,191,36,0.3)' },
    vigilant:           { cls: 'tier-orange', scoreCol: '#fb923c', badgeBg: 'rgba(251,146,60,0.15)', badgeCol: '#fb923c', border: 'rgba(251,146,60,0.3)' },
    suspicious:         { cls: 'tier-red', scoreCol: '#f87171', badgeBg: 'rgba(248,113,113,0.15)', badgeCol: '#f87171', border: 'rgba(248,113,113,0.3)' },
  };

  const colors = colorMap[result.tier] || colorMap.vigilant;

  cardEl.className = `compliance-result-card ${colors.cls}`;

  cardEl.innerHTML = `
    <div class="result-tier-label" style="color:${colors.scoreCol}">● ${result.tier_label || result.tier}</div>
    <div class="result-score-row">
      <div class="result-score-num" style="color:${colors.scoreCol}">${result.confidence_score}</div>
      <div class="result-score-label">/ 100<br/><span style="font-size:11px;color:var(--text-muted)">Confidence Score</span></div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
      <span class="result-tier-badge" style="background:${colors.badgeBg};color:${colors.badgeCol};border:1px solid ${colors.border}">
        ${result.tier.replace(/_/g, ' ').toUpperCase()}
      </span>
      <span style="font-size:12px;color:var(--text-muted)">
        Asset #${result.asset_id} &nbsp;·&nbsp; ${new Date(result.checked_at).toLocaleTimeString()}
      </span>
    </div>
  `;

  // Lens breakdown
  const lensWeights = { claims: 20, regulatory: 30, brand: 15, accuracy: 35 };
  const lensIcons = { claims: '📋', regulatory: '⚖️', brand: '🎨', accuracy: '✅' };
  const lenses = result.lens_results || {};

  lensEl.innerHTML = `
    <h3>Lens Breakdown</h3>
    ${Object.entries(lenses).map(([lens, data]) => {
      const score = data.score || 0;
      const barColor = score >= 75 ? '#4ade80' : score >= 50 ? '#fbbf24' : '#f87171';
      const phrases = Array.isArray(data.flagged_phrases) ? data.flagged_phrases : [];
      return `
        <div class="lens-item">
          <div class="lens-item-header">
            <span class="lens-name">${lensIcons[lens] || '🔍'} ${lens.charAt(0).toUpperCase() + lens.slice(1)} <span style="font-size:10px;color:var(--text-muted);font-weight:400">(Weight: ${lensWeights[lens] || 25}%)</span></span>
            <span class="lens-score" style="color:${barColor}">${score}/100</span>
          </div>
          <div class="lens-bar">
            <div class="lens-fill" style="width:${score}%;background:${barColor}"></div>
          </div>
          <div class="lens-reason">${escapeHtml(data.reason || '')}</div>
          ${phrases.length > 0 ? `
            <div class="lens-phrases">
              ${phrases.map(p => `<span class="phrase-tag">⚠️ ${escapeHtml(p)}</span>`).join('')}
            </div>` : ''}
        </div>
      `;
    }).join('')}
  `;

  // Review actions
  reviewEl.innerHTML = `
    <div style="width:100%;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px">
      Human Review Required — You are the final decision maker
    </div>
    <button class="review-btn approve" onclick="handleReview('approved')">✓ Approve</button>
    <button class="review-btn revision" onclick="handleReview('needs_revision')">✏️ Needs Revision</button>
    <button class="review-btn reject" onclick="handleReview('rejected')">✕ Reject</button>
  `;

  resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function handleReview(decision) {
  if (!currentAssetId) {
    showToast('No active compliance check to review.', 'error');
    return;
  }

  const tag = decision === 'approved' ? null : prompt('Optional: add a reason tag (e.g. "too salesy", "inaccurate claim"):') || null;

  showLoader('Recording review decision...');
  try {
    await CORTEX_API.reviewAsset(currentAssetId, { decision, tag });
    showToast(`Decision recorded: ${decision.replace(/_/g, ' ')}`, 'success');
    document.getElementById('review-actions').innerHTML = `
      <div style="padding:16px;text-align:center;color:var(--text-muted)">
        ✓ Human review recorded: <strong style="color:var(--text-primary)">${decision.replace(/_/g, ' ')}</strong>
      </div>
    `;
    loadComplianceHistory();
  } catch (err) {
    showToast(`Failed to record review: ${err.message}`, 'error');
  } finally {
    hideLoader();
  }
}

window.handleReview = handleReview;

async function loadComplianceHistory() {
  const historyEl = document.getElementById('compliance-history');
  if (!historyEl) return;

  try {
    const history = await CORTEX_API.getComplianceHistory(15);
    if (!history || history.length === 0) {
      historyEl.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">No compliance checks yet. Run your first check above.</p>';
      return;
    }

    const tierColors = {
      highly_recommended: '#4ade80',
      recommended_review: '#fbbf24',
      vigilant: '#fb923c',
      suspicious: '#f87171',
    };

    historyEl.innerHTML = history.map(a => {
      const color = tierColors[a.tier] || '#888';
      const statusColor = a.status === 'approved' ? '#4ade80' : a.status === 'rejected' ? '#f87171' : '#888';
      return `
        <div class="history-item" onclick="loadComplianceAsset(${a.id})">
          <div class="history-dot" style="background:${color}"></div>
          <div class="history-item-text">
            <div class="history-item-title">${escapeHtml(a.content_type)} — ${escapeHtml(a.brand)} · ${escapeHtml(a.region)}</div>
            <div class="history-item-meta">
              Score: ${a.confidence_score ?? 'N/A'} &nbsp;·&nbsp; ${a.tier || 'pending'}
              &nbsp;·&nbsp; <span style="color:${statusColor}">${a.status}</span>
            </div>
          </div>
          <div class="history-item-time">${a.created_at ? timeAgo(a.created_at) : ''}</div>
        </div>
      `;
    }).join('');
  } catch {
    historyEl.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">CORTEX Gateway not connected. Start the gateway server to see history.</p>';
  }
}

async function loadComplianceAsset(assetId) {
  showLoader('Loading compliance record...');
  try {
    const asset = await CORTEX_API.getComplianceAsset(assetId);
    // Pre-fill form
    document.getElementById('c-content').value = asset.body_text || '';
    document.getElementById('c-brand').value = asset.brand || 'JA Assure';
    document.getElementById('c-region').value = asset.region || 'SG';

    const fakeResult = {
      asset_id: assetId,
      confidence_score: asset.confidence_score,
      tier: asset.tier,
      tier_label: (asset.tier || '').replace(/_/g, ' '),
      tier_color: 'amber',
      status: asset.status,
      lens_results: asset.lens_results || {},
      checked_at: asset.created_at || new Date().toISOString(),
    };

    currentAssetId = assetId;
    renderComplianceResult(fakeResult);
  } catch (err) {
    showToast(`Could not load record: ${err.message}`, 'error');
  } finally {
    hideLoader();
  }
}

window.loadComplianceAsset = loadComplianceAsset;

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

document.addEventListener('DOMContentLoaded', initCompliance);
