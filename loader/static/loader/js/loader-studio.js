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
    var ctrl = window.ShopSeedLoader.preview(cfg, mount);
    if (ctrl && ctrl.play) ctrl.play();
  }

  function bindChange(el, fn) {
    if (el) el.addEventListener('change', fn);
  }

  bindChange(initialType, renderPreview);
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

  renderPreview();
})(window, document);
