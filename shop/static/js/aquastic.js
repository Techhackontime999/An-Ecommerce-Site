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
      const revealElements = document.querySelectorAll('.fade-up');
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
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => AQUASTIC.init());
  } else {
    AQUASTIC.init();
  }

  window.AQUASTIC = AQUASTIC;
})();
