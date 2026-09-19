(function(){
  'use strict';
  const root=document.getElementById('reviews');if(!root)return;
  const {api,esc}=AppAPI,$=id=>document.getElementById(id);
  let offset=0,sequence=0,items=[],snapshot='',pending=false;
  const active=()=>root.classList.contains('active');
  async function load(background=false){
    if(!active()||pending||(background&&(root.contains(document.activeElement)||root.querySelector('[data-dirty]'))))return;
    const seq=++sequence,visibility=$('reviewVisibility').value;
    if(!background)$('adminReviewStatus').textContent='리뷰를 불러오는 중입니다.';
    try{const data=await api('/api/admin/reviews?'+new URLSearchParams({visibility,offset,limit:20}),{cache:'no-store'});if(seq!==sequence||!active())return;
      if(!data.items.length&&offset>0){offset=Math.max(0,offset-20);return load()}
      const current=JSON.stringify(data);if(current===snapshot){$('adminReviewStatus').textContent=`총 ${data.total}건`;return}snapshot=current;items=data.items;
      $('adminReviewStatus').textContent=`총 ${data.total}건`;
      $('adminReviewList').innerHTML=items.map((r,i)=>`<article class="review-card"><div class="review-heading"><div><b>${esc(r.productName)}</b><p class="muted">주문번호 ${esc(r.orderNo)} · ${esc(r.author)} · ${new Date(r.createdAt).toLocaleString('ko-KR')}</p></div><span class="badge">${r.hidden?'숨김':'공개'}</span></div><span class="review-stars" aria-label="5점 만점에 ${r.rating}점">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</span><p class="review-text">${esc(r.content)}</p><div class="review-photos">${(r.photos||[]).map((p,i)=>`<a href="${esc(p.url)}" target="_blank" rel="noopener"><img src="${esc(p.url)}" alt="리뷰 첨부 사진 ${i+1}" loading="lazy" width="110" height="110"></a>`).join('')}</div>${r.hidden?`<p class="review-hidden">숨김 사유: ${esc(r.hiddenReason)}</p>`:''}<form data-review-reply="${i}"><label>판매자 답변<textarea name="content" rows="3" maxlength="1000">${esc(r.reply)}</textarea></label><button class="btn primary small" type="submit">답변 저장</button></form><form data-review-visibility="${i}" class="review-moderation">${r.hidden?'':`<label>숨김 사유<input name="reason" maxlength="300" required placeholder="예: 개인정보 노출, 상품과 무관한 광고"></label>`}<button class="btn ghost small" type="submit">${r.hidden?'다시 공개':'숨김 처리'}</button></form><div class="event-read-actions" data-event-kind="reviews" data-event-target="${esc(r.id)}" data-event-through="${r.notificationThrough}">${r.unreadCount?`<span class="event-unread">미확인 ${r.unreadCount}건</span><button class="btn ghost small" type="button" data-event-confirm>확인</button>`:''}</div></article>`).join('')||'<p class="muted">해당 리뷰가 없습니다.</p>';
      $('adminReviewPage').textContent=`${data.total?Math.floor(offset/20)+1:0} / ${Math.ceil(data.total/20)} 페이지`;$('adminReviewPrev').disabled=!offset;$('adminReviewNext').disabled=offset+20>=data.total;
      window.AdminNotifications?.watchThreads();
    }catch(e){if(seq===sequence)$('adminReviewStatus').textContent=e.message}
  }
  root.addEventListener('input',e=>{const form=e.target.closest('form');if(form)form.dataset.dirty='true'});
  root.addEventListener('submit',async e=>{
    const form=e.target.closest('[data-review-reply],[data-review-visibility]');if(!form)return;e.preventDefault();if(pending)return;
    const isReply=form.dataset.reviewReply!==undefined,r=items[Number(isReply?form.dataset.reviewReply:form.dataset.reviewVisibility)],f=new FormData(form);
    if(!isReply&&!confirm(r.hidden?'리뷰를 다시 공개할까요?':'리뷰를 숨길까요? 작성자는 사유를 확인할 수 있습니다.'))return;
    pending=true;form.querySelector('button').disabled=true;$('adminReviewStatus').textContent='저장하는 중입니다.';
    try{await api('/api/admin/reviews/'+encodeURIComponent(r.id)+(isReply?'/reply':'/visibility'),{method:isReply?'POST':'PATCH',body:isReply?{content:f.get('content'),revision:r.revision}:{hidden:!r.hidden,reason:f.get('reason')||'',revision:r.revision}});window.AdminNotifications?.confirm({kind:'reviews',target:r.id,through:r.notificationThrough});form.removeAttribute('data-dirty');snapshot='';pending=false;await load()}
    catch(err){$('adminReviewStatus').textContent=err.message}
    finally{pending=false;form.querySelector('button').disabled=false}
  });
  $('reviewVisibility').onchange=()=>{offset=0;snapshot='';load()};$('refreshAdminReviews').onclick=()=>{snapshot='';load();window.AdminNotifications?.refresh()};
  $('adminReviewPrev').onclick=()=>{offset=Math.max(0,offset-20);load()};$('adminReviewNext').onclick=()=>{offset+=20;load()};
  document.querySelector('.side nav').addEventListener('click',e=>{if(e.target.closest('[data-view="reviews"]'))load();else if(e.target.closest('[data-view]'))sequence++});
  window.reloadAdminReviews=()=>load(true);
})();
