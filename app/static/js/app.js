(function () {
  // Toasts: dismiss on click, auto-hide after 6s
  document.querySelectorAll('.toast').forEach(function (toast) {
    toast.querySelector('.toast-close').addEventListener('click', function () { toast.remove(); });
    setTimeout(function () { toast.remove(); }, 6000);
  });

  // Mobile sidebar
  var menu = document.getElementById('menu-toggle');
  var sidebar = document.getElementById('sidebar');
  if (menu && sidebar) {
    menu.addEventListener('click', function () {
      var open = sidebar.classList.toggle('open');
      menu.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // Live table search
  var search = document.getElementById('table-search');
  if (search) {
    search.addEventListener('input', function () {
      var term = search.value.toLowerCase();
      document.querySelectorAll('table[data-searchable] tbody tr').forEach(function (row) {
        row.hidden = term && row.textContent.toLowerCase().indexOf(term) === -1;
      });
    });
  }

  // Confirmation dialogs + loading state on forms
  var dialog = document.getElementById('confirm-dialog');
  document.querySelectorAll('form').forEach(function (form) {
    var message = form.dataset.confirm;
    var loading = form.hasAttribute('data-loading');
    form.addEventListener('submit', function (event) {
      if (form.dataset.confirmed === '1') { start(); return; }
      if (message && dialog && typeof dialog.showModal === 'function') {
        event.preventDefault();
        document.getElementById('confirm-text').textContent = message;
        dialog.returnValue = '';
        dialog.showModal();
        dialog.addEventListener('close', function onClose() {
          dialog.removeEventListener('close', onClose);
          if (dialog.returnValue === 'ok') { form.dataset.confirmed = '1'; form.requestSubmit(); }
        });
      } else { start(); }
    });
    function start() {
      if (!loading) return;
      var button = form.querySelector('button[type="submit"]');
      if (button) { button.disabled = true; button.classList.add('loading'); button.textContent = 'Please wait'; }
    }
  });
})();
