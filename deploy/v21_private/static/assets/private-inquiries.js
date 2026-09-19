(function () {
  'use strict';
  const {esc} = AppAPI;
  function card(row, kind) {
    const readable = !row.isPrivate || row.canRead === true;
    const badge = row.isPrivate ? '<span class="privacy-badge">🔒 비밀글</span> ' : '';
    const title = readable ? row.title : '비밀글입니다.';
    const category = kind === 'board' ? `${esc(row.category)} · ` : '';
    let body = '<p class="privacy-locked">작성자와 관리자만 확인할 수 있는 비밀글입니다.</p>';
    if (readable) {
      body = `<p class="privacy-content">${esc(row.content)}</p>${(row.messages || []).map(message => `<div class="privacy-message"><b>${message.role === 'seller' ? '판매자 답변' : '고객 추가문의'}</b><p>${esc(message.content)}</p></div>`).join('')}`;
      if (kind === 'board' && row.canFollowup) {
        body += `<div class="follow"><input id="f-${esc(row.id)}" placeholder="추가 문의" aria-label="추가 문의"><button class="btn ghost" data-follow-id="${esc(row.id)}">등록</button></div>`;
      }
      if (kind === 'board' && row.canMakePrivate) {
        body += `<button class="btn ghost small privacy-convert" type="button" data-private-id="${esc(row.id)}">🔒 비밀글로 변경</button>`;
      }
    }
    return `<article class="${kind === 'board' ? 'post' : 'card'}"><div class="row"><div><b>${badge}${category}${esc(title)}</b><div class="muted">${esc(readable ? row.author : '비공개')} · ${esc(new Date(row.createdAt).toLocaleString())}</div></div><span class="badge ${row.status === '답변완료' ? '' : 'warn'}">${esc(row.status)}</span></div>${body}</article>`;
  }
  function watch(clear, reload) {
    // Clear personalized threads before a page enters the history cache, and
    // recheck server permissions when another tab changes the signed-in account.
    window.addEventListener('pagehide', clear);
    window.addEventListener('pageshow', event => { if (event.persisted) { clear(); reload(); } });
    window.addEventListener('focus', () => { clear(); reload(); });
  }
  window.PrivateInquiryUI = {card, watch};
})();
