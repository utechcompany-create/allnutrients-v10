(function(){
  'use strict';
  const {esc,cookie}=AppAPI;
  async function request(path,options={}){
    const headers={};
    if(options.body){headers['Content-Type']='application/json';headers['x-csrf-token']=decodeURIComponent(cookie('allnutrients_csrf'));}
    const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...options,headers,body:options.body?JSON.stringify(options.body):undefined});
    let data;try{data=await r.json()}catch(_){data={}}
    if(!r.ok){const e=new Error(data.detail||'대화방을 불러오지 못했습니다.');e.status=r.status;throw e}return data;
  }
  const messageHTML=m=>`<article class="chat-message ${m.isMine?'mine':''}"><small>${m.senderRole==='admin'?'관리자 · ':''}${esc(m.senderName)}</small><p>${esc(m.content)}</p><time>${esc(new Date(m.createdAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}))}</time></article>`;
  function mount(root,{admin=false}={}){
    const sidebar=admin?'<aside class="chat-rooms"><h3>1:1 대화방</h3><form class="chat-start"><label>고객 선택<select aria-label="상담 고객"><option value="">고객 선택</option></select></label><button class="btn ghost">새 상담 시작</button></form><div class="chat-room-list"></div></aside>':'';
    root.innerHTML=`<div class="chat-layout ${admin?'':'member-chat-layout'} group">${sidebar}<section class="chat-panel"><div class="chat-heading"><h2>대화방</h2><p class="chat-notice sales-note"></p><div class="chat-status" role="status"></div></div><button class="btn ghost small chat-older" hidden>이전 대화 보기</button><div class="chat-log" role="log" aria-label="대화 내용" aria-live="polite"></div><form class="chat-compose"><label>메시지<textarea maxlength="2000" rows="2" required placeholder="메시지를 입력하세요. (최대 2,000자)" disabled></textarea></label><button class="btn primary" disabled>전송</button></form><p class="chat-error" role="alert"></p></section></div>`;
    const $=q=>root.querySelector(q), layout=$('.chat-layout'),list=$('.chat-room-list'),log=$('.chat-log'),form=$('.chat-compose'),input=$('textarea'),send=form.querySelector('button'),status=$('.chat-status'),error=$('.chat-error'),older=$('.chat-older');
    let active=false,kind='GROUP',generation=0,room=null,viewer=null,source=null,timer=null,messages=new Map(),cursor=0,sending=false,pending=null,polling=false;
    function stop(){if(source)source.close();source=null;clearInterval(timer);timer=null;generation++;polling=false;}
    function clear(){room=null;messages.clear();cursor=0;log.innerHTML='';if(list)list.innerHTML='';input.value='';input.disabled=true;send.disabled=true;older.hidden=true;pending=null;sending=false;}
    function fail(e){error.textContent=e.message;if([401,403,404].includes(e.status)){stop();clear();status.textContent='로그인 또는 대화방 접근 권한을 확인해 주세요.';}}
    function render(batch,prepend=false,advance=true){const near=log.scrollHeight-log.scrollTop-log.clientHeight<100,previous=log.scrollHeight;for(const m of batch)messages.set(m.id,m);const ordered=[...messages.values()].sort((a,b)=>a.id-b.id);if(advance&&batch.length)cursor=Math.max(cursor,...batch.map(m=>m.id));const empty=!admin&&kind==='DIRECT'?'궁금한 점을 남겨 주세요. 관리자가 확인 후 답변합니다.':'첫 메시지를 보내 대화를 시작하세요.';log.innerHTML=ordered.length?ordered.map(messageHTML).join(''):`<p class="muted chat-empty">${empty}</p>`;if(prepend)log.scrollTop+=log.scrollHeight-previous;else if(near||batch.some(m=>m.isMine))log.scrollTop=log.scrollHeight;}
    function stream(g){if(!window.EventSource){status.textContent='자동 새로고침으로 연결되었습니다.';return}source=new EventSource(`/api/chat/rooms/${encodeURIComponent(room.id)}/events?after=${cursor}`);source.addEventListener('ready',()=>{if(g===generation)status.textContent='실시간 연결됨'});source.addEventListener('messages',e=>{if(g===generation)render(JSON.parse(e.data))});source.addEventListener('access-denied',()=>{if(g===generation)fail(Object.assign(new Error('로그인이 만료되었거나 접근 권한이 변경되었습니다.'),{status:401}))});source.onerror=()=>{if(g===generation)status.textContent='연결 복구 중 · 메시지는 자동으로 다시 확인합니다.'};}
    async function selectRoom(next){
      stop();const g=generation;clear();room=next;error.textContent='';status.textContent='대화를 불러오는 중입니다.';$('.chat-heading h2').textContent=!admin&&kind==='DIRECT'?'관리자 1:1 상담':next.name;
      try{const data=await request(`/api/chat/rooms/${encodeURIComponent(next.id)}/messages`);if(g!==generation||!active)return;room=data.room;render(data.messages);older.hidden=!data.hasOlder;input.disabled=false;send.disabled=false;stream(g);timer=setInterval(()=>refresh(g),3000);await refresh(g,true)}catch(e){if(g===generation)fail(e)}
    }
    async function roomList(g){const rows=await request(admin?'/api/chat/rooms':'/api/chat/rooms?mine=true');if(g!==generation)return;if(list)list.innerHTML=rows.filter(x=>x.kind==='DIRECT').map(x=>`<button class="chat-room ${room?.id===x.id?'active':''}" data-room="${esc(x.id)}"><b>${esc(x.name)}</b><small>${esc(x.lastMessage||'새 대화방')}</small></button>`).join('')||'<p class="muted">접수된 1:1 상담이 없습니다.</p>';return rows;}
    let ticks=0;
    async function refresh(g,onlyList=false){if(g!==generation||polling||!active||document.hidden)return;polling=true;try{if(onlyList||ticks++%3===0){const me=await request('/api/auth/me');if(g!==generation)return;if(!me.authenticated||me.id!==viewer?.id||me.role!==viewer?.role){stop();clear();await open(kind);return}await roomList(g)}if(!onlyList&&room&&g===generation){const data=await request(`/api/chat/rooms/${encodeURIComponent(room.id)}/messages?after=${cursor}`);if(g===generation)render(data.messages)}}catch(e){if(g===generation)fail(e)}finally{if(g===generation)polling=false}}
    async function open(nextKind='GROUP'){
      active=true;kind=nextKind;stop();clear();const g=generation;error.textContent='';layout.classList.toggle('group',kind==='GROUP');$('.chat-heading h2').textContent=kind==='GROUP'?'전체 대화방':admin?'1:1 대화방':'관리자 1:1 상담';$('.chat-notice').textContent=kind==='GROUP'?'모든 회원과 관리자가 볼 수 있습니다. 개인정보는 1:1 상담으로 보내 주세요.':admin?'해당 고객과 관리자만 대화 내용을 볼 수 있습니다.':'나와 관리자만 볼 수 있는 비공개 상담입니다.';input.placeholder=!admin&&kind==='DIRECT'?'상품, 주문, 배송에 대해 문의해 주세요. (최대 2,000자)':'메시지를 입력하세요. (최대 2,000자)';status.textContent='대화방을 불러오는 중입니다.';
      try{const me=await request('/api/auth/me');if(g!==generation)return;if(!me.authenticated||(admin&&me.role!=='admin'))throw Object.assign(new Error('로그인이 필요합니다.'),{status:401});viewer=me;const rows=await roomList(g);if(g!==generation)return;
        if(kind==='GROUP')return selectRoom(rows.find(x=>x.kind==='GROUP'));
        if(!admin){const own=await request('/api/chat/rooms/direct',{method:'POST',body:{}});if(g===generation)return selectRoom(own)}
        else{const users=await request('/api/admin/users');if(g!==generation)return;$('.chat-start select').innerHTML='<option value="">고객 선택</option>'+users.filter(u=>u.role==='customer'&&u.isActive).map(u=>`<option value="${esc(u.id)}">${esc(u.name)} (${esc(u.email)})</option>`).join('');const first=rows.find(x=>x.kind==='DIRECT');if(first)return selectRoom(first);status.textContent='고객을 선택하거나 새 상담이 접수될 때까지 기다려 주세요.';timer=setInterval(()=>refresh(g,true),10000);}
      }catch(e){if(g===generation)fail(e)}
    }
    if(list)list.onclick=async e=>{const b=e.target.closest('[data-room]');if(!b)return;const g=generation;try{const rows=await request('/api/chat/rooms');if(g===generation){const next=rows.find(x=>x.id===b.dataset.room);if(next)await selectRoom(next)}}catch(err){if(g===generation)fail(err)}};
    if(admin)$('.chat-start').onsubmit=async e=>{e.preventDefault();const customerId=$('.chat-start select').value;if(!customerId)return;const g=generation;try{const next=await request('/api/chat/rooms/direct',{method:'POST',body:{customerId}});if(g===generation)await selectRoom(next)}catch(err){if(g===generation)fail(err)}};
    older.onclick=async()=>{if(!room||!messages.size)return;const g=generation;older.disabled=true;try{const before=Math.min(...messages.keys());const data=await request(`/api/chat/rooms/${encodeURIComponent(room.id)}/messages?before=${before}`);if(g===generation){render(data.messages,true,false);older.hidden=!data.hasOlder}}catch(e){if(g===generation)fail(e)}finally{older.disabled=false}};
    form.onsubmit=async e=>{e.preventDefault();const content=input.value.trim();if(!content||!room||sending)return;const g=generation;sending=true;send.disabled=true;error.textContent='';if(!pending||pending.content!==content)pending={content,clientId:crypto.randomUUID()};const body=pending;try{const message=await request(`/api/chat/rooms/${encodeURIComponent(room.id)}/messages`,{method:'POST',body});if(g!==generation)return;render([message],false,false);input.value='';pending=null;input.focus()}catch(err){if(g===generation)fail(err)}finally{if(g===generation){sending=false;send.disabled=false}}};
    input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();form.requestSubmit()}});
    function pause(){stop();clear();status.textContent='연결을 다시 확인합니다.';}
    document.addEventListener('visibilitychange',()=>{if(!active)return;if(document.hidden)pause();else open(kind)});
    window.addEventListener('pagehide',pause);window.addEventListener('pageshow',e=>{if(e.persisted&&active)open(kind)});
    return {open,close(){active=false;pause()}};
  }
  window.ChatUI={mount,messageHTML};
})();
