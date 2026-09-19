(async function(){
  'use strict';
  const root=document.getElementById('customerChat');
  try{
    const me=await AppAPI.api('/api/auth/me',{cache:'no-store'});
    if(!me.authenticated){location.href='login.html?next=chat.html';return}
    // Storefront presentation is always the member experience. Account roles
    // remain enforced by the server; only admin.html mounts the admin controls.
    const chat=ChatUI.mount(root,{admin:false});
    document.getElementById('memberChatGreeting').textContent=me.name+'님, 회원들과 대화하거나 관리자에게 1:1로 문의해 주세요.';
    document.querySelector('.chat-tabs').onclick=e=>{
      const button=e.target.closest('[data-kind]');if(!button)return;
      document.querySelectorAll('[data-kind]').forEach(item=>{item.classList.toggle('active',item===button);item.setAttribute('aria-pressed',String(item===button))});
      chat.open(button.dataset.kind);
    };
    await chat.open('GROUP');
  }catch(e){root.textContent='대화방을 불러오지 못했습니다. 페이지를 새로고침해 주세요.'}
})();
