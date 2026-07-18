/**
 * DCMS Theme Studio — colors, modes, buttons, typography, sizes
 */
(function () {
  const STORAGE_KEY = 'dcms_theme_v1';

  const FONT_URLS = {
    Tajawal: 'https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap',
    Cairo: 'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap',
    'IBM Plex Sans Arabic': 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap',
    Almarai: 'https://fonts.googleapis.com/css2?family=Almarai:wght@400;700;800&display=swap',
    Inter: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap',
  };

  const PRESETS = {
    midnight: {
      nameKey: 'theme.preset.midnight',
      mode: 'dark',
      primary: '#3b82f6',
      accent: '#22c55e',
      surface: '#1a2332',
      background: '#0b1220',
      text: '#f1f5f9',
      muted: '#94a3b8',
    },
    ocean: {
      nameKey: 'theme.preset.ocean',
      mode: 'dark',
      primary: '#06b6d4',
      accent: '#14b8a6',
      surface: '#0f2838',
      background: '#071018',
      text: '#ecfeff',
      muted: '#67e8f9',
    },
    moroor: {
      nameKey: 'theme.preset.moroor',
      mode: 'dark',
      primary: '#2563eb',
      accent: '#eab308',
      surface: '#1e293b',
      background: '#0f172a',
      text: '#f8fafc',
      muted: '#94a3b8',
    },
    lightpro: {
      nameKey: 'theme.preset.lightpro',
      mode: 'light',
      primary: '#2563eb',
      accent: '#059669',
      surface: '#ffffff',
      background: '#f1f5f9',
      text: '#0f172a',
      muted: '#64748b',
    },
    sunrise: {
      nameKey: 'theme.preset.sunrise',
      mode: 'light',
      primary: '#ea580c',
      accent: '#ca8a04',
      surface: '#fffbeb',
      background: '#fef3c7',
      text: '#292524',
      muted: '#78716c',
    },
  };

  const DEFAULTS = {
    preset: 'midnight',
    mode: 'dark',
    primary: '#3b82f6',
    accent: '#22c55e',
    surface: '#1a2332',
    background: '#0b1220',
    text: '#f1f5f9',
    muted: '#94a3b8',
    buttonStyle: '3d',
    buttonShape: 'rounded',
    buttonSize: 'md',
    fontFamily: 'Tajawal',
    fontScale: 100,
    radius: 12,
    animations: true,
  };

  let current = { ...DEFAULTS };

  function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
  }

  function hexToRgb(hex) {
    const h = hex.replace('#', '');
    const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h;
    const n = parseInt(full, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }

  function darken(hex, pct) {
    const { r, g, b } = hexToRgb(hex);
    const f = 1 - pct / 100;
    return `#${[r, g, b].map(v => Math.round(v * f).toString(16).padStart(2, '0')).join('')}`;
  }

  function loadFont(name) {
    const url = FONT_URLS[name];
    if (!url) return;
    const id = `font-${name.replace(/\s+/g, '-')}`;
    if (document.getElementById(id)) return;
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = url;
    document.head.appendChild(link);
  }

  function computeDerived(cfg) {
    const primaryDark = darken(cfg.primary, 18);
    const primaryDarker = darken(cfg.primary, 32);
    const isLight = cfg.mode === 'light';
    return {
      '--bg': cfg.background,
      '--bg-elevated': isLight ? '#ffffff' : darken(cfg.background, 5),
      '--surface': cfg.surface,
      '--surface-hover': isLight ? darken(cfg.surface, 4) : darken(cfg.surface, -8),
      '--border': isLight ? darken(cfg.surface, 12) : darken(cfg.background, -15),
      '--border-light': isLight ? darken(cfg.surface, 18) : darken(cfg.background, -22),
      '--text': cfg.text,
      '--muted': cfg.muted,
      '--primary': cfg.primary,
      '--accent': cfg.accent,
      '--primary-dark': primaryDark,
      '--primary-darker': primaryDarker,
      '--radius-sm': `${Math.round(cfg.radius * 0.65)}px`,
      '--radius-md': `${cfg.radius}px`,
      '--radius-lg': `${Math.round(cfg.radius * 1.35)}px`,
      '--font-family-base': `'${cfg.fontFamily}', 'Segoe UI', Tahoma, sans-serif`,
      '--font-scale': String(cfg.fontScale / 100),
      '--btn-py': cfg.buttonSize === 'sm' ? '0.45rem' : cfg.buttonSize === 'lg' ? '0.82rem' : '0.62rem',
      '--btn-px': cfg.buttonSize === 'sm' ? '0.9rem' : cfg.buttonSize === 'lg' ? '1.55rem' : '1.25rem',
      '--btn-font': cfg.buttonSize === 'sm' ? '0.82rem' : cfg.buttonSize === 'lg' ? '1rem' : '0.9rem',
      '--glass': isLight ? 'rgba(255,255,255,0.88)' : 'rgba(26, 35, 50, 0.85)',
      '--header-grad-1': isLight ? 'rgba(255,255,255,0.98)' : 'rgba(26, 35, 50, 0.98)',
      '--header-grad-2': isLight ? 'rgba(241,245,249,0.95)' : 'rgba(17, 24, 39, 0.95)',
      '--body-glow-1': isLight ? `rgba(${hexToRgb(cfg.primary).r},${hexToRgb(cfg.primary).g},${hexToRgb(cfg.primary).b},0.08)` : `rgba(${hexToRgb(cfg.primary).r},${hexToRgb(cfg.primary).g},${hexToRgb(cfg.primary).b},0.15)`,
      '--body-glow-2': isLight ? `rgba(${hexToRgb(cfg.accent).r},${hexToRgb(cfg.accent).g},${hexToRgb(cfg.accent).b},0.06)` : `rgba(${hexToRgb(cfg.accent).r},${hexToRgb(cfg.accent).g},${hexToRgb(cfg.accent).b},0.06)`,
      '--title-grad-1': isLight ? cfg.text : '#ffffff',
      '--title-grad-2': isLight ? cfg.primary : '#93c5fd',
    };
  }

  function apply(cfg) {
    current = { ...DEFAULTS, ...cfg };
    const root = document.documentElement;
    const derived = computeDerived(current);

    Object.entries(derived).forEach(([k, v]) => root.style.setProperty(k, v));

    root.setAttribute('data-theme', current.mode);
    root.setAttribute('data-btn-style', current.buttonStyle);
    root.setAttribute('data-btn-shape', current.buttonShape);
    root.setAttribute('data-btn-size', current.buttonSize);
    root.setAttribute('data-animations', current.animations ? '1' : '0');

    loadFont(current.fontFamily);
    document.body.style.fontFamily = derived['--font-family-base'];
    document.body.style.fontSize = `calc(1rem * ${derived['--font-scale']})`;

    localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
    document.dispatchEvent(new CustomEvent('dcms:themechange', { detail: { ...current } }));
  }

  function applyPreset(key) {
    const p = PRESETS[key];
    if (!p) return;
    apply({ ...current, ...p, preset: key });
  }

  function toggleMode() {
    const next = current.mode === 'dark' ? 'light' : 'dark';
    if (next === 'light') {
      apply({ ...current, mode: 'light', ...PRESETS.lightpro, preset: 'lightpro' });
    } else {
      apply({ ...current, mode: 'dark', ...PRESETS.midnight, preset: 'midnight' });
    }
  }

  function reset() {
    apply({ ...DEFAULTS });
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) apply(JSON.parse(raw));
      else apply({ ...DEFAULTS });
    } catch {
      apply({ ...DEFAULTS });
    }
  }

  function getConfig() {
    return { ...current };
  }

  function getPresets() {
    return PRESETS;
  }

  function bindAppearancePanel() {
    const panel = document.getElementById('appearance-panel');
    const overlay = document.getElementById('theme-overlay');
    const openBtns = [document.getElementById('theme-fab'), document.getElementById('open-appearance')];
    const closeBtn = document.getElementById('close-appearance');

    function openPanel() {
      panel?.classList.add('open');
      overlay?.classList.add('open');
      syncPanelControls();
    }
    function closePanel() {
      panel?.classList.remove('open');
      overlay?.classList.remove('open');
    }

    openBtns.forEach(b => b?.addEventListener('click', openPanel));
    closeBtn?.addEventListener('click', closePanel);
    overlay?.addEventListener('click', closePanel);

    document.getElementById('theme-mode-toggle')?.addEventListener('click', () => {
      toggleMode();
      syncPanelControls();
    });

    document.querySelectorAll('[data-preset]').forEach(el => {
      el.addEventListener('click', () => {
        applyPreset(el.dataset.preset);
        syncPanelControls();
      });
    });

    ['primary', 'accent', 'surface', 'background', 'text'].forEach(key => {
      const input = document.getElementById(`theme-color-${key}`);
      input?.addEventListener('input', (e) => {
        apply({ ...current, [key]: e.target.value, preset: 'custom' });
      });
    });

    document.getElementById('theme-btn-style')?.addEventListener('change', (e) => {
      apply({ ...current, buttonStyle: e.target.value, preset: 'custom' });
    });
    document.getElementById('theme-btn-shape')?.addEventListener('change', (e) => {
      apply({ ...current, buttonShape: e.target.value, preset: 'custom' });
    });
    document.getElementById('theme-btn-size')?.addEventListener('change', (e) => {
      apply({ ...current, buttonSize: e.target.value, preset: 'custom' });
    });
    document.getElementById('theme-font')?.addEventListener('change', (e) => {
      apply({ ...current, fontFamily: e.target.value, preset: 'custom' });
    });

    const scaleInput = document.getElementById('theme-font-scale');
    const scaleVal = document.getElementById('theme-font-scale-val');
    scaleInput?.addEventListener('input', (e) => {
      const v = clamp(Number(e.target.value), 85, 130);
      if (scaleVal) scaleVal.textContent = `${v}%`;
      apply({ ...current, fontScale: v, preset: 'custom' });
    });

    const radiusInput = document.getElementById('theme-radius');
    const radiusVal = document.getElementById('theme-radius-val');
    radiusInput?.addEventListener('input', (e) => {
      const v = clamp(Number(e.target.value), 4, 24);
      if (radiusVal) radiusVal.textContent = `${v}px`;
      apply({ ...current, radius: v, preset: 'custom' });
    });

    document.getElementById('theme-animations')?.addEventListener('change', (e) => {
      apply({ ...current, animations: e.target.checked, preset: 'custom' });
    });

    document.getElementById('theme-reset')?.addEventListener('click', () => {
      reset();
      syncPanelControls();
    });

    document.addEventListener('dcms:langchange', syncPanelLabels);
  }

  function syncPanelControls() {
    const c = getConfig();
    ['primary', 'accent', 'surface', 'background', 'text'].forEach(key => {
      const el = document.getElementById(`theme-color-${key}`);
      if (el) el.value = c[key];
    });
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    setVal('theme-btn-style', c.buttonStyle);
    setVal('theme-btn-shape', c.buttonShape);
    setVal('theme-btn-size', c.buttonSize);
    setVal('theme-font', c.fontFamily);
    const scale = document.getElementById('theme-font-scale');
    if (scale) scale.value = c.fontScale;
    const scaleVal = document.getElementById('theme-font-scale-val');
    if (scaleVal) scaleVal.textContent = `${c.fontScale}%`;
    const radius = document.getElementById('theme-radius');
    if (radius) radius.value = c.radius;
    const radiusVal = document.getElementById('theme-radius-val');
    if (radiusVal) radiusVal.textContent = `${c.radius}px`;
    const anim = document.getElementById('theme-animations');
    if (anim) anim.checked = c.animations;
    const modeBtn = document.getElementById('theme-mode-toggle');
    if (modeBtn) {
      modeBtn.classList.toggle('is-light', c.mode === 'light');
      modeBtn.setAttribute('aria-pressed', c.mode === 'light' ? 'true' : 'false');
    }
    document.querySelectorAll('[data-preset]').forEach(el => {
      el.classList.toggle('active', el.dataset.preset === c.preset);
    });
    syncPanelLabels();
  }

  function syncPanelLabels() {
    const t = window.t || ((k) => k);
    document.querySelectorAll('#appearance-panel [data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll('[data-preset]').forEach(el => {
      const key = PRESETS[el.dataset.preset]?.nameKey;
      const label = el.querySelector('.preset-name');
      if (key && label) label.textContent = t(key);
    });
  }

  window.ThemeStudio = {
    load,
    apply,
    applyPreset,
    toggleMode,
    reset,
    getConfig,
    getPresets,
    bindAppearancePanel,
    syncPanelControls,
  };
})();
