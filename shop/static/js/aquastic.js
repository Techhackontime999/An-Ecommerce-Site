(function() {
  'use strict';

  const AQUASTIC = {
    init: function() {
      this.navbar();
      this.mobileMenu();
      this.scrollReveal();
      this.magneticButtons();
      this.cartBadgePulse();
      this.searchExpand();
      this.staggerAnimations();
      this.productViewToggle();
      this.scrollProgress();
      this.heroParallax();
      this.parallaxShowcase();
      this.themeManager();
    },

    navbar: function() {
      const nav = document.querySelector('.nav-aq');
      if (!nav) return;

      const handleScroll = () => {
        requestAnimationFrame(() => {
          if (window.scrollY > 50) {
            nav.classList.add('scrolled');
          } else {
            nav.classList.remove('scrolled');
          }
        });
      };

      window.addEventListener('scroll', handleScroll, { passive: true });
      handleScroll();
    },

    mobileMenu: function() {
      const hamburger = document.querySelector('.nav-aq-hamburger');
      const menu = document.querySelector('.mobile-menu-aq');
      if (!hamburger || !menu) return;

      hamburger.addEventListener('click', () => {
        const isOpen = menu.classList.toggle('open');
        hamburger.classList.toggle('active');
        document.body.style.overflow = isOpen ? 'hidden' : '';
      });

      menu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
          menu.classList.remove('open');
          hamburger.classList.remove('active');
          document.body.style.overflow = '';
        });
      });
    },

    scrollReveal: function() {
      const revealElements = document.querySelectorAll('.fade-up, .fade-left, .fade-right, .fade-scale');
      if (!revealElements.length) return;

      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
      });

      revealElements.forEach(el => observer.observe(el));
    },

    scrollProgress: function() {
      const bar = document.getElementById('aq-scroll-progress');
      if (!bar) return;

      const hero = document.getElementById('hero-aq');
      const content = hero ? hero.querySelector('.hero-aq-content') : null;
      const prefersReduced = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      let ticking = false;

      const update = () => {
        const doc = document.documentElement;
        const max = doc.scrollHeight - window.innerHeight;
        const pct = max > 0 ? (window.scrollY / max) : 0;
        bar.style.width = (pct * 100) + '%';

        if (content && !prefersReduced) {
          const heroH = hero.offsetHeight || window.innerHeight;
          const progress = Math.min(1, window.scrollY / (heroH * 0.9));
          content.style.opacity = String(1 - progress * 0.65);
          content.style.transform =
            `translateY(${(-progress * 50).toFixed(1)}px) scale(${(1 - progress * 0.04).toFixed(4)})`;
        }

        ticking = false;
      };

      const requestUpdate = () => {
        if (!ticking) {
          ticking = true;
          requestAnimationFrame(update);
        }
      };

      window.addEventListener('scroll', requestUpdate, { passive: true });
      window.addEventListener('resize', requestUpdate, { passive: true });
      requestUpdate();
    },

    magneticButtons: function() {
      const buttons = document.querySelectorAll('.btn-aq-primary, .btn-aq-ghost');

      buttons.forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
          const rect = btn.getBoundingClientRect();
          const x = e.clientX - rect.left - rect.width / 2;
          const y = e.clientY - rect.top - rect.height / 2;
          btn.style.transform = `translate(${x * 0.15}px, ${y * 0.15}px)`;
        });

        btn.addEventListener('mouseleave', () => {
          btn.style.transform = '';
        });
      });
    },

    cartBadgePulse: function() {
      const badge = document.querySelector('.cart-count');
      if (!badge) return;

      setInterval(() => {
        badge.style.animation = 'none';
        badge.offsetHeight;
        badge.style.animation = 'pulse-glow 2s ease-in-out infinite';
      }, 3000);
    },

    searchExpand: function() {
      const searchInput = document.querySelector('.nav-aq-search input');
      if (!searchInput) return;

      searchInput.addEventListener('focus', () => {
        searchInput.closest('.nav-aq-search').classList.add('expanded');
      });

      searchInput.addEventListener('blur', () => {
        if (!searchInput.value) {
          searchInput.closest('.nav-aq-search').classList.remove('expanded');
        }
      });
    },

    staggerAnimations: function() {
      document.querySelectorAll('[data-stagger]').forEach(parent => {
        const children = parent.children;
        Array.from(children).forEach((child, i) => {
          child.style.setProperty('--index', i);
          child.style.opacity = '0';
          child.style.animation = `fade-up 0.6s ease ${i * 0.1}s forwards`;
        });
      });
    },

    productViewToggle: function() {
      document.querySelectorAll('[data-aq-toggle]').forEach(toggle => {
        const target = toggle.dataset.aqToggle;
        if (!target) return;
        const grid = document.querySelector(target);
        if (!grid) return;

        const buttons = toggle.querySelectorAll('[data-layout]');

        const setActive = (mode) => {
          buttons.forEach(btn => {
            btn.classList.toggle('is-active', btn.dataset.layout === mode);
          });
        };

        const applyMode = (mode) => {
          grid.dataset.layout = mode;
          grid.querySelectorAll(':scope > .product-aq-card').forEach((card, i) => {
            card.style.setProperty('--i', i);
          });
          grid.classList.remove('aq-reveal');
          void grid.offsetWidth;
          grid.classList.add('aq-reveal');
          clearTimeout(grid._aqToggleTimer);
          grid._aqToggleTimer = setTimeout(() => {
            grid.classList.remove('aq-reveal');
          }, 800);
          setActive(mode);
        };

        buttons.forEach(btn => {
          btn.addEventListener('click', () => {
            applyMode(btn.dataset.layout);
          });
        });

        setActive(grid.dataset.layout || '4col');
      });
    },

    heroParallax: function() {
      const container = document.getElementById('hero-parallax-aq');
      if (!container) return;

      const dataEl = document.getElementById('hero-layer-images');
      let urls = [];
      if (dataEl) {
        try { urls = JSON.parse(dataEl.textContent); } catch (err) { urls = []; }
      }
      if (!urls.length) return;

      const prefersReduced = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      const presets = [
        { top: '18%', left: '14%', w: 210 },
        { top: '20%', left: '88%', w: 180 },
        { top: '58%', left: '6%', w: 200 },
        { top: '52%', left: '94%', w: 220 },
        { top: '42%', left: '2%', w: 150 },
        { top: '36%', left: '98%', w: 150 }
      ];

      const items = urls.slice(0, presets.length).map((url, i) => {
        const cfg = presets[i];
        const rot = ((i % 3) - 1) * 8;
        const img = document.createElement('img');
        img.src = url;
        img.alt = '';
        img.loading = 'lazy';
        img.style.zIndex = String(i + 1);
        img.style.top = cfg.top;
        img.style.left = cfg.left;
        img.style.width = cfg.w + 'px';
        img.style.transform = `translate(-50%, -50%) rotate(${rot}deg)`;
        container.appendChild(img);
        return {
          el: img,
          rot: rot,
          speedX: 0.04 + i * 0.02,
          speedY: 0.035 + i * 0.02
        };
      });

      if (prefersReduced) return;

      const title = document.querySelector('.hero-aq .display-hero');

      let ticking = false;

      const update = (e) => {
        const xVal = e.clientX - window.innerWidth / 2;
        const yVal = e.clientY - window.innerHeight / 2;
        const rotateDeg = (xVal / (window.innerWidth / 2)) * 12;

        items.forEach((it) => {
          it.el.style.transform =
            `translate(-50%, -50%) ` +
            `translate3d(${(-xVal * it.speedX).toFixed(2)}px, ${(yVal * it.speedY).toFixed(2)}px, 0) ` +
            `rotateY(${(rotateDeg * 0.06).toFixed(2)}deg) ` +
            `rotate(${it.rot}deg)`;
        });

        if (title) {
          title.style.transform =
            `perspective(1200px) rotateY(${(rotateDeg * 0.03).toFixed(2)}deg) ` +
            `translate3d(${(xVal * 0.07).toFixed(2)}px, ${(yVal * 0.05).toFixed(2)}px, 0)`;
        }

        ticking = false;
      };

      const requestUpdate = (e) => {
        if (!ticking) {
          ticking = true;
          requestAnimationFrame(() => update(e));
        }
      };

      document.addEventListener('mousemove', requestUpdate, { passive: true });
    },

    parallaxShowcase: function() {
      const section = document.getElementById('parallax-aq');
      if (!section) return;
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

      const layers = section.querySelectorAll('[data-parallax-speed]');
      const isTitle = (el) => el.classList.contains('parallax-aq-title');
      const vh = () => window.innerHeight;

      let ticking = false;

      const update = () => {
        const rect = section.getBoundingClientRect();
        const total = vh() + rect.height;
        if (total <= 0) return;
        let progress = 1 - ((rect.top + vh()) / total);
        progress = Math.max(0, Math.min(1, progress));

        layers.forEach((el) => {
          const speed = parseFloat(el.getAttribute('data-parallax-speed')) || 0;
          const y = progress * speed * (rect.height / 100);
          if (isTitle(el)) {
            el.style.transform = `translate(-50%, calc(-50% + ${y}px))`;
          } else {
            el.style.transform = `translate3d(0, ${y}px, 0)`;
          }
        });

        ticking = false;
      };

      const requestUpdate = () => {
        if (!ticking) {
          ticking = true;
          requestAnimationFrame(update);
        }
      };

      window.addEventListener('scroll', requestUpdate, { passive: true });
      window.addEventListener('resize', requestUpdate, { passive: true });
      update();
    },

    themeManager: function() {
      const root = document.documentElement;
      const toggle = document.querySelector('[data-theme-toggle]');
      if (!toggle) return;

      const STORAGE_KEY = 'aq-theme';

      const persist = (theme) => {
        try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) {}
        if (!window.fetch) return;
        const form = new URLSearchParams();
        form.set('theme', theme);
        fetch(toggle.getAttribute('data-url') || '/preferences/toggle-theme/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': toggle.getAttribute('data-csrf') || '',
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          credentials: 'same-origin',
          body: form.toString()
        }).catch(() => {});
      };

      // Apply a brief transition only while switching (avoids flashing on load).
      const enableTransition = () => {
        root.classList.add('aq-theming');
        window.setTimeout(() => root.classList.remove('aq-theming'), 450);
      };

      toggle.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        enableTransition();
        root.setAttribute('data-theme', next);
        persist(next);
      });
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => AQUASTIC.init());
  } else {
    AQUASTIC.init();
  }

  window.AQUASTIC = AQUASTIC;
})();
