(function () {
  'use strict';
  const {api, esc, money} = AppAPI;
  const $ = id => document.getElementById(id);
  const query = new URLSearchParams(location.search);
  const form = $('requestForm');
  const field = name => form.elements.namedItem(name);
  const guestField = name => $('guestForm').elements.namedItem(name);
  const statusKo = {REQUESTED:'접수',APPROVED:'승인',COLLECTING:'회수 중',RECEIVED:'입고 완료',REFUNDING:'환불 처리 중',REFUNDED:'반품·환불 완료',EXCHANGE_PREPARING:'교환 준비 중',EXCHANGE_SHIPPED:'교환품 재배송',COMPLETED:'교환 완료',REJECTED:'거절',CANCELED:'취소'};
  let order = null, member = false, reasons = [], requests = [], ready = false, busy = false, loadVersion = 0, selectedNo = '';
  let guestCred = {email:'',phone:'',pin:''};
  if (['RETURN','EXCHANGE'].includes(query.get('type'))) field('requestType').value = query.get('type');

  function toast(message) { $('toast').textContent=message; $('toast').classList.add('show'); setTimeout(()=>$('toast').classList.remove('show'),2400); }
  function showError(error) { $('pageErrorText').textContent = error.message || String(error); $('pageError').hidden=false; }
  function dateText(value) { if(!value)return '기록 없음'; const d=new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value)?value:value+'Z'); return Number.isNaN(d.getTime())?'기록 없음':d.toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}); }
  function shipped(o) { return ['SHIPPED','DELIVERED','PARTIAL_RETURN','RETURNED','EXCHANGE_IN_PROGRESS','EXCHANGED'].includes(o.orderStatus) || !!(o.shipment && ((o.shipment.trackingNumber||'').trim() || ['SHIPPED','DELIVERED','RETURNED'].includes((o.shipment.status||'').toUpperCase()))); }
  function available(item) {
    const used=requests.reduce((sum,r)=>['REJECTED','CANCELED'].includes(r.status)||(r.requestType==='EXCHANGE'&&r.status==='COMPLETED')?sum:sum+(r.items||[]).filter(i=>i.orderItemId===item.orderItemId).reduce((n,i)=>n+Number(i.qty),0),0);
    return Math.max(0,Number(item.qty)-used);
  }
  function blockedReason() {
    if (!order) return '주문을 선택하거나 비회원 주문을 확인하면 신청할 수 있습니다.';
    if (!ready) return '주문과 신청 내역을 확인 중입니다. 오류가 표시되면 다시 불러오기를 눌러 주세요.';
    if (order.paymentStatus==='REFUNDED') return '환불이 완료된 주문입니다. 아래에서 반품·교환 완료 내역을 확인해 주세요.';
    if (!['PAID','PARTIAL_REFUNDED'].includes(order.paymentStatus)) return '결제 완료된 주문부터 반품·교환을 신청할 수 있습니다.';
    if (!shipped(order)) return '송장번호가 등록되거나 배송이 시작된 후 신청할 수 있습니다. 배송 전 취소는 주문조회에서 신청해 주세요.';
    if (!order.items.some(i=>available(i)>0)) return '모든 상품이 이미 반품·교환 신청되었거나 반품 완료되었습니다. 아래 신청 내역을 확인해 주세요.';
    if (!reasons.length) return '현재 선택할 수 있는 신청 사유가 없습니다. 판매자에게 문의해 주세요.';
    return '';
  }
  function updateAvailability() {
    const message=blockedReason();
    $('requestFields').disabled=busy||!!message;
    $('orderSelect').disabled=busy;$('guestLookupButton').disabled=busy;$('retryPage').disabled=busy;
    $('requestNotice').textContent=busy?'신청을 처리하고 있습니다.':message||'신청 유형과 사유를 고른 후 상품·수량을 선택해 주세요.';
  }
  function updateBank() {
    const needed=order?.paymentMethod==='CASH'&&field('requestType').value==='RETURN';
    $('cashRefund').hidden=!needed;
    ['refundBankName','refundBankAccount','refundBankHolder'].forEach(name=>{field(name).required=needed;field(name).disabled=!needed;});
  }
  function selectedItems() { return [...document.querySelectorAll('.pick:checked')].map(c=>({control:c,orderItemId:Number(c.dataset.id),qty:Number(document.querySelector(`.qty[data-id="${c.dataset.id}"]`).value)})); }
  function packing() {
    const picked=selectedItems(); let load=0,hasBundle=false,separate=0;
    for(const {control:c,qty} of picked){if(c.dataset.bundle!=='false'){hasBundle=true;const capacity=Number(c.dataset.capacity);if(capacity>0)load+=qty/capacity;}else separate+=qty;}
    return {bundled:hasBundle?Math.max(1,Math.ceil(load-1e-10)):0,separate};
  }
  function pickedFee(key) { const picked=selectedItems(),pack=packing(); let bundled=0,separate=0; for(const {control:c,qty} of picked){const fee=Number(c.dataset[key]||0);if(c.dataset.bundle!=='false')bundled=Math.max(bundled,fee);else separate+=fee*qty;} return bundled*pack.bundled+separate; }
  function isPartialOneBox() { const picked=new Map(selectedItems().map(i=>[i.orderItemId,i.qty])),pack=packing(); return order.items.some(i=>(picked.get(i.orderItemId)||0)<Number(i.qty))&&pack.bundled+pack.separate===1; }
  function updateFeeNotice() {
    if(!order)return;
    const reason=reasons.find(r=>r.code===field('reasonCode').value);
    if(!reason){$('feeNotice').textContent='신청 사유를 선택해 주세요.';return;}
    if(!selectedItems().length){$('feeNotice').textContent='상품과 수량을 선택하면 예상 배송비가 표시됩니다.';return;}
    const typ=field('requestType').value,changeMind=reason.code==='CHANGE_MIND'||String(reason.name||'').replace(/\s/g,'')==='단순변심';
    let fee=0,half=false;
    if(typ==='RETURN'&&changeMind){fee=pickedFee('returnFee');half=isPartialOneBox();if(half)fee=Math.floor(fee/2);}else if(typ==='EXCHANGE'&&reason.responsibility==='CUSTOMER')fee=pickedFee('exchangeFee');
    $('feeNotice').innerHTML=typ==='RETURN'?`<b>${esc(reason.name)}</b> · ${changeMind?`예상 반품배송비 <b>${money(fee)}</b>${half?' (1박스 분량 부분 반품 50%)':''}가 환불금에서 차감됩니다.`:'차감 없이 전액 환불됩니다.'}`:`<b>${esc(reason.name)}</b> · 교환 배송비 고객 부담 <b>${money(fee)}</b>`;
  }
  function renderOrder() {
    $('orderBox').hidden=false;
    $('orderBox').innerHTML=`<div class="row order-summary"><div><h2>${esc(order.orderNo)}</h2><p class="muted">${esc(dateText(order.createdAt))} · ${esc(order.paymentMethod)}</p></div><b>${money(order.totalAmount)}</b></div>`;
    $('itemChoices').innerHTML='<h3>반품·교환 상품/수량</h3>'+order.items.map(i=>{const remaining=available(i);return `<div class="item-row"><label style="display:flex;align-items:center;gap:8px"><input type="checkbox" class="pick" data-id="${Number(i.orderItemId)}" data-return-fee="${Number(i.returnFee||0)}" data-exchange-fee="${Number(i.exchangeFee||0)}" data-bundle="${i.bundleAllowed!==false}" data-capacity="${Number(i.bundleCapacity||0)}" ${remaining?'':'disabled'}><span><b>${esc(i.name)}</b><span class="muted" style="display:block">주문 ${Number(i.qty)}개 · 신청 가능 ${remaining}개 · ${money(i.price)}</span></span></label><label>신청수량<input type="number" class="qty" data-id="${Number(i.orderItemId)}" min="1" max="${remaining}" value="${remaining?1:0}" disabled></label></div>`;}).join('');
    document.querySelectorAll('.pick').forEach(c=>c.onchange=()=>{document.querySelector(`.qty[data-id="${c.dataset.id}"]`).disabled=!c.checked;updateFeeNotice();});
    document.querySelectorAll('.qty').forEach(input=>input.oninput=updateFeeNotice);
    updateBank();updateAvailability();updateFeeNotice();
  }
  function renderHistory() {
    $('historyBox').hidden=false;
    $('requestHistoryList').innerHTML=requests.length?requests.map(r=>`<article class="req"><div class="row"><b>${esc(r.requestNo)} · ${r.requestType==='RETURN'?'반품':'교환'}</b><span class="badge">${esc(statusKo[r.status]||r.status)}</span></div><p class="muted">신청일 ${esc(dateText(r.createdAt))}${r.completedAt?' · 처리 완료일 '+esc(dateText(r.completedAt)):''}</p><p>${(r.items||[]).map(i=>esc(i.name)+' × '+Number(i.qty)).join('<br>')}</p><p>사유: ${esc(r.reasonName||r.reasonCode)}<br>${esc(r.reasonDetail||'')}</p><p>${r.requestType==='RETURN'?'반품배송비 차감':'교환배송비 고객 부담'}: ${money(r.returnShippingFee)}</p>${r.requestType==='RETURN'?`<p>${['REJECTED','CANCELED'].includes(r.status)?'환불 미진행':['COMPLETED','MANUAL_COMPLETED'].includes(r.refundStatus)?'환불 완료 금액: '+money(r.refundAmount):'환불 예정 금액: '+money(r.refundAmount)}</p>`:''}${r.pickup?.trackingNumber?`<p class="muted">회수: ${esc(r.pickup.carrier)} ${esc(r.pickup.trackingNumber)}</p>`:''}${r.exchangeShipment?.trackingNumber?`<p class="muted">교환 재배송: ${esc(r.exchangeShipment.carrier)} ${esc(r.exchangeShipment.trackingNumber)}</p>`:''}${r.adminNote?`<p class="notice">판매자 안내: ${esc(r.adminNote)}</p>`:''}<div class="photos">${(r.attachments||[]).filter(x=>typeof x==='string'&&x.startsWith('/uploads/')).map(x=>`<a href="${esc(x)}" target="_blank" rel="noopener"><img src="${esc(x)}" alt="신청 첨부 사진"></a>`).join('')}</div></article>`).join(''):'<p class="muted">신청 내역이 없습니다.</p>';
  }
  function reasonOptions(rows) { reasons=rows;field('reasonCode').innerHTML='<option value="">사유 선택</option>'+rows.map(r=>`<option value="${esc(r.code)}">${esc(r.name)}</option>`).join('');if(rows.some(r=>r.code===query.get('reason')))field('reasonCode').value=query.get('reason'); }
  async function getOrder(no) { return member?api('/api/orders/'+encodeURIComponent(no)):api('/api/orders/guest-lookup',{method:'POST',body:{orderNo:no,...guestCred}}); }
  async function getHistory(no) { return member?api('/api/returns/my?orderNo='+encodeURIComponent(no)):api('/api/returns/guest-list',{method:'POST',body:{orderNo:no,...guestCred}}); }
  async function loadOrder(no) {
    selectedNo=no;
    const version=++loadVersion;ready=false;order=null;requests=[];$('orderBox').hidden=true;$('historyBox').hidden=true;$('pageError').hidden=true;
    $('itemChoices').innerHTML='<p class="muted">주문을 확인하고 있습니다.</p>';updateAvailability();
    if(!no){$('itemChoices').innerHTML='<p class="muted">신청할 주문을 선택해 주세요.</p>';return;}
    try {
      const nextOrder=await getOrder(no);if(version!==loadVersion)return;
      order=nextOrder;
      const [rows,reasonRows]=await Promise.all([getHistory(no),api('/api/return-reasons?requestType='+field('requestType').value)]);
      if(version!==loadVersion)return;
      requests=rows;reasonOptions(reasonRows);ready=true;renderOrder();renderHistory();
      const url=new URL(location.href);url.searchParams.set('orderNo',no);window.history.replaceState(null,'',url.pathname+url.search+url.hash);
      if(location.hash==='#historyBox')$('historyBox').scrollIntoView({block:'start'});
    } catch(error){if(version!==loadVersion)return;ready=false;showError(error);updateAvailability();}
  }
  async function loadReasons() {
    if(!order)return;const version=++loadVersion;ready=false;updateAvailability();$('pageError').hidden=true;
    try { const rows=await api('/api/return-reasons?requestType='+field('requestType').value);if(version!==loadVersion)return;reasonOptions(rows);ready=true;updateBank();updateFeeNotice();updateAvailability(); }
    catch(error){if(version!==loadVersion)return;showError(error);updateAvailability();}
  }
  async function lookupGuest() {
    const no=guestField('orderNo').value.trim();
    if(!no)return;
    guestCred={email:guestField('email').value.trim(),phone:guestField('phone').value.trim(),pin:guestField('pin').value.trim()};
    $('guestLookupButton').disabled=true;
    try{await loadOrder(no);}finally{$('guestLookupButton').disabled=false;}
  }
  async function init() {
    $('pageError').hidden=true;
    try {
      const me=await api('/api/auth/me');member=!!me.authenticated&&query.get('guest')!=='1';
      $('memberOrders').hidden=!member;$('guestAuth').hidden=member;
      const no=new URLSearchParams(location.search).get('orderNo')||'';
      if(member){
        const orders=await api('/api/orders/my');
        $('orderSelect').innerHTML='<option value="">주문을 선택해 주세요</option>'+orders.map(o=>`<option value="${esc(o.orderNo)}">${esc(o.orderNo)} · ${esc((o.items||[]).map(i=>i.name).join(', '))}</option>`).join('');
        $('orderSelectHelp').textContent=orders.length?'주문을 선택하면 반품·교환 신청과 완료 내역을 확인할 수 있습니다.':'회원 주문 내역이 없습니다. 비회원으로 구매했다면 비회원 주문 확인을 이용해 주세요.';
        if(no){$('orderSelect').value=no;await loadOrder(no);}else updateAvailability();
      }else{
        const loginNext=new URL('return-request.html',location.href);if(no)loginNext.searchParams.set('orderNo',no);
        $('memberLoginLink').href='login.html?next='+encodeURIComponent(loginNext.pathname+loginNext.search);
        guestField('orderNo').value=no;
        try { for(const key of ['email','phone','pin'])guestField(key).value=sessionStorage.getItem('guest_'+key+'_'+no)||''; } catch(error){ /* manual entry remains available when storage is blocked */ }
        if(no&&['email','phone','pin'].every(key=>guestField(key).value))await lookupGuest();
      }
    }catch(error){showError(error);updateAvailability();}
  }
  async function uploadFiles() {
    const files=[...$('attachments').files];if(files.length>5)throw new Error('사진은 최대 5장까지 첨부할 수 있습니다.');
    for(const file of files)if(file.size>5*1024*1024||!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('사진은 JPG, PNG, WebP 형식으로 각 5MB 이하만 첨부할 수 있습니다.');
    const urls=[];for(const file of files){const data=new FormData();data.append('file',file);if(!member){data.append('orderNo',order.orderNo);for(const [key,value]of Object.entries(guestCred))data.append(key,value);}urls.push((await api(member?'/api/returns/upload':'/api/returns/guest-upload',{method:'POST',body:data})).url);}return urls;
  }
  form.onsubmit=async event=>{
    event.preventDefault();if(busy||blockedReason())return updateAvailability();
    const selected=selectedItems();if(!selected.length)return toast('상품을 한 개 이상 선택해 주세요.');
    if(selected.some(i=>!Number.isInteger(i.qty)||i.qty<1||i.qty>available(order.items.find(x=>x.orderItemId===i.orderItemId))))return toast('신청 가능한 수량을 확인해 주세요.');
    const data=new FormData(form),typ=data.get('requestType');if(!data.get('reasonCode'))return toast('신청 사유를 선택해 주세요.');
    busy=true;updateAvailability();$('pageError').hidden=true;
    try {
      const urls=await uploadFiles();const body={orderNo:order.orderNo,requestType:typ,reasonCode:data.get('reasonCode'),reasonDetail:data.get('reasonDetail'),customerNote:data.get('customerNote'),items:selected.map(({orderItemId,qty})=>({orderItemId,qty})),attachments:urls,refundBankName:data.get('refundBankName')||'',refundBankAccount:data.get('refundBankAccount')||'',refundBankHolder:data.get('refundBankHolder')||''};
      await api(member?'/api/returns':'/api/returns/guest',{method:'POST',body:member?body:{...body,...guestCred}});
      const no=order.orderNo;form.reset();field('requestType').value=typ;await loadOrder(no);toast('반품·교환 신청이 등록되었습니다.');
    }catch(error){showError(error);}finally{busy=false;updateAvailability();}
  };
  $('guestForm').onsubmit=async event=>{event.preventDefault();await lookupGuest();};
  $('orderSelect').onchange=()=>loadOrder($('orderSelect').value);
  field('requestType').onchange=loadReasons;field('reasonCode').onchange=updateFeeNotice;
  $('retryPage').onclick=()=>selectedNo?loadOrder(selectedNo):init();
  init();
})();
