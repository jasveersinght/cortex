/**
 * CORTEX — Time-Aware Dynamic Environment Engine
 * Automatically sets sky environment based on real time or manual preset.
 */

const ENV_PRESETS = {
  dawn: {
    label: 'Dawn',
    timeRange: '05:00 - 08:59',
    bgGradient: 'linear-gradient(180deg, #2b1d38 0%, #613b56 30%, #a65858 60%, #e0976e 85%, #f5cf95 100%)',
    overlayColor: 'rgba(235, 150, 110, 0.12)',
    treeGlow: '0 0 40px rgba(224, 151, 110, 0.2)',
    hillsColor: '#3a2436',
    sunMoon: { type: 'sun', color: '#ffdfa9', top: '70%', left: '20%', shadow: '0 0 60px #ffb36b' },
    particles: 'dew',
  },
  day: {
    label: 'Day',
    timeRange: '09:00 - 16:59',
    bgGradient: 'linear-gradient(180deg, #1a3c61 0%, #2a5a8c 35%, #4b82b5 65%, #7eb3d4 85%, #bce0ee 100%)',
    overlayColor: 'rgba(255, 255, 255, 0.05)',
    treeGlow: '0 0 50px rgba(255, 255, 255, 0.15)',
    hillsColor: '#1d422a',
    sunMoon: { type: 'sun', color: '#fff6d1', top: '15%', left: '75%', shadow: '0 0 80px rgba(255,246,209,0.8)' },
    particles: 'pollen',
  },
  sunset: {
    label: 'Sunset',
    timeRange: '17:00 - 19:29',
    bgGradient: 'linear-gradient(180deg, #0f172a 0%, #1e1b4b 25%, #4c1d95 48%, #831843 68%, #9a3412 85%, #c2410c 100%)',
    overlayColor: 'rgba(249, 115, 22, 0.12)',
    treeGlow: '0 0 60px rgba(249, 115, 22, 0.25)',
    hillsColor: '#1a1024',
    sunMoon: { type: 'sun', color: '#ff7b3d', top: '65%', left: '30%', shadow: '0 0 90px #ff5500' },
    particles: 'fireflies',
  },
  night: {
    label: 'Night',
    timeRange: '19:30 - 04:59',
    bgGradient: 'linear-gradient(180deg, #020617 0%, #070f26 40%, #0d1b3e 75%, #132448 100%)',
    overlayColor: 'rgba(99, 102, 241, 0.08)',
    treeGlow: '0 0 50px rgba(129, 140, 248, 0.2)',
    hillsColor: '#050a14',
    sunMoon: { type: 'moon', color: '#e0e7ff', top: '18%', left: '80%', shadow: '0 0 50px rgba(224, 231, 255, 0.6)' },
    particles: 'stars',
  }
};

let currentEnv = 'sunset';

function getAutoEnvKey() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 9) return 'dawn';
  if (hour >= 9 && hour < 17) return 'day';
  if (hour >= 17 && hour < 19.5) return 'sunset';
  return 'night';
}

function applyEnvironment(envKey) {
  if (!ENV_PRESETS[envKey]) envKey = 'sunset';
  currentEnv = envKey;
  const config = ENV_PRESETS[envKey];

  const envContainer = document.getElementById('env-canvas-container');
  if (envContainer) {
    envContainer.style.background = config.bgGradient;
  }

  // Update body class
  document.body.className = `env-${envKey}`;

  // Update sun/moon element
  const orb = document.getElementById('celestial-orb');
  if (orb) {
    orb.style.background = config.sunMoon.color;
    orb.style.top = config.sunMoon.top;
    orb.style.left = config.sunMoon.left;
    orb.style.boxShadow = config.sunMoon.shadow;
  }

  // Update environment tag display
  const tagEl = document.getElementById('env-status-tag');
  if (tagEl) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    tagEl.innerHTML = `<span class="env-icon">${envKey === 'night' ? '🌙' : envKey === 'sunset' ? '🌅' : envKey === 'dawn' ? '🌄' : '☀️'}</span> <span>${config.label} · ${timeStr}</span>`;
  }

  // Render atmospheric stars/particles
  renderParticles(config.particles);
}

function renderParticles(type) {
  const pContainer = document.getElementById('env-particles');
  if (!pContainer) return;
  pContainer.innerHTML = '';

  if (type === 'stars' || type === 'fireflies') {
    const count = type === 'stars' ? 60 : 30;
    for (let i = 0; i < count; i++) {
      const p = document.createElement('div');
      p.className = type === 'stars' ? 'env-star' : 'env-firefly';
      p.style.left = `${Math.random() * 100}%`;
      p.style.top  = `${Math.random() * (type === 'stars' ? 70 : 90)}%`;
      p.style.animationDelay = `${Math.random() * 4}s`;
      p.style.animationDuration = `${2 + Math.random() * 3}s`;
      pContainer.appendChild(p);
    }
  }
}

function initEnvironmentEngine() {
  const autoEnv = getAutoEnvKey();
  applyEnvironment(autoEnv);

  // Re-check time every 60 seconds
  setInterval(() => {
    applyEnvironment(getAutoEnvKey());
  }, 60000);
}

window.applyEnvironment = applyEnvironment;
window.initEnvironmentEngine = initEnvironmentEngine;
