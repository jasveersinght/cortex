/**
 * CORTEX — API Client
 * All backend communication for Research and Compliance agents
 */

const CORTEX_API = {
  // CORTEX Gateway (compliance, activity, health)
  gateway: localStorage.getItem('cortex_gateway_url') || 'http://localhost:8001',
  // Research Agent (direct or through gateway proxy)
  research: localStorage.getItem('cortex_research_url') || 'http://localhost:8000',

  updateUrls(gateway, research) {
    this.gateway = gateway || this.gateway;
    this.research = research || this.research;
    if (gateway) localStorage.setItem('cortex_gateway_url', gateway);
    if (research) localStorage.setItem('cortex_research_url', research);
  },

  async _fetch(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || err.message || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // ── Research Agent ────────────────────────────────── //

  async runResearch({ brand, market, research_type, objective, competitors, lookback_days, force_refresh, max_sources }) {
    // Try direct research API first
    try {
      return await this._fetch(`${this.research}/discover/run`, {
        method: 'POST',
        body: JSON.stringify({
          brand, market, research_type, objective,
          competitors: competitors || [],
          lookback_days: lookback_days || 30,
          force_refresh: force_refresh || false,
          max_sources: max_sources || 20,
        }),
      });
    } catch (e) {
      // Fall back to gateway proxy
      return await this._fetch(`${this.gateway}/research/run`, {
        method: 'POST',
        body: JSON.stringify({
          brand, market, research_type, objective,
          competitors: competitors || [],
          lookback_days: lookback_days || 30,
          force_refresh: force_refresh || false,
          max_sources: max_sources || 20,
        }),
      });
    }
  },

  async getResearchStatus() {
    try {
      return await this._fetch(`${this.research}/discover/status`);
    } catch {
      return await this._fetch(`${this.gateway}/research/status`);
    }
  },

  async getResearchRun(runId) {
    try {
      return await this._fetch(`${this.research}/discover/${runId}`);
    } catch {
      return await this._fetch(`${this.gateway}/research/${runId}`);
    }
  },

  async getFindings(runId, filters = {}) {
    const params = new URLSearchParams(filters).toString();
    try {
      return await this._fetch(`${this.research}/discover/${runId}/findings${params ? '?' + params : ''}`);
    } catch {
      return await this._fetch(`${this.gateway}/research/${runId}/findings${params ? '?' + params : ''}`);
    }
  },

  // ── Compliance Agent ──────────────────────────────── //

  async checkCompliance({ body_text, brand, region, content_type, platform, policy_context }) {
    return await this._fetch(`${this.gateway}/compliance/check`, {
      method: 'POST',
      body: JSON.stringify({ body_text, brand, region, content_type, platform, policy_context: policy_context || '' }),
    });
  },

  async getComplianceHistory(limit = 20) {
    return await this._fetch(`${this.gateway}/compliance/history?limit=${limit}`);
  },

  async getComplianceAsset(assetId) {
    return await this._fetch(`${this.gateway}/compliance/asset/${assetId}`);
  },

  async reviewAsset(assetId, { decision, tag, note }) {
    return await this._fetch(`${this.gateway}/compliance/review/${assetId}`, {
      method: 'POST',
      body: JSON.stringify({ decision, tag, note }),
    });
  },

  // ── Content Agent ─────────────────────────────────── //

  async generateContent({ research_insight, product, target_audience, campaign_goal, platforms, language, tone, content_format }) {
    return await this._fetch(`${this.gateway}/content/generate`, {
      method: 'POST',
      body: JSON.stringify({
        research_insight,
        product: product || 'Term Insurance',
        target_audience: target_audience || 'Young Professionals',
        campaign_goal: campaign_goal || 'Lead Generation',
        platforms: platforms || ['LinkedIn', 'Instagram', 'X'],
        language: language || 'English',
        tone: tone || 'Professional but human',
        content_format: content_format || 'Campaign',
      }),
    });
  },

  async contentHealth() {
    return await this._fetch(`${this.gateway}/content/health`).catch(() =>
      this._fetch('http://localhost:8002/health')
    );
  },

  // ── Activity Feed ─────────────────────────────────── //

  async getActivity(limit = 30) {
    return await this._fetch(`${this.gateway}/activity?limit=${limit}`);
  },

  // ── Health ────────────────────────────────────────── //

  async health() {
    return await this._fetch(`${this.gateway}/health`);
  },

  async researchHealth() {
    return await this._fetch(`${this.research}/health`);
  },
};

window.CORTEX_API = CORTEX_API;
