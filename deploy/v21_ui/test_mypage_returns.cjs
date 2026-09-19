// Browser-independent UI regression checks using DOM stubs and the real page scripts.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
process.chdir(__dirname);
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {textContent:'', innerHTML:'', hidden:false, disabled:false, dataset:{}, attributes:{}, handlers:{}, classList:{add(){},remove(){},toggle(){}}, setAttribute(key,value){this.attributes[key]=value}, addEventListener(name,fn){this.handlers[name]=fn}});
  return elements.get(id);
}
const buttons = ['all','active','completed'].map(value => ({...element('filter-'+value), dataset:{returnFilter:value}}));
element('returnFilters').querySelectorAll = () => buttons;
const context = vm.createContext({window:{}, document:{cookie:'',getElementById:element}, console, setTimeout(){}, location:{}, encodeURIComponent, FormData:class{}, fetch:async()=>{throw Error('Unexpected network access')}});
vm.runInContext(fs.readFileSync('static/assets/api.js','utf8'), context);
context.AppAPI = context.window.AppAPI;
let response = [];
let fail = false;
context.AppAPI.api = async () => {if(fail)throw Error('offline');return response;};
vm.runInContext(fs.readFileSync('static/assets/return-progress.js','utf8'),context);context.ReturnProgress=context.window.ReturnProgress;
vm.runInContext(fs.readFileSync('static/assets/mypage-returns.js','utf8'), context);
const history = element('returnHistory');
const base = {requestType:'RETURN', status:'REFUNDED', requestNo:'R001', orderNo:'O001', refundStatus:'MANUAL_COMPLETED', itemAmount:20000, returnShippingFee:2000, refundAmount:18000, reasonCode:'CHANGE_MIND', reasonName:'단순 변심', createdAt:'2026-09-18T01:00:00', completedAt:'2026-09-18T03:00:00', receivedAt:'2026-09-18T02:00:00', items:[{name:'코코넛워터 2개입',qty:2,lineTotal:20000}], reasonDetail:'<img src=x onerror=alert(1)>', adminNote:'<script>alert(1)</script>'};
function filter(value){const button=buttons.find(b=>b.dataset.returnFilter===value);element('returnFilters').handlers.click({target:{closest:()=>button}});}
(async()=>{
  response = [base, {...base,requestNo:'R002',status:'REQUESTED',refundStatus:'PENDING_REVIEW',refundAmount:16000,completedAt:null}, {...base,requestNo:'E001',requestType:'EXCHANGE',status:'COMPLETED',refundAmount:999999}, {...base,requestNo:'R003',status:'REJECTED',refundStatus:'NOT_REQUESTED'}];
  await context.window.MyPageReturns.load();
  assert.match(element('returnSummary').textContent,/전체 3건 · 반품 완료 1건 · 환불 완료 합계 18,000원/);
  assert.match(history.innerHTML,/2개 · 20,000원/);
  assert.match(history.innerHTML,/환불 완료 금액/);
  assert.match(history.innerHTML,/반품 완료일/);
  assert.match(history.innerHTML,/반품배송비 차감액/);
  assert.match(history.innerHTML,/2,000원/);
  assert.match(history.innerHTML,/상세 반품 정보/);
  assert.match(history.innerHTML,/&lt;img/);
  assert.doesNotMatch(history.innerHTML,/<script>|<img|E001/);
  filter('completed'); assert.match(history.innerHTML,/R001/); assert.doesNotMatch(history.innerHTML,/R002|R003/);
  filter('active'); assert.match(history.innerHTML,/R002/); assert.doesNotMatch(history.innerHTML,/R001|R003/);
  filter('all'); assert.match(history.innerHTML,/R003/);
  response=[{...base,requestNo:'AUTO',refundStatus:'COMPLETED',returnShippingFee:0,refundAmount:20000}];
  await element('refreshReturns').handlers.click();
  assert.match(element('returnSummary').textContent,/20,000원/);
  assert.match(history.innerHTML,/AUTO/);
  // A refund flag alone, or a terminal status without receipt, cannot close a return.
  for(const mismatch of [
    {...base,status:'APPROVED',receivedAt:null},
    {...base,status:'COLLECTING',receivedAt:null,refundStatus:'COMPLETED'},
    {...base,receivedAt:null},
    {...base,status:'RECEIVED',refundStatus:'MANUAL_PENDING'},
    {...base,status:'APPROVED'},
    {...base,receiptConfirmed:false},
    {...base,refundCompleted:false},
    {...base,status:'REJECTED'},
    {...base,status:'CANCELED'},
  ]){
    response=[mismatch];filter('all');await context.window.MyPageReturns.load();
    assert.match(element('returnSummary').textContent,/반품 완료 0건 · 환불 완료 합계 0원/);
    assert.doesNotMatch(history.innerHTML,/환불 완료 금액|반품·환불 완료|판매자가 환불 처리를 완료/);
    filter('completed');assert.match(history.innerHTML,/완료된 반품 내역이 없습니다/);
  }
  response=[{...base,receivedAt:null,refundStatus:'COMPLETED',status:'COLLECTING'}];filter('active');await context.window.MyPageReturns.load();
  assert.match(history.innerHTML,/입고 확인 전/);assert.match(history.innerHTML,/환불 예정 금액/);
  response=[base];filter('completed');await context.window.MyPageReturns.load();assert.match(history.innerHTML,/환불 완료 금액/);
  filter('all');
  fail=true; await context.window.MyPageReturns.load();
  assert.equal(element('returnError').hidden,false);
  assert.equal(element('refreshReturns').disabled,false);
  assert.equal(history.attributes['aria-busy'],'false');
  assert.equal(history.innerHTML,'');
  fail=false;response=[];await element('refreshReturns').handlers.click();
  assert.equal(element('returnError').hidden,true);
  assert.match(history.innerHTML,/반품 내역이 없습니다/);
  filter('completed');assert.match(history.innerHTML,/완료된 반품 내역이 없습니다/);
  // The history button must remain usable when a fully refunded order is ineligible for a new request.
  const page=fs.readFileSync('static/mypage.html','utf8');
  const inline=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1].replace('load().catch(e=>toast(e.message));','');
  for(const id of ['pwForm','logoutBtn'])context[id]=element(id);
  vm.runInContext(inline, context);
  const html=vm.runInContext("actionHtml({orderNo:'O-COMPLETE',paymentStatus:'REFUNDED',orderStatus:'RETURNED'})", context);
  assert.match(html,/반품·교환 내역 확인/);
  assert.match(html,/return-request.html\?orderNo=O-COMPLETE#historyBox/);
  assert.match(html,/disabled>반품 신청/);
  console.log('PASS: completed/pending/rejected states, exchange exclusion, totals, filters, refresh, failures, escaping and full-refund history access');
})().catch(error=>{console.error(error);process.exitCode=1;});
