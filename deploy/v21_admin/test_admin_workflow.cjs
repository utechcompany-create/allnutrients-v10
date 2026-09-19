// Run the deployed controllers with an isolated DOM/API substitute, without a browser or network.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
process.chdir(__dirname);
const settle=async()=>{for(let i=0;i<20;i++)await Promise.resolve()};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
(async()=>{
  const badges=['orders','returns','exchanges','cancellations'].map(key=>({dataset:{workCount:key},textContent:'—',attrs:{},classList:{toggle(k,v){this[k]=v},remove(k){this[k]=false}},setAttribute(k,v){this.attrs[k]=v}}));
  let payload={orders:12,returns:2,exchanges:0,cancellations:1},calls=0,error=false,timer;
  const events={},document={hidden:false,querySelectorAll:()=>badges,addEventListener(k,f){events[k]=f}},window={addEventListener(k,f){events[k]=f}};
  vm.runInNewContext(fs.readFileSync('static/assets/admin-workflow.js','utf8'),{document,window,AppAPI:{api:async path=>{assert.equal(path,'/api/admin/work-counts');calls++;if(error)throw Error('offline');return payload}},setInterval(f,ms){assert.equal(ms,30000);timer=f}});
  await settle();assert.deepEqual(badges.map(x=>x.textContent),['12','2','0','1']);
  assert.equal(badges[0].classList['has-work'],true);assert.equal(badges[2].classList['has-work'],false);
  assert.match(badges[0].attrs['aria-label'],/미발송 주문 12건/);
  document.hidden=true;await timer();assert.equal(calls,1);
  document.hidden=false;payload={orders:0,returns:1,exchanges:1,cancellations:0};await events.visibilitychange();
  assert.deepEqual(badges.map(x=>x.textContent),['0','1','1','0']);
  error=true;await events.focus();assert.equal(badges[0].textContent,'—');assert.match(badges[0].title,/불러오지/);
  error=false;await window.AdminWorkCounts.refresh();assert.equal(badges[0].textContent,'0');

  const page=fs.readFileSync('static/returns-admin.html','utf8');
  const receive=page.slice(page.indexOf('const receiving=new Set();'),page.indexOf('async function refundReq(no)'));
  let confirmed=true,fail=false,post=[],prompts=[],toasts=[],refreshes=0,release;
  const rows=[{requestNo:'R1',requestType:'RETURN',paymentMethod:'CASH',refundAmount:18000,returnShippingFee:2000}];
  const button={dataset:{receiveNo:'R1'},disabled:false};
  const context=vm.createContext({rows,document:{querySelectorAll:()=>[button]},money:n=>n.toLocaleString('ko-KR')+'원',confirm:s=>{prompts.push(s);return confirmed},api:async(path,options)=>{post.push({path,options});if(release)await release;if(fail)throw Error('환불 요청 실패')},load:async()=>{refreshes++},toastMsg:s=>toasts.push(s)});
  vm.runInContext(receive,context);
  confirmed=false;await context.receive('R1');assert.equal(post.length,0);
  confirmed=true;let resolve;release=new Promise(r=>resolve=r);
  const one=context.receive('R1');await settle();assert.equal(button.disabled,true);
  await context.receive('R1');assert.equal(post.length,1,'repeated clicks cannot create another request');
  resolve();await one;release=null;
  assert.equal(post[0].options.body.manualRefundConfirmed,true);assert.match(prompts.at(-1),/실제 계좌 송금을 완료/);assert.match(prompts.at(-1),/18,000원/);
  assert.equal(button.disabled,false);assert.equal(refreshes,1);assert.match(toasts.at(-1),/입고 및 환불 완료/);
  rows[0].paymentMethod='CARD';fail=true;await context.receive('R1');assert.equal(post.at(-1).options.body.manualRefundConfirmed,false);
  assert.equal(button.disabled,false);assert.equal(refreshes,1);assert.equal(toasts.at(-1),'환불 요청 실패');
  fail=false;rows[0].requestType='EXCHANGE';await context.receive('R1');assert.doesNotMatch(prompts.at(-1),/환불을 실행/);assert.match(toasts.at(-1),/재배송/);

  const admin=fs.readFileSync('static/admin.html','utf8');
  const render=admin.slice(admin.indexOf('function renderOrders()'),admin.indexOf('async function setOrderStatus'));
  const order={orderNo:'O1',createdAt:'2026-09-19',customerName:'고객',customerEmail:'',customerPhone:'',totalAmount:10000,paymentMethod:'CARD',paymentStatus:'PAID',orderStatus:'PAID',items:[]};
  const orders=[order,{...order,orderNo:'O2',cancelRequest:{status:'REQUESTED',reason:'단순변심'}},{...order,orderNo:'O3',orderStatus:'SHIPPED',shipment:{trackingNumber:'TRACK',status:'SHIPPED'}},{...order,orderNo:'O4',paymentStatus:'CANCELED',orderStatus:'CANCELED'}];
  const scope={value:'cancel'},list={innerHTML:''};
  const filtered=vm.createContext({orders,orderList:list,document:{getElementById:id=>{assert.equal(id,'orderScope');return scope}},esc,money:n=>n+'원'});
  vm.runInContext(render,filtered);filtered.renderOrders();assert.match(list.innerHTML,/O2/);assert.doesNotMatch(list.innerHTML,/O1|O3|O4/);
  scope.value='pending';filtered.renderOrders();assert.match(list.innerHTML,/O1/);assert.doesNotMatch(list.innerHTML,/O2|O3|O4/);
  scope.value='all';filtered.renderOrders();for(const no of ['O1','O2','O3','O4'])assert.ok(list.innerHTML.includes(no));
  console.log('PASS: automatic counters, visibility/focus refresh, error/recovery, receipt confirmation, duplicate/error controls, exchange actions, and order/cancellation filters');
})().catch(e=>{console.error(e);process.exitCode=1});
