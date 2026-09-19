(function(){
  'use strict';
  const keys=['orders','returns','exchanges','cancellations','groupChat','directChat','inquiry','board'];
  const labels={orders:'미발송 주문',returns:'처리 중 반품',exchanges:'처리 중 교환',cancellations:'취소 승인 대기',returnTotal:'처리 중 반품·교환',groupChat:'미확인 전체 대화',directChat:'미확인 1:1 대화',liveChat:'미확인 대화',inquiry:'미확인 상품 문의',board:'미확인 게시글',communications:'미확인 고객소통'};
  let adminId=null,last=null,lastTime=0,roomUnread={},polling=false,reading=false,epoch=0,wanted=true,audio=null,activating=false,observer=null,readTimer=null;
  const pending=new Map(),seen=new Map(),viewTimers=new Map();
  const keyOf=item=>item.kind+':'+item.target;
  const side=document.querySelector('.side nav')||document.querySelector('aside .menu');
  const button=document.createElement('button');button.type='button';button.className='event-sound';button.id='adminEventSound';
  const note=document.createElement('p');note.className='event-note';note.setAttribute('role','status');
  side?.append(button,note);
  const prefKey=()=>`admin-event-sound:${adminId}`;
  const snapshotKey=()=>`admin-event-baseline:${adminId}`;
  const getStored=key=>{try{return JSON.parse(localStorage.getItem(key)||'null')}catch(_){return null}};
  const saveStored=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value))}catch(_){}};
  function soundLabel(){const ready=wanted&&audio?.state==='running';button.textContent=ready?'🔔 알림음 켜짐 · 끄기':'🔕 알림음 켜기';button.setAttribute('aria-pressed',String(!!ready));note.textContent=ready?'새 이벤트가 증가하면 소리로 알려드립니다.':wanted?'화면을 한 번 클릭하거나 알림음 켜기를 눌러 주세요.':'알림음이 꺼져 있습니다. 카운터는 계속 갱신됩니다.';button.disabled=!adminId;}
  function beep(){if(!wanted||audio?.state!=='running')return;try{const time=audio.currentTime;[660,880].forEach((frequency,i)=>{const oscillator=audio.createOscillator(),gain=audio.createGain(),start=time+i*.2;oscillator.frequency.value=frequency;gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(.12,start+.015);gain.gain.exponentialRampToValueAtTime(.001,start+.17);oscillator.connect(gain);gain.connect(audio.destination);oscillator.start(start);oscillator.stop(start+.18)})}catch(_){note.textContent='소리를 재생하지 못했습니다. 알림음을 다시 켜 주세요.'}}
  async function activate(sample=false){
    if(!adminId||!wanted||activating)return;activating=true;
    try{const Context=window.AudioContext||window.webkitAudioContext;if(!Context)throw Error('unsupported');audio=audio||new Context();await audio.resume();if(audio.state!=='running')throw Error('blocked');if(last)saveStored(snapshotKey(),{counts:last,time:lastTime});soundLabel();if(sample)beep()}
    catch(_){note.textContent='브라우저의 소리 재생이 차단되었습니다. 알림음 켜기를 다시 눌러 주세요.'}
    finally{activating=false}
  }
  button.onclick=()=>{if(!adminId)return;if(wanted&&audio?.state==='running'){wanted=false;saveStored(prefKey(),false);soundLabel()}else{wanted=true;saveStored(prefKey(),true);activate(true)}};
  document.addEventListener('pointerdown',e=>{if(!e.target.closest('#adminEventSound')&&wanted&&audio?.state!=='running')activate()},{passive:true});
  document.addEventListener('keydown',e=>{if(e.isTrusted&&!e.target.closest('#adminEventSound')&&wanted&&audio?.state!=='running')activate()});
  soundLabel();
  async function alertIncrease(data,previous){
    const id=adminId,current=Object.fromEntries(keys.map(k=>[k,data[k]])),time=Date.parse(data.updatedAt)||Date.now();
    const task=async()=>{
      if(id!==adminId)return;
      const stored=getStored(snapshotKey());
      if(!previous){if(!stored)saveStored(snapshotKey(),{counts:current,time});return}
      const rose=keys.some(k=>current[k]>previous[k]);
      if(stored&&time<stored.time)return;
      if(rose&&(!wanted||audio?.state!=='running'))return;
      const baseline=stored?.counts||previous;
      const notify=rose&&keys.some(k=>current[k]>Number(baseline[k]||0));
      saveStored(snapshotKey(),{counts:current,time});
      if(notify)beep();
    };
    // One sound per increase across administrator tabs in supported browsers.
    if(navigator.locks?.request)await navigator.locks.request('admin-event-sound:'+id,task);else await task();
  }
  function consume(data){
    if(!data.adminId||keys.some(k=>!Number.isSafeInteger(data[k])||data[k]<0))throw Error('이벤트 건수 응답 오류');
    if(adminId!==data.adminId){adminId=data.adminId;last=null;seen.clear();pending.clear();wanted=getStored(prefKey())!==false;soundLabel();watchThreads()}
    const previous=last;last=Object.fromEntries(keys.map(k=>[k,data[k]]));lastTime=Date.parse(data.updatedAt)||Date.now();roomUnread=data.roomUnread||{};
    document.querySelectorAll('[data-work-count]').forEach(badge=>{const key=badge.dataset.workCount,n=data[key];if(!Number.isSafeInteger(n)||n<0)return;badge.textContent=n.toLocaleString('ko-KR');badge.classList.toggle('has-work',n>0);badge.setAttribute('aria-label',`${labels[key]} ${n}건`);badge.title=`${labels[key]} ${n}건 · 5초마다 갱신`});
    document.querySelectorAll('.chat-room[data-room]').forEach(row=>{const n=roomUnread[row.dataset.room]||0;let badge=row.querySelector('.event-unread');if(n&&!badge){badge=document.createElement('span');badge.className='event-unread';row.prepend(badge)}if(badge){badge.textContent=String(n);badge.hidden=!n}});
    alertIncrease(data,previous).catch(()=>{});
  }
  async function refresh(){
    if(polling||reading)return;polling=true;const g=epoch;
    try{const data=await AppAPI.api('/api/admin/event-counts',{cache:'no-store'});if(g===epoch)consume(data)}
    catch(_){if(g===epoch)document.querySelectorAll('[data-work-count]').forEach(b=>{b.textContent='—';b.classList.remove('has-work');b.title='건수 확인 실패 · 자동으로 다시 확인합니다.'})}
    finally{polling=false}
  }
  function confirm(item){
    if(!adminId||!item.through||item.through<=(seen.get(keyOf(item))||0))return;
    const key=keyOf(item),old=pending.get(key);if(!old||old.through<item.through)pending.set(key,item);
    clearTimeout(readTimer);readTimer=setTimeout(flush,250);
  }
  async function flush(){
    if(reading||!pending.size)return;reading=true;epoch++;
    const items=[...pending.values()].slice(0,100),account=adminId;items.forEach(item=>pending.delete(keyOf(item)));
    try{
      const data=await AppAPI.api('/api/admin/events/read',{method:'POST',body:{adminId:account,items}});
      if(account!==adminId)return;
      for(const item of items)seen.set(keyOf(item),Math.max(seen.get(keyOf(item))||0,item.through));
      document.querySelectorAll('[data-event-kind]').forEach(el=>{const item=elementItem(el);if(item.through<=(seen.get(keyOf(item))||0)){el.querySelector('.event-unread')?.remove();el.querySelector('[data-event-confirm]')?.remove()}});
      consume(data);saveStored('admin-event-read-signal',{adminId,time:Date.now()});
    }catch(_){if(account===adminId){items.forEach(item=>{const old=pending.get(keyOf(item));if(!old||old.through<item.through)pending.set(keyOf(item),item)});note.textContent='확인 상태를 저장하지 못했습니다. 자동으로 다시 시도합니다.'}}
    finally{reading=false;if(pending.size)readTimer=setTimeout(flush,3000)}
  }
  function elementItem(el){return {kind:el.dataset.eventKind,target:el.dataset.eventTarget,through:Number(el.dataset.eventThrough)}}
  function canRead(el){return !document.hidden&&document.hasFocus()&&!!el.closest('.view.active')&&el.getClientRects().length>0}
  function watchThreads(){
    observer?.disconnect();viewTimers.forEach(clearTimeout);viewTimers.clear();
    if(!window.IntersectionObserver)return;
    observer=new IntersectionObserver(entries=>{for(const entry of entries){const el=entry.target;clearTimeout(viewTimers.get(el));viewTimers.delete(el);if(entry.isIntersecting&&entry.intersectionRatio>=.95&&canRead(el)){viewTimers.set(el,setTimeout(()=>{if(canRead(el))confirm(elementItem(el));viewTimers.delete(el)},700))}}},{threshold:[0,.95]});
    document.querySelectorAll('[data-event-kind]').forEach(el=>{const item=elementItem(el);if(item.through&&item.through<=(seen.get(keyOf(item))||0)){el.querySelector('.event-unread')?.remove();el.querySelector('[data-event-confirm]')?.remove()}else if(el.querySelector('[data-event-confirm]'))observer.observe(el)});
  }
  document.addEventListener('click',e=>{const control=e.target.closest('[data-event-confirm]');if(control){confirm(elementItem(control.closest('[data-event-kind]')));return}const tab=e.target.closest('[data-view="communications"]');if(tab){window.reloadCommunications?.();watchThreads()}});
  function chatVisible({room,kind,through,log}){if(!adminId||document.hidden||!document.hasFocus()||!log.closest('.view.active')||!log.clientHeight||log.scrollHeight-log.scrollTop-log.clientHeight>80)return;confirm({kind:kind==='GROUP'?'groupChat':'directChat',target:room,through})}
  window.AdminNotifications={refresh,confirm,watchThreads,chatVisible,roomCount:id=>roomUnread[id]||0};
  window.AdminWorkCounts={refresh};
  window.addEventListener('focus',()=>{refresh();watchThreads()});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){viewTimers.forEach(clearTimeout);viewTimers.clear()}else{refresh();watchThreads()}});
  window.addEventListener('storage',e=>{if(e.key===prefKey()){wanted=getStored(prefKey())!==false;soundLabel()}if(e.key==='admin-event-read-signal')refresh()});
  let ticks=0;
  setInterval(()=>{refresh();if(!document.hidden&&++ticks%2===0&&document.getElementById('communications')?.classList.contains('active'))window.reloadCommunications?.()},5000);
  refresh();
})();
