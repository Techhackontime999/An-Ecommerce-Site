/* ==========================================================================
   Shop-Seed Loader Experience System — Engine (Phase 1)

   - Initial loader: rendered by the server (instant paint), decided + animated
     here, finished as soon as the page is ready (with a minimum display time).
   - Navigation loader: slim top progress bar on internal navigation + a brief
     "route" bar on subsequent page loads. The big intro is never replayed.
   - Configuration is read from the inline JSON the server injects (versioned)
     and cached in localStorage; the JSON endpoint refreshes it in the
     background without blocking startup.
   - Degrades gracefully: reduced motion, slow/save-data networks and phones
     fall back to the lightweight spinner.
   ========================================================================== */
(function (global, document) {
  'use strict';

  var STORE_KEY = 'ss_loader_cached_config';
  var SEEN_KEY = 'ss_loader_seen';
  var SESSION_SHOWN_KEY = 'ss_loader_shown';

  var EXIT_CLASSES = {
    fade: 'ss-exit-fade',
    zoom: 'ss-exit-zoom',
    slide: 'ss-exit-slide',
    none: 'ss-exit-none'
  };

  var currentConfig = null;

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function getJSON(id) {
    var node = document.getElementById(id);
    if (!node) return null;
    try { return JSON.parse(node.textContent || 'null'); } catch (e) { return null; }
  }

  function deviceType() {
    var w = global.innerWidth || document.documentElement.clientWidth || 0;
    if (w < 768) return 'mobile';
    if (w < 1024) return 'tablet';
    return 'desktop';
  }

  function reducedMotion() {
    return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function slowNetwork() {
    var nav = global.navigator || {};
    if (!nav.connection) return false;
    if (nav.connection.saveData) return true;
    var et = String(nav.connection.effectiveType || '').toLowerCase();
    return et === 'slow-2g' || et === '2g';
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  /* ---- Scene builders --------------------------------------------------- */
  function brandParts(cfg, pulse) {
    var mark;
    if (cfg.logo_image) {
      mark = document.createElement('img');
      mark.className = 'ss-brand__img';
      mark.src = cfg.logo_image;
      mark.alt = '';
    } else {
      mark = el('span', 'ss-brand__mark' + (pulse ? ' is-pulse' : ''));
      mark.textContent = cfg.logoMark || 'S';
    }
    var name = el('span', 'ss-brand__name', cfg.logo_text || cfg.siteName || 'Shop-Seed');
    return { mark: mark, name: name };
  }

  /* ---- Skeleton layout (shared by scene + layer) ------------------------- */
  function skeletonLayout() {
    var sk = el('div', 'ss-skeleton');
    sk.appendChild(el('div', 'ss-skeleton__bar'));
    sk.appendChild(el('div', 'ss-skeleton__hero'));
    var section = el('div', 'ss-skeleton__section');
    section.appendChild(el('div', 'ss-skeleton__title'));
    var grid = el('div', 'ss-skeleton__grid');
    for (var i = 0; i < 4; i++) {
      var card = el('div', 'ss-skeleton__card');
      card.appendChild(el('div', 'ss-skeleton__img'));
      card.appendChild(el('div', 'ss-skeleton__line'));
      card.appendChild(el('div', 'ss-skeleton__line ss-skeleton__line--short'));
      card.appendChild(el('div', 'ss-skeleton__line ss-skeleton__line--btn'));
      grid.appendChild(card);
    }
    section.appendChild(grid);
    sk.appendChild(section);
    return sk;
  }

  function buildScene(cfg, type) {
    var scene = el('div', 'ss-loader__scene');
    var parts, brand;
    switch (type) {
      case 'seed': {
        var seed = el('div', 'ss-seed');
        seed.appendChild(el('div', 'ss-seed__soil'));
        seed.appendChild(el('div', 'ss-seed__grain'));
        var stem = el('div', 'ss-seed__sprout');
        var lwL = el('div', 'ss-seed__leaf-wrap--l'); lwL.appendChild(el('div', 'ss-seed__leaf'));
        var lwR = el('div', 'ss-seed__leaf-wrap--r'); lwR.appendChild(el('div', 'ss-seed__leaf'));
        stem.appendChild(lwL);
        stem.appendChild(lwR);
        seed.appendChild(stem);
        scene.appendChild(seed);
        parts = brandParts(cfg, true);
        brand = el('div', 'ss-brand');
        brand.appendChild(parts.mark);
        brand.appendChild(parts.name);
        scene.appendChild(brand);
        break;
      }
      case 'logo': {
        parts = brandParts(cfg, false);
        var markBox = el('span', 'ss-brand__mark');
        markBox.style.position = 'relative';
        markBox.appendChild(el('span', 'ss-ring'));
        markBox.appendChild(parts.mark);
        brand = el('div', 'ss-brand');
        brand.appendChild(markBox);
        brand.appendChild(parts.name);
        scene.appendChild(brand);
        break;
      }
      case 'spinner':
        scene.appendChild(el('span', 'ss-spinner'));
        break;
      case 'progress': {
        var wrap = el('div', 'ss-progress');
        wrap.appendChild(el('div', 'ss-progress__bar'));
        wrap.appendChild(el('div', 'ss-progress__hint', 'Loading experience'));
        scene.appendChild(wrap);
        break;
      }
      case 'skeleton':
        scene.appendChild(skeletonLayout());
        break;
      default:
        scene.appendChild(el('span', 'ss-spinner'));
    }
    return scene;
  }

  /* ---- Overlay playback ------------------------------------------------- */
  function playOverlay(overlay, cfg, opts) {
    opts = opts || {};
    var done = false;
    function exit() {
      if (done) return;
      done = true;
      var cls = EXIT_CLASSES[cfg.exit_animation] || 'ss-exit-fade';
      overlay.classList.add(cls);
      var delay = cfg.exit_animation === 'slide' ? 620 : (cfg.exit_animation === 'none' ? 10 : 470);
      setTimeout(function () {
        overlay.classList.add('is-removed');
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        if (opts.onDone) opts.onDone();
      }, delay);
    }

    var duration = clamp(parseInt(cfg.duration_ms, 10) || 1600, 400, 6000);
    var minMs = Math.min(duration, 480);
    var maxMs = duration + 500;
    var start = Date.now();
    var ready = !!opts.ready;
    var finished = false;

    function tryFinish() {
      if (finished) return;
      if (ready && Date.now() - start >= minMs) {
        finished = true;
        exit();
      }
    }

    function onReady() {
      ready = true;
      tryFinish();
    }

    if (!opts.preview) global.addEventListener('load', onReady);
    setTimeout(onReady, Math.min(duration, 1200));
    setTimeout(function () {
      if (!finished) { finished = true; exit(); }
    }, maxMs);
  }

  function runInitial(overlay, cfg, opts) {
    opts = opts || {};
    var type = cfg.initial_type;
    if (cfg.network_fallback && slowNetwork() && (type === 'seed' || type === 'logo')) type = 'spinner';
    if (cfg.lightweight_mobile && deviceType() === 'mobile' && (type === 'seed' || type === 'logo')) type = 'spinner';

    if (overlay.getAttribute('data-type') !== type) {
      overlay.innerHTML = '';
      overlay.appendChild(buildScene(cfg, type));
    }
    overlay.classList.remove('ss-loader--seed', 'ss-loader--logo', 'ss-loader--spinner', 'ss-loader--progress', 'ss-loader--skeleton');
    overlay.classList.add('ss-loader--' + type);
    playOverlay(overlay, cfg, opts);
  }

  /* ---- Skeleton screen (post-intro, while content loads) ----------------- */
  function skeletonEligible(cfg) {
    if (!cfg || !cfg.enabled || !cfg.skeleton_enabled) return false;
    if (cfg.respect_reduced_motion && reducedMotion()) return false;
    return !!cfg['device_' + deviceType()];
  }

  function showSkeletonLayer(cfg) {
    var layer = document.createElement('div');
    layer.className = 'ss-skeleton-layer';
    layer.style.setProperty('--ss-bg', cfg.background_color || '#0c1017');
    layer.setAttribute('role', 'status');
    layer.setAttribute('aria-label', 'Loading content');
    layer.appendChild(skeletonLayout());
    document.body.appendChild(layer);

    var start = Date.now();
    var minMs = 500;
    var maxMs = 3000;
    var finished = false;
    function finish() {
      if (finished) return;
      finished = true;
      layer.classList.add('ss-skeleton--exit');
      setTimeout(function () {
        if (layer.parentNode) layer.parentNode.removeChild(layer);
      }, 400);
    }
    function check() {
      if (finished) return;
      if (document.readyState === 'complete' && Date.now() - start >= minMs) finish();
    }
    if (document.readyState === 'complete') setTimeout(check, minMs);
    else global.addEventListener('load', check);
    var poll = setInterval(check, 200);
    setTimeout(function () { clearInterval(poll); finish(); }, maxMs);
  }

  function maybeSkeleton(cfg) {
    if (!skeletonEligible(cfg)) return;
    if (cfg.initial_type === 'skeleton') return; // the overlay already is the skeleton
    showSkeletonLayer(cfg);
  }

  /* ---- Show / hide decision -------------------------------------------- */
  function decideInitial(cfg) {
    if (!cfg || !cfg.enabled) return 'off';
    if (cfg.initial_type === 'none') return 'off';
    if (!cfg['device_' + deviceType()]) return 'device';
    if (cfg.respect_reduced_motion && reducedMotion()) return 'motion';
    if (cfg.show_on === 'first_visit') {
      try { if (global.localStorage.getItem(SEEN_KEY)) return 'seen'; } catch (e) {}
    }
    if (cfg.show_on === 'once_per_session') {
      try { if (global.sessionStorage.getItem(SESSION_SHOWN_KEY)) return 'seen'; } catch (e) {}
    }
    return 'show';
  }

  function markSeen(cfg) {
    try {
      if (cfg.show_on === 'first_visit') global.localStorage.setItem(SEEN_KEY, '1');
      if (cfg.show_on === 'once_per_session') global.sessionStorage.setItem(SESSION_SHOWN_KEY, '1');
    } catch (e) {}
  }

  /* ---- Navigation loader ------------------------------------------------ */
  function getNavbar() {
    return document.getElementById('ss-navbar');
  }

  function showNavbar() {
    var bar = getNavbar();
    if (!bar) return;
    bar.style.setProperty('--ss-accent', (currentConfig && currentConfig.accent_color) || '#ff7a2f');
    bar.classList.add('is-active');
  }

  function hideNavbar() {
    var bar = getNavbar();
    if (bar) bar.classList.remove('is-active');
  }

  function bindNavClicks(cfg) {
    if (!cfg || !cfg.enabled || cfg.navigation_type === 'none') return;
    if (!cfg['device_' + deviceType()]) return;
    if (cfg.respect_reduced_motion && reducedMotion()) return;
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      if (e.defaultPrevented) return;
      if (a.target === '_blank' || a.hasAttribute('download')) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      if (a.closest('[data-no-loader]')) return;
      var href = a.getAttribute('href') || '';
      if (href.charAt(0) === '#' || /^(mailto:|tel:|javascript:)/i.test(href)) return;
      try {
        if (/^https?:/i.test(href) && new URL(href, location.href).origin !== location.origin) return;
      } catch (err) { return; }
      showNavbar();
      setTimeout(hideNavbar, 1200);
    });
  }

  /* ---- Config caching ---------------------------------------------------- */
  function cacheConfig(cfg) {
    try {
      global.localStorage.setItem(STORE_KEY, JSON.stringify({ version: cfg.version, config: cfg }));
    } catch (e) {}
  }

  function refreshConfig(callback) {
    if (!global.fetch) {
      if (callback) callback(null);
      return;
    }
    global.fetch('/api/loader/config.json', { credentials: 'same-origin' })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data) cacheConfig(data);
        if (callback) callback(data);
      })
      .catch(function () { if (callback) callback(null); });
  }

  /* ---- Public preview API (used by Loader Studio) ------------------------ */
  function preview(config, container) {
    if (!container) return null;
    var overlay = document.createElement('div');
    overlay.className = 'ss-loader is-preview ss-loader--' + (config.initial_type || 'spinner');
    overlay.style.setProperty('--ss-bg', config.background_color || '#0c1017');
    overlay.style.setProperty('--ss-accent', config.accent_color || '#ff7a2f');
    overlay.appendChild(buildScene(config, config.initial_type || 'spinner'));
    container.innerHTML = '';
    container.appendChild(overlay);
    return {
      overlay: overlay,
      play: function () { playOverlay(overlay, config, { preview: true }); }
    };
  }

  /* ---- Init -------------------------------------------------------------- */
  function init() {
    var cfg = getJSON('ss-loader-config');
    if (!cfg) return;

    var overlay = document.getElementById('ss-loader');
    if (overlay) {
      cfg.logoMark = overlay.getAttribute('data-mark') || 'S';
      cfg.siteName = overlay.getAttribute('data-site-name') || cfg.logo_text || 'Shop-Seed';
    }
    currentConfig = cfg;
    cacheConfig(cfg);

    var bar = getNavbar();
    if (bar) bar.style.setProperty('--ss-accent', cfg.accent_color || '#ff7a2f');

    var decision = decideInitial(cfg);
    if (decision === 'show') {
      if (overlay) {
        runInitial(overlay, cfg, { onDone: function () { maybeSkeleton(cfg); } });
        markSeen(cfg);
      } else {
        maybeSkeleton(cfg);
      }
    } else {
      if (overlay) overlay.classList.add('is-removed');
      if (decision === 'motion' || decision === 'seen') markSeen(cfg);
      maybeSkeleton(cfg);
    }

    if (decision !== 'show') {
      var bar2 = getNavbar();
      if (bar2 && cfg.navigation_type !== 'none' && cfg.enabled && cfg['device_' + deviceType()]) {
        if (!(cfg.respect_reduced_motion && reducedMotion())) {
          var firstVisit = false;
          try { firstVisit = !global.localStorage.getItem(SEEN_KEY); } catch (e) {}
          if (!firstVisit) {
            showNavbar();
            setTimeout(hideNavbar, 800);
          }
        }
      }
    }

    bindNavClicks(cfg);
    refreshConfig(function (fresh) {
      if (fresh && fresh.version && cfg.version && fresh.version !== cfg.version) {
        currentConfig = fresh;
      }
    });
  }

  global.ShopSeedLoader = {
    config: function () { return currentConfig; },
    preview: preview,
    showNav: showNavbar,
    hideNav: hideNavbar,
    refreshConfig: refreshConfig
  };

  init();
})(window, document);
