/* ==========================================================================
   Shop-Seed Loader Studio — live preview for Loader Studio
   Reads the saved config (json_script), binds form controls, and drives the
   engine's preview API. Requires loader-engine.js to be loaded first.
   ========================================================================== */
(function (window, document) {
  'use strict';

  function readBaseConfig() {
    var node = document.getElementById('ss-loader-studio-config');
    if (!node) return {};
    try { return JSON.parse(node.textContent || '{}') || {}; } catch (e) { return {}; }
  }

  var base = readBaseConfig();

  var mount = document.getElementById('ls-preview-mount');
  var note = document.getElementById('ls-preview-note');
  var frame = document.getElementById('ls-preview-frame');
  var form = document.getElementById('ls-form');

  var enabled = document.getElementById('id_enabled');
  var initialType = document.getElementById('id_initial_type');
  var skeletonEnabled = document.getElementById('id_skeleton_enabled');
  var exitAnim = document.getElementById('id_exit_animation');
  var bg = document.getElementById('id_background_color');
  var accent = document.getElementById('id_accent_color');
  var duration = document.getElementById('id_duration_ms');
  var logoText = document.getElementById('id_logo_text');
  var logoImage = document.getElementById('id_logo_image');

  var fileUrl = null;

  function buildConfig() {
    var cfg = {
      enabled: enabled ? enabled.checked : true,
      initial_type: initialType ? initialType.value : (base.initial_type || 'seed'),
      skeleton_enabled: skeletonEnabled ? skeletonEnabled.checked : true,
      exit_animation: exitAnim ? exitAnim.value : (base.exit_animation || 'fade'),
      background_color: bg ? bg.value : (base.background_color || '#0c1017'),
      accent_color: accent ? accent.value : (base.accent_color || '#ff7a2f'),
      duration_ms: parseInt(duration && duration.value, 10) || 1600,
      logo_text: logoText ? logoText.value : (base.logo_text || ''),
      siteName: base.site_name || 'Shop-Seed',
      logoMark: base.logo_mark || 'S',
      logo_image: fileUrl || base.logo_image || ''
    };
    return cfg;
  }

  function setNote(message) {
    if (note) note.textContent = message || '';
  }

  function renderPreview() {
    if (mount) mount.innerHTML = '';
    setNote('');
    if (!window.ShopSeedLoader || !window.ShopSeedLoader.preview) {
      setNote('Loader engine failed to load.');
      return;
    }
    if (enabled && !enabled.checked) {
      setNote('Loader is disabled — enable it to preview.');
      return;
    }
    var cfg = buildConfig();
    if (cfg.initial_type === 'none') {
      setNote('Initial loader is off. Choose an animation to preview.');
      return;
    }
    if (cfg.initial_type === 'skeleton' && !cfg.skeleton_enabled) {
      setNote('Skeleton screen is disabled — enable it to preview.');
      return;
    }
    var ctrl = window.ShopSeedLoader.preview(cfg, mount);
    if (ctrl && ctrl.play) ctrl.play();
  }

  function bindChange(el, fn) {
    if (el) el.addEventListener('change', fn);
  }

  bindChange(initialType, renderPreview);
  bindChange(skeletonEnabled, renderPreview);
  bindChange(exitAnim, renderPreview);
  bindChange(bg, renderPreview);
  bindChange(accent, renderPreview);
  bindChange(duration, renderPreview);
  bindChange(enabled, renderPreview);
  if (logoText) logoText.addEventListener('input', renderPreview);

  if (logoImage) {
    logoImage.addEventListener('change', function () {
      var file = logoImage.files && logoImage.files[0];
      if (file && window.URL && window.URL.createObjectURL) {
        if (fileUrl) URL.revokeObjectURL(fileUrl);
        fileUrl = URL.createObjectURL(file);
      } else {
        fileUrl = null;
      }
      renderPreview();
    });
  }

  var deviceBtns = document.querySelectorAll('[data-ls-device]');
  Array.prototype.forEach.call(deviceBtns, function (btn) {
    btn.addEventListener('click', function () {
      var device = btn.getAttribute('data-ls-device');
      Array.prototype.forEach.call(deviceBtns, function (b) {
        b.classList.toggle('is-active', b === btn);
      });
      if (frame) {
        frame.classList.toggle('is-desktop', device === 'desktop');
        frame.classList.toggle('is-tablet', device === 'tablet');
        frame.classList.toggle('is-mobile', device === 'mobile');
      }
      renderPreview();
    });
  });

  var replay = document.getElementById('ls-replay');
  if (replay) replay.addEventListener('click', renderPreview);

  var LS_PRESETS = [
    {
      key: 'recommended',
      label: 'Recommended',
      desc: 'Balanced UX: brand intro, skeleton everywhere, slim nav bar.',
      fields: {
        'id_enabled': true,
        'id_initial_type': 'seed',
        'id_navigation_type': 'progress',
        'id_show_on': 'first_visit',
        'id_duration_ms': '1600',
        'id_exit_animation': 'fade',
        'id_background_color': '#0c1017',
        'id_accent_color': '#ff7a2f',
        'id_skeleton_enabled': true,
        'id_lightweight_mobile': true,
        'id_respect_reduced_motion': true,
        'id_network_fallback': true,
        'id_device_desktop': true,
        'id_device_tablet': true,
        'id_device_mobile': true,
        'skeleton_all': true
      }
    },
    {
      key: 'minimal',
      label: 'Minimal & Fast',
      desc: 'Lightweight spinner, short intro, skeleton everywhere.',
      fields: {
        'id_enabled': true,
        'id_initial_type': 'spinner',
        'id_navigation_type': 'progress',
        'id_show_on': 'every_visit',
        'id_duration_ms': '900',
        'id_exit_animation': 'fade',
        'id_background_color': '#0c1017',
        'id_accent_color': '#ff7a2f',
        'id_skeleton_enabled': true,
        'id_lightweight_mobile': true,
        'id_respect_reduced_motion': true,
        'id_network_fallback': true,
        'id_device_desktop': true,
        'id_device_tablet': true,
        'id_device_mobile': true,
        'skeleton_all': true
      }
    },
    {
      key: 'brand',
      label: 'Brand Hero',
      desc: 'Logo reveal intro, logo nav, no skeleton — pure branding.',
      fields: {
        'id_enabled': true,
        'id_initial_type': 'logo',
        'id_navigation_type': 'logo',
        'id_show_on': 'first_visit',
        'id_duration_ms': '2200',
        'id_exit_animation': 'zoom',
        'id_background_color': '#0c1017',
        'id_accent_color': '#ff7a2f',
        'id_skeleton_enabled': false,
        'id_lightweight_mobile': false,
        'id_respect_reduced_motion': true,
        'id_network_fallback': true,
        'id_device_desktop': true,
        'id_device_tablet': true,
        'id_device_mobile': true,
        'skeleton_all': false
      }
    },
    {
      key: 'performance',
      label: 'Performance',
      desc: 'Fast progress bar, skeleton on, lightweight everywhere.',
      fields: {
        'id_enabled': true,
        'id_initial_type': 'progress',
        'id_navigation_type': 'progress',
        'id_show_on': 'once_per_session',
        'id_duration_ms': '700',
        'id_exit_animation': 'fade',
        'id_background_color': '#0c1017',
        'id_accent_color': '#ff7a2f',
        'id_skeleton_enabled': true,
        'id_lightweight_mobile': true,
        'id_respect_reduced_motion': true,
        'id_network_fallback': true,
        'id_device_desktop': true,
        'id_device_tablet': true,
        'id_device_mobile': true,
        'skeleton_all': true
      }
    },
    {
      key: 'skeleton_first',
      label: 'Skeleton First',
      desc: 'Straight to the page: skeleton only, no intro, no nav bar.',
      fields: {
        'id_enabled': true,
        'id_initial_type': 'skeleton',
        'id_navigation_type': 'none',
        'id_show_on': 'every_visit',
        'id_duration_ms': '1200',
        'id_exit_animation': 'fade',
        'id_background_color': '#0c1017',
        'id_accent_color': '#ff7a2f',
        'id_skeleton_enabled': true,
        'id_lightweight_mobile': false,
        'id_respect_reduced_motion': true,
        'id_network_fallback': false,
        'id_device_desktop': true,
        'id_device_tablet': true,
        'id_device_mobile': true,
        'skeleton_all': true
      }
    }
  ];

  function setFieldValue(input, value) {
    if (!input) return;
    if (input.type === 'checkbox') {
      input.checked = !!value;
    } else {
      input.value = value;
    }
  }

  function applyPreset(preset) {
    var fields = preset.fields;
    Object.keys(fields).forEach(function (key) {
      if (key === 'skeleton_all') return;
      setFieldValue(document.getElementById(key), fields[key]);
    });
    var skeletonAll = fields.skeleton_all;
    Array.prototype.forEach.call(
      document.querySelectorAll('input[name^="skeleton_page_"]'),
      function (cb) { cb.checked = !!skeletonAll; }
    );
    renderPreview();
  }

  function renderPresets() {
    var container = document.getElementById('ls-presets');
    if (!container) return;
    LS_PRESETS.forEach(function (preset) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ls-preset' + (preset.key === 'recommended' ? ' ls-preset--recommended' : '');
      var label = document.createElement('span');
      label.className = 'ls-preset__label';
      label.textContent = preset.key === 'recommended' ? preset.label + ' (default)' : preset.label;
      var desc = document.createElement('span');
      desc.className = 'ls-preset__desc';
      desc.textContent = preset.desc;
      btn.appendChild(label);
      btn.appendChild(desc);
      btn.addEventListener('click', function () { applyPreset(preset); });
      container.appendChild(btn);
    });
  }

  renderPresets();
  renderPreview();
})(window, document);
