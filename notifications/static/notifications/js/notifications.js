(function () {
  'use strict';

  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  var CSRF = getCookie('csrftoken');

  function post(url, done) {
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': CSRF,
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        if (done) done(data);
      })
      .catch(function () {
        if (done) done({ ok: false });
      });
  }

  function updateBadge(unread) {
    document.querySelectorAll('.nav-aq-notif-btn').forEach(function (btn) {
      var badge = btn.querySelector('[data-badge]');
      if (!badge) return;
      if (unread > 0) {
        badge.textContent = unread;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    });
  }

  function removeItem(item) {
    var list = item.closest('.aq-notif-list');
    item.remove();
    if (list && !list.querySelector('.aq-notif-item')) {
      list.innerHTML =
        '<div class="aq-notif-empty"><i class="fas fa-bell-slash"></i><p>No notifications here yet.</p></div>';
    }
  }

  function bindDropdown() {
    var notif = document.getElementById('aq-notif-dropdown');
    if (!notif) return;

    var btn = notif.querySelector('.nav-aq-notif-btn');

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = notif.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    document.addEventListener('click', function (e) {
      if (!notif.classList.contains('open')) return;
      if (!notif.contains(e.target)) {
        notif.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && notif.classList.contains('open')) {
        notif.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  function bindMarkAll() {
    document.querySelectorAll('.aq-mark-all').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        var url = el.getAttribute('data-url');
        if (!url) return;
        post(url, function (data) {
          if (data.ok) {
            updateBadge(0);
            document.querySelectorAll('.aq-notif-unread').forEach(function (item) {
              item.classList.remove('aq-notif-unread');
            });
          }
        });
      });
    });
  }

  function bindClearRead() {
    document.querySelectorAll('.aq-clear-read').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        var url = el.getAttribute('data-url');
        if (!url) return;
        post(url, function (data) {
          if (data.ok) {
            document.querySelectorAll('.aq-notif-item:not(.aq-notif-unread)').forEach(removeItem);
          }
        });
      });
    });
  }

  function bindItems() {
    document.querySelectorAll('.aq-notif-item').forEach(function (item) {
      var readUrl = item.getAttribute('data-read-url');
      var link = item.getAttribute('data-link');

      item.addEventListener('click', function (e) {
        if (e.target.closest('.aq-notif-dismiss')) return;
        var markRead = item.classList.contains('aq-notif-unread') && readUrl;
        if (markRead) {
          item.classList.remove('aq-notif-unread');
          post(readUrl, function (data) {
            if (data.ok) updateBadge(data.unread);
          });
        }
        if (link) {
          window.location.href = link;
        }
      });

      var dismiss = item.querySelector('.aq-notif-dismiss');
      if (dismiss) {
        dismiss.addEventListener('click', function (e) {
          e.stopPropagation();
          e.preventDefault();
          var url = dismiss.getAttribute('data-delete-url');
          if (!url) return;
          post(url, function (data) {
            if (data.ok) {
              updateBadge(data.unread);
              removeItem(item);
            }
          });
        });
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindDropdown();
    bindMarkAll();
    bindClearRead();
    bindItems();
  });
})();
