(function(){
  'use strict';
  const {api,esc}=AppAPI,$=id=>document.getElementById(id);
  const publicRoot=$('productReviews'),ownRoot=$('myReviews');
  if(!publicRoot&&!ownRoot)return;
  const productId=publicRoot?new URLSearchParams(location.search).get('id'):'';
  let publicOffset=0,ownOffset=0,publicSeq=0,ownSeq=0,purchases=[],editing=null,busy=false,opener=null,photos=[];
  const date=x=>new Date(x).toLocaleDateString('ko-KR');
  const stars=n=>`<span class="review-stars" aria-label="5점 만점에 ${n}점">${'★'.repeat(n)}${'☆'.repeat(5-n)}</span>`;
  const gallery=r=>(r.photos||[]).length?`<div class="review-photos">${r.photos.map((p,i)=>`<a href="${esc(p.url)}" target="_blank" rel="noopener"><img src="${esc(p.url)}" alt="구매자 첨부 사진 ${i+1}" loading="lazy" width="110" height="110"></a>`).join('')}</div>`:'';
  const body=r=>`<div class="review-head">${stars(r.rating)}<span class="badge">구매 인증</span><small>${esc(r.author)} · ${date(r.createdAt)}</small></div><p class="review-text">${esc(r.content)}</p>${gallery(r)}${r.reply?`<div class="review-reply"><b>판매자 답변</b><p class="review-text">${esc(r.reply)}</p></div>`:''}`;
  const pager=(prefix,data)=>`<div class="review-pager"><button type="button" class="btn ghost small" data-${prefix}-page="prev" ${data.offset===0?'disabled':''}>이전</button><span>${data.total?Math.floor(data.offset/data.limit)+1:0} / ${Math.ceil(data.total/data.limit)} 페이지 · ${data.total}건</span><button type="button" class="btn ghost small" data-${prefix}-page="next" ${data.offset+data.limit>=data.total?'disabled':''}>다음</button></div>`;
  if(publicRoot){
    publicRoot.innerHTML='<div class="review-heading"><div><div class="eyebrow">VERIFIED REVIEWS</div><h2>구매 리뷰</h2></div><a class="btn ghost small" href="#reviewPurchases">내 리뷰 작성</a></div><p id="reviewSummary" role="status">리뷰를 불러오는 중입니다.</p><div id="reviewPublicList"></div><div id="reviewPublicPager"></div><div id="reviewPurchases" class="review-purchases"></div>';
    publicRoot.addEventListener('click',e=>{const b=e.target.closest('[data-public-page]');if(!b||b.disabled)return;publicOffset=Math.max(0,publicOffset+(b.dataset.publicPage==='next'?10:-10));loadPublic()});
  }
  const mine=ownRoot||$('reviewPurchases');
  mine.innerHTML='<div class="review-heading"><h2>내 구매 리뷰</h2><button class="btn ghost small" type="button" id="refreshPurchaseReviews">새로고침</button></div><p class="muted">배송 완료된 회원 주문의 상품별로 별점과 후기를 남겨 주세요. 주문 상품 1건당 리뷰 1개를 작성할 수 있습니다.</p><p id="reviewOwnStatus" role="status"></p><div id="reviewOwnList"></div><div id="reviewOwnPager"></div>';
  const dialog=document.createElement('dialog');dialog.className='review-dialog';dialog.setAttribute('aria-labelledby','reviewDialogTitle');
  dialog.innerHTML=`<form id="reviewForm"><div class="review-heading"><h2 id="reviewDialogTitle">구매 리뷰 작성</h2><button type="button" class="btn ghost small" data-review-close aria-label="리뷰 작성 닫기">닫기</button></div><p id="reviewProductLabel"></p><fieldset class="review-rating"><legend>별점 선택 <small>(필수)</small></legend>${[1,2,3,4,5].map(n=>`<label><input type="radio" name="rating" value="${n}" required><span aria-hidden="true">★</span>${n}점</label>`).join('')}</fieldset><label for="reviewContent">구매 후기</label><textarea id="reviewContent" name="content" required minlength="5" maxlength="2000" rows="7" placeholder="맛, 포장, 배송 등 구매 경험을 5자 이상 적어 주세요."></textarea><div class="review-heading"><small class="muted">후기는 다른 고객에게 공개됩니다.</small><small id="reviewLength">0 / 2,000자</small></div><div class="review-photo-picker"><label for="reviewPhotoInput">사진 첨부 (선택)</label><input id="reviewPhotoInput" type="file" accept="image/jpeg,image/png,image/webp" multiple><p class="muted">최대 5장 · JPG, PNG, WebP · 한 장당 10MB 이하</p><div id="reviewPhotoPreview" class="review-photo-previews"></div></div><p id="reviewFormError" role="alert" class="review-error"></p><div class="review-actions"><button class="btn ghost" type="button" data-review-close>취소</button><button class="btn primary" type="submit" id="saveReview">리뷰 등록</button></div></form>`;
  document.body.append(dialog);
  const form=$('reviewForm');
  function clearPhotos(){for(const photo of photos){if(photo.file)URL.revokeObjectURL(photo.url);if(photo.draft&&photo.id)api('/api/review-photos/'+encodeURIComponent(photo.id),{method:'DELETE'}).catch(()=>{})}photos=[]}
  function previewPhotos(){
    $('reviewPhotoPreview').innerHTML=photos.map((p,i)=>`<div><img src="${esc(p.url)}" alt="첨부 예정 사진 ${i+1}" width="92" height="92"><button type="button" class="btn ghost small" data-remove-photo="${i}" aria-label="사진 ${i+1} 삭제">삭제</button></div>`).join('');$('reviewPhotoInput').disabled=photos.length>=5||busy;
  }
  $('reviewPhotoInput').onchange=e=>{const files=[...e.target.files];e.target.value='';if(files.length+photos.length>5){$('reviewFormError').textContent='사진은 최대 5장까지 첨부할 수 있습니다.';return}if(files.some(f=>f.size>10*1024*1024)){$('reviewFormError').textContent='사진은 한 장당 10MB 이하로 첨부해 주세요.';return}for(const file of files)photos.push({file,url:URL.createObjectURL(file),draft:true});$('reviewFormError').textContent='';previewPhotos()};
  $('reviewPhotoPreview').onclick=e=>{const b=e.target.closest('[data-remove-photo]');if(!b||busy)return;const [photo]=photos.splice(Number(b.dataset.removePhoto),1);if(photo.file)URL.revokeObjectURL(photo.url);if(photo.draft&&photo.id)api('/api/review-photos/'+encodeURIComponent(photo.id),{method:'DELETE'}).catch(()=>{});previewPhotos()};
  dialog.addEventListener('close',()=>{if(!busy)clearPhotos()});
  function close(){if(busy)return;dialog.close();opener?.focus()}
  dialog.querySelectorAll('[data-review-close]').forEach(b=>b.onclick=close);
  dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault()});
  $('reviewContent').oninput=()=>{$('reviewLength').textContent=`${$('reviewContent').value.length.toLocaleString()} / 2,000자`};
  function open(item,button){clearPhotos();photos=(item.review?.photos||[]).map(p=>({...p}));previewPhotos();editing=item;opener=button;form.reset();$('reviewFormError').textContent='';$('reviewProductLabel').textContent=item.productName+' · '+item.orderNo;const r=item.review;$('reviewDialogTitle').textContent=r?'구매 리뷰 수정':'구매 리뷰 작성';$('saveReview').textContent=r?'수정 저장':'리뷰 등록';if(r){form.querySelector(`[name="rating"][value="${r.rating}"]`).checked=true;$('reviewContent').value=r.content}$('reviewContent').oninput();dialog.showModal();form.querySelector('input:checked')?.focus()}
  async function loadPublic(){
    if(!publicRoot)return;const seq=++publicSeq;
    try{const data=await api('/api/reviews?'+new URLSearchParams({productId,offset:publicOffset,limit:10}),{cache:'no-store'});if(seq!==publicSeq)return;
      $('reviewSummary').innerHTML=data.total?`<strong class="review-average">★ ${Number(data.average).toFixed(1)}</strong> / 5 · 구매 리뷰 ${data.total}건`:'아직 구매 리뷰가 없습니다. 첫 후기를 남겨 주세요.';
      $('reviewPublicList').innerHTML=data.items.map(r=>`<article class="review-card">${body(r)}</article>`).join('');$('reviewPublicPager').innerHTML=pager('public',data);
    }catch(e){if(seq===publicSeq)$('reviewSummary').textContent='리뷰를 불러오지 못했습니다. '+e.message}
  }
  async function loadPurchases(){
    const seq=++ownSeq;$('reviewOwnStatus').textContent='구매 내역을 확인하는 중입니다.';
    try{const me=await api('/api/auth/me',{cache:'no-store'});if(seq!==ownSeq)return;
      if(!me.authenticated||me.role==='admin'){
        purchases=[];$('reviewOwnList').replaceChildren();$('reviewOwnPager').replaceChildren();
        $('reviewOwnStatus').innerHTML=me.authenticated?'리뷰 작성은 구매한 회원 계정에서 이용해 주세요.':`<a class="btn ghost small" href="login.html?next=${encodeURIComponent(location.pathname+location.search+'#'+(ownRoot?'myReviews':'reviewPurchases'))}">로그인하고 구매 리뷰 작성</a>`;return;
      }
      const data=await api('/api/reviews/purchases?'+new URLSearchParams({productId,offset:ownOffset,limit:10}),{cache:'no-store'});if(seq!==ownSeq)return;
      if(!data.items.length&&ownOffset>0){ownOffset=Math.max(0,ownOffset-10);return loadPurchases()}
      purchases=data.items;$('reviewOwnStatus').textContent=data.total?'':'작성 가능한 배송 완료 상품이 없습니다.';
      $('reviewOwnList').innerHTML=purchases.map((item,i)=>`<article class="review-card"><div class="review-heading"><div><b>${esc(item.productName)}</b><p class="muted">주문번호 ${esc(item.orderNo)} · ${item.quantity}개</p></div></div>${item.review?body(item.review):'<p class="muted">이 상품의 구매 경험을 들려주세요.</p>'}${item.review?.hidden?`<p class="review-hidden">관리자 숨김 처리 · ${esc(item.review.hiddenReason)}<br>내용을 수정해도 관리자가 공개하기 전까지 표시되지 않습니다.</p>`:''}<div class="review-actions">${item.review||item.canWrite?`<button class="btn ${item.review?'ghost':'primary'} small" type="button" data-review-edit="${i}">${item.review?'리뷰 수정':'리뷰 작성'}</button>`:''}${item.review?`<button type="button" class="btn ghost small" data-review-delete="${i}">삭제</button>`:''}<a class="btn ghost small" href="detail.html?id=${encodeURIComponent(item.productId)}#productReviews">상품 리뷰 보기</a></div></article>`).join('');$('reviewOwnPager').innerHTML=pager('own',data);
    }catch(e){if(seq===ownSeq){$('reviewOwnStatus').textContent=e.message;$('reviewOwnList').replaceChildren();$('reviewOwnPager').replaceChildren()}}
  }
  $('refreshPurchaseReviews').onclick=()=>{loadPurchases();loadPublic()};
  mine.addEventListener('click',async e=>{
    const b=e.target.closest('[data-review-edit],[data-review-delete],[data-own-page]');if(!b||b.disabled||busy)return;
    if(b.dataset.ownPage){ownOffset=Math.max(0,ownOffset+(b.dataset.ownPage==='next'?10:-10));return loadPurchases()}
    if(b.dataset.reviewEdit!==undefined)return open(purchases[Number(b.dataset.reviewEdit)],b);
    const r=purchases[Number(b.dataset.reviewDelete)].review;if(!confirm('작성한 리뷰를 삭제할까요?'))return;
    b.disabled=true;try{await api('/api/reviews/'+encodeURIComponent(r.id),{method:'DELETE',body:{revision:r.revision}});await Promise.all([loadPurchases(),loadPublic()])}catch(err){$('reviewOwnStatus').textContent=err.message;b.disabled=false}
  });
  form.onsubmit=async e=>{
    e.preventDefault();if(busy||!editing)return;const f=new FormData(form),content=String(f.get('content')||'').trim(),rating=Number(f.get('rating'));if(content.length<5){$('reviewFormError').textContent='후기를 5자 이상 입력해 주세요.';return}
    busy=true;dialog.querySelectorAll('button,input,textarea').forEach(b=>b.disabled=true);$('reviewFormError').textContent='';
    try{for(const photo of photos){if(photo.id)continue;const data=new FormData();data.set('orderItemId',String(editing.orderItemId));data.set('file',photo.file);const uploaded=await api('/api/review-photos',{method:'POST',body:data});photo.id=uploaded.id}const r=editing.review;await api('/api/reviews'+(r?'/'+encodeURIComponent(r.id):''),{method:r?'PUT':'POST',body:{rating,content,photoIds:photos.map(p=>p.id),...(r?{revision:r.revision}:{orderItemId:editing.orderItemId})}});photos.forEach(p=>p.draft=false);clearPhotos();dialog.close();await Promise.all([loadPurchases(),loadPublic()]);$('refreshPurchaseReviews').focus()}
    catch(err){$('reviewFormError').textContent=err.message}
    finally{busy=false;dialog.querySelectorAll('button,input,textarea').forEach(b=>b.disabled=false);previewPhotos()}
  };
  loadPublic();loadPurchases();
})();
