// npm install jsdom@26 in a test-only directory; set NODE_PATH to its node_modules.
const fs=require('node:fs'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const settle=async()=>{for(let n=0;n<20;n++)await Promise.resolve()};
const read=p=>fs.readFileSync(p,'utf8');
function dom(page,url='https://shop.example.test/'+page+'.html'){
  const d=new JSDOM(read('static/'+page+'.html'),{url,runScripts:'outside-only',pretendToBeVisual:true});
  d.window.matchMedia=()=>({matches:true,addEventListener(){},removeEventListener(){}});
  d.window.HTMLDialogElement.prototype.showModal=function(){this.open=true};
  d.window.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new d.window.Event('close'))};
  d.window.HTMLElement.prototype.scrollIntoView=function(){};
  return d;
}
function script(d,name){d.window.eval(read('static/assets/'+name))}
(async()=>{
  const home=dom('index','https://shop.example.test/index.html?openCart=1&category=cat-1#products'),w=home.window,$=id=>w.document.getElementById(id);
  w.fetch=async()=>({ok:true,json:async()=>({authenticated:false})});
  script(home,'api.js');script(home,'shop-core.js');script(home,'storefront-online.js');script(home,'mobile.js');await settle();
  assert.equal(w.document.querySelectorAll('.mobile-bottom-nav>*').length,5);
  assert.ok($('drawer').classList.contains('open'));assert.equal($('drawer').inert,false);
  assert.equal(w.location.search,'?category=cat-1');assert.equal(w.location.hash,'#products');
  w.closeCart();await settle();assert.equal($('drawer').inert,true);
  $('mobileMenuButton').click();assert.equal($('mobileMenu').open,true);assert.match($('mobileCategoryLinks').textContent,/코코넛워터/);
  $('mobileMenu').querySelector('.mobile-menu-close').click();assert.equal($('mobileMenuButton').getAttribute('aria-expanded'),'false');
  w.addCart('P1001');await settle();assert.equal($('mobileCartCount').textContent,'1');assert.equal($('mobileCartCount').hidden,false);
  $('mobileCartLink').click();await settle();assert.ok($('drawer').classList.contains('open'));
  $('drawer').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await settle();assert.equal($('drawer').inert,true);
  home.window.close();

  const account=dom('mypage'),a=account.window;
  a.document.getElementById('rows').innerHTML='<tr><td>ON123</td><td>2026-09-19</td><td>상품 × 1</td><td>결제완료</td><td>배송중</td><td>배송중<div>송장 1234</div></td><td>10,000원</td><td><button>반품 신청</button></td></tr>';
  script(account,'mobile.js');await settle();
  assert.equal(a.document.querySelector('td:nth-child(6)').dataset.mobileLabel,'배송');
  assert.equal(a.document.querySelectorAll('td .mobile-cell-value').length,8);
  assert.match(a.document.querySelector('td:nth-child(6) .mobile-cell-value').textContent,/송장 1234/);
  a.document.getElementById('rows').innerHTML='<tr><td colspan="8">주문내역이 없습니다.</td></tr>';await settle();assert.equal(a.document.querySelectorAll('td .mobile-cell-value').length,1);
  account.window.close();

  const checkout=dom('checkout'),c=checkout.window,q=id=>c.document.getElementById(id),form=q('orderForm');
  script(checkout,'api.js');script(checkout,'mobile.js');script(checkout,'shipping-addresses.js');
  q('total').textContent='39,800원';await settle();assert.equal(q('mobilePayTotal').textContent,'39,800원');
  assert.equal(c.document.querySelectorAll('#payBtn').length,1);
  form.elements.namedItem('customerName').focus();assert.ok(c.document.body.classList.contains('mobile-editing'));
  form.elements.namedItem('customerName').blur();await new Promise(r=>setTimeout(r,0));assert.ok(!c.document.body.classList.contains('mobile-editing'));
  const original={id:'addr_a',customerName:'<img src=x onerror=alert(1)>',customerPhone:'01000000000',postcode:'63123',address1:'제주 테스트길',address2:'101호',deliveryMemo:'문 앞'};
  let rows=[original],calls=[],changed=0,fail=false,resolveLoad=null;
  c.AppAPI.api=async(path,options={})=>{
    calls.push({path,options});
    if(options.method==='DELETE'){rows=[];return {ok:true}}
    if(fail)throw new Error('연결 오류');
    if(resolveLoad)return new Promise(r=>{resolveLoad=r});
    return rows;
  };
  c.ShippingAddresses.mount({user:{authenticated:false},form,onChange(){}});assert.equal(q('shippingAddressBook').hidden,true);
  c.ShippingAddresses.mount({user:{authenticated:true,name:'회원',phone:'01012345678'},form,onChange:()=>changed++});await settle();
  assert.equal(q('shippingAddressBook').hidden,false);assert.equal(q('shippingAddressSelect').options.length,2);assert.equal(q('shippingAddressSelect').querySelector('img'),null);
  form.elements.namedItem('customerEmail').value='member@example.test';
  q('shippingAddressSelect').value='addr_a';q('shippingAddressSelect').dispatchEvent(new c.Event('change'));assert.equal(changed,1);
  for(const name of ['customerName','customerPhone','postcode','address1','address2','deliveryMemo'])assert.equal(form.elements.namedItem(name).value,original[name]);
  assert.equal(form.elements.namedItem('customerEmail').value,'member@example.test');
  q('newShippingAddress').click();assert.equal(changed,2);assert.equal(form.elements.namedItem('postcode').value,'');assert.equal(form.elements.namedItem('customerName').value,'회원');
  q('shippingAddressSelect').value='addr_a';q('shippingAddressSelect').dispatchEvent(new c.Event('change'));
  q('deleteShippingAddress').click();assert.equal(q('shippingDeleteConfirm').hidden,false);assert.ok(!calls.some(x=>x.options.method==='DELETE'));
  q('confirmShippingDelete').click();await settle();assert.ok(calls.some(x=>x.path.endsWith('/addr_a')&&x.options.method==='DELETE'));
  assert.equal(q('saveShippingAddress').checked,false);assert.equal(form.elements.namedItem('postcode').value,'63123');assert.equal(q('shippingAddressSelect').disabled,true);
  fail=true;q('reloadShippingAddresses').click();await settle();assert.match(q('shippingAddressError').textContent,/직접 입력/);assert.equal(form.elements.namedItem('customerName').disabled,false);
  fail=false;resolveLoad=true;q('reloadShippingAddresses').click();await settle();c.dispatchEvent(new c.Event('pagehide'));resolveLoad([original]);await settle();assert.equal(q('shippingAddressSelect').options.length,1);
  checkout.window.close();
  for(const page of ['index','detail','checkout','login','mypage','guest-order','return-request','board','chat','payment-success','payment-fail']){
    const html=read('static/'+page+'.html');assert.match(html,/viewport-fit=cover/);assert.match(html,/mobile\.css\?v=/);assert.match(html,/mobile\.js\?v=/);
  }
  assert.doesNotMatch(read('static/admin.html'),/assets\/mobile\.(css|js)/);
  assert.match(read('static/detail.html'),/<div class="purchase-actions"><button[^>]+onclick="buyNow\(\)"/);
  console.log('PASS: real DOM mobile navigation/cart/keyboard/cards, checkout amount reflection, address selection/recalculation hook/deletion/error/stale-response handling, guest and admin separation');
})().catch(e=>{console.error(e);process.exitCode=1});
