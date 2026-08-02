(function () {
  'use strict';

  var menu = document.getElementById('mobile-drawer');
  var hamburger = document.querySelector('.nav-aq-hamburger');
  var closeEls = document.querySelectorAll('[data-drawer-close]');
  var lastFocus = null;

  if (menu) {
    var syncDrawer = function (isOpen) {
      if (isOpen) {
        lastFocus = document.activeElement;
        if (closeEls.length) closeEls[0].classList.add('is-visible');
        document.body.style.overflow = 'hidden';
        if (hamburger) hamburger.setAttribute('aria-expanded', 'true');
        var closeBtn = document.querySelector('.ds-drawer-close');
        if (closeBtn && !closeBtn.contains(document.activeElement)) {
          closeBtn.focus();
        }
      } else {
        if (closeEls.length) closeEls[0].classList.remove('is-visible');
        document.body.style.overflow = '';
        if (hamburger) {
          hamburger.classList.remove('active');
          hamburger.setAttribute('aria-expanded', 'false');
        }
        if (lastFocus && lastFocus.focus) lastFocus.focus();
        lastFocus = null;
      }
    };

    var closeDrawer = function () {
      menu.classList.remove('open');
      syncDrawer(false);
    };

    if ('MutationObserver' in window) {
      var observer = new MutationObserver(function () {
        syncDrawer(menu.classList.contains('open'));
      });
      observer.observe(menu, { attributes: true, attributeFilter: ['class'] });
    }

    if (hamburger) {
      hamburger.addEventListener('click', function () {
        setTimeout(function () {
          syncDrawer(menu.classList.contains('open'));
        }, 0);
      });
    }

    closeEls.forEach(function (el) {
      el.addEventListener('click', closeDrawer);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('open')) {
        closeDrawer();
      }
    });
  }

  var mqDesktop = window.matchMedia('(min-width: 768px)');

  document.querySelectorAll('[data-acc-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (mqDesktop.matches) return;
      var col = btn.closest('[data-acc-col]');
      if (!col) return;
      var isOpen = col.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  });

  if (mqDesktop.addEventListener) {
    mqDesktop.addEventListener('change', function () {
      if (!mqDesktop.matches) return;
      document.querySelectorAll('[data-acc-col]').forEach(function (col) {
        col.classList.remove('is-open');
        var btn = col.querySelector('[data-acc-toggle]');
        if (btn) btn.setAttribute('aria-expanded', 'false');
      });
    });
  }
})();
