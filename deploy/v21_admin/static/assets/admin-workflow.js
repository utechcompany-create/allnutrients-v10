(function () {
  'use strict';
  const labels = {orders: '미발송 주문', returns: '처리 중 반품', exchanges: '처리 중 교환', cancellations: '취소 승인 대기'};
  let loading = false;
  async function refresh() {
    if (loading || document.hidden) return;
    loading = true;
    try {
      const counts = await AppAPI.api('/api/admin/work-counts');
      document.querySelectorAll('[data-work-count]').forEach(badge => {
        const key = badge.dataset.workCount;
        const count = Number(counts[key]);
        if (!Number.isSafeInteger(count) || count < 0) throw new Error('카운터 응답 오류');
        badge.textContent = count.toLocaleString('ko-KR');
        badge.classList.toggle('has-work', count > 0);
        badge.setAttribute('aria-label', `${labels[key]} ${count}건`);
        badge.title = `${labels[key]} ${count}건 · 30초마다 갱신`;
      });
    } catch (_) {
      document.querySelectorAll('[data-work-count]').forEach(badge => {
        badge.textContent = '—';
        badge.classList.remove('has-work');
        badge.setAttribute('aria-label', '건수 확인 실패');
        badge.title = '건수를 불러오지 못했습니다. 잠시 후 다시 확인합니다.';
      });
    } finally { loading = false; }
  }
  window.AdminWorkCounts = {refresh};
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', refresh);
  setInterval(refresh, 30000);
  refresh();
})();
