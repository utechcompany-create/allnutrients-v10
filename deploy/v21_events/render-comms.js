function renderComms(){
  function card(x,kind){
    const unseen=Number(x.unreadCount||0),through=Number(x.notificationThrough||0);
    return `<div class="order-card"><div class="row"><b>${esc(kind==='inquiry'?x.productName:x.category)} · ${x.isPrivate?'<span class="badge">🔒 비밀글</span> ':''}${esc(x.title)}</b><span class="badge ${x.status==='답변완료'?'':'warn'}">${esc(x.status)}</span></div><p>${esc(x.author)}: ${esc(x.content)}</p>${convo(x)}<div class="event-read-actions" data-event-kind="${kind}" data-event-target="${esc(x.id)}" data-event-through="${through}">${unseen?`<span class="event-unread">미확인 ${unseen}건</span><button class="btn ghost small" type="button" data-event-confirm>확인</button>`:'<span class="event-read-state">확인한 문의</span>'}<button class="btn primary small" onclick="reply('${kind}','${esc(x.id)}')">답변</button></div></div>`;
  }
  inqList.innerHTML=comms.inquiries.length?comms.inquiries.map(x=>card(x,'inquiry')).join(''):'<div class="muted">문의가 없습니다.</div>';
  boardList.innerHTML=comms.board.length?comms.board.map(x=>card(x,'board')).join(''):'<div class="muted">게시글이 없습니다.</div>';
  window.AdminNotifications?.watchThreads();
}
let commLoadSequence=0;
async function reloadCommunications(){
  const seq=++commLoadSequence;
  try{const data=await api('/api/admin/communications',{cache:'no-store'});if(seq!==commLoadSequence||document.hidden||!document.getElementById('communications').classList.contains('active'))return;if(JSON.stringify(data)!==JSON.stringify(comms)){comms=data;renderComms()}}
  catch(e){if(seq===commLoadSequence&&document.getElementById('communications').classList.contains('active'))toast(e.message)}
}
async function reply(kind,id){
  const item=comms[kind==='inquiry'?'inquiries':'board'].find(x=>x.id===id),through=Number(item?.notificationThrough||0);
  const content=prompt('판매자 답변을 입력하세요.');if(!content)return;
  try{await api(`/api/admin/communications/${kind}/${id}/reply`,{method:'POST',body:{content}});if(through)window.AdminNotifications?.confirm({kind,target:id,through});await loadAll()}catch(e){toast(e.message)}
}
