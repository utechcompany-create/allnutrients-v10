(function(){
  'use strict';
  const {api,esc,money}=AppAPI,$=id=>document.getElementById(id),chat=ChatUI.mount($('adminChat'),{admin:true});
  let sequence=0,currentReport=null;
  function day(d){return new Date(d.getTime()+9*3600000).toISOString().slice(0,10)}
  function preset(value){const today=new Date(),end=day(today);$('salesEnd').value=end;$('salesStart').value=value==='today'?end:value==='week'?day(new Date(today.getTime()-6*86400000)):end.slice(0,8)+'01';}
  preset('month');
  async function load(){
    const seq=++sequence;currentReport=null;$('salesExport').disabled=true;$('salesError').textContent='';$('salesStatus').textContent='매출을 집계하는 중입니다.';
    $('salesSummary').innerHTML='';$('salesDaily').innerHTML='';$('salesOrders').innerHTML='';$('salesUnresolved').textContent='';
    const query=new URLSearchParams({start:$('salesStart').value,end:$('salesEnd').value});
    try{const data=await api('/api/admin/sales?'+query,{cache:'no-store'});if(seq!==sequence)return;currentReport={data,query};
      $('salesSummary').innerHTML=[['결제 주문',data.totals.orderCount.toLocaleString('ko-KR')+'건'],['결제 매출',money(data.totals.grossAmount)],['완료 환불액',money(data.totals.refundAmount)],['순매출',money(data.totals.netAmount)]].map(([label,value])=>`<article><span>${label}</span><strong>${esc(value)}</strong></article>`).join('');
      $('salesDaily').innerHTML=data.daily.map(x=>`<tr><td>${esc(x.date)}</td><td>${x.orderCount}건</td><td>${money(x.grossAmount)}</td><td>${money(x.refundAmount)}</td><td><b>${money(x.netAmount)}</b></td></tr>`).join('')||'<tr><td colspan="5">해당 기간의 결제 주문이 없습니다.</td></tr>';
      $('salesOrders').innerHTML=data.orders.map(x=>`<tr><td>${esc(x.date)}</td><td>${esc(x.orderNo)}</td><td>${esc(x.customerName)}</td><td>${esc(AdminLabels.paymentMethod(x.paymentMethod))}</td><td>${esc(AdminLabels.paymentStatus(x.paymentStatus))}</td><td>${money(x.grossAmount)}</td><td>${money(x.refundAmount)}</td><td>${money(x.netAmount)}</td></tr>`).join('')||'<tr><td colspan="8">해당 기간의 결제 주문이 없습니다.</td></tr>';
      const unresolved=data.unreconciledOrders||[];$('salesUnresolved').textContent=unresolved.length?`PG 취소 금액 확인이 필요한 ${unresolved.length}건은 합계에서 제외되었습니다. 확인 대상: ${unresolved.map(x=>x.orderNo).join(', ')}. 확인 전에는 CSV 다운로드가 제한됩니다.`:'';
      $('salesStatus').textContent=`${data.start} ~ ${data.end} · ${new Date(data.updatedAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})} 기준`;$('salesExport').disabled=!!unresolved.length;
    }catch(e){if(seq===sequence){$('salesError').textContent=e.message;$('salesStatus').textContent='조회 기간을 확인하고 다시 시도해 주세요.'}}
  }
  $('salesForm').onsubmit=e=>{e.preventDefault();load()};document.querySelectorAll('[data-sales-preset]').forEach(b=>b.onclick=()=>{preset(b.dataset.salesPreset);load()});
  $('salesExport').onclick=async()=>{if(!currentReport)return;const current=currentReport;try{const response=await fetch('/api/admin/sales/export.csv?'+current.query,{credentials:'same-origin',cache:'no-store'});if(!response.ok){const err=await response.json();throw new Error(err.detail||'다운로드에 실패했습니다.')}const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=`매출_${current.data.start}_${current.data.end}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){$('salesError').textContent=e.message}};
  $('chatMenuToggle').onclick=()=>{const expanded=$('chatMenuToggle').getAttribute('aria-expanded')==='true';$('chatMenuToggle').setAttribute('aria-expanded',String(!expanded));$('chatSubnav').hidden=expanded};
  document.querySelector('.side nav').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;if(b.dataset.view==='sales')load();else{sequence++;currentReport=null;$('salesSummary').innerHTML='';$('salesDaily').innerHTML='';$('salesOrders').innerHTML='';}if(b.dataset.view==='liveChat')chat.open(b.dataset.chatKind||'GROUP');else chat.close()});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){sequence++;currentReport=null;$('salesSummary').innerHTML='';$('salesDaily').innerHTML='';$('salesOrders').innerHTML='';$('salesExport').disabled=true;}else if($('sales').classList.contains('active'))load()});
})();
