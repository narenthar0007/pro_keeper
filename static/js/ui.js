(function () {
  function findPopup(id) {
    return document.getElementById(id);
  }

  function openPopup(id) {
    var el = findPopup(id);
    if (!el) return;
    if (typeof el.showModal === 'function') {
      if (!el.open) el.showModal();
    } else {
      el.setAttribute('open', '');
    }
  }

  function closePopup(el) {
    if (!el) return;
    if (typeof el.close === 'function') {
      el.close();
    } else {
      el.removeAttribute('open');
    }
  }

  document.addEventListener('click', function (event) {
    var openBtn = event.target.closest('[data-ui-open]');
    if (openBtn) {
      event.preventDefault();
      openPopup(openBtn.getAttribute('data-ui-open'));
      return;
    }

    var closeBtn = event.target.closest('[data-ui-close]');
    if (closeBtn) {
      event.preventDefault();
      closePopup(closeBtn.closest('dialog[data-ui-popup]'));
      return;
    }

    if (event.target.matches('dialog[data-ui-popup]')) {
      closePopup(event.target);
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('dialog[data-ui-popup][open]').forEach(closePopup);
  });
})();
