(function () {
  'use strict';
  const forms = ['loginForm', 'registerForm'].map(id => document.getElementById(id));
  let submitting = false;
  // A return destination must stay within this storefront, including query/hash.
  function safeNext(value) {
    try {
      const url = new URL(value || 'mypage.html', location.href);
      if (url.origin === location.origin && ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) {
        return url.pathname + url.search + url.hash;
      }
    } catch (_) {}
    return 'mypage.html';
  }
  const next = safeNext(new URLSearchParams(location.search).get('next'));
  forms.forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      if (submitting || !form.reportValidity()) return;
      const error = form.querySelector('[role="alert"]');
      error.hidden = true;
      error.textContent = '';
      const f = new FormData(form), register = form.id === 'registerForm';
      const body = {email: String(f.get('email') || '').trim(), password: f.get('password')};
      if (register) Object.assign(body, {name: String(f.get('name') || '').trim(), phone: String(f.get('phone') || '').trim()});
      submitting = true;
      forms.forEach(item => {item.querySelector('button[type="submit"]').disabled = true;});
      form.setAttribute('aria-busy', 'true');
      try {
        await AppAPI.api('/api/auth/' + (register ? 'register' : 'login'), {method: 'POST', body});
        location.href = next;
      } catch (err) {
        error.textContent = err.message || '잠시 후 다시 시도해 주세요.';
        error.hidden = false;
        error.focus();
        submitting = false;
        forms.forEach(item => {item.querySelector('button[type="submit"]').disabled = false;});
        form.removeAttribute('aria-busy');
      }
    };
  });
  document.querySelectorAll('[data-auth-jump]').forEach(link => {
    link.addEventListener('click', () => {
      const field = document.querySelector(link.getAttribute('href') + ' input');
      if (field) requestAnimationFrame(() => field.focus({preventScroll: true}));
    });
  });
})();
