(async function(){
  try{
    const me=await AppAPI.api('/api/auth/me'),el=document.getElementById('accountLink');
    if(!el)return;
    if(me.authenticated){el.textContent='마이페이지';el.href='mypage.html'}
    else{el.textContent='로그인';el.href='login.html'}
  }catch(_){}
})();