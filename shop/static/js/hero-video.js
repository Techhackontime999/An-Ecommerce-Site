/* ═══════════════════════════════════════════════════════════════════════
   Shop-Seed — Theme-Aware Video Hero
   -----------------------------------------------------------------------
   Autoplays the light/dark theme-matched hero video (muted, looping),
   swaps the video the moment the visitor toggles the theme, fades the
   overlay content as the hero scrolls out, and powers the hero autocomplete
   search. Vanilla JS, no deps.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var SUGGEST_DEBOUNCE_MS = 300;
  var SUGGEST_MIN_CHARS = 2;

  var prefersReducedMotion = function () {
    return window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  };

  var clamp = function (v, lo, hi) { return Math.max(lo, Math.min(hi, v)); };

  /* ── Helpers ─────────────────────────────────────────────────────── */
  function currentTheme() {
    var theme = document.documentElement.getAttribute('data-theme') || 'light';
    return theme === 'dark' ? 'dark' : 'light';
  }

  function buildVideoSource(video) {
    var theme = currentTheme();
    var light = video.getAttribute('data-light') || '';
    var dark = video.getAttribute('data-dark') || '';
    return theme === 'dark' ? (dark || light) : (light || dark) || '';
  }

  /* ══ Hero video ════════════════════════════════════════════════════ */
  function HeroVideo(section) {
    var self = this;
    self.section = section;
    self.video = section.querySelector('video[data-hero-video-element]');
    self.content = section.querySelector('.hero-video-aq-content');
    self.progressFill = section.querySelector('.hero-video-aq-progress span');
    self.scrollhint = section.querySelector('.hero-video-aq-scrollhint');

    if (!self.video) return;

    self.reduced = prefersReducedMotion();
    self.ticking = false;

    self.video.muted = true;
    self.video.setAttribute('muted', '');
    self.video.loop = true;
    if (self.video.getAttribute('data-poster')) {
      self.video.poster = self.video.getAttribute('data-poster');
    }

    self.video.addEventListener('loadedmetadata', function () {
      if (self.reduced) {
        // Frozen frame for reduced-motion visitors — no autoplay.
        self.video.currentTime = 0.05;
        self.frozen = true;
        return;
      }
      self.playVideo();
    });

    self.video.addEventListener('error', function () {
      // Video missing / unreadable — the gradient bg behind it stays visible.
      self.video.classList.add('is-error');
    });

    self.selectVideo();
    if (!self.reduced) {
      self.playVideo();
    }

    window.addEventListener('scroll', self.requestUpdate.bind(self), { passive: true });
    window.addEventListener('resize', self.requestUpdate.bind(self), { passive: true });

    // Keep the light/dark video in sync with the navbar theme toggle.
    self.themeObserver = new MutationObserver(function () {
      self.selectVideo();
    });
    self.themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
  }

  HeroVideo.prototype.playVideo = function () {
    if (!this.video || this.reduced || this.frozen) return;
    var p = this.video.play();
    if (p && p.catch) {
      p.catch(function () {
        /* Autoplay declined — a static frame/poster stays up. */
      });
    }
  };

  HeroVideo.prototype.selectVideo = function () {
    if (!this.video) return;
    var src = buildVideoSource(this.video);
    if (src === (this.video.getAttribute('src') || '')) return;
    if (!src) {
      this.video.removeAttribute('src');
      this.video.load();
      return;
    }
    this.video.setAttribute('src', src);
    this.video.load();
  };

  HeroVideo.prototype.requestUpdate = function () {
    if (this.ticking) return;
    this.ticking = true;
    var self = this;
    window.requestAnimationFrame(function () { self.update(); });
  };

  HeroVideo.prototype.update = function () {
    this.ticking = false;
    var rect = this.section.getBoundingClientRect();
    // 0 = hero fully in view at the top; 1 = hero scrolled fully past.
    var progress = clamp(-rect.top / rect.height, 0, 1);

    if (this.progressFill) {
      this.progressFill.style.transform = 'scaleX(' + progress.toFixed(4) + ')';
    }

    if (this.scrollhint) {
      var hintFade = clamp(1 - progress * 8, 0, 1);
      this.scrollhint.style.opacity = hintFade.toFixed(3);
      this.scrollhint.style.visibility = hintFade > 0 ? 'visible' : 'hidden';
    }

    this.updateContent(progress);
  };

  HeroVideo.prototype.updateContent = function (progress) {
    if (!this.content) return;
    var start = 0.45;
    var end = 0.95;
    var p = clamp((progress - start) / (end - start), 0, 1);
    var opacity = 1 - p * 0.6;
    var translate = -p * 42;
    this.content.style.opacity = opacity.toFixed(3);
    this.content.style.transform = 'translateY(' + translate.toFixed(1) + 'px)';
  };

  /* ══ Search autocomplete ═══════════════════════════════════════════ */
  function HeroSearch(container) {
    if (!container) return;
    var self = this;
    self.container = container;
    self.form = container.querySelector('form');
    self.input = container.querySelector('input[data-hero-search]');
    self.dropdown = container.querySelector('[data-hero-suggestions]');
    self.url = self.input.getAttribute('data-suggest-url');
    if (!self.input || !self.dropdown) return;

    // Render the panel fixed at viewport level so the hero's overflow and
    // entrance transforms can never clip it or let hero content cover it.
    document.body.appendChild(self.dropdown);
    self.dropdown.style.position = 'fixed';
    self.dropdown.style.zIndex = '1000';

    self.items = [];        // rendered anchor elements in display order
    self.activeIndex = -1;
    self.timer = null;

    self.input.addEventListener('input', self.onInput.bind(self));
    self.input.addEventListener('keydown', self.onKeydown.bind(self));
    self.input.addEventListener('focus', self.onFocus.bind(self));
    window.addEventListener('scroll', self.positionDropdown.bind(self), { passive: true });
    window.addEventListener('resize', self.positionDropdown.bind(self), { passive: true });
    document.addEventListener('click', function (e) {
      if (!container.contains(e.target) && !self.dropdown.contains(e.target)) self.close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') self.close();
    });
  }

  HeroSearch.prototype.positionDropdown = function () {
    if (this.dropdown.hidden) return;
    var rect = this.input.getBoundingClientRect();
    var top = Math.round(rect.bottom + 8);
    var maxH = Math.max(140, Math.round(window.innerHeight - top - 16));
    this.dropdown.style.top = top + 'px';
    this.dropdown.style.left = Math.round(rect.left) + 'px';
    this.dropdown.style.width = Math.round(rect.width) + 'px';
    this.dropdown.style.maxHeight = maxH + 'px';
  };

  HeroSearch.prototype.bestUrl = function () {
    var q = this.input.value.trim();
    return this.url.replace('__query__', encodeURIComponent(q));
  };

  HeroSearch.prototype.onInput = function () {
    var self = this;
    var q = this.input.value.trim();
    if (q.length < SUGGEST_MIN_CHARS) {
      this.close();
      return;
    }
    clearTimeout(this.timer);
    this.showLoading();
    this.timer = setTimeout(function () { self.fetchSuggestions(); }, SUGGEST_DEBOUNCE_MS);
  };

  HeroSearch.prototype.onFocus = function () {
    if (this.input.value.trim().length >= SUGGEST_MIN_CHARS && this.items.length) {
      this.open();
    }
  };

  HeroSearch.prototype.fetchSuggestions = function () {
    var self = this;
    var q = this.input.value.trim();
    if (q.length < SUGGEST_MIN_CHARS) return;
    fetch(this.bestUrl(), { headers: { 'Accept': 'application/json' } })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error(res.status)); })
      .then(function (data) { self.render(data, q); })
      .catch(function () { self.showError(); });
  };

  HeroSearch.prototype.showLoading = function () {
    this.dropdown.innerHTML = '<div class="hero-video-aq-sug-loading">Searching…</div>';
    this.open();
  };

  HeroSearch.prototype.showError = function () {
    this.dropdown.innerHTML = '<div class="hero-video-aq-sug-empty">Could not search right now — try again.</div>';
    this.open();
  };

  HeroSearch.prototype.render = function (data, q) {
    var self = this;
    var html = '';
    this.items = [];

    var products = data.products || [];
    var categories = data.categories || [];
    var brands = data.brands || [];
    var idx = 0;

    if (products.length) {
      html += '<div class="hero-video-aq-sug-group"><div class="hero-video-aq-sug-title">Products</div>';
      html += products.map(function (p) {
        return self.itemAnchor(p.url, self.itemMedia(p.image || ''), self.itemName(p.name), self.priceLabel(p.price), idx++);
      }).join('');
      html += '</div>';
    }

    if (categories.length) {
      html += '<div class="hero-video-aq-sug-group"><div class="hero-video-aq-sug-title">Categories</div>';
      html += categories.map(function (c) {
        return self.itemAnchor(c.url, self.itemIcon('fa-layer-group'), self.itemName(c.name), '', idx++);
      }).join('');
      html += '</div>';
    }

    if (brands.length) {
      html += '<div class="hero-video-aq-sug-group"><div class="hero-video-aq-sug-title">Brands</div>';
      html += brands.map(function (b) {
        return self.itemAnchor(b.url, self.itemIcon('fa-tags'), self.itemName(b.name), '', idx++);
      }).join('');
      html += '</div>';
    }

    if (!html) {
      html = '<div class="hero-video-aq-sug-empty">No results for “' +
        escapeHtml(q) + '”. <a href="' + self.searchPageFor(q) + '" style="color:var(--aq-accent)">View all results</a></div>';
    } else {
      html += '<a class="hero-video-aq-sug-item" href="' + self.searchPageFor(q) +
        '" data-hero-sug data-all id="hero-video-sug-item-' + idx +
        '" role="option"><span class="hero-video-aq-sug-meta"><span class="name">See all results for “' +
        escapeHtml(q) + '”</span><i class="fas fa-arrow-right" style="color:var(--aq-accent)"></i></span></a>';
    }

    this.dropdown.innerHTML = html;
    this.dropdown.querySelectorAll('a[data-hero-sug]').forEach(function (el) {
      self.items.push(el);
    });
    this.activeIndex = -1;
    this.open();
  };

  HeroSearch.prototype.itemMedia = function (image) {
    if (!image) return this.itemIcon('fa-box-open');
    return '<img class="hero-video-aq-sug-thumb" src="' + escapeAttr(image) + '" alt="" loading="lazy">';
  };

  HeroSearch.prototype.itemIcon = function (icon) {
    return '<span class="hero-video-aq-sug-thumb" style="display:inline-flex;align-items:center;justify-content:center;color:var(--aq-accent)"><i class="fas ' + icon + '"></i></span>';
  };

  HeroSearch.prototype.itemName = function (name) {
    return '<span class="name" data-hero-sug-name>' + escapeHtml(name) + '</span>';
  };

  HeroSearch.prototype.priceLabel = function (price) {
    if (!price) return '';
    return '<span class="price">' + escapeHtml(String(price)) + '</span>';
  };

  HeroSearch.prototype.itemAnchor = function (href, media, nameMeta, price, index) {
    return '<a class="hero-video-aq-sug-item" href="' + escapeAttr(href) +
      '" data-hero-sug id="hero-video-sug-item-' + index + '" role="option">' +
      media +
      '<span class="hero-video-aq-sug-meta">' + nameMeta + price + '</span>' +
      '</a>';
  };

  HeroSearch.prototype.searchPageFor = function (q) {
    var form = this.form;
    if (!form) return '?q=' + encodeURIComponent(q);
    return form.getAttribute('action') + '?q=' + encodeURIComponent(q);
  };

  HeroSearch.prototype.open = function () {
    this.dropdown.hidden = false;
    this.positionDropdown();
    this.input.setAttribute('aria-expanded', 'true');
  };

  HeroSearch.prototype.close = function () {
    this.dropdown.hidden = true;
    this.input.setAttribute('aria-expanded', 'false');
    this.activeIndex = -1;
    this.input.removeAttribute('aria-activedescendant');
  };

  HeroSearch.prototype.setActiveIndex = function (index) {
    var self = this;
    var clampedIndex = clamp(index, -1, this.items.length - 1);
    if (clampedIndex === this.activeIndex) return;
    if (this.activeIndex >= 0 && this.items[this.activeIndex]) {
      this.items[this.activeIndex].removeAttribute('aria-selected');
    }
    this.activeIndex = clampedIndex;
    if (clampedIndex >= 0) {
      var active = this.items[clampedIndex];
      active.setAttribute('aria-selected', 'true');
      this.input.setAttribute('aria-activedescendant', active.id || '');
      if (active.scrollIntoView) {
        active.scrollIntoView({ block: 'nearest' });
      }
    } else {
      this.input.removeAttribute('aria-activedescendant');
    }
  };

  HeroSearch.prototype.move = function (delta) {
    this.setActiveIndex(this.activeIndex + delta);
  };

  HeroSearch.prototype.onKeydown = function (e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (this.items.length) this.move(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (this.items.length) this.move(-1);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      this.close();
      this.input.blur();
    } else if (e.key === 'Enter') {
      var active = this.items[this.activeIndex];
      if (active) {
        e.preventDefault();
        window.location.href = active.getAttribute('href');
      }
      // No active item → the form handles the full-page search.
    }
    e.stopPropagation();
  };

  /* ══ Init ═══════════════════════════════════════════════════════════ */
  function init() {
    var hero = document.querySelector('[data-hero-video]');
    if (hero) new HeroVideo(hero);

    var search = document.querySelector('[data-hero-search-container]');
    if (search) new HeroSearch(search);
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function escapeAttr(str) {
    return escapeHtml(str);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();