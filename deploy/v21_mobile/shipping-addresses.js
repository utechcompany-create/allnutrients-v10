(function(){
  'use strict';
  const fields=['customerName','customerPhone','postcode','address1','address2','deliveryMemo'];
  function mount({user,form,onChange}){
    const $=id=>document.getElementById(id),box=$('shippingAddressBook');
    if(!user?.authenticated||!box)return;
    box.hidden=false;$('saveShippingOption').hidden=false;
    const select=$('shippingAddressSelect'),remove=$('deleteShippingAddress'),status=$('shippingAddressStatus'),error=$('shippingAddressError'),confirm=$('shippingDeleteConfirm');
    let addresses=[],generation=0,deleting=false;
    const esc=AppAPI.esc;
    function render(selected=''){
      select.innerHTML='<option value="">'+(addresses.length?'배송지를 선택하세요':'저장된 배송지가 없습니다')+'</option>'+addresses.map(a=>`<option value="${esc(a.id)}">${esc(a.customerName)} · ${esc(a.address1)} ${esc(a.address2)}</option>`).join('');
      select.value=addresses.some(a=>a.id===selected)?selected:'';select.disabled=!addresses.length;remove.disabled=!select.value||deleting;
      status.textContent=addresses.length?`저장된 배송지 ${addresses.length}개 · 선택하면 배송정보가 자동 입력됩니다.`:'아래 배송정보를 입력하고 주문하면 다음 주문부터 선택할 수 있습니다.';
    }
    async function load(){
      const g=++generation,selected=select.value;error.textContent='';status.textContent='배송지를 불러오는 중입니다.';select.disabled=true;remove.disabled=true;confirm.hidden=true;
      try{const rows=await AppAPI.api('/api/shipping-addresses',{cache:'no-store'});if(g!==generation)return;addresses=rows;render(selected)}
      catch(e){if(g!==generation)return;addresses=[];render();error.textContent='배송지를 불러오지 못했습니다. 새로고침하거나 직접 입력해 주세요. '+e.message}
    }
    select.onchange=()=>{
      confirm.hidden=true;error.textContent='';const selected=addresses.find(a=>a.id===select.value);remove.disabled=!selected;
      if(!selected)return;
      for(const name of fields)form.elements.namedItem(name).value=selected[name]||'';
      onChange();status.textContent='선택한 배송지를 적용했습니다. 받는 분과 상세주소를 확인해 주세요.';
    };
    $('newShippingAddress').onclick=()=>{
      select.value='';remove.disabled=true;confirm.hidden=true;error.textContent='';
      for(const name of fields)form.elements.namedItem(name).value=name==='customerName'?(user.name||''):name==='customerPhone'?(user.phone||''):'';
      onChange();form.elements.namedItem('customerName').focus();status.textContent='새 배송지를 입력해 주세요.';
    };
    remove.onclick=()=>{if(select.value){confirm.hidden=false;$('confirmShippingDelete').focus()}};
    $('cancelShippingDelete').onclick=()=>{confirm.hidden=true;remove.focus()};
    $('confirmShippingDelete').onclick=async()=>{
      const id=select.value;if(!id||deleting)return;deleting=true;const g=++generation;
      select.disabled=true;remove.disabled=true;$('confirmShippingDelete').disabled=true;error.textContent='';
      try{
        await AppAPI.api('/api/shipping-addresses/'+encodeURIComponent(id),{method:'DELETE'});if(g!==generation)return;
        addresses=addresses.filter(a=>a.id!==id);confirm.hidden=true;render();
        // Keep the order draft, but do not silently re-save an address just deleted.
        $('saveShippingAddress').checked=false;status.textContent='배송지를 삭제했습니다. 현재 주문서에 입력한 주소는 유지됩니다.';
      }catch(e){if(g===generation){render(id);error.textContent=e.message}}
      finally{deleting=false;$('confirmShippingDelete').disabled=false;if(g===generation)remove.disabled=!select.value}
    };
    $('reloadShippingAddresses').onclick=()=>{if(!deleting)load()};
    window.addEventListener('pagehide',()=>{generation++;addresses=[];select.innerHTML='<option value="">배송지를 다시 확인합니다.</option>';select.disabled=true;remove.disabled=true;confirm.hidden=true});
    window.addEventListener('pageshow',e=>{if(e.persisted)load()});
    load();
  }
  window.ShippingAddresses={mount};
})();
