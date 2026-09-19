const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('static/assets/admin-events.js','utf8');
const settle=async()=>{for(let n=0;n<60;n++)await Promise.resolve()};
const shared=new Map(),locks={tail:Promise.resolve(),request(name,fn){const next=this.tail.then(fn);this.tail=next.catch(()=>{});return next}};
let serverTime=Date.parse('2026-09-19T06:00:00Z');
const base={adminId:'admin-a',orders:2,returns:0,exchanges:0,cancellations:0,groupChat:0,directChat:0,inquiry:0,board:0,roomUnread:{}};
function fixture(){
  const dom=new JSDOM(fs.readFileSync('static/admin.html','utf8'),{url:'https://shop.example.test/admin.html',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,doc=w.document,timers=new Map(),intervals=[],calls=[],observers=[];let serial=0,notes=0,data={...base},fail=false,hold=null;
  Object.defineProperty(w,'localStorage',{value:{getItem:k=>shared.get(k)||null,setItem:(k,v)=>shared.set(k,String(v))}});
  Object.defineProperty(w.navigator,'locks',{value:locks});
  let hidden=false,focused=true;
  Object.defineProperty(doc,'hidden',{get:()=>hidden});doc.hasFocus=()=>focused;
  w.HTMLElement.prototype.getClientRects=()=>[{}];
  w.setTimeout=(fn,ms)=>{timers.set(++serial,{fn,ms});return serial};w.clearTimeout=id=>timers.delete(id);w.setInterval=fn=>intervals.push(fn);
  w.IntersectionObserver=class {constructor(fn){this.fn=fn;this.targets=[];observers.push(this)}observe(el){this.targets.push(el)}disconnect(){this.targets=[]}emit(el){this.fn([{target:el,isIntersecting:true,intersectionRatio:1}])}};
  w.AudioContext=class {constructor(){this.state='suspended';this.currentTime=0;this.destination={}}async resume(){this.state='running'}createOscillator(){return {frequency:{value:0},connect(){},start(){notes++},stop(){}}}createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}}}};
  function response(){return {...data,liveChat:data.groupChat+data.directChat,communications:data.inquiry+data.board,returnTotal:data.returns+data.exchanges,updatedAt:new Date(++serverTime).toISOString()}}
  w.AppAPI={api:async(path,options={})=>{calls.push({path,options});if(fail)throw Error('offline');if(hold&&path.endsWith('event-counts')){const pending=hold;hold=null;return pending}if(options.method==='POST'){for(const item of options.body.items)data[item.kind]=0;return response()}return response()}};
  doc.getElementById('communications').classList.add('active');
  doc.getElementById('boardList').innerHTML='<div class="event-read-actions" data-event-kind="board" data-event-target="post" data-event-through="3"><span class="event-unread">미확인 1건</span><button data-event-confirm>확인</button></div>';
  w.eval(source);
  return {w,doc,calls,observers,intervals,timers,setData:x=>{data={...data,...x}},getData:response,fail:v=>{fail=v},hold:p=>{hold=p},notes:()=>notes,hide:v=>{hidden=v;doc.dispatchEvent(new w.Event('visibilitychange'))},focus:v=>{focused=v},async timersAt(ms){const batch=[...timers.entries()].filter(([,x])=>x.ms===ms);for(const [id,x] of batch){timers.delete(id);await x.fn()}await settle()},close:()=>dom.window.close()};
}
(async()=>{
  const t=fixture();await settle();const button=t.doc.getElementById('adminEventSound');
  assert.equal(t.notes(),0);assert.equal(t.doc.querySelector('[data-work-count=orders]').textContent,'2');
  button.click();await settle();assert.equal(t.notes(),2);assert.equal(button.getAttribute('aria-pressed'),'true');
  await t.w.AdminWorkCounts.refresh();await settle();assert.equal(t.notes(),2);
  t.setData({orders:3,returns:1});await t.w.AdminWorkCounts.refresh();await settle();assert.equal(t.notes(),4,'one chime for a batch of increases');
  t.setData({orders:1,returns:0});await t.w.AdminWorkCounts.refresh();await settle();assert.equal(t.notes(),4,'no chime for a decrease');
  t.fail(true);await t.w.AdminWorkCounts.refresh();assert.equal(t.doc.querySelector('[data-work-count=orders]').textContent,'—');
  t.fail(false);await t.w.AdminWorkCounts.refresh();await settle();assert.equal(t.notes(),4,'recovery does not replay old counts');
  button.click();await settle();t.setData({groupChat:1});await t.w.AdminWorkCounts.refresh();await settle();assert.equal(t.notes(),4,'mute persists');
  button.click();await settle();assert.equal(t.notes(),6);

  const other=fixture();other.setData({orders:1,groupChat:1});await settle();await other.w.AdminWorkCounts.refresh();other.doc.getElementById('adminEventSound').click();await settle();
  const before=t.notes()+other.notes();t.setData({directChat:1});other.setData({directChat:1});
  await Promise.all([t.w.AdminWorkCounts.refresh(),other.w.AdminWorkCounts.refresh()]);await settle();
  assert.equal(t.notes()+other.notes(),before+2,'two tabs play one chime for the same increase');

  t.setData({board:1});await t.w.AdminWorkCounts.refresh();await settle();
  const marker=t.doc.querySelector('[data-event-kind=board]');
  t.hide(true);await settle();t.observers.at(-1).emit(marker);await t.timersAt(700);await t.timersAt(250);assert.ok(!t.calls.some(x=>x.options.method==='POST'));
  t.hide(false);await settle();t.focus(false);t.observers.at(-1).emit(marker);await t.timersAt(700);await t.timersAt(250);assert.ok(!t.calls.some(x=>x.options.method==='POST'));
  t.focus(true);t.w.AdminNotifications.watchThreads();t.observers.at(-1).emit(marker);await t.timersAt(700);await t.timersAt(250);
  const read=t.calls.find(x=>x.options.method==='POST');assert.equal(read.options.body.adminId,'admin-a');assert.equal(read.options.body.items[0].through,3);assert.equal(t.doc.querySelector('[data-work-count=communications]').textContent,'0');assert.equal(marker.querySelector('[data-event-confirm]'),null);
  const live=t.doc.getElementById('liveChat');live.classList.add('active');const log=t.doc.createElement('div');live.append(log);
  Object.defineProperties(log,{clientHeight:{value:100},scrollHeight:{value:500},scrollTop:{value:0,writable:true}});
  const readCount=()=>t.calls.filter(x=>x.options.method==='POST').length;
  let n=readCount();t.w.AdminNotifications.chatVisible({room:'direct_x',kind:'DIRECT',through:7,log});await t.timersAt(250);assert.equal(readCount(),n,'older scroll position is not read');
  log.scrollTop=400;t.w.AdminNotifications.chatVisible({room:'direct_x',kind:'DIRECT',through:7,log});await t.timersAt(250);assert.equal(readCount(),n+1);
  t.w.AdminNotifications.chatVisible({room:'direct_x',kind:'DIRECT',through:7,log});await t.timersAt(250);assert.equal(readCount(),n+1,'seen messages do not keep posting receipts');
  // A slow poll from before acknowledgement cannot bring an old unread count back.
  let resolve;const stale=t.getData();stale.directChat=8;t.hold(new Promise(r=>resolve=r));const poll=t.w.AdminWorkCounts.refresh();await settle();
  t.w.AdminNotifications.confirm({kind:'directChat',target:'direct_x',through:8});await t.timersAt(250);resolve(stale);await poll;await settle();assert.equal(t.doc.querySelector('[data-work-count=directChat]').textContent,'0');
  other.close();t.close();
  console.log('PASS: baseline silence, increases only, mute/unlock, sound deduplication across tabs, recovery, visible-thread reads, chat scroll gating, monotonic client receipts and stale-poll exclusion');
})().catch(e=>{console.error(e);process.exitCode=1});
