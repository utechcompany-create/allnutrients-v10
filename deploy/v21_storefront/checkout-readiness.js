(function () {
  'use strict';
  let ready = false, busy = false, config = null;
  function available(method) {
    if (!ready || !config) return false;
    if (method === 'CASH') return ['name', 'account', 'holder'].every(key => String(config.bank?.[key] || '').trim());
    return Boolean(config.tossEnabled && typeof window.TossPayments === 'function');
  }
  function error(message) {
    const el = document.getElementById('checkoutError');
    el.textContent = message || '';
    el.hidden = !message;
  }
  function configure(value) {
    config = value; ready = true;
    const buttons = [...document.querySelectorAll('.pay-option')];
    buttons.forEach(button => {
      button.disabled = !available(button.dataset.method);
      if (button.disabled) button.querySelector('.muted').textContent = '현재 이용할 수 없습니다';
    });
    const selected = buttons.find(button => button.classList.contains('active') && !button.disabled) || buttons.find(button => !button.disabled);
    buttons.forEach(button => button.classList.remove('active'));
    if (selected) selected.click();
    const hint = document.getElementById('pgHint');
    hint.textContent = !selected ? '현재 결제 서비스를 준비 중입니다. 이용 문의는 고객게시판을 이용해 주세요.' :
      available('CARD') ? '선택한 결제수단으로 결제를 진행합니다.' : '현재 무통장 입금 주문만 가능합니다. 아래 입금계좌를 확인해 주세요.';
    document.getElementById('payBtn').disabled = !selected;
    document.getElementById('payBtn').textContent = selected ? '주문하고 결제하기' : '결제 준비 중';
  }
  function start(method) {
    if (busy) return false;
    if (!available(method)) {error('선택한 결제수단을 현재 이용할 수 없습니다. 결제수단 안내를 확인해 주세요.'); return false;}
    busy = true; error('');
    const button = document.getElementById('payBtn');
    button.disabled = true; button.textContent = '주문 처리 중…'; button.setAttribute('aria-busy', 'true');
    document.querySelectorAll('.pay-option').forEach(item => {item.disabled = true;});
    return true;
  }
  function finish() {
    busy = false;
    document.getElementById('payBtn').removeAttribute('aria-busy');
    if (config) configure(config);
  }
  window.CheckoutReadiness = {configure, start, finish, error};
})();
