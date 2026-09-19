const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
process.chdir(__dirname);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const settle=async()=>{for(let i=0;i<40;i++)await Promise.resolve()};
function element(){let text='';const children={},listeners={},classes=new Set();return {value:'',disabled:false,hidden:false,scrollHeight:100,scrollTop:0,clientHeight:100,
 get innerHTML(){return text},set innerHTML(v){text=v},get textContent(){return text},set textContent(v){text=v},
 classList:{toggle(k,on){if(on)classes.add(k);else classes.delete(k)},contains:k=>classes.has(k)},focus(){},setAttribute(){},getAttribute(){},
 querySelector(q){return children[q]||(children[q]=element())},addEventListener(k,fn){listeners[k]=fn},listeners};}
function chatContext({admin=true,role='admin'}={}){
 const root=element(),events={},intervals=new Map(),calls=[],streams=[];let timerId=0,nonce=0,authenticated=true,hold=null;
 const group={id:'all',kind:'GROUP',name:'전체 대화방'},direct={id:'direct_owner',kind:'DIRECT',name:'고객님'};
 const m=(id,content,isMine=false)=>({id,content,isMine,senderName:'<고객>',senderRole:'customer',createdAt:'2026-09-19T01:00:00Z'});
 const history={all:[m(1,'공개 대화')],direct_owner:[m(2,'SECRET_PRIVATE')]};
 class EventSource {constructor(url){this.url=url;this.listeners={};this.closed=false;streams.push(this)}addEventListener(k,fn){this.listeners[k]=fn}close(){this.closed=true}emit(k,data){this.listeners[k]?.({data:JSON.stringify(data)})}}
 const document={hidden:false,addEventListener(k,fn){events[k]=fn}};
 const window={EventSource,addEventListener(k,fn){events[k]=fn}};
 const fetch=async(path,options={})=>{calls.push({path,options});let data;
   if(path==='/api/auth/me')data={authenticated,id:'viewer',role};
   else if(path==='/api/admin/users')data=[{id:'owner',role:'customer',isActive:true,name:'고객',email:'owner@example.test'}];
   else if(path==='/api/chat/rooms')data=[group,direct];
   else if(path==='/api/chat/rooms?mine=true')data=[group,direct];
   else if(path==='/api/chat/rooms/direct')data=direct;
   else {const url=new URL(path,'https://test.invalid'),roomId=url.pathname.split('/')[4];
     if(options.method==='POST'){const body=JSON.parse(options.body);data=m(4,body.content,true)}
     else if(hold&&roomId==='direct_owner'){const promise=hold;hold=null;data=await promise}
     else {const after=Number(url.searchParams.get('after')||0);data={room:roomId==='all'?group:direct,messages:history[roomId].filter(x=>x.id>after),hasOlder:false}}
   }return {ok:true,status:200,json:async()=>data};
 };
 const ctx=vm.createContext({window,document,AppAPI:{esc,cookie:()=>''},fetch,EventSource,crypto:{randomUUID:()=>String(++nonce)},setInterval(fn){intervals.set(++timerId,fn);return timerId},clearInterval(id){intervals.delete(id)},console});
 vm.runInContext(fs.readFileSync('static/assets/chat.js','utf8'),ctx);
 if(!admin){const query=root.querySelector.bind(root);root.querySelector=q=>q==='.chat-room-list'?null:query(q)}
 return {chat:window.ChatUI.mount(root,{admin}),root,events,document,streams,calls,history,m,intervals,setAuthenticated(v){authenticated=v},defer(p){hold=p}};
}
(async()=>{
 const t=chatContext(),q=s=>t.root.querySelector(s),log=q('.chat-log');
 await t.chat.open('GROUP');assert.match(log.innerHTML,/공개 대화/);assert.equal(t.streams.length,1);
 assert.match(q('.chat-notice').textContent,/모든 회원/);
 t.streams[0].emit('ready',{});assert.equal(q('.chat-status').textContent,'실시간 연결됨');
 q('textarea').value='<img src=x onerror=alert(1)>';
 await q('.chat-compose').onsubmit({preventDefault(){}});
 assert.match(log.innerHTML,/&lt;img/);assert.doesNotMatch(log.innerHTML,/<img/);
 assert.equal(t.calls.find(x=>x.options.method==='POST').options.headers['Content-Type'],'application/json');
 // A locally acknowledged send must not skip a peer message that arrived just before it.
 t.history.all.push(t.m(3,'동시에 도착한 메시지'),t.m(4,'<img src=x onerror=alert(1)>',true));
 for(const fn of [...t.intervals.values()])await fn();await settle();
 assert.match(log.innerHTML,/동시에 도착한 메시지/);assert.equal((log.innerHTML.match(/&lt;img/g)||[]).length,1);
 await t.chat.open('DIRECT');assert.match(log.innerHTML,/SECRET_PRIVATE/);assert.ok(t.streams[0].closed);
 assert.match(q('.chat-notice').textContent,/해당 고객과 관리자만/);
 let resolve;t.defer(new Promise(r=>resolve=r));const pending=t.chat.open('DIRECT');await settle();
 await t.chat.open('GROUP');resolve({room:{id:'direct_owner',name:'고객님'},messages:[t.m(5,'SECRET_DELAYED')],hasOlder:false});await pending;
 assert.doesNotMatch(log.innerHTML,/SECRET_/);
 // Hidden tabs and expired sessions must clear conversation content and close the stream.
 t.document.hidden=true;t.events.visibilitychange();assert.equal(log.innerHTML,'');assert.ok(t.streams.at(-1).closed);
 t.setAuthenticated(false);t.document.hidden=false;t.events.visibilitychange();await settle();
 assert.equal(log.innerHTML,'');assert.ok(q('textarea').disabled);assert.match(q('.chat-error').textContent,/로그인/);
 t.chat.close();assert.equal(t.intervals.size,0);
 // Storefront mode stays a member form for both member and administrator logins.
 for(const role of ['customer','admin']){
   const member=chatContext({admin:false,role}),el=q=>member.root.querySelector(q);
   assert.match(member.root.innerHTML,/member-chat-layout/);
   assert.doesNotMatch(member.root.innerHTML,/<aside|chat-room-list|chat-start|고객 선택|새 상담 시작/);
   await member.chat.open('GROUP');assert.match(el('.chat-log').innerHTML,/공개 대화/);
   await member.chat.open('DIRECT');assert.match(el('.chat-log').innerHTML,/SECRET_PRIVATE/);
   assert.equal(el('.chat-heading h2').textContent,'관리자 1:1 상담');
   assert.match(el('.chat-notice').textContent,/나와 관리자만/);
   assert.equal(el('textarea').disabled,false);
   assert.ok(member.calls.some(x=>x.path==='/api/chat/rooms?mine=true'));
   assert.ok(!member.calls.some(x=>x.path.startsWith('/api/admin/')||x.path==='/api/chat/rooms'));
   assert.equal(member.calls.find(x=>x.path==='/api/chat/rooms/direct').options.body,'{}');
   el('textarea').value='나의 상담 내용';await el('.chat-compose').onsubmit({preventDefault(){}});
   assert.match(el('.chat-log').innerHTML,/나의 상담 내용/);
   member.chat.close();assert.equal(member.intervals.size,0);
 }
 const pageSource=fs.readFileSync('static/assets/member-chat.js','utf8');
 for(const role of ['customer','admin','anonymous']){
   const root=element(),greeting=element(),tabs=element(),buttons=[{...element(),dataset:{kind:'GROUP'}},{...element(),dataset:{kind:'DIRECT'}}],mounts=[],opened=[],location={href:''};
   await vm.runInNewContext(pageSource,{document:{getElementById:id=>id==='customerChat'?root:greeting,querySelector:()=>tabs,querySelectorAll:()=>buttons},location,AppAPI:{api:async()=>({authenticated:role!=='anonymous',role,name:'회원'})},ChatUI:{mount:(target,options)=>{mounts.push(options);return {open:async kind=>opened.push(kind)}}}});
   if(role==='anonymous'){assert.equal(mounts.length,0);assert.equal(location.href,'login.html?next=chat.html')}
   else{assert.equal(mounts.length,1);assert.equal(mounts[0].admin,false);assert.deepEqual(opened,['GROUP']);tabs.onclick({target:{closest:()=>buttons[1]}});assert.deepEqual(opened,['GROUP','DIRECT'])}
 }
 const denied=chatContext({admin:true,role:'customer'});await denied.chat.open('DIRECT');assert.ok(!denied.calls.some(x=>x.path.startsWith('/api/admin/')));denied.chat.close();
 const admin=fs.readFileSync('static/admin.html','utf8');
 assert.match(admin,/id="chatMenuToggle"[^>]*>(?:<span>)?실시간 대화방/);
 assert.match(admin,/data-chat-kind="GROUP"[^>]*>(?:<span>)?전체 대화방/);assert.match(admin,/data-chat-kind="DIRECT"[^>]*>(?:<span>)?1:1 대화방/);
 assert.match(admin,/data-view="sales">매출 관리/);assert.match(admin,/주문일 기준\(한국시간\)/);
 for(const page of ['mypage.html','board.html'])assert.match(fs.readFileSync('static/'+page,'utf8'),/href="chat.html">실시간 대화방/);
 console.log('PASS: separate member/admin presentation, administrator storefront regression, own-room requests, messaging, live delivery, session revocation and navigation');
})().catch(e=>{console.error(e);process.exitCode=1});
