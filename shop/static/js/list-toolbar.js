(function () {
  'use strict';

  function initForm(form) {
    var toggle = form.querySelector('[data-bulk-toggle]');
    var items = Array.prototype.slice.call(form.querySelectorAll('[data-bulk-item]'));
    var submit = form.querySelector('[data-bulk-submit]');
    if (!items.length) {
      return;
    }

    function refresh() {
      var checked = items.filter(function (item) { return item.checked; }).length;
      if (submit) {
        submit.disabled = checked === 0;
      }
      if (toggle) {
        toggle.checked = checked === items.length;
        toggle.indeterminate = checked > 0 && checked < items.length;
      }
    }

    if (toggle) {
      toggle.addEventListener('change', function () {
        items.forEach(function (item) { item.checked = toggle.checked; });
        refresh();
      });
    }

    items.forEach(function (item) {
      item.addEventListener('change', refresh);
    });

    refresh();
  }

  function init() {
    Array.prototype.slice
      .call(document.querySelectorAll('[data-bulk-form]'))
      .forEach(initForm);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
