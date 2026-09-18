// Local, network-free regression tests for the actual request-page controller.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
process.chdir(__dirname);
const script=fs.readFileSync('static/assets/return-request.js','utf8');
const page=fs.readFileSync('static/return-request.html','utf8');
const sample={orderNo:'O1',paymentStatus:'PAID',orderStatus:'PREPARING',paymentMethod:'CARD',shipment:{trackingNumber:'LOCAL-TRACK',status:'PREPARING'},createdAt:'2026-09-18T01:00:00',totalAmount:40000,items:[{orderItemId:1,name:'주스 <img onerror=1>',qty:4,price:10000,lineTotal:40000,returnFee:4000,exchangeFee:5000,bundleAllowed:true,bundleCapacity:2}]};
const completed={requestNo:'R-DONE',requestType:'RETURN',status:'REFUNDED',refundStatus:'COMPLETED',refundAmount:40000,returnShippingFee:0,items:sample.items,completedAt:'2026-09-18T01:00:00',attachments:[]};
const clone=value=>JSON.parse(JSON.stringify(value));
async function settle(){for(let i=0;i<20;i++)await Promise.resolve();}
function make({search='',authenticated=true,record=sample,history=[],failHistory=false}={}){
  const elements=new Map(),controls=new Map(),guest=new Map(),calls=[],picks=[],quantities=[];
  let errors=failHistory;
  function element(id){if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',hidden:false,disabled:false,files:[],dataset:{},classList:{add(){},remove(){}},scrollIntoView(){}});return elements.get(id);}
  for(const m of page.matchAll(/<[^>]+id="([^"]+)"[^>]*>/g)){const e=element(m[1]);e.hidden=/\shidden(?:[\s>])/.test(m[0]);e.disabled=/\sdisabled(?:[\s>])/.test(m[0]);}
  const control=name=>{if(!controls.has(name))controls.set(name,element('field-'+name));return controls.get(name);};
  const guestControl=name=>{if(!guest.has(name))guest.set(name,element('guest-'+name));return guest.get(name);};
  ['requestType','reasonCode','reasonDetail','customerNote','refundBankName','refundBankAccount','refundBankHolder'].forEach(control);
  control('requestType').value='RETURN';
  element('requestForm').elements={namedItem:control};element('guestForm').elements={namedItem:guestControl};
  element('requestForm').reset=()=>{for(const c of controls.values())c.value='';control('requestType').value='RETURN';};
  Object.defineProperty(element('itemChoices'),'innerHTML',{get(){return this.html||'';},set(html){this.html=html;picks.length=0;quantities.length=0;for(const m of html.matchAll(/<input[^>]+>/g)){const attrs=Object.fromEntries([...m[0].matchAll(/([\w-]+)="([^"]*)"/g)].map(a=>[a[1],a[2]]));if(!['pick','qty'].includes(attrs.class))continue;const c={value:attrs.value||'',checked:false,disabled:/\sdisabled[\s>]/.test(m[0]),dataset:{},max:attrs.max};for(const [key,val]of Object.entries(attrs))if(key.startsWith('data-'))c.dataset[key.slice(5).replace(/-([a-z])/g,(_,s)=>s.toUpperCase())]=val;(attrs.class==='pick'?picks:quantities).push(c);}}});
  const url=new URL('https://local.invalid/return-request.html'+search);
  const api=async(path,options={})=>{
    calls.push({path,...options});
    if(path==='/api/auth/me')return {authenticated};
    if(path==='/api/orders/my')return [record];
    if(path.startsWith('/api/orders/'))return clone(record);
    if(path.startsWith('/api/return-reasons'))return [{code:'CHANGE_MIND',name:'단순 변심',responsibility:'CUSTOMER'},{code:'DEFECT',name:'상품 불량',responsibility:'SELLER'}];
    if(path.startsWith('/api/returns/my')||path==='/api/returns/guest-list'){if(errors)throw Error('History failed');return clone(history);}
    if(path==='/api/returns'||path==='/api/returns/guest'){history.unshift({...completed,...options.body,status:'REQUESTED',requestNo:'R-NEW'});return history[0];}
    throw Error('Unexpected endpoint '+path);
  };
  const context=vm.createContext({AppAPI:{api,esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),money:n=>Number(n||0).toLocaleString('ko-KR')+'원'},document:{getElementById:element,querySelectorAll:s=>s==='.pick:checked'?picks.filter(p=>p.checked):s==='.pick'?picks:s==='.qty'?quantities:[],querySelector:s=>quantities.find(x=>x.dataset.id===s.match(/data-id="([^"]+)"/)[1])},window:{history:{replaceState(){}}},location:url,URL,URLSearchParams,sessionStorage:{getItem(){return '';}},setTimeout(){},FormData:class{constructor(){this.values=new Map([...controls].filter(([,v])=>!v.disabled).map(([k,v])=>[k,v.value]));}get(name){return this.values.get(name)||null;}},console});
  vm.runInContext(script,context);
  return {element,control,guestControl,calls,picks,quantities,setHistoryFailure:v=>errors=v};
}
(async()=>{
  let t=make();await settle();
  assert.equal(t.element('memberOrders').hidden,false);
  assert.equal(t.element('guestAuth').hidden,true);
  assert.equal(t.element('requestBox').hidden,false);
  assert.equal(t.element('requestFields').disabled,true);
  assert.match(t.element('orderSelect').innerHTML,/O1/);
  t.element('orderSelect').value='O1';await t.element('orderSelect').onchange();
  assert.equal(t.element('requestFields').disabled,false,'tracking number alone must allow the request');
  assert.match(t.element('itemChoices').innerHTML,/&lt;img/);
  assert.equal(t.element('historyBox').hidden,false);
  t.picks[0].checked=true;t.picks[0].onchange();t.quantities[0].value='2';
  t.control('reasonCode').value='CHANGE_MIND';t.control('reasonCode').onchange();
  assert.match(t.element('feeNotice').innerHTML,/2,000원/);
  await t.element('requestForm').onsubmit({preventDefault(){}});
  let sent=t.calls.find(x=>x.path==='/api/returns');assert.equal(sent.body.requestType,'RETURN');assert.equal(sent.body.items[0].qty,2);
  assert.match(t.element('requestHistoryList').innerHTML,/R-NEW/);
  assert.equal(t.quantities[0].max,'2','pending returns reduce available quantity');

  t=make({search:'?orderNo=O1&type=EXCHANGE',record:{...sample,paymentMethod:'CASH'}});await settle();
  assert.equal(t.element('requestFields').disabled,false);
  assert.equal(t.element('cashRefund').hidden,true);
  assert.equal(t.control('refundBankAccount').required,false);
  t.picks[0].checked=true;t.picks[0].onchange();t.control('reasonCode').value='DEFECT';
  await t.element('requestForm').onsubmit({preventDefault(){}});
  sent=t.calls.find(x=>x.path==='/api/returns');assert.equal(sent.body.requestType,'EXCHANGE');

  t=make({search:'?orderNo=O1',record:{...sample,paymentStatus:'REFUNDED'},history:[completed]});await settle();
  assert.equal(t.element('requestBox').hidden,false);assert.equal(t.element('requestFields').disabled,true);
  assert.match(t.element('requestNotice').textContent,/환불이 완료/);
  assert.match(t.element('requestHistoryList').innerHTML,/R-DONE/);
  t=make({search:'?orderNo=O1',record:{...sample,shipment:null}});await settle();assert.equal(t.element('requestFields').disabled,true);assert.match(t.element('requestNotice').textContent,/송장번호/);
  t=make({search:'?orderNo=O1',history:[{...completed,requestType:'EXCHANGE',status:'COMPLETED'}]});await settle();assert.equal(t.quantities[0].max,'4');
  t=make({search:'?orderNo=O1',failHistory:true});await settle();assert.equal(t.element('pageError').hidden,false);assert.equal(t.element('requestFields').disabled,true);t.setHistoryFailure(false);await t.element('retryPage').onclick();assert.equal(t.element('requestFields').disabled,false);

  t=make({search:'?guest=1',authenticated:true});await settle();
  assert.equal(t.element('guestAuth').hidden,false);assert.equal(t.element('memberOrders').hidden,true);
  assert.equal(t.element('requestBox').hidden,false);
  for(const [name,value]of Object.entries({orderNo:'O1',email:'fixture@example.com',phone:'01000000000',pin:'0000'}))t.guestControl(name).value=value;
  await t.element('guestForm').onsubmit({preventDefault(){}});
  assert.equal(t.element('requestFields').disabled,false);
  assert(t.calls.some(x=>x.path==='/api/orders/guest-lookup'));
  t.picks[0].checked=true;t.picks[0].onchange();t.control('reasonCode').value='DEFECT';
  await t.element('requestForm').onsubmit({preventDefault(){}});
  assert(t.calls.some(x=>x.path==='/api/returns/guest'&&x.body.orderNo==='O1'));
  console.log('PASS: direct entry, member selection, guest flow, tracking-only eligibility, return/exchange submission, completion history, remaining quantity and failure retry');
})().catch(e=>{console.error(e);process.exitCode=1;});
