/* ═══════════════════════════════════════════════════════════════════════
   Shop-Seed — Advanced Search Autocomplete
   -----------------------------------------------------------------------
   Powers the navbar search boxes (desktop + mobile). Fetches the
   /api/search/suggest/ JSON endpoint as the user types, then renders an
   autocomplete dropdown with product thumbnails, name + price, category
   and brand suggestions. Debounced, keyboard-navigable, ARIA combobox.
   Vanilla JS, no deps.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var SUGGEST_DEBOUNCE_MS = 300;
  var SUGGEST_MIN_CHARS = 2;

  var clamp = function (v, lo, hi) { return Math.max(lo, Math.min(hi, v)); };

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function escapeAttr(str) { return escapeHtml(str); }

  /* ── Autocomplete widget ──────────────────────────────────────────── */
  function SearchAutocomplete(wrapper) {
    if (!wrapper) return;
    var self = this;
    self.wrapper = wrapper;
    self.form = wrapper.querySelector('form');
    self.input = wrapper.querySelector('input[data-search-suggest-url]');
    self.dropdown = wrapper.querySelector('[data-search-suggestions]');
    if (!self.input || !self.dropdown) return;

    self.minChars = parseInt(self.input.getAttribute('data-min-chars') || '', 10) || SUGGEST_MIN_CHARS;
    self.items = [];
    self.activeIndex = -1;
    self.timer = null;

    self.input.addEventListener('input', self.onInput.bind(self));
    self.input.addEventListener('keydown', self.onKeydown.bind(self));
    self.input.addEventListener('focus', self.onFocus.bind(self));
    window.addEventListener('resize', self.refreshPosition.bind(self), { passive: true });
    document.addEventListener('click', self.onDocClick.bind(self));
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') self.close();
    });
  }

  SearchAutocomplete.prototype.suggestUrl = function () {
    var q = this.input.value.trim();
    return this.input.getAttribute('data-search-suggest-url').replace('__query__', encodeURIComponent(q));
  };

  SearchAutocomplete.prototype.onDocClick = function (e) {
    if (!this.wrapper.contains(e.target) && !this.dropdown.contains(e.target)) {
      this.close();
    }
  };

  SearchAutocomplete.prototype.onInput = function () {
    var self = this;
    var q = this.input.value.trim();
    if (q.length < this.minChars) {
      this.close();
      return;
    }
    clearTimeout(this.timer);
    this.showLoading();
    this.timer = setTimeout(function () { self.fetchSuggestions(); }, SUGGEST_DEBOUNCE_MS);
  };

  SearchAutocomplete.prototype.onFocus = function () {
    if (this.input.value.trim().length >= this.minChars && this.items.length) {
      this.open();
    }
  };

  SearchAutocomplete.prototype.fetchSuggestions = function () {
    var self = this;
    var q = this.input.value.trim();
    if (q.length < this.minChars) return;
    fetch(this.suggestUrl(), { headers: { 'Accept': 'application/json' } })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error(res.status)); })
      .then(function (data) { self.render(data, q); })
      .catch(function () { self.showError(); });
  };

  SearchAutocomplete.prototype.showLoading = function () {
    this.dropdown.innerHTML = '<div class="aq-search-sug-loading">Searching…</div>';
    this.open();
  };

  SearchAutocomplete.prototype.showError = function () {
    this.dropdown.innerHTML =
      '<div class="aq-search-sug-empty">Could not search right now — try again.</div>';
    this.open();
  };

  SearchAutocomplete.prototype.render = function (data, q) {
    var self = this;
    var html = '';
    this.items = [];

    var products = data.products || [];
    var categories = data.categories || [];
    var brands = data.brands || [];
    var idx = 0;

    if (products.length) {
      html += '<div class="aq-search-sug-group"><div class="aq-search-sug-title">Products</div>';
      html += products.map(function (p) {
        return self.itemAnchor(p.url, self.itemMedia(p.image || ''), self.itemName(p.name), self.priceLabel(p.price), idx++);
      }).join('');
      html += '</div>';
    }

    if (categories.length) {
      html += '<div class="aq-search-sug-group"><div class="aq-search-sug-title">Categories</div>';
      html += categories.map(function (c) {
        return self.itemAnchor(c.url, self.itemIcon('fa-layer-group'), self.itemName(c.name), '', idx++);
      }).join('');
      html += '</div>';
    }

    if (brands.length) {
      html += '<div class="aq-search-sug-group"><div class="aq-search-sug-title">Brands</div>';
      html += brands.map(function (b) {
        return self.itemAnchor(b.url, self.itemIcon('fa-tags'), self.itemName(b.name), '', idx++);
      }).join('');
      html += '</div>';
    }

    if (!html) {
      html = '<div class="aq-search-sug-empty">No results for “' + escapeHtml(q) + '”. ' +
        '<a href="' + self.searchPageFor(q) + '" class="aq-search-sug-all">View all results</a></div>';
    } else {
      html += '<a class="aq-search-sug-item" href="' + self.searchPageFor(q) +
        '" data-search-sug data-all id="aq-search-sug-item-' + idx + '" role="option">' +
        '<span class="aq-search-sug-meta"><span class="name">See all results for “' + escapeHtml(q) +
        '”</span><i class="fas fa-arrow-right aq-search-sug-arrow" aria-hidden="true"></i></span></a>';
    }

    this.dropdown.innerHTML = html;
    this.dropdown.querySelectorAll('a[data-search-sug]').forEach(function (el) {
      self.items.push(el);
    });
    this.activeIndex = -1;
    this.open();
  };

  SearchAutocomplete.prototype.itemMedia = function (image) {
    if (!image) return this.itemIcon('fa-box-open');
    return '<img class="aq-search-sug-thumb" src="' + escapeAttr(image) + '" alt="" loading="lazy">';
  };

  SearchAutocomplete.prototype.itemIcon = function (icon) {
    return '<span class="aq-search-sug-thumb aq-search-sug-thumb-icon" aria-hidden="true"><i class="fas ' + icon + '"></i></span>';
  };

  SearchAutocomplete.prototype.itemName = function (name) {
    return '<span class="name">' + escapeHtml(name) + '</span>';
  };

  SearchAutocomplete.prototype.priceLabel = function (price) {
    if (!price) return '';
    return '<span class="price">' + escapeHtml(String(price)) + '</span>';
  };

  SearchAutocomplete.prototype.itemAnchor = function (href, media, nameMeta, price, index) {
    return '<a class="aq-search-sug-item" href="' + escapeAttr(href) +
      '" data-search-sug id="aq-search-sug-item-' + index + '" role="option">' +
      media +
      '<span class="aq-search-sug-meta">' + nameMeta + price + '</span>' +
      '</a>';
  };

  SearchAutocomplete.prototype.searchPageFor = function (q) {
    var form = this.form;
    if (!form) return '?q=' + encodeURIComponent(q);
    return form.getAttribute('action') + '?q=' + encodeURIComponent(q);
  };

  SearchAutocomplete.prototype.refreshPosition = function () {
    if (this.dropdown.hidden) return;
    var rect = this.input.getBoundingClientRect();
    this.dropdown.style.maxHeight =
      Math.max(140, Math.round(window.innerHeight - rect.bottom - 16)) + 'px';
  };

  SearchAutocomplete.prototype.open = function () {
    this.dropdown.classList.add('is-open');
    this.dropdown.hidden = false;
    this.input.setAttribute('aria-expanded', 'true');
    this.refreshPosition();
  };

  SearchAutocomplete.prototype.close = function () {
    if (!this.dropdown.hidden) {
      this.dropdown.hidden = true;
      this.dropdown.classList.remove('is-open');
    }
    this.input.setAttribute('aria-expanded', 'false');
    this.activeIndex = -1;
    this.input.removeAttribute('aria-activedescendant');
  };

  SearchAutocomplete.prototype.setActiveIndex = function (index) {
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

  SearchAutocomplete.prototype.move = function (delta) {
    this.setActiveIndex(this.activeIndex + delta);
  };

  SearchAutocomplete.prototype.onKeydown = function (e) {
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
      // No active item → the form submits and the full results page loads.
    }
    e.stopPropagation();
  };

  /* ── Init ─────────────────────────────────────────────────────────── */
  function init() {
    document.querySelectorAll('[data-search-autocomplete]').forEach(function (wrapper) {
      new SearchAutocomplete(wrapper);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();