(function () {
  'use strict';
  const {api, esc, money} = AppAPI;
  const statusNames = {REQUESTED:'반품 접수', APPROVED:'반품 승인', COLLECTING:'상품 회수 중', RECEIVED:'반품 입고 완료', REFUNDING:'환불 처리 중', REFUNDED:'반품 완료', COMPLETED:'반품 완료', REJECTED:'반품 거절', CANCELED:'반품 취소'};
  const refundNames = {NOT_REQUESTED:'환불 미진행', PENDING_REVIEW:'검토 중', APPROVED:'환불 승인', MANUAL_PENDING:'입금 대기', COMPLETED:'환불 완료', MANUAL_COMPLETED:'환불 완료'};
  const reasonNames = {CHANGE_MIND:'단순 변심', DAMAGE:'파손·누수', WRONG_ITEM:'오배송', DEFECT:'상품 불량', QUALITY:'유통기한·품질', OTHER:'기타'};
  let records = [];
  let filter = 'all';
  let loading = false;
  const byId = id => document.getElementById(id);
  const completed = r => r.requestType === 'RETURN' && (r.status === 'REFUNDED' || r.status === 'COMPLETED' || ['COMPLETED','MANUAL_COMPLETED'].includes(r.refundStatus));
  const closed = r => completed(r) || ['REJECTED','CANCELED'].includes(r.status);

  function dateText(value) {
    if (!value) return '기록 없음';
    // The database stores UTC; SQLite responses can omit the timezone suffix.
    const date = new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value) ? value : value + 'Z');
    return Number.isNaN(date.getTime()) ? '기록 없음' : date.toLocaleString('ko-KR', {timeZone:'Asia/Seoul', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
  }

  function card(r) {
    const done = completed(r);
    const stopped = ['REJECTED','CANCELED'].includes(r.status);
    const reason = r.reasonName && r.reasonName !== r.reasonCode ? r.reasonName : (reasonNames[r.reasonCode] || r.reasonName || r.reasonCode || '미등록');
    const detail = (label, value) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
    return `<article class="return-card" aria-label="${esc(r.requestNo)} 반품 내역">
      <div class="return-heading"><div><h3>${esc(r.requestNo)}</h3><p class="muted">주문번호 ${esc(r.orderNo)}</p></div><span class="badge ${done?'return-done':stopped?'warn':''}">${esc(done?'반품 완료':statusNames[r.status] || r.status)}</span></div>
      <ul class="return-products">${(r.items || []).map(i => `<li><strong>${esc(i.name)}</strong><span>${esc(i.qty)}개 · ${money(i.lineTotal)}</span></li>`).join('')}</ul>
      <dl class="return-details">
        ${detail('반품 사유', reason)}${detail('신청일', dateText(r.createdAt))}
        ${detail(done?'반품 완료일':'처리 완료일', done || stopped ? dateText(r.completedAt) : '처리 중')}
        ${detail('환불 상태', refundNames[r.refundStatus] || r.refundStatus || '확인 중')}
        ${detail('반품 상품금액', money(r.itemAmount))}${detail('반품배송비 차감액', money(r.returnShippingFee))}
        ${detail(done?'환불 완료 금액':stopped?'환불 금액':'환불 예정 금액', stopped?'해당 없음':money(r.refundAmount))}
        ${r.pickup?.trackingNumber ? detail('회수 운송장', `${r.pickup.carrier || ''} ${r.pickup.trackingNumber}`) : ''}
      </dl>
      ${done?'<p class="muted">판매자가 환불 처리를 완료했습니다. 결제수단에 따라 실제 취소·입금 반영 시점은 다를 수 있습니다.</p>':''}
      <details class="return-more"><summary>상세 반품 정보</summary>
        <p><strong>상세 사유</strong><br>${esc(r.reasonDetail || '등록된 상세 사유가 없습니다.')}</p>
        ${r.customerNote?`<p><strong>요청사항</strong><br>${esc(r.customerNote)}</p>`:''}
        ${r.adminNote?`<p class="notice"><strong>판매자 안내</strong><br>${esc(r.adminNote)}</p>`:''}
      </details>
    </article>`;
  }

  function render() {
    const done = records.filter(completed);
    byId('returnSummary').textContent = `전체 ${records.length}건 · 반품 완료 ${done.length}건 · 환불 완료 합계 ${money(done.reduce((sum, r) => sum + Number(r.refundAmount || 0), 0))}`;
    byId('returnFilters').querySelectorAll('[data-return-filter]').forEach(button => {
      const active = button.dataset.returnFilter === filter;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    const selected = records.filter(r => filter === 'completed' ? completed(r) : filter === 'active' ? !closed(r) : true);
    byId('returnHistory').innerHTML = selected.length ? selected.map(card).join('') : `<p class="muted">${filter === 'completed'?'완료된 반품 내역이 없습니다.':filter === 'active'?'진행 중인 반품 내역이 없습니다.':'반품 내역이 없습니다.'}</p>`;
  }

  async function load() {
    if (loading) return;
    loading = true;
    byId('refreshReturns').disabled = true;
    byId('returnHistory').setAttribute('aria-busy', 'true');
    byId('returnError').hidden = true;
    try {
      const result = await api('/api/returns/my');
      if (!Array.isArray(result)) throw new Error('반품 내역 응답을 확인할 수 없습니다.');
      records = result.filter(r => r.requestType === 'RETURN').sort((a, b) => String(b.completedAt || b.createdAt || '').localeCompare(String(a.completedAt || a.createdAt || '')));
      render();
    } catch (error) {
      records = [];
      byId('returnSummary').textContent = '반품 내역을 확인할 수 없습니다.';
      byId('returnHistory').innerHTML = '';
      byId('returnError').textContent = '반품 내역을 불러오지 못했습니다. 새로고침을 눌러 다시 확인해 주세요.';
      byId('returnError').hidden = false;
    } finally {
      loading = false;
      byId('refreshReturns').disabled = false;
      byId('returnHistory').setAttribute('aria-busy', 'false');
    }
  }

  byId('returnFilters').addEventListener('click', event => {
    const button = event.target.closest('[data-return-filter]');
    if (!button) return;
    filter = button.dataset.returnFilter;
    render();
  });
  byId('refreshReturns').addEventListener('click', load);
  window.MyPageReturns = {load};
})();
