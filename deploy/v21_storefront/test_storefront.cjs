// Run from an assembled build with NODE_PATH pointing to test-only jsdom.
const fs=require('node:fs'), assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=p=>fs.readFileSync(p,'utf8');
const settle=async()=>{for(let n=0;n<25;n++)await Promise.resolve()};
function dom(page,query=''){
 const d=new JSDOM(read('static/'+page+'.html'),{url:'https://shop.test/'+page+'.html'+query,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:new VirtualConsole()});
 d.window.matchMedia=()=>({matches:false,addEventListener(){}});
 for(const form of d.window.document.forms)for(const field of form.elements)if(field.name&&!form[field.name])Object.defineProperty(form,field.name,{value:field});
 return d;
}
function script(d,name){d.window.eval(read('static/assets/'+name))}
function inline(d){for(const el of d.window.document.querySelectorAll('script:not([src])'))d.window.eval(el.textContent+(d.window.document.body.dataset.shopPage==='checkout'?"\nwindow.setCouponForTest=list=>{couponList=list;couponSelect.innerHTML='<option value=cp>coupon</option>';recalc()};":''))}
async function checkout({pg=false,bank=false,sdk=true}={}){
 const d=dom('checkout'),w=d.window;
 script(d,'api.js');script(d,'shop-core.js');script(d,'checkout-readiness.js');
 w.localStorage.setItem(w.ShopCore.KEYS.cart,JSON.stringify({P1001:1}));
 if(sdk)w.TossPayments=()=>({payment(){return {requestPayment:async()=>{}}}});
 w.ShippingAddresses={mount(){}};
 w.AppAPI.api=async url=>url==='/api/auth/me'?{authenticated:false}:{tossEnabled:pg,bank:bank?{name:'Test bank',account:'000',holder:'Test'}:{},commerce:{shippingFee:3000,freeShippingThreshold:50000}};
 inline(d);await settle();return d;
}
(async()=>{
 for(const loggedIn of [false,true]){
  const d=dom('index');d.window.AppAPI={api:async()=>({authenticated:loggedIn})};script(d,'account-nav.js');await settle();
  const link=d.window.document.getElementById('accountLink');assert.equal(link.textContent,loggedIn?'마이페이지':'로그인/회원가입');assert.ok(link.href.endsWith(loggedIn?'mypage.html':'login.html'));d.window.close();
 }
 const login=dom('login','?next=https://outside.test/'),l=login.window;
 assert.match(l.document.title,/로그인\/회원가입/);assert.ok(l.document.querySelector('[href="#registerSection"]'));
 let resolve,calls=0;l.AppAPI={api:()=>{calls++;return new Promise((r,j)=>{resolve=j})}};script(login,'login-access.js');
 const form=l.document.getElementById('loginForm');form.email.value='test@example.test';form.password.value='test-pass';
 form.dispatchEvent(new l.Event('submit',{cancelable:true}));form.dispatchEvent(new l.Event('submit',{cancelable:true}));assert.equal(calls,1);
 resolve(new Error('다시 확인해 주세요.'));await settle();assert.equal(form.querySelector('[role=alert]').textContent,'다시 확인해 주세요.');assert.equal(form.querySelector('button').disabled,false);login.window.close();
 // Validate the actual redirect sanitizer without submitting any credentials.
 const fn=read('static/assets/login-access.js').match(/function safeNext\(value\) \{[\s\S]*?\n  \}/)[0];
 const getNext=new Function('URL','location',fn+';return safeNext;')(URL,{href:'https://shop.test/login.html',origin:'https://shop.test'});
 for(const next of ['https://outside.test/','//outside.test','javascript:alert(1)','https://user@shop.test/'])assert.equal(getNext(next),'mypage.html');
 assert.equal(getNext('/detail.html?id=P1001#reviewPurchases'),'/detail.html?id=P1001#reviewPurchases');
 assert.equal(getNext('checkout.html'),'/checkout.html');
 for(const scenario of [{pg:false,bank:false},{pg:false,bank:true},{pg:true,bank:false},{pg:true,bank:true,sdk:false}]){
  const d=await checkout(scenario),w=d.window,$=id=>w.document.getElementById(id);
  const canPay=scenario.bank||(scenario.pg&&scenario.sdk!==false);
  assert.equal($('payBtn').disabled,!canPay);assert.equal($('checkoutMemberEntry').hidden,false);
  assert.equal(w.document.querySelector('[data-method="CARD"]').disabled,!(scenario.pg&&scenario.sdk!==false));
  if(!canPay)assert.match($('pgHint').textContent,/準備|준비/);
  if(scenario.bank)assert.equal(w.document.querySelector('[data-method="CASH"]').disabled,false);
  // Displayed coupon and total must match the merchandise-only server formula.
  w.setCouponForTest([{id:'cp',discountType:'PERCENT',value:10,minOrder:0}]);
  assert.equal($('couponDiscount').textContent,'-1,590원');assert.equal($('total').textContent,'17,310원');
  w.setCouponForTest([{id:'cp',discountType:'PERCENT',value:10,minOrder:18000}]);assert.equal($('couponDiscount').textContent,'-0원');
  w.setCouponForTest([{id:'cp',discountType:'FIXED',value:20000,minOrder:0}]);assert.equal($('couponDiscount').textContent,'-18,900원');assert.equal($('total').textContent,'0원');
  w.setCouponForTest([{id:'cp',discountType:'PERCENT',value:10,minOrder:0,maxDiscount:1000}]);assert.equal($('couponDiscount').textContent,'-1,000원');
  d.window.close();
 }
 let orders=0,reject;
 const single=dom('checkout'),s=single.window;
 script(single,'api.js');script(single,'shop-core.js');script(single,'checkout-readiness.js');s.localStorage.setItem(s.ShopCore.KEYS.cart,JSON.stringify({P1001:1}));
 s.ShippingAddresses={mount(){}};s.TossPayments=()=>({payment(){return {requestPayment:async()=>{}}}});
 s.AppAPI.api=(url)=>{
  if(url==='/api/auth/me')return Promise.resolve({authenticated:false});
  if(url==='/api/config')return Promise.resolve({tossEnabled:true,bank:{},commerce:{shippingFee:3000,freeShippingThreshold:50000}});
  if(url==='/api/orders'){orders++;return new Promise((r,j)=>{reject=j})}
  throw new Error(url);
 };
 inline(single);await settle();
 const f=s.document.getElementById('orderForm');for(const [key,value] of Object.entries({customerName:'Local test',customerPhone:'01000000000',customerEmail:'test@example.test',postcode:'12345',address1:'Local test address',guestPin:'1234',guestPinConfirm:'1234'}))f.elements.namedItem(key).value=value;
 const a=s.placeOrder(),b=s.placeOrder();await settle();assert.equal(orders,1);assert.equal(s.document.getElementById('payBtn').disabled,true);
 reject(new Error('Local simulated order failure'));await Promise.all([a,b]);assert.equal(s.document.getElementById('payBtn').disabled,false);assert.match(s.document.getElementById('checkoutError').textContent,/simulated/);single.window.close();
 for(const {stock,status,q,valid} of [{stock:10,status:'판매중',q:'1.5',valid:false},{stock:10,status:'판매중',q:'11',valid:false},{stock:0,status:'품절',q:'1',valid:false},{stock:10,status:'판매중지',q:'1',valid:false},{stock:10,status:'판매중',q:'2',valid:true}]){
  const detail=dom('detail','?id=P1001'),v=detail.window;script(detail,'api.js');script(detail,'shop-core.js');
  const products=v.ShopCore.productList();products[0].stock=stock;products[0].status=status;v.ShopCore.productList=()=>products;
  v.AppAPI.api=async()=>[];v.PrivateInquiryUI={watch(){},card(){return ''}};inline(detail);v.document.getElementById('qty').value=q;
  assert.equal(v.putCart(false),valid);assert.equal(Boolean(v.localStorage.getItem(v.ShopCore.KEYS.cart)),valid);
  const before=v.location.href;v.buyNow();if(!valid)assert.equal(v.location.href,before);detail.window.close();
 }
 console.log('PASS: signup entry, safe return links, auth/order repeat-click guards, payment readiness, coupon totals, stock/quantity validation');
})().catch(e=>{console.error(e);process.exit(1)});
